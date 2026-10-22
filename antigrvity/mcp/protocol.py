"""Model Context Protocol (MCP) JSON-RPC 2.0 specifications and models."""

import json
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Union
from antigrvity.core.exceptions import MCPProtocolError

JSONRPC_VERSION = "2.0"
DEFAULT_MCP_PROTOCOL_VERSION = "2024-11-05"

# Standard JSON-RPC 2.0 Error Codes
PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603


@dataclass
class JSONRPCRequest:
    method: str
    id: Optional[Union[str, int]] = None
    params: Optional[Dict[str, Any]] = None
    jsonrpc: str = JSONRPC_VERSION

    def to_json(self) -> str:
        d = {"jsonrpc": self.jsonrpc, "method": self.method}
        if self.id is not None:
            d["id"] = self.id
        if self.params is not None:
            d["params"] = self.params
        return json.dumps(d)


@dataclass
class JSONRPCResponse:
    id: Optional[Union[str, int]]
    result: Optional[Any] = None
    error: Optional[Dict[str, Any]] = None
    jsonrpc: str = JSONRPC_VERSION

    def to_json(self) -> str:
        d = {"jsonrpc": self.jsonrpc, "id": self.id}
        if self.error is not None:
            d["error"] = self.error
        else:
            d["result"] = self.result if self.result is not None else {}
        return json.dumps(d)


@dataclass
class MCPTool:
    """Tool exposed over MCP."""
    name: str
    description: str
    inputSchema: Dict[str, Any] = field(default_factory=lambda: {
        "type": "object",
        "properties": {},
    })

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.inputSchema,
        }


@dataclass
class MCPToolResult:
    """Structured response to a tool execution."""
    content: List[Dict[str, Any]] = field(default_factory=list)
    isError: bool = False

    @classmethod
    def text(cls, text: str, is_error: bool = False) -> "MCPToolResult":
        return cls(content=[{"type": "text", "text": str(text)}], isError=is_error)

    @classmethod
    def json(cls, data: Any, is_error: bool = False) -> "MCPToolResult":
        text = json.dumps(data, indent=2) if not isinstance(data, str) else data
        return cls(content=[{"type": "text", "text": text}], isError=is_error)

    def to_dict(self) -> Dict[str, Any]:
        return {"content": self.content, "isError": self.isError}


def parse_jsonrpc_message(raw_text: str) -> Union[JSONRPCRequest, JSONRPCResponse]:
    """Parse and validate an incoming JSON-RPC 2.0 message."""
    try:
        data = json.loads(raw_text.strip())
    except Exception as exc:
        raise MCPProtocolError(f"Parse error: {exc}", code=PARSE_ERROR) from exc

    if not isinstance(data, dict):
        raise MCPProtocolError("Message must be a JSON object", code=INVALID_REQUEST)

    if data.get("jsonrpc") != JSONRPC_VERSION:
        raise MCPProtocolError(f"Unsupported jsonrpc version: {data.get('jsonrpc')}", code=INVALID_REQUEST)

    if "method" in data:
        return JSONRPCRequest(
            method=data["method"],
            id=data.get("id"),
            params=data.get("params"),
        )
    elif "result" in data or "error" in data:
        return JSONRPCResponse(
            id=data.get("id"),
            result=data.get("result"),
            error=data.get("error"),
        )
    else:
        raise MCPProtocolError("Invalid JSON-RPC payload: missing method, result, or error", code=INVALID_REQUEST)
