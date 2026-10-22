# Project ANTIGRVITY: Multi-Agent Operating Rules

Welcome to **Project ANTIGRVITY**. This workspace is governed by a distributed multi-agent cold-start orchestration framework and an MCP bridge subsystem.

## Architectural Directives

1. **Cold-Start Integrity**:
   - Before executing tasks that require agent consensus or external tools, verify the system cold-start state.
   - All agents boot via the structured 5-phase cold-start lifecycle (`System Probe` -> `Topology Bootstrap` -> `MCP Bridge Warmup` -> `State Consensus` -> `Dispatch Ready`).
   - If a subsystem reports degraded status, follow graceful degradation protocols rather than crashing unhandled.

2. **Multi-Agent Coordination & Roles**:
   - **Orchestrator**: Sole agent responsible for task decomposition, DAG generation, and workflow state.
   - **Researcher**: Read-only context gatherer; queries files, codebase references, and external docs.
   - **Synthesizer**: Generates code, tests, and configuration artifacts; never bypasses safety validations.
   - **Reviewer**: Evaluates generated diffs, verifies constraints, and participates in consensus voting.
   - **Bridge Agent**: Manages MCP JSON-RPC 2.0 communication and notebook kernel interfaces.

3. **Model Context Protocol (MCP) Bridge Standards**:
   - Always communicate using standard JSON-RPC 2.0 specifications.
   - Tool names must follow snake_case naming (e.g., `antigrvity_dispatch_task`, `antigrvity_blackboard_read`).
   - Errors returned from tool calls must include appropriate JSON-RPC error codes (`-32600` Invalid Request, `-32601` Method not found, `-32602` Invalid params, `-32603` Internal error).

4. **Blackboard State & Shared Memory**:
   - Agents must write state checkpoints to the shared blackboard rather than maintaining siloed ephemeral states.
   - Keys in the blackboard must use namespaced notation (e.g., `coldstart:status`, `task:<id>:result`, `agent:<id>:heartbeat`).

5. **Code Quality & Testing**:
   - All core modules must operate with standard Python 3.10+ libraries without hard failure when external packages are absent.
   - Maintain comprehensive unit tests under `tests/`.
