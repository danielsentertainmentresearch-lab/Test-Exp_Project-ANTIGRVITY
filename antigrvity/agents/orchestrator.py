"""Lead Orchestration Agent."""

import asyncio
from typing import Any, Dict
from antigrvity.agents.base import BaseAgent, AgentState


class OrchestratorAgent(BaseAgent):
    """Lead Orchestrator responsible for task decomposition, scheduling, and consensus."""

    async def _on_probe(self) -> bool:
        # Check event bus and blackboard access
        await self.blackboard.set("orchestrator:probe", "ok", agent_id=self.id)
        val = await self.blackboard.get("orchestrator:probe")
        return val == "ok"

    async def _on_initialize(self) -> bool:
        # Initialize scheduling queues and state registers
        await self.blackboard.set("orchestrator:queue_active", True, agent_id=self.id)
        return True

    async def execute_task(self, task_id: str, task_input: Dict[str, Any]) -> Dict[str, Any]:
        await self.transition_to(AgentState.BUSY)
        try:
            goal = task_input.get("goal", "Execute plan")
            subtasks = task_input.get("subtasks", [])
            self.logger.info(f"Decomposing objective '{goal}' into execution steps...")

            # Record plan on blackboard
            plan = {
                "task_id": task_id,
                "goal": goal,
                "subtasks_count": len(subtasks),
                "status": "in_progress",
            }
            await self.blackboard.set(f"task:{task_id}:plan", plan, agent_id=self.id)

            return {
                "task_id": task_id,
                "status": "planned",
                "plan": plan,
                "assigned_agents": ["synthesizer", "researcher", "reviewer"],
            }
        finally:
            await self.transition_to(AgentState.READY)
