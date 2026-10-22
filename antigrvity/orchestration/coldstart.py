"""Multi-agent cold-start orchestration engine."""

import asyncio
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional
from antigrvity.agents.base import AgentState, BaseAgent
from antigrvity.agents.orchestrator import OrchestratorAgent
from antigrvity.agents.registry import AgentRegistry
from antigrvity.agents.researcher import ResearcherAgent
from antigrvity.agents.reviewer import ReviewerAgent
from antigrvity.agents.synthesizer import SynthesizerAgent
from antigrvity.core.config import (
    ColdStartConfig,
    SwarmTopologyConfig,
    MCPBridgeConfig,
    load_json_file,
)
from antigrvity.core.context import Blackboard
from antigrvity.core.events import EventBus
from antigrvity.core.exceptions import ColdStartError, QuorumError
from antigrvity.mcp.bridge import MCPBridge
from antigrvity.orchestration.consensus import ConsensusEngine, Proposal
from antigrvity.utils.logger import get_logger
from antigrvity.utils.system import run_full_system_probe


@dataclass
class PhaseResult:
    phase_id: str
    name: str
    success: bool
    duration_sec: float
    details: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None


@dataclass
class ColdStartResult:
    is_successful: bool
    elapsed_sec: float
    phases: List[PhaseResult]
    quorum: Dict[str, Any]
    mcp_tools_count: int
    error_summary: Optional[str] = None
    telemetry: Dict[str, Any] = field(default_factory=dict)


