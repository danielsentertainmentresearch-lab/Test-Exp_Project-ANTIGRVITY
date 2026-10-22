"""Tests for MCP Protocol, MCPServer, and MCPBridge."""

import json
import unittest
from antigrvity.core.config import MCPBridgeConfig, MCPServerConfig
from antigrvity.core.context import Blackboard
from antigrvity.core.events import EventBus
from antigrvity.mcp.bridge import MCPBridge
from antigrvity.mcp.protocol import (
    JSONRPCRequest,
    MCPTool,
    MCPToolResult,
    parse_jsonrpc_message,
)
from antigrvity.mcp.server import MCPServer
from antigrvity.mcp.transports import InProcessTransport


class TestMCPBridge(unittest.IsolatedAsyncioTestCase):

    async def test_jsonrpc_parsing(self):
        req_str = '{"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}'
        msg = parse_jsonrpc_message(req_str)
        self.assertIsInstance(msg, JSONRPCRequest)
        self.assertEqual(msg.method, "tools/list")
        self.assertEqual(msg.id, 1)

    async def test_mcp_server_initialize_and_tools(self):
        server = MCPServer(name="test-server", version="1.0.0")

        tool = MCPTool(
            name="test_tool",
            description="A test tool",
            inputSchema={"type": "object", "properties": {"msg": {"type": "string"}}},
        )

        async def handler(args):
            return MCPToolResult.text(f"Echo: {args.get('msg')}")

        server.register_tool(tool, handler)

        # 1. Initialize handshake
        init_req = JSONRPCRequest(id=1, method="initialize", params={})
        resp = await server.handle_request(init_req)
        self.assertIsNotNone(resp)
        self.assertEqual(resp.result["serverInfo"]["name"], "test-server")

        # 2. tools/list
        list_req = JSONRPCRequest(id=2, method="tools/list")
        resp_list = await server.handle_request(list_req)
        self.assertEqual(len(resp_list.result["tools"]), 1)
        self.assertEqual(resp_list.result["tools"][0]["name"], "test_tool")

        # 3. tools/call
        call_req = JSONRPCRequest(id=3, method="tools/call", params={"name": "test_tool", "arguments": {"msg": "hello"}})
        resp_call = await server.handle_request(call_req)
        self.assertFalse(resp_call.result["isError"])
        self.assertEqual(resp_call.result["content"][0]["text"], "Echo: hello")

    async def test_mcp_bridge_multiplexer(self):
        cfg = MCPBridgeConfig(servers={
            "antigrvity-internal-tools": MCPServerConfig(id="antigrvity-internal-tools")
        })
        blackboard = Blackboard()
        event_bus = EventBus()
        bridge = MCPBridge(config=cfg, blackboard=blackboard, event_bus=event_bus)

        status = await bridge.initialize()
        self.assertTrue(status["ready"])
        self.assertGreater(status["tool_count"], 0)

        # Call blackboard tool via bridge
        set_res = await bridge.call_tool("antigrvity_blackboard_set", {"key": "mcp_key", "value": 999})
        self.assertFalse(set_res.isError)

        get_res = await bridge.call_tool("antigrvity_blackboard_get", {"key": "mcp_key"})
        data = json.loads(get_res.content[0]["text"])
        self.assertTrue(data["found"])
        self.assertEqual(data["value"], 999)

        # Call notebook execution tool via bridge
        nb_res = await bridge.call_tool("antigrvity_notebook_run_code", {"code": "res = 21 * 2\nres"})
        nb_data = json.loads(nb_res.content[0]["text"])
        self.assertTrue(nb_data["success"])
        self.assertEqual(nb_data["return_value"], "42")

        await bridge.shutdown()


if __name__ == "__main__":
    unittest.main()
