"""Blackboard access tools exposed via MCP."""

from typing import Any, Dict, List
from antigrvity.core.context import Blackboard
from antigrvity.mcp.protocol import MCPTool, MCPToolResult


def get_blackboard_tools(blackboard: Blackboard) -> List[tuple[MCPTool, Any]]:
    """Return list of (MCPTool, handler) tuples for blackboard operations."""

    tool_get = MCPTool(
        name="antigrvity_blackboard_get",
        description="Retrieve a value from the shared multi-agent blackboard by key.",
        inputSchema={
            "type": "object",
            "properties": {
                "key": {"type": "string", "description": "Blackboard key identifier"}
            },
            "required": ["key"],
        },
    )

    async def handle_get(args: Dict[str, Any]) -> MCPToolResult:
        key = args.get("key")
        val = await blackboard.get(key)
        if val is None:
            return MCPToolResult.json({"key": key, "found": False, "value": None})
        return MCPToolResult.json({"key": key, "found": True, "value": val})

    tool_set = MCPTool(
        name="antigrvity_blackboard_set",
        description="Write or update a key on the shared multi-agent blackboard.",
        inputSchema={
            "type": "object",
            "properties": {
                "key": {"type": "string", "description": "Blackboard key identifier"},
                "value": {"description": "Value to store (any JSON-serializable structure)"},
                "ttl_sec": {"type": "number", "description": "Optional TTL in seconds"},
            },
            "required": ["key", "value"],
        },
    )

    async def handle_set(args: Dict[str, Any]) -> MCPToolResult:
        key = args.get("key")
        value = args.get("value")
        ttl = args.get("ttl_sec")
        entry = await blackboard.set(key, value, agent_id="mcp_bridge", ttl_sec=ttl)
        return MCPToolResult.json({"key": key, "version": entry.version, "status": "stored"})

    tool_list = MCPTool(
        name="antigrvity_blackboard_list",
        description="List active keys present in the shared multi-agent blackboard.",
        inputSchema={
            "type": "object",
            "properties": {
                "prefix": {"type": "string", "description": "Optional prefix filter"}
            },
        },
    )

    async def handle_list(args: Dict[str, Any]) -> MCPToolResult:
        prefix = args.get("prefix")
        keys = await blackboard.list_keys(prefix)
        return MCPToolResult.json({"keys": keys, "count": len(keys)})

    return [
        (tool_get, handle_get),
        (tool_set, handle_set),
        (tool_list, handle_list),
    ]
