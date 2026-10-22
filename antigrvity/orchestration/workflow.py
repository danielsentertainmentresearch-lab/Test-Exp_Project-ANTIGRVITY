"""Task DAG and asynchronous multi-agent workflow scheduling."""

import asyncio
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set
from antigrvity.agents.registry import AgentRegistry
from antigrvity.core.context import Blackboard
from antigrvity.core.exceptions import WorkflowError
from antigrvity.utils.logger import get_logger


class TaskStatus(str, Enum):
    PENDING = "PENDING"
    READY = "READY"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


@dataclass
class TaskNode:
    """A node within a task DAG."""
    id: str
    target_role_or_agent: str
    input_data: Dict[str, Any]
    dependencies: Set[str] = field(default_factory=set)
    status: TaskStatus = TaskStatus.PENDING
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    started_at: Optional[float] = None
    completed_at: Optional[float] = None


class TaskDAG:
    """Directed Acyclic Graph of tasks for multi-agent execution."""

    def __init__(self, workflow_id: str):
        self.workflow_id = workflow_id
        self.nodes: Dict[str, TaskNode] = {}

    def add_task(
        self,
        task_id: str,
        target_role_or_agent: str,
        input_data: Dict[str, Any],
        dependencies: Optional[List[str]] = None,
    ) -> TaskNode:
        """Add a task node to the DAG."""
        if task_id in self.nodes:
            raise WorkflowError(f"Duplicate task id: {task_id}")
        deps = set(dependencies or [])
        node = TaskNode(
            id=task_id,
            target_role_or_agent=target_role_or_agent,
            input_data=input_data,
            dependencies=deps,
        )
        self.nodes[task_id] = node
        return node

    def validate(self) -> None:
        """Validate dependencies exist and detect cycles."""
        for task_id, node in self.nodes.items():
            for dep in node.dependencies:
                if dep not in self.nodes:
                    raise WorkflowError(f"Task '{task_id}' depends on undefined task '{dep}'")

        # Cycle detection using DFS
        visited: Dict[str, int] = {}  # 0=unvisited, 1=visiting, 2=visited

        def _dfs(node_id: str):
            visited[node_id] = 1
            for dep in self.nodes[node_id].dependencies:
                state = visited.get(dep, 0)
                if state == 1:
                    raise WorkflowError(f"Cycle detected in task DAG involving '{node_id}' and '{dep}'")
                elif state == 0:
                    _dfs(dep)
            visited[node_id] = 2

        for task_id in self.nodes:
            if visited.get(task_id, 0) == 0:
                _dfs(task_id)


class WorkflowEngine:
    """Executes a TaskDAG using registered swarm agents and the shared blackboard."""

    def __init__(self, registry: AgentRegistry, blackboard: Blackboard, max_concurrency: int = 4):
        self.registry = registry
        self.blackboard = blackboard
        self.max_concurrency = max_concurrency
        self.logger = get_logger("workflow.engine")

    async def execute(self, dag: TaskDAG) -> Dict[str, Any]:
        """Execute all tasks in the DAG honoring dependencies."""
        dag.validate()
        semaphore = asyncio.Semaphore(self.max_concurrency)
        running_tasks: Dict[str, asyncio.Task] = {}
        completed: Set[str] = set()
        failed: Set[str] = set()

        self.logger.info(f"Starting workflow '{dag.workflow_id}' with {len(dag.nodes)} tasks...")

        while len(completed) + len(failed) < len(dag.nodes):
            # Find eligible nodes that are PENDING and all dependencies COMPLETED
            eligible = [
                node for node in dag.nodes.values()
                if node.status == TaskStatus.PENDING
                and node.dependencies.issubset(completed)
                and node.id not in running_tasks
            ]

            if not eligible and not running_tasks:
                # Deadlock or unmet dependencies
                for node in dag.nodes.values():
                    if node.status == TaskStatus.PENDING:
                        node.status = TaskStatus.SKIPPED
                        node.error = "Unmet dependencies due to earlier failures"
                        failed.add(node.id)
                break

            for node in eligible:
                node.status = TaskStatus.READY
                task = asyncio.create_task(self._run_node(node, semaphore))
                running_tasks[node.id] = task

            # Wait for at least one running task to complete
            if running_tasks:
                done, _ = await asyncio.wait(
                    running_tasks.values(),
                    return_when=asyncio.FIRST_COMPLETED,
                )
                for task in done:
                    # Find task id
                    done_id = [t_id for t_id, t in running_tasks.items() if t == task][0]
                    del running_tasks[done_id]
                    node = dag.nodes[done_id]
                    if node.status == TaskStatus.COMPLETED:
                        completed.add(done_id)
                    else:
                        failed.add(done_id)

        self.logger.info(
            f"Workflow '{dag.workflow_id}' finished: {len(completed)} completed, {len(failed)} failed"
        )
        return {
            "workflow_id": dag.workflow_id,
            "completed": list(completed),
            "failed": list(failed),
            "results": {n.id: n.result for n in dag.nodes.values() if n.result is not None},
            "errors": {n.id: n.error for n in dag.nodes.values() if n.error is not None},
        }

    async def _run_node(self, node: TaskNode, semaphore: asyncio.Semaphore) -> None:
        async with semaphore:
            node.status = TaskStatus.RUNNING
            node.started_at = time.time()
            self.logger.info(f"Task '{node.id}' dispatching to '{node.target_role_or_agent}'...")

            # Resolve target agent
            agent = self.registry.get(node.target_role_or_agent)
            if not agent:
                # Try finding by role
                agents_with_role = self.registry.get_by_role(node.target_role_or_agent)
                if agents_with_role:
                    agent = agents_with_role[0]

            if not agent:
                node.status = TaskStatus.FAILED
                node.error = f"No agent found for target '{node.target_role_or_agent}'"
                node.completed_at = time.time()
                return

            try:
                result = await agent.execute_task(node.id, node.input_data)
                node.result = result
                node.status = TaskStatus.COMPLETED
                await self.blackboard.set(f"task:{node.id}:result", result, agent_id=agent.id)
            except Exception as exc:
                self.logger.error(f"Task '{node.id}' failed: {exc}", exc_info=True)
                node.status = TaskStatus.FAILED
                node.error = str(exc)
            finally:
                node.completed_at = time.time()
