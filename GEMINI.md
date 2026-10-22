# Project ANTIGRVITY Rules & Workspace Guidelines

> [!IMPORTANT]
> This repository houses the Project ANTIGRVITY Multi-Agent Cold-Start Orchestration Framework and MCP Bridge.

## Quick CLI Reference
- Run Cold-Start Bootstrap: `python -m antigrvity.cli coldstart`
- Check Framework Status: `python -m antigrvity.cli status`
- Start MCP Bridge Server: `python -m antigrvity.cli mcp-server`
- Execute Full Test Suite: `python -m unittest discover tests`

## Framework Protocols
- Subsystem communication adheres to Model Context Protocol (MCP) JSON-RPC 2.0.
- State sharing operates via the central thread-safe async Blackboard (`antigrvity.core.context.Blackboard`).
- Agent lifecycle transitions: `OFFLINE` -> `PROBING` -> `INITIALIZING` -> `WARMING_MCP` -> `CONSENSUS` -> `READY` -> `EXECUTING`.
