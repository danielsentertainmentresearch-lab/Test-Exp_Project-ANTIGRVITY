"""Model Context Protocol (MCP) subsystem for Project ANTIGRVITY."""

from antigrvity.mcp.protocol import (
    JSONRPCRequest,
    JSONRPCResponse,
    MCPTool,
    MCPToolResult,
    parse_jsonrpc_message,
)
from antigrvity.mcp.transports import (
    BaseTransport,
    InProcessTransport,
    StdioTransport,
)
from antigrvity.mcp.server import MCPServer
from antigrvity.mcp.bridge import MCPBridge

__all__ = [
    "JSONRPCRequest",
    "JSONRPCResponse",
    "MCPTool",
    "MCPToolResult",
    "parse_jsonrpc_message",
    "BaseTransport",
    "InProcessTransport",
    "StdioTransport",
    "MCPServer",
    "MCPBridge",
]
