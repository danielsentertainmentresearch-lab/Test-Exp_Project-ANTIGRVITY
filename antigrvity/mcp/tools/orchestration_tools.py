"""Swarm orchestration and status tools exposed via MCP."""

import time
from typing import Any, Dict, List
from antigrvity.agents.registry import AgentRegistry
from antigrvity.core.context import Blackboard
from antigrvity.mcp.protocol import MCPTool, MCPToolResult


def get_orchestration_tools(registry: AgentRegistry, blackboard: Blackboard) -> List[tuple[MCPTool, Any]]:
    """Return list of (MCPTool, handler) tuples for swarm orchestration."""

    tool_status = MCPTool(
        name="antigrvity_coldstart_status",
        description="Query the cold-start health, quorum metrics, and active phases of the ANTIGRVITY swarm.",
        inputSchema={
            "type": "object",
            "properties": {},
        },
    )

    async def handle_status(args: Dict[str, Any]) -> MCPToolResult:
        quorum = registry.calculate_quorum()
        coldstart_state = await blackboard.get("coldstart:state", default={})
        agents_data = []
        for a in registry.list_all():
            agents_data.append({
                "id": a.id,
                "name": a.name,
                "role": a.role,
                "state": a.state.value,
                "critical": a.is_critical,
                "capabilities": a.capabilities,
                "last_heartbeat": a.last_heartbeat,
            })
        return MCPToolResult.json({
            "quorum": quorum,
            "coldstart_state": coldstart_state,
            "agents": agents_data,
            "timestamp": time.time(),
        })

    tool_list_agents = MCPTool(
        name="antigrvity_list_agents",
        description="List all registered agents in the ANTIGRVITY swarm with their capabilities.",
        inputSchema={
            "type": "object",
            "properties": {
                "role": {"type": "string", "description": "Optional role filter"}
            },
        },
    )

    async def handle_list_agents(args: Dict[str, Any]) -> MCPToolResult:
        role = args.get("role")
        agents = registry.get_by_role(role) if role else registry.list_all()
        return MCPToolResult.json({
            "agents": [
                {
                    "id": a.id,
                    "name": a.name,
                    "role": a.role,
                    "state": a.state.value,
                    "is_critical": a.is_critical,
                    "capabilities": a.capabilities,
                }
                for a in agents
            ]
        })

    tool_dispatch = MCPTool(
        name="antigrvity_dispatch_task",
        description="Dispatch a task to a specific agent or role in the ANTIGRVITY swarm.",
        inputSchema={
            "type": "object",
            "properties": {
                "target": {"type": "string", "description": "Agent ID or role to handle the task"},
                "task_id": {"type": "string", "description": "Unique identifier for this task execution"},
                "input_data": {"type": "object", "description": "Task payload and directives"},
            },
            "required": ["target", "task_id", "input_data"],
        },
    )

    async def handle_dispatch(args: Dict[str, Any]) -> MCPToolResult:
        target = args.get("target")
        task_id = args.get("task_id")
        input_data = args.get("input_data", {})

        agent = registry.get(target)
        if not agent:
            by_role = registry.get_by_role(target)
            if by_role:
                agent = by_role[0]

        if not agent:
            return MCPToolResult.text(f"No agent found for target '{target}'", is_error=True)

        try:
            res = await agent.execute_task(task_id, input_data)
            return MCPToolResult.json({"task_id": task_id, "handled_by": agent.id, "result": res})
        except Exception as exc:
            return MCPToolResult.text(f"Task execution failed: {exc}", is_error=True)

    return [
        (tool_status, handle_status),
        (tool_list_agents, handle_list_agents),
        (tool_dispatch, handle_dispatch),
    ]
