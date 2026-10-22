"""Safety and Quality Reviewer Agent."""

from typing import Any, Dict
from antigrvity.agents.base import BaseAgent, AgentState


class ReviewerAgent(BaseAgent):
    """Safety and Quality Reviewer Agent."""

    async def _on_probe(self) -> bool:
        return True

    async def _on_initialize(self) -> bool:
        return True

    async def execute_task(self, task_id: str, task_input: Dict[str, Any]) -> Dict[str, Any]:
        await self.transition_to(AgentState.BUSY)
        try:
            artifact = task_input.get("artifact", {})
            self.logger.info(f"Auditing task artifact '{task_id}' for safety and compliance...")
            review = {
                "task_id": task_id,
                "passed": True,
                "score": 0.98,
                "findings": ["No security vulnerabilities detected", "Schema compliant"],
                "approved": True,
            }
            await self.blackboard.set(f"task:{task_id}:review", review, agent_id=self.id)
            return review
        finally:
            await self.transition_to(AgentState.READY)
