"""
Project ANTIGRVITY: Multi-Agent Cold-Start Orchestration Framework & MCP Bridge.
"""

__version__ = "0.1.0"
__author__ = "Project ANTIGRVITY Team"

from antigrvity.core.context import Blackboard
from antigrvity.core.events import EventBus, Event
from antigrvity.agents.base import BaseAgent, AgentState
from antigrvity.agents.registry import AgentRegistry
from antigrvity.orchestration.coldstart import ColdStartEngine, ColdStartResult
from antigrvity.mcp.bridge import MCPBridge

__all__ = [
    "__version__",
    "Blackboard",
    "EventBus",
    "Event",
    "BaseAgent",
    "AgentState",
    "AgentRegistry",
    "ColdStartEngine",
    "ColdStartResult",
    "MCPBridge",
]
