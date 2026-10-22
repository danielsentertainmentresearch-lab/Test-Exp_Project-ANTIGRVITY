"""Command-line interface for Project ANTIGRVITY."""

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Optional
from antigrvity import __version__
from antigrvity.core.context import Blackboard
from antigrvity.core.events import EventBus
from antigrvity.mcp.bridge import MCPBridge
from antigrvity.mcp.server import MCPServer
from antigrvity.mcp.transports import StdioTransport
from antigrvity.mcp.tools import get_blackboard_tools, get_orchestration_tools, get_notebook_tools
from antigrvity.orchestration.coldstart import ColdStartEngine
from antigrvity.orchestration.workflow import TaskDAG, WorkflowEngine
from antigrvity.utils.logger import get_logger, BOLD, GREEN, RED, CYAN, RESET, YELLOW, DIM


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="antigrvity",
        description="Project ANTIGRVITY: Multi-Agent Cold-Start Orchestration & MCP Bridge",
    )
    parser.add_argument("--version", action="version", version=f"antigrvity v{__version__}")

    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # Command: coldstart
    cs_parser = subparsers.add_parser("coldstart", help="Execute 5-phase multi-agent cold-start orchestration")
    cs_parser.add_argument("--workspace", type=Path, default=Path.cwd(), help="Workspace directory")
    cs_parser.add_argument("--json", action="store_true", help="Output results in JSON format")

    # Command: status
    status_parser = subparsers.add_parser("status", help="Inspect swarm health, quorum, and MCP bridge status")
    status_parser.add_argument("--workspace", type=Path, default=Path.cwd(), help="Workspace directory")
    status_parser.add_argument("--json", action="store_true", help="Output in JSON format")

    # Command: mcp-server
    mcp_parser = subparsers.add_parser("mcp-server", help="Launch the native MCP Stdio Bridge server")
    mcp_parser.add_argument("--name", default="antigrvity-bridge", help="MCP server name")

    # Command: mcp-list-tools
    tools_parser = subparsers.add_parser("mcp-list-tools", help="List all tools exposed across the MCP bridge")
    tools_parser.add_argument("--workspace", type=Path, default=Path.cwd(), help="Workspace directory")
    tools_parser.add_argument("--json", action="store_true", help="Output tools in JSON format")

    # Command: run-task
    task_parser = subparsers.add_parser("run-task", help="Execute a multi-agent task workflow")
    task_parser.add_argument("--goal", default="Initialize and verify system", help="High-level goal description")
    task_parser.add_argument("--workspace", type=Path, default=Path.cwd(), help="Workspace directory")

    return parser


async def cmd_coldstart(args) -> int:
    workspace = args.workspace.resolve()
    engine = ColdStartEngine.from_directory(workspace)
    result = await engine.execute_bootstrap()

    if args.json:
        out = {
            "version": __version__,
            "successful": result.is_successful,
            "elapsed_sec": result.elapsed_sec,
            "quorum": result.quorum,
            "mcp_tools_count": result.mcp_tools_count,
            "error_summary": result.error_summary,
            "phases": [
                {
                    "id": p.phase_id,
                    "name": p.name,
                    "success": p.success,
                    "duration_sec": p.duration_sec,
                    "error": p.error,
                }
                for p in result.phases
            ],
        }
        print(json.dumps(out, indent=2))
        return 0 if result.is_successful else 1

    # Pretty print
    print("\n" + "=" * 65)
    print(f"{BOLD}{CYAN}Project ANTIGRVITY Multi-Agent Cold-Start Report{RESET}")
    print("=" * 65)
    for p in result.phases:
        status_badge = f"{GREEN}[PASS]{RESET}" if p.success else f"{RED}[FAIL]{RESET}"
        print(f"  {status_badge} {BOLD}{p.name.ljust(35)}{RESET} ({p.duration_sec:.3f}s)")
        if p.error:
            print(f"         {RED}Error: {p.error}{RESET}")

    print("-" * 65)
    q = result.quorum
    q_color = GREEN if q["has_quorum"] else RED
    print(f"  Swarm Quorum:   {q_color}{q['ready']}/{q['total']} Ready{RESET} (Critical: {q['critical_ready']}/{q['critical_total']})")
    print(f"  MCP Tools:      {GREEN}{result.mcp_tools_count} Active Tools{RESET}")
    print(f"  Total Duration: {result.elapsed_sec:.3f}s")
    print("=" * 65 + "\n")

    await engine.shutdown()
    return 0 if result.is_successful else 1


