"""Tests for the 5-phase ColdStartEngine and workflow execution."""

import unittest
from pathlib import Path
from antigrvity.orchestration.coldstart import ColdStartEngine
from antigrvity.orchestration.workflow import TaskDAG, WorkflowEngine


class TestColdStart(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        self.workspace_dir = Path(__file__).parent.parent
        self.engine = ColdStartEngine.from_directory(self.workspace_dir)

    async def asyncTearDown(self):
        await self.engine.shutdown()

    async def test_coldstart_full_pipeline(self):
        result = await self.engine.execute_bootstrap()
        self.assertTrue(result.is_successful)
        self.assertEqual(len(result.phases), 5)
        self.assertTrue(all(p.success for p in result.phases))
        self.assertTrue(result.quorum["has_quorum"])
        self.assertGreater(result.mcp_tools_count, 0)

        # Check blackboard recorded coldstart state
        bb_state = await self.engine.blackboard.get("coldstart:state")
        self.assertIsNotNone(bb_state)
        self.assertTrue(bb_state["success"])

    async def test_workflow_execution_post_coldstart(self):
        # Bootstrap first
        await self.engine.execute_bootstrap()

        # Build DAG
        dag = TaskDAG(workflow_id="test_dag")
        dag.add_task("task_res", "analyst", {"query": "Unit test query"})
        dag.add_task("task_plan", "coordinator", {"goal": "Test goal"}, dependencies=["task_res"])
        dag.add_task("task_syn", "worker", {"target": "code"}, dependencies=["task_plan"])

        wf = WorkflowEngine(self.engine.registry, self.engine.blackboard)
        result = await wf.execute(dag)

        self.assertEqual(len(result["completed"]), 3)
        self.assertEqual(len(result["failed"]), 0)
        self.assertIn("task_res", result["results"])


if __name__ == "__main__":
    unittest.main()
