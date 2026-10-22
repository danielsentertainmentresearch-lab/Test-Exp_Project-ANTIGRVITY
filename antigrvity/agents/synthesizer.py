"""Code and Artifact Synthesizer Agent."""

from typing import Any, Dict
from antigrvity.agents.base import BaseAgent, AgentState


class SynthesizerAgent(BaseAgent):
    """Artifact and Code Synthesizer Agent."""

    async def _on_probe(self) -> bool:
        return True

    async def _on_initialize(self) -> bool:
        return True

    async def execute_task(self, task_id: str, task_input: Dict[str, Any]) -> Dict[str, Any]:
        await self.transition_to(AgentState.BUSY)
        try:
            target = task_input.get("target", "artifact")
            spec = task_input.get("spec", {})
            self.logger.info(f"Synthesizing artifact for target: '{target}'")
            output = {
                "task_id": task_id,
                "target": target,
                "synthesized": True,
                "generated_files": spec.get("files", []),
                "artifacts_count": len(spec.get("files", [])),
            }
            await self.blackboard.set(f"task:{task_id}:artifacts", output, agent_id=self.id)
            return output
        finally:
            await self.transition_to(AgentState.READY)
