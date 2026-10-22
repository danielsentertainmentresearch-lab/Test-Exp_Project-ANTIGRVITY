"""Registry for managing multi-agent swarm membership, quorum, and health."""

import asyncio
from typing import Any, Dict, List, Optional
from antigrvity.agents.base import BaseAgent, AgentState
from antigrvity.core.exceptions import QuorumError
from antigrvity.utils.logger import get_logger


class AgentRegistry:
    """Central registry and life-cycle manager for all swarm agents."""

    def __init__(self):
        self._agents: Dict[str, BaseAgent] = {}
        self.logger = get_logger("agent.registry")

    def register(self, agent: BaseAgent) -> None:
        """Register an agent into the swarm."""
        self._agents[agent.id] = agent
        self.logger.info(f"Registered agent [{agent.id}] role='{agent.role}' critical={agent.is_critical}")

    def deregister(self, agent_id: str) -> Optional[BaseAgent]:
        """Deregister an agent from the swarm."""
        return self._agents.pop(agent_id, None)

    def get(self, agent_id: str) -> Optional[BaseAgent]:
        """Look up an agent by ID."""
        return self._agents.get(agent_id)

    def list_all(self) -> List[BaseAgent]:
        """Return all registered agents."""
        return list(self._agents.values())

    def get_by_role(self, role: str) -> List[BaseAgent]:
        """Filter agents by functional role."""
        return [a for a in self._agents.values() if a.role == role]

    def get_by_capability(self, capability: str) -> List[BaseAgent]:
        """Filter agents by specific capability tag."""
        return [a for a in self._agents.values() if capability in a.capabilities]

    def get_critical_agents(self) -> List[BaseAgent]:
        """Return all critical agents required for core quorum."""
        return [a for a in self._agents.values() if a.is_critical]

    def calculate_quorum(self) -> Dict[str, Any]:
        """Calculate swarm health and quorum statistics."""
        total = len(self._agents)
        if total == 0:
            return {
                "total": 0,
                "ready": 0,
                "critical_total": 0,
                "critical_ready": 0,
                "has_quorum": False,
                "health_ratio": 0.0,
            }

        critical_agents = self.get_critical_agents()
        critical_ready = sum(1 for a in critical_agents if a.state in (AgentState.READY, AgentState.BUSY))
        total_ready = sum(1 for a in self._agents.values() if a.state in (AgentState.READY, AgentState.BUSY))

        # Quorum requires 100% of critical agents and at least 50% overall
        has_critical_quorum = (critical_ready == len(critical_agents))
        overall_ratio = total_ready / total
        has_quorum = has_critical_quorum and (overall_ratio >= 0.5)

        return {
            "total": total,
            "ready": total_ready,
            "critical_total": len(critical_agents),
            "critical_ready": critical_ready,
            "has_quorum": has_quorum,
            "health_ratio": round(overall_ratio, 2),
        }

    def verify_quorum(self) -> None:
        """Enforce quorum checks; raises QuorumError if unmet."""
        q = self.calculate_quorum()
        if not q["has_quorum"]:
            unready_critical = [
                a.id for a in self.get_critical_agents()
                if a.state not in (AgentState.READY, AgentState.BUSY)
            ]
            raise QuorumError(
                f"Swarm quorum not met: {q['ready']}/{q['total']} agents ready. "
                f"Unready critical agents: {unready_critical}"
            )

    async def broadcast_heartbeat(self) -> None:
        """Emit heartbeats for all active registered agents."""
        tasks = [a.heartbeat() for a in self._agents.values()]
        await asyncio.gather(*tasks, return_exceptions=True)

    async def shutdown_all(self) -> None:
        """Gracefully shut down all registered agents."""
        tasks = [a.shutdown() for a in self._agents.values()]
        await asyncio.gather(*tasks, return_exceptions=True)
        self.logger.info("All registered agents shut down cleanly.")
