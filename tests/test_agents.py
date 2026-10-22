"""Tests for Agent lifecycle, states, and registry."""

import unittest
from antigrvity.agents.base import AgentState
from antigrvity.agents.orchestrator import OrchestratorAgent
from antigrvity.agents.registry import AgentRegistry
from antigrvity.agents.reviewer import ReviewerAgent
from antigrvity.agents.synthesizer import SynthesizerAgent
from antigrvity.core.config import AgentDefinition
from antigrvity.core.context import Blackboard
from antigrvity.core.events import EventBus
from antigrvity.core.exceptions import QuorumError


class TestAgents(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        self.bb = Blackboard()
        self.eb = EventBus()
        self.registry = AgentRegistry()

        # Orchestrator (critical)
        self.orch_def = AgentDefinition(
            id="orchestrator",
            name="Lead Orchestrator",
            role="coordinator",
            description="Lead",
            capabilities=["task_decomposition"],
            is_critical=True,
        )
        self.orch = OrchestratorAgent(self.orch_def, self.bb, self.eb)

        # Reviewer (critical)
        self.rev_def = AgentDefinition(
            id="reviewer",
            name="Reviewer",
            role="evaluator",
            description="Safety",
            capabilities=["safety_audit"],
            is_critical=True,
        )
        self.rev = ReviewerAgent(self.rev_def, self.bb, self.eb)

        # Synthesizer (optional)
        self.syn_def = AgentDefinition(
            id="synthesizer",
            name="Synthesizer",
            role="worker",
            description="Worker",
            capabilities=["code_generation"],
            is_critical=False,
        )
        self.syn = SynthesizerAgent(self.syn_def, self.bb, self.eb)

        self.registry.register(self.orch)
        self.registry.register(self.rev)
        self.registry.register(self.syn)

    async def test_agent_lifecycle_probe_init_ready(self):
        self.assertEqual(self.orch.state, AgentState.OFFLINE)
        self.assertTrue(await self.orch.probe())
        self.assertEqual(self.orch.state, AgentState.PROBING)

        self.assertTrue(await self.orch.initialize())
        self.assertEqual(self.orch.state, AgentState.INITIALIZING)

        await self.orch.mark_ready()
        self.assertEqual(self.orch.state, AgentState.READY)

    async def test_quorum_calculation(self):
        q = self.registry.calculate_quorum()
        self.assertEqual(q["total"], 3)
        self.assertEqual(q["ready"], 0)
        self.assertFalse(q["has_quorum"])

        # Mark 1 critical and 1 optional ready
        await self.orch.mark_ready()
        await self.syn.mark_ready()

        # Still missing reviewer (critical)
        q2 = self.registry.calculate_quorum()
        self.assertFalse(q2["has_quorum"])
        self.assertEqual(q2["critical_ready"], 1)

        # Mark reviewer ready
        await self.rev.mark_ready()
        q3 = self.registry.calculate_quorum()
        self.assertTrue(q3["has_quorum"])
        self.assertEqual(q3["critical_ready"], 2)
        self.assertEqual(q3["ready"], 3)

    async def test_verify_quorum_exception(self):
        with self.assertRaises(QuorumError):
            self.registry.verify_quorum()


if __name__ == "__main__":
    unittest.main()