async def cmd_status(args) -> int:
    workspace = args.workspace.resolve()
    engine = ColdStartEngine.from_directory(workspace)
    # Quick probe
    res = await engine._run_phase_1_system_probe()
    topo_res = await engine._run_phase_2_topology_bootstrap()
    mcp_res = await engine._run_phase_3_mcp_bridge_warmup()

    q = engine.registry.calculate_quorum()
    tools = engine.mcp_bridge.list_tools()

    if args.json:
        data = {
            "version": __version__,
            "workspace": str(workspace),
            "system_probe": res.details,
            "quorum": q,
            "agents": [
                {"id": a.id, "role": a.role, "state": a.state.value, "critical": a.is_critical}
                for a in engine.registry.list_all()
            ],
            "mcp_tools": [t.name for t in tools],
        }
        print(json.dumps(data, indent=2))
        await engine.shutdown()
        return 0

    print(f"\n{BOLD}{CYAN}Project ANTIGRVITY Status{RESET} (v{__version__})")
    print(f"Workspace: {workspace}")
    print(f"Quorum:    {q['ready']}/{q['total']} ready, ratio={q['health_ratio']:.0%}")
    print(f"\n{BOLD}Registered Agents:{RESET}")
    for a in engine.registry.list_all():
        crit_tag = f"{YELLOW}[CRITICAL]{RESET}" if a.is_critical else "[OPTIONAL]"
        print(f"  * {BOLD}{a.id.ljust(15)}{RESET} role={a.role.ljust(12)} state={a.state.value.ljust(12)} {crit_tag}")

    print(f"\n{BOLD}Active MCP Tools ({len(tools)}):{RESET}")
    for t in tools:
        print(f"  * {BOLD}{t.name.ljust(32)}{RESET} - {t.description}")
    print()

    await engine.shutdown()
    return 0


async def cmd_mcp_server(args) -> int:
    """Run native MCP Server communicating via Stdio JSON-RPC 2.0."""
    server = MCPServer(name=args.name, version=__version__)
    blackboard = Blackboard()
    event_bus = EventBus()

    # Register standard tool packages
    for tool, handler in get_blackboard_tools(blackboard):
        server.register_tool(tool, handler)

    for tool, handler in get_notebook_tools():
        server.register_tool(tool, handler)

    transport = StdioTransport()
    await server.run(transport)
    return 0


async def cmd_mcp_list_tools(args) -> int:
    workspace = args.workspace.resolve()
    engine = ColdStartEngine.from_directory(workspace)
    await engine._run_phase_2_topology_bootstrap()
    await engine._run_phase_3_mcp_bridge_warmup()

    tools = engine.mcp_bridge.list_tools()
    if args.json:
        out = [{"name": t.name, "description": t.description, "inputSchema": t.inputSchema} for t in tools]
        print(json.dumps(out, indent=2))
    else:
        print(f"\n{BOLD}{CYAN}Available MCP Tools ({len(tools)}):{RESET}")
        for t in tools:
            print(f"\n  {BOLD}{GREEN}{t.name}{RESET}")
            print(f"    Description: {t.description}")
            props = t.inputSchema.get("properties", {})
            if props:
                print(f"    Parameters: {', '.join(props.keys())}")
        print()

    await engine.shutdown()
    return 0


async def cmd_run_task(args) -> int:
    workspace = args.workspace.resolve()
    print(f"\n{BOLD}{CYAN}Bootstrapping swarm for task execution...{RESET}")
    engine = ColdStartEngine.from_directory(workspace)
    init_res = await engine.execute_bootstrap()
    if not init_res.is_successful:
        print(f"{RED}Cold-start failed: {init_res.error_summary}{RESET}")
        return 1

    # Build a task DAG
    dag = TaskDAG(workflow_id="task_pipeline_01")
    dag.add_task(
        task_id="t1_research",
        target_role_or_agent="analyst",
        input_data={"query": f"Research context and constraints for: {args.goal}"},
    )
    dag.add_task(
        task_id="t2_orchestrate",
        target_role_or_agent="coordinator",
        input_data={"goal": args.goal, "subtasks": ["t1_research", "t3_synthesize"]},
        dependencies=["t1_research"],
    )
    dag.add_task(
        task_id="t3_synthesize",
        target_role_or_agent="worker",
        input_data={"target": "artifact_manifest", "spec": {"files": ["solution.py"]}},
        dependencies=["t2_orchestrate"],
    )
    dag.add_task(
        task_id="t4_review",
        target_role_or_agent="evaluator",
        input_data={"artifact": {"target": "solution.py"}},
        dependencies=["t3_synthesize"],
    )

    wf_engine = WorkflowEngine(engine.registry, engine.blackboard)
    exec_result = await wf_engine.execute(dag)

    print(f"\n{BOLD}{GREEN}Workflow '{exec_result['workflow_id']}' execution complete!{RESET}")
    print(f"  Completed tasks: {len(exec_result['completed'])} / {len(dag.nodes)}")
    for t_id in exec_result["completed"]:
        print(f"  {GREEN}[OK]{RESET} Task '{t_id}' successfully executed")

    await engine.shutdown()
    return 0


def main():
    parser = build_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    try:
        if args.command == "coldstart":
            sys.exit(asyncio.run(cmd_coldstart(args)))
        elif args.command == "status":
            sys.exit(asyncio.run(cmd_status(args)))
        elif args.command == "mcp-server":
            sys.exit(asyncio.run(cmd_mcp_server(args)))
        elif args.command == "mcp-list-tools":
            sys.exit(asyncio.run(cmd_mcp_list_tools(args)))
        elif args.command == "run-task":
            sys.exit(asyncio.run(cmd_run_task(args)))
    except KeyboardInterrupt:
        print("\nAborted by user.")
        sys.exit(130)


if __name__ == "__main__":
    main()
