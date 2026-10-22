"""Specialized exceptions for Project ANTIGRVITY."""

class AntigrvityError(Exception):
    """Base exception for all ANTIGRVITY framework errors."""
    pass


class ConfigurationError(AntigrvityError):
    """Raised when configuration files are missing, invalid, or malformed."""
    pass


class ColdStartError(AntigrvityError):
    """Raised when cold-start bootstrap fails or fails to meet readiness thresholds."""
    pass


class QuorumError(ColdStartError):
    """Raised when critical agent quorum cannot be achieved."""
    pass


class AgentLifecycleError(AntigrvityError):
    """Raised on illegal agent state transitions or communication failures."""
    pass


class WorkflowError(AntigrvityError):
    """Raised during task DAG execution or dependency cycle detection."""
    pass


class MCPBridgeError(AntigrvityError):
    """Raised when MCP servers or RPC bridges fail to communicate."""
    pass


class MCPProtocolError(MCPBridgeError):
    """Raised when JSON-RPC 2.0 validation or message schema fails."""
    def __init__(self, message: str, code: int = -32603, data: dict = None):
        super().__init__(message)
        self.code = code
        self.data = data or {}
