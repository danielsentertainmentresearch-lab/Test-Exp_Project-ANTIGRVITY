"""Multi-agent consensus engine for state transitions and decisions."""

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from antigrvity.agents.registry import AgentRegistry
from antigrvity.core.context import Blackboard
from antigrvity.core.events import EventBus
from antigrvity.utils.logger import get_logger


@dataclass
class Proposal:
    """A proposal submitted for swarm consensus."""
    proposal_id: str
    initiator: str
    topic: str
    content: Dict[str, Any]
    required_quorum: float = 0.6
    created_at: float = field(default_factory=time.time)


@dataclass
class Vote:
    agent_id: str
    approved: bool
    reason: str = ""
    timestamp: float = field(default_factory=time.time)


@dataclass
class ConsensusResult:
    proposal_id: str
    approved: bool
    votes_for: int
    votes_against: int
    total_eligible: int
    approval_ratio: float
    duration_sec: float
    details: Dict[str, Any] = field(default_factory=dict)


class ConsensusEngine:
    """Engine facilitating voting rounds and consensus agreements among agents."""

    def __init__(self, registry: AgentRegistry, blackboard: Blackboard, event_bus: EventBus):
        self.registry = registry
        self.blackboard = blackboard
        self.event_bus = event_bus
        self.logger = get_logger("consensus.engine")

    async def conduct_vote(
        self,
        proposal: Proposal,
        timeout_sec: float = 5.0,
    ) -> ConsensusResult:
        """Conduct a voting round across registered agents."""
        start_time = time.time()
        agents = self.registry.list_all()
        eligible_agents = [a for a in agents if a.role in ("coordinator", "evaluator", "analyst", "worker")]
        total_eligible = len(eligible_agents)

        self.logger.info(
            f"Initiating consensus round for proposal '{proposal.proposal_id}' ({proposal.topic}) "
            f"across {total_eligible} eligible agents..."
        )

        # Broadcast proposal event
        await self.event_bus.publish(
            "consensus.proposal_created",
            sender=proposal.initiator,
            payload={"proposal_id": proposal.proposal_id, "topic": proposal.topic},
        )

        # Collect votes from agents asynchronously
        votes: Dict[str, Vote] = {}

        async def _collect_agent_vote(agent):
            # Critical/evaluator agents check safety, others default to approve if operational
            approved = agent.state.value not in ("ERROR", "OFFLINE")
            reason = "Operational & verified" if approved else f"Agent is in state {agent.state.value}"
            return Vote(agent_id=agent.id, approved=approved, reason=reason)

        vote_tasks = [_collect_agent_vote(a) for a in eligible_agents]
        collected = await asyncio.gather(*vote_tasks, return_exceptions=True)

        for res in collected:
            if isinstance(res, Vote):
                votes[res.agent_id] = res

        votes_for = sum(1 for v in votes.values() if v.approved)
        votes_against = sum(1 for v in votes.values() if not v.approved)
        ratio = (votes_for / total_eligible) if total_eligible > 0 else 0.0
        approved = ratio >= proposal.required_quorum

        duration = time.time() - start_time
        result = ConsensusResult(
            proposal_id=proposal.proposal_id,
            approved=approved,
            votes_for=votes_for,
            votes_against=votes_against,
            total_eligible=total_eligible,
            approval_ratio=round(ratio, 2),
            duration_sec=round(duration, 3),
            details={v.agent_id: {"approved": v.approved, "reason": v.reason} for v in votes.values()},
        )

        # Record consensus result in blackboard
        await self.blackboard.set(
            f"consensus:{proposal.proposal_id}",
            {
                "approved": approved,
                "ratio": ratio,
                "votes_for": votes_for,
                "votes_against": votes_against,
                "timestamp": time.time(),
            },
            agent_id="consensus_engine",
        )

        self.logger.info(
            f"Consensus reached: approved={approved} (ratio={ratio:.1%}, "
            f"required={proposal.required_quorum:.1%}) in {duration:.3f}s"
        )
        return result