class ColdStartEngine:
    """Orchestrates the 5-phase cold-start lifecycle for Project ANTIGRVITY."""

    def __init__(
        self,
        coldstart_config: ColdStartConfig,
        topology_config: SwarmTopologyConfig,
        mcp_config: MCPBridgeConfig,
        workspace_path: Optional[Path] = None,
        blackboard: Optional[Blackboard] = None,
        event_bus: Optional[EventBus] = None,
    ):
        self.config = coldstart_config
        self.topology_config = topology_config
        self.mcp_config = mcp_config
        self.workspace_path = workspace_path or Path.cwd()
        self.blackboard = blackboard or Blackboard()
        self.event_bus = event_bus or EventBus()
        self.registry = AgentRegistry()
        self.mcp_bridge = MCPBridge(
            config=self.mcp_config,
            blackboard=self.blackboard,
            event_bus=self.event_bus,
            registry=self.registry,
        )
        self.consensus_engine = ConsensusEngine(
            registry=self.registry,
            blackboard=self.blackboard,
            event_bus=self.event_bus,
        )
        self.logger = get_logger("coldstart.engine")

    @classmethod
    def from_directory(cls, base_dir: Path) -> "ColdStartEngine":
        """Factory method to load configs and initialize from workspace path."""
        config_dir = base_dir / "config"
        cs_data = load_json_file(config_dir / "coldstart.json")
        topo_data = load_json_file(config_dir / "agents.json")
        mcp_data = load_json_file(config_dir / "mcp_servers.json")

        return cls(
            coldstart_config=ColdStartConfig.from_dict(cs_data),
            topology_config=SwarmTopologyConfig.from_dict(topo_data),
            mcp_config=MCPBridgeConfig.from_dict(mcp_data),
            workspace_path=base_dir,
        )

    async def execute_bootstrap(self) -> ColdStartResult:
        """Run the end-to-end 5-phase cold-start orchestration pipeline."""
        start_time = time.time()
        self.logger.info("=" * 60)
        self.logger.info("INITIATING ANTIGRVITY MULTI-AGENT COLD-START ORCHESTRATION")
        self.logger.info("=" * 60)

        phase_results: List[PhaseResult] = []
        overall_success = True
        error_summary = None

        try:
            # PHASE 1: SYSTEM PROBE
            p1_res = await self._run_phase_1_system_probe()
            phase_results.append(p1_res)
            if not p1_res.success:
                raise ColdStartError(f"Phase 1 failed: {p1_res.error}")

            # PHASE 2: TOPOLOGY BOOTSTRAP
            p2_res = await self._run_phase_2_topology_bootstrap()
            phase_results.append(p2_res)
            if not p2_res.success:
                raise ColdStartError(f"Phase 2 failed: {p2_res.error}")

            # PHASE 3: MCP BRIDGE WARMUP
            p3_res = await self._run_phase_3_mcp_bridge_warmup()
            phase_results.append(p3_res)
            if not p3_res.success:
                raise ColdStartError(f"Phase 3 failed: {p3_res.error}")

            # PHASE 4: STATE CONSENSUS
            p4_res = await self._run_phase_4_state_consensus()
            phase_results.append(p4_res)
            if not p4_res.success:
                raise ColdStartError(f"Phase 4 failed: {p4_res.error}")

            # PHASE 5: DISPATCH READY
            p5_res = await self._run_phase_5_dispatch_ready()
            phase_results.append(p5_res)
            if not p5_res.success:
                raise ColdStartError(f"Phase 5 failed: {p5_res.error}")

        except Exception as exc:
            overall_success = False
            error_summary = str(exc)
            self.logger.error(f"Cold-start sequence aborted: {exc}", exc_info=True)

        elapsed = time.time() - start_time
        quorum = self.registry.calculate_quorum()
        tools_count = len(self.mcp_bridge.tools_registry)

        # Store final cold-start outcome on blackboard
        await self.blackboard.set(
            "coldstart:state",
            {
                "success": overall_success,
                "elapsed_sec": round(elapsed, 3),
                "quorum": quorum,
                "mcp_tools": tools_count,
                "timestamp": time.time(),
            },
            agent_id="coldstart_engine",
        )

        status_text = "SUCCESS" if overall_success else "FAILED"
        self.logger.info("=" * 60)
        self.logger.info(
            f"COLD-START PIPELINE {status_text} in {elapsed:.2f}s "
            f"(Quorum: {quorum['ready']}/{quorum['total']}, Tools: {tools_count})"
        )
        self.logger.info("=" * 60)

        return ColdStartResult(
            is_successful=overall_success,
            elapsed_sec=round(elapsed, 3),
            phases=phase_results,
            quorum=quorum,
            mcp_tools_count=tools_count,
            error_summary=error_summary,
            telemetry={
                "workspace": str(self.workspace_path),
                "topology": self.topology_config.topology,
            },
        )

    async def _run_phase_1_system_probe(self) -> PhaseResult:
        """Phase 1: Validate system, storage, VCS, and Python capabilities."""
        start = time.time()
        self.logger.info("PHASE 1: System & Runtime Capability Probe...")
        try:
            probe_data = run_full_system_probe(self.workspace_path)
            # Verify Python version >= 3.10
            py_ver = probe_data["python"]["version"]
            major, minor = map(int, py_ver.split(".")[:2])
            if (major, minor) < (3, 10):
                raise ColdStartError(f"Python >= 3.10 required, detected: {py_ver}")

            # Verify storage writability
            if not probe_data["storage"]["is_writable"]:
                raise ColdStartError(f"Workspace path {self.workspace_path} is not writable")

            await self.blackboard.set("coldstart:system_probe", probe_data, agent_id="coldstart")
            dur = time.time() - start
            self.logger.info(f"Phase 1 PASSED ({dur:.3f}s): Host OS={probe_data['platform']['os']}, Python={py_ver}")
            return PhaseResult("phase_1_system_probe", "System Probe", True, round(dur, 3), details=probe_data)
        except Exception as exc:
            dur = time.time() - start
            return PhaseResult("phase_1_system_probe", "System Probe", False, round(dur, 3), error=str(exc))

    async def _run_phase_2_topology_bootstrap(self) -> PhaseResult:
        """Phase 2: Instantiate agent roles and execute lifecycle probes."""
        start = time.time()
        self.logger.info("PHASE 2: Topology Bootstrap & Role Allocation...")
        try:
            registered_ids = []
            for agent_def in self.topology_config.agents:
                # Instantiate specialized agent class based on role/id
                if agent_def.id == "orchestrator" or agent_def.role == "coordinator":
                    agent = OrchestratorAgent(agent_def, self.blackboard, self.event_bus)
                elif agent_def.id == "researcher" or agent_def.role == "analyst":
                    agent = ResearcherAgent(agent_def, self.blackboard, self.event_bus)
                elif agent_def.id == "synthesizer" or agent_def.role == "worker":
                    agent = SynthesizerAgent(agent_def, self.blackboard, self.event_bus)
                elif agent_def.id == "reviewer" or agent_def.role == "evaluator":
                    agent = ReviewerAgent(agent_def, self.blackboard, self.event_bus)
                else:
                    agent = OrchestratorAgent(agent_def, self.blackboard, self.event_bus)

                self.registry.register(agent)
                registered_ids.append(agent.id)

            # Run agent probes and initialization concurrently
            agents = self.registry.list_all()
            probe_tasks = [a.probe() for a in agents]
            probe_results = await asyncio.gather(*probe_tasks, return_exceptions=True)

            init_tasks = [a.initialize() for a in agents]
            init_results = await asyncio.gather(*init_tasks, return_exceptions=True)

            # Check that critical agents initialized successfully
            for a in self.registry.get_critical_agents():
                if a.state in (AgentState.ERROR, AgentState.DEGRADED):
                    raise ColdStartError(f"Critical agent [{a.id}] failed to initialize: {a.error_reason}")

            dur = time.time() - start
            self.logger.info(f"Phase 2 PASSED ({dur:.3f}s): {len(registered_ids)} agents instantiated.")
            return PhaseResult(
                "phase_2_topology_bootstrap",
                "Topology Bootstrap",
                True,
                round(dur, 3),
                details={"agents": registered_ids},
            )
        except Exception as exc:
            dur = time.time() - start
            return PhaseResult("phase_2_topology_bootstrap", "Topology Bootstrap", False, round(dur, 3), error=str(exc))

    async def _run_phase_3_mcp_bridge_warmup(self) -> PhaseResult:
        """Phase 3: Bootstrap MCP Bridge multiplexer, connect tools, and probe servers."""
        start = time.time()
        self.logger.info("PHASE 3: MCP Bridge Warmup & Capability Negotiation...")
        try:
            bridge_status = await self.mcp_bridge.initialize()
            dur = time.time() - start
            self.logger.info(
                f"Phase 3 PASSED ({dur:.3f}s): MCP Bridge multiplexer warmed up "
                f"with {bridge_status['tool_count']} active tools."
            )
            return PhaseResult(
                "phase_3_mcp_bridge_warmup",
                "MCP Bridge Warmup",
                True,
                round(dur, 3),
                details=bridge_status,
            )
        except Exception as exc:
            dur = time.time() - start
            return PhaseResult("phase_3_mcp_bridge_warmup", "MCP Bridge Warmup", False, round(dur, 3), error=str(exc))

    async def _run_phase_4_state_consensus(self) -> PhaseResult:
        """Phase 4: Conduct consensus voting round on cold-start readiness."""
        start = time.time()
        self.logger.info("PHASE 4: State Consensus & Handshake Round...")
        try:
            proposal = Proposal(
                proposal_id=f"coldstart_consensus_{int(time.time())}",
                initiator="orchestrator",
                topic="Cold-Start System Readiness Certification",
                content={
                    "agents_registered": len(self.registry.list_all()),
                    "mcp_tools_active": len(self.mcp_bridge.tools_registry),
                },
                required_quorum=0.6,
            )
            vote_result = await self.consensus_engine.conduct_vote(proposal, timeout_sec=6.0)
            if not vote_result.approved:
                raise ColdStartError(f"Consensus quorum not reached: {vote_result.approval_ratio:.1%}")

            dur = time.time() - start
            self.logger.info(
                f"Phase 4 PASSED ({dur:.3f}s): Consensus certified with "
                f"{vote_result.votes_for}/{vote_result.total_eligible} approvals."
            )
            return PhaseResult(
                "phase_4_state_consensus",
                "State Consensus",
                True,
                round(dur, 3),
                details={"proposal_id": proposal.proposal_id, "approved": vote_result.approved},
            )
        except Exception as exc:
            dur = time.time() - start
            return PhaseResult("phase_4_state_consensus", "State Consensus", False, round(dur, 3), error=str(exc))

    async def _run_phase_5_dispatch_ready(self) -> PhaseResult:
        """Phase 5: Transition operational agents to READY, arm scheduler, emit ready signal."""
        start = time.time()
        self.logger.info("PHASE 5: Arming Swarm & Emitting Dispatch Ready...")
        try:
            # Mark all operational agents ready
            for agent in self.registry.list_all():
                if agent.state not in (AgentState.ERROR, AgentState.DEGRADED):
                    await agent.mark_ready()

            # Enforce quorum checks
            self.registry.verify_quorum()

            # Emit framework ready event
            await self.event_bus.publish(
                "antigrvity.coldstart_ready",
                sender="coldstart_engine",
                payload={"ready": True, "timestamp": time.time()},
            )

            dur = time.time() - start
            self.logger.info(f"Phase 5 PASSED ({dur:.3f}s): Swarm fully armed and ready for task ingestion.")
            return PhaseResult("phase_5_dispatch_ready", "Dispatch Ready", True, round(dur, 3))
        except Exception as exc:
            dur = time.time() - start
            return PhaseResult("phase_5_dispatch_ready", "Dispatch Ready", False, round(dur, 3), error=str(exc))

    async def shutdown(self) -> None:
        """Tear down swarm and bridge cleanly."""
        await self.mcp_bridge.shutdown()
        await self.registry.shutdown_all()
