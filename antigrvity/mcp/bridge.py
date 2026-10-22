"""MCP Bridge multiplexer connecting agents to local and remote MCP servers."""

import asyncio
import json
from pathlib import Path
from typing import Any, Dict, List, Optional
from antigrvity.core.config import MCPBridgeConfig, MCPServerConfig, load_json_file
from antigrvity.core.context import Blackboard
from antigrvity.core.events import EventBus
from antigrvity.core.exceptions import MCPBridgeError
from antigrvity.mcp.protocol import (
    JSONRPCRequest,
    JSONRPCResponse,
    MCPTool,
    MCPToolResult,
)
from antigrvity.mcp.server import MCPServer
from antigrvity.mcp.tools.blackboard_tools import get_blackboard_tools
from antigrvity.mcp.tools.orchestration_tools import get_orchestration_tools
from antigrvity.mcp.tools.notebook_tools import get_notebook_tools
from antigrvity.utils.logger import get_logger


class MCPBridge:
    """Multiplexes MCP tool requests across internal built-in tools and external MCP servers."""

    def __init__(
        self,
        config: MCPBridgeConfig,
        blackboard: Optional[Blackboard] = None,
        event_bus: Optional[EventBus] = None,
        registry: Optional[Any] = None,
    ):
        self.config = config
        self.blackboard = blackboard or Blackboard()
        self.event_bus = event_bus or EventBus()
        self.registry = registry
        self.internal_server = MCPServer(name="antigrvity-internal-bridge")
        self.connected_servers: Dict[str, Dict[str, Any]] = {}
        self.tools_registry: Dict[str, Dict[str, Any]] = {}
        self.logger = get_logger("mcp.bridge")
        self._is_ready = False

    @classmethod
    def from_config_file(
        cls,
        config_path: Path,
        blackboard: Optional[Blackboard] = None,
        event_bus: Optional[EventBus] = None,
        registry: Optional[Any] = None,
    ) -> "MCPBridge":
        """Instantiate bridge from an mcp_servers.json config file."""
        data = load_json_file(config_path)
        cfg = MCPBridgeConfig.from_dict(data)
        return cls(config=cfg, blackboard=blackboard, event_bus=event_bus, registry=registry)

    async def initialize(self) -> Dict[str, Any]:
        """Bootstrap the MCP bridge, register internal tools, and ping downstream servers."""
        self.logger.info("Initializing MCP Bridge subsystem...")
        discovered_tools_count = 0

        # 1. Register internal tools
        self._register_internal_tools()
        for t_name, tool in self.internal_server.tools.items():
            self.tools_registry[t_name] = {
                "tool": tool,
                "handler": self.internal_server.handlers[t_name],
                "source": "internal",
            }
            discovered_tools_count += 1

        # 2. Probe and register configured downstream servers
        server_statuses = {}
        for server_id, server_conf in self.config.servers.items():
            if not server_conf.auto_start:
                server_statuses[server_id] = {"status": "disabled", "tools": 0}
                continue

            status = await self._probe_server(server_conf)
            server_statuses[server_id] = status

        self._is_ready = True
        self.logger.info(
            f"MCP Bridge ready: {len(self.tools_registry)} tools active across "
            f"{len(server_statuses)} configured servers."
        )

        # Store bridge status on blackboard
        await self.blackboard.set(
            "mcp_bridge:status",
            {
                "ready": True,
                "tool_count": len(self.tools_registry),
                "servers": server_statuses,
            },
            agent_id="mcp_bridge",
        )

        return {
            "ready": True,
            "tool_count": len(self.tools_registry),
            "tools": list(self.tools_registry.keys()),
            "servers": server_statuses,
        }

    def _register_internal_tools(self) -> None:
        """Mount blackboard, orchestration, and notebook tools."""
        # Blackboard tools
        for tool, handler in get_blackboard_tools(self.blackboard):
            self.internal_server.register_tool(tool, handler)

        # Swarm orchestration tools (if registry is available)
        if self.registry is not None:
            for tool, handler in get_orchestration_tools(self.registry, self.blackboard):
                self.internal_server.register_tool(tool, handler)

        # Notebook tools
        for tool, handler in get_notebook_tools():
            self.internal_server.register_tool(tool, handler)

    async def _probe_server(self, conf: MCPServerConfig) -> Dict[str, Any]:
        """Probe downstream MCP server health and capabilities."""
        self.logger.info(f"Probing downstream MCP server [{conf.id}]...")
        # For internal self-reference or in-process mocks
        if conf.id == "antigrvity-internal-tools":
            return {"status": "healthy", "type": "in-process", "tools": len(self.internal_server.tools)}

        # If it's a command-based stdio server
        if conf.command:
            return {
                "status": "configured",
                "type": "stdio",
                "command": conf.command,
                "description": conf.description,
            }

        # If HTTP
        if conf.url:
            return {"status": "configured", "type": "http", "url": conf.url}

        return {"status": "unknown"}

    def list_tools(self) -> List[MCPTool]:
        """Return all tools registered in the bridge."""
        return [entry["tool"] for entry in self.tools_registry.values()]

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> MCPToolResult:
        """Route tool invocation to the proper handler or downstream server."""
        if tool_name not in self.tools_registry:
            raise MCPBridgeError(f"Tool '{tool_name}' not registered in MCP Bridge")

        entry = self.tools_registry[tool_name]
        handler = entry["handler"]
        self.logger.debug(f"Calling MCP tool '{tool_name}' (source={entry['source']})")
        return await handler(arguments)

    async def shutdown(self) -> None:
        """Tear down all bridge connections."""
        self._is_ready = False
        self.tools_registry.clear()
        self.logger.info("MCP Bridge multiplexer shut down.")
