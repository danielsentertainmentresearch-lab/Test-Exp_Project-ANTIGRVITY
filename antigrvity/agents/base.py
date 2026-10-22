"""Base agent abstractions, states, and lifecycle hooks."""

import asyncio
import enum
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from antigrvity.core.context import Blackboard
from antigrvity.core.events import EventBus, Event
from antigrvity.core.config import AgentDefinition
from antigrvity.utils.logger import get_logger


class AgentState(str, enum.Enum):
    OFFLINE = "OFFLINE"
    PROBING = "PROBING"
    INITIALIZING = "INITIALIZING"
    WARMING_MCP = "WARMING_MCP"
    CONSENSUS = "CONSENSUS"
    READY = "READY"
    BUSY = "BUSY"
    DEGRADED = "DEGRADED"
    ERROR = "ERROR"


class BaseAgent(ABC):
    """Abstract base class for all autonomous agents in Project ANTIGRVITY."""

    def __init__(
        self,
        definition: AgentDefinition,
        blackboard: Blackboard,
        event_bus: EventBus,
    ):
        self.definition = definition
        self.blackboard = blackboard
        self.event_bus = event_bus
        self.state = AgentState.OFFLINE
        self.logger = get_logger(f"agent.{definition.id}")
        self.last_heartbeat: float = time.time()
        self.error_reason: Optional[str] = None
        self.assigned_tasks: List[str] = []

    @property
    def id(self) -> str:
        return self.definition.id

    @property
    def name(self) -> str:
        return self.definition.name

    @property
    def role(self) -> str:
        return self.definition.role

    @property
    def is_critical(self) -> bool:
        return self.definition.is_critical

    @property
    def capabilities(self) -> List[str]:
        return self.definition.capabilities

    async def transition_to(self, new_state: AgentState, reason: Optional[str] = None) -> None:
        """Safely transition agent state and broadcast state change event."""
        old_state = self.state
        self.state = new_state
        if reason:
            self.error_reason = reason
        self.last_heartbeat = time.time()

        # Update blackboard entry
        await self.blackboard.set(
            f"agent:{self.id}:state",
            {
                "state": self.state.value,
                "role": self.role,
                "timestamp": self.last_heartbeat,
                "reason": reason,
            },
            agent_id=self.id,
            ttl_sec=60.0,
        )

        # Broadcast event
        await self.event_bus.publish(
            f"agent.{self.id}.state_changed",
            sender=self.id,
            payload={"old_state": old_state.value, "new_state": new_state.value, "reason": reason},
        )
        self.logger.info(f"Transitioned {old_state.value} -> {new_state.value}" + (f" ({reason})" if reason else ""))

    async def heartbeat(self) -> None:
        """Emit a heartbeat signal to verify liveness."""
        self.last_heartbeat = time.time()
        await self.blackboard.set(
            f"agent:{self.id}:heartbeat",
            {"timestamp": self.last_heartbeat, "state": self.state.value},
            agent_id=self.id,
            ttl_sec=30.0,
        )

    # Lifecycle Hooks
    async def probe(self) -> bool:
        """Phase 1 Cold-Start Hook: Self-check environmental readiness."""
        await self.transition_to(AgentState.PROBING)
        try:
            success = await self._on_probe()
            if not success:
                await self.transition_to(AgentState.DEGRADED, "Self-probe check failed")
                return False
            return True
        except Exception as exc:
            await self.transition_to(AgentState.ERROR, str(exc))
            return False

    async def initialize(self) -> bool:
        """Phase 2 Cold-Start Hook: Initialize internal states and bindings."""
        await self.transition_to(AgentState.INITIALIZING)
        try:
            success = await self._on_initialize()
            if not success:
                await self.transition_to(AgentState.DEGRADED, "Initialization failed")
                return False
            return True
        except Exception as exc:
            await self.transition_to(AgentState.ERROR, str(exc))
            return False

    async def mark_ready(self) -> None:
        """Phase 5 Cold-Start Hook: Arm agent for active task intake."""
        await self.transition_to(AgentState.READY)

    async def shutdown(self) -> None:
        """Gracefully release resources and disconnect."""
        try:
            await self._on_shutdown()
        finally:
            await self.transition_to(AgentState.OFFLINE, "Clean shutdown")

    @abstractmethod
    async def _on_probe(self) -> bool:
        """Subclass implementation of self-diagnostics."""
        return True

    @abstractmethod
    async def _on_initialize(self) -> bool:
        """Subclass implementation of resource initialization."""
        return True

    async def _on_shutdown(self) -> None:
        """Subclass optional teardown logic."""
        pass

    @abstractmethod
    async def execute_task(self, task_id: str, task_input: Dict[str, Any]) -> Dict[str, Any]:
        """Execute assigned task and return structured output."""
        pass
