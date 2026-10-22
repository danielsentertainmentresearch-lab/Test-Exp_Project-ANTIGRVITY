---
name: mcp-bridge
description: Manages the Model Context Protocol (MCP) bridge, enabling multiplexing across downstream tool servers, diagnostic probes, and notebook kernel execution.
---

# MCP Bridge Skill

This skill documents how to operate, query, and test the Model Context Protocol (MCP) bridge in Project ANTIGRVITY.

## When to Use
- When discovering or registering new MCP tools for agents.
- When running diagnostic checks against connected MCP servers.
- When executing code or commands via the MCP notebook bridge.

## Procedures

### 1. Launching Native MCP Server
Run the stdio-compatible MCP server:
```sh
python -m antigrvity.cli mcp-server
```

### 2. Testing MCP Tool Discovery
Query tools registered with the bridge:
```sh
python -m antigrvity.cli mcp-list-tools
```

### 3. Programmatic Tool Invocation
```python
import asyncio
from antigrvity.mcp.bridge import MCPBridge

async def call_tool():
    bridge = MCPBridge.from_config("config/mcp_servers.json")
    await bridge.initialize()
    result = await bridge.call_tool("antigrvity_coldstart_status", {})
    print("Tool result:", result)
    await bridge.shutdown()

if __name__ == "__main__":
    asyncio.run(call_tool())
```
