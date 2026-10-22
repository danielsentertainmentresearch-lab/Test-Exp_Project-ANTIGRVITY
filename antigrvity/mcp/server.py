"""Model Context Protocol (MCP) Server implementation."""

import asyncio
import json
import sys
from typing import Any, Callable, Coroutine, Dict, List, Optional
from antigrvity.core.exceptions import MCPProtocolError
from antigrvity.mcp.protocol import (
    JSONRPCRequest,
    JSONRPCResponse,
    MCPTool,
    MCPToolResult,
    parse_jsonrpc_message,
    INTERNAL_ERROR,
    METHOD_NOT_FOUND,
    INVALID_PARAMS,
    DEFAULT_MCP_PROTOCOL_VERSION,
)
from antigrvity.mcp.transports import BaseTransport, StdioTransport
from antigrvity.utils.logger import get_logger

ToolHandler = Callable[[Dict[str, Any]], Coroutine[Any, Any, MCPToolResult]]


class MCPServer:
    """Server that exposes tools to MCP clients via JSON-RPC 2.0."""

    def __init__(self, name: str = "antigrvity-bridge-server", version: str = "0.1.0"):
        self.name = name
        self.version = version
        self.tools: Dict[str, MCPTool] = {}
        self.handlers: Dict[str, ToolHandler] = {}
        self.logger = get_logger("mcp.server")
        self._is_initialized = False

    def register_tool(self, tool: MCPTool, handler: ToolHandler) -> None:
        """Register a tool with its execution coroutine handler."""
        self.tools[tool.name] = tool
        self.handlers[tool.name] = handler
        self.logger.debug(f"Registered MCP tool: {tool.name}")

    async def handle_request(self, request: JSONRPCRequest) -> Optional[JSONRPCResponse]:
        """Dispatch a single JSON-RPC request to the appropriate handler."""
        method = request.method
        req_id = request.id
        params = request.params or {}

        # Notification (no id)
        is_notification = (req_id is None)

        try:
            if method == "initialize":
                self._is_initialized = True
                result = {
                    "protocolVersion": DEFAULT_MCP_PROTOCOL_VERSION,
                    "capabilities": {
                        "tools": {"listChanged": True},
                        "resources": {},
                        "prompts": {},
                    },
                    "serverInfo": {
                        "name": self.name,
                        "version": self.version,
                    },
                }
                return JSONRPCResponse(id=req_id, result=result) if not is_notification else None

            elif method == "notifications/initialized":
                return None

            elif method == "ping":
                return JSONRPCResponse(id=req_id, result={}) if not is_notification else None

            elif method == "tools/list":
                tools_list = [t.to_dict() for t in self.tools.values()]
                return JSONRPCResponse(id=req_id, result={"tools": tools_list})

            elif method == "tools/call":
                tool_name = params.get("name")
                tool_args = params.get("arguments", {})
                if not tool_name or tool_name not in self.handlers:
                    return JSONRPCResponse(
                        id=req_id,
                        error={"code": METHOD_NOT_FOUND, "message": f"Tool '{tool_name}' not found"},
                    )

                handler = self.handlers[tool_name]
                tool_result: MCPToolResult = await handler(tool_args)
                return JSONRPCResponse(id=req_id, result=tool_result.to_dict())

            else:
                return JSONRPCResponse(
                    id=req_id,
                    error={"code": METHOD_NOT_FOUND, "message": f"Method '{method}' not implemented"},
                )

        except Exception as exc:
            self.logger.error(f"Error handling method {method}: {exc}", exc_info=True)
            return JSONRPCResponse(
                id=req_id,
                error={"code": INTERNAL_ERROR, "message": str(exc)},
            )

    async def run(self, transport: Optional[BaseTransport] = None) -> None:
        """Run the MCP server event loop over the given transport (default Stdio)."""
        t = transport or StdioTransport()
        self.logger.info(f"Starting {self.name} v{self.version} MCP server loop...")
        try:
            while True:
                raw = await t.receive()
                if raw is None:
                    break
                raw = raw.strip()
                if not raw:
                    continue

                try:
                    msg = parse_jsonrpc_message(raw)
                    if isinstance(msg, JSONRPCRequest):
                        resp = await self.handle_request(msg)
                        if resp is not None:
                            await t.send(resp.to_json())
                except MCPProtocolError as err:
                    resp = JSONRPCResponse(
                        id=None,
                        error={"code": err.code, "message": str(err)},
                    )
                    await t.send(resp.to_json())
        finally:
            await t.close()
            self.logger.info(f"{self.name} MCP server stopped.")
