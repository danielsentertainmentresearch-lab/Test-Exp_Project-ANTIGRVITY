import time
import json
import sys
from datetime import datetime
from typing import List, Dict, Any, Optional


class ZeroContextAgentWithEviction:
    """
    Represents an agent model deployed at 'Technical Zero' context load
    with an active Context Window Eviction & Compression Policy.
    """
    def __init__(self, agent_id: str, role: str, system_directive: str, max_context_tokens: int = 100):
        self.agent_id = agent_id
        self.role = role
        self.max_context_tokens = max_context_tokens
        
        # Technical Zero Context State
        self.system_directive: str = system_directive
        self.system_prompt_tokens: int = len(system_directive.split())
        self.working_memory: List[Dict[str, Any]] = []
        self.short_term_buffer: List[Dict[str, Any]] = []
        self.eviction_logs: List[Dict[str, Any]] = []
        
        # Initialize context count to strictly system prompt (cold start)
        self.context_window_tokens: int = self.system_prompt_tokens
        
        self.deployment_log: Dict[str, Any] = {
            "status": "DEPLOYED_COLD_START",
            "initial_memory_load_bytes": 0,
            "initial_context_tokens": self.context_window_tokens,
            "max_context_cap_tokens": self.max_context_tokens,
            "deployed_at": datetime.now().isoformat()
        }

    def apply_eviction_policy(self) -> Optional[Dict[str, Any]]:
        """
        Enforces strict context window limits. Evicts older short-term buffer items
        and compresses old working memory when context exceeds max_context_tokens.
        """
        if self.context_window_tokens <= self.max_context_tokens:
            return None
        tokens_before = self.context_window_tokens
        evicted_items = 0
        
        # Phase 1: Prune short-term buffer items
        while self.short_term_buffer and self.context_window_tokens > self.max_context_tokens:
            oldest_item = self.short_term_buffer.pop(0)
            freed_tokens = oldest_item.get("tokens_added", 5)
            self.context_window_tokens = max(self.system_prompt_tokens, self.context_window_tokens - freed_tokens)
            evicted_items += 1

        # Phase 2: Truncate context window to cap if single payload overhead exceeds max cap
        if self.context_window_tokens > self.max_context_tokens:
            self.context_window_tokens = self.max_context_tokens

        eviction_record = {
            "timestamp": datetime.now().isoformat(),
            "agent_id": self.agent_id,
            "tokens_before": tokens_before,
            "tokens_after": self.context_window_tokens,
            "items_evicted": evicted_items,
            "max_context_cap": self.max_context_tokens
        }
        self.eviction_logs.append(eviction_record)
        return eviction_record

    def ingest_stimulus(self, sender: str, payload: Dict[str, Any]) -> tuple[Dict[str, Any], Optional[Dict[str, Any]]]:
        """Ingests new input, measuring context window expansion and enforcing eviction policy."""
        payload_str = json.dumps(payload)
        payload_tokens = len(payload_str.split())
        
        self.context_window_tokens += payload_tokens
        entry = {
            "timestamp": datetime.now().isoformat(),
            "sender": sender,
            "payload": payload,
            "tokens_added": payload_tokens,
            "cumulative_context_tokens": self.context_window_tokens
        }
        self.working_memory.append(entry)
        self.short_term_buffer.append(entry)
        
        # Enforce Context Eviction Cap
        eviction = self.apply_eviction_policy()
        return entry, eviction

    def generate_response(self, action: str, output_data: Dict[str, Any]) -> tuple[Dict[str, Any], Optional[Dict[str, Any]]]:
        """Generates agent response while managing context window bounds."""
        response_payload = {
            "agent_id": self.agent_id,
            "role": self.role,
            "action": action,
            "data": output_data,
            "current_context_load_tokens": self.context_window_tokens
        }
        resp_str = json.dumps(response_payload)
        output_tokens = len(resp_str.split())
        self.context_window_tokens += output_tokens
        
        # Enforce Context Eviction Cap
        eviction = self.apply_eviction_policy()
        return response_payload, eviction

    def get_buffer_summary(self) -> str:
        """Compact string representation of current short-term buffer."""
        if not self.short_term_buffer:
            return "[Empty Buffer]"
        items = []
        for item in self.short_term_buffer:
            sender = item.get("sender", "self")
            toks = item.get("tokens_added", 0)
            action = item.get("payload", {}).get("action") or item.get("payload", {}).get("data", {}).get("status", "msg")
            items.append(f"<{sender}:{action}(+{toks}t)>")
        return " -> ".join(items)


class ManagedColdStartRuntime:
    """
    Orchestrates the deployment of models starting from technical zero context load
    with active context window eviction policies.
    """
    def __init__(self, max_context_cap: int = 100):
        self.max_context_cap = max_context_cap
        self.agents: Dict[str, ZeroContextAgentWithEviction] = {}
        self.history: List[Dict[str, Any]] = []

    def deploy_agent_cold_start(self, agent_id: str, role: str, system_directive: str) -> ZeroContextAgentWithEviction:
        agent = ZeroContextAgentWithEviction(agent_id, role, system_directive, max_context_tokens=self.max_context_cap)
        self.agents[agent_id] = agent
        return agent

    def run_managed_simulation(self, cycles: int = 10, verbose_inspect: bool = True):
        print(f"\n{'='*80}")
        print(f"=== ANTIGRVITY ZERO-CONTEXT RUNTIME ({cycles} Cycles | Cap: {self.max_context_cap} Tokens) ===")
        print(f"{'='*80}\n")
        
        coordinator = self.deploy_agent_cold_start("Coordinator_Zero", "Orchestrator", "Coordinate multi-agent workflows.")
        executor = self.deploy_agent_cold_start("Executor_Zero", "Execution_Node", "Execute dApp verification actions.")
        observer = self.deploy_agent_cold_start("Observer_Zero", "Fine_Tuning_Observer", "Observe drift and evaluate real-time tuning.")

        print(f"[BOOTSTRAP] Initialized 3 agents at Technical Zero context load:")
        for a in self.agents.values():
            print(f"  * {a.agent_id.ljust(18)} | Prompt: {a.system_prompt_tokens:2d} tokens | Cap: {a.max_context_tokens} tokens | Buffer: {len(a.short_term_buffer)} items")
        print()

        for c in range(1, cycles + 1):
            cycle_evictions = []

            # 1. Coordinator dispatch
            coord_resp, e1 = coordinator.generate_response("DISPATCH", {"task": f"TASK_{c}", "cycle": c})
            if e1: cycle_evictions.append(e1)
            
            # 2. Executor ingest and output
            _, e2 = executor.ingest_stimulus(coordinator.agent_id, coord_resp)
            if e2: cycle_evictions.append(e2)
            exec_resp, e3 = executor.generate_response("EXECUTE", {"status": "SUCCESS", "cycle": c})
            if e3: cycle_evictions.append(e3)
            
            # 3. Observer ingest and output
            _, e4 = observer.ingest_stimulus(executor.agent_id, exec_resp)
            if e4: cycle_evictions.append(e4)
            obs_resp, e5 = observer.generate_response("FINE_TUNE", {"drift": False, "cycle": c})
            if e5: cycle_evictions.append(e5)

            # Record metrics
            cycle_snapshot = {
                "cycle": c,
                "coordinator_tokens": coordinator.context_window_tokens,
                "executor_tokens": executor.context_window_tokens,
                "observer_tokens": observer.context_window_tokens,
                "total_evictions": sum(len(a.eviction_logs) for a in self.agents.values()),
                "new_evictions": len(cycle_evictions),
            }
            self.history.append(cycle_snapshot)

            # Terminal Inspection Logging
            print(f"{'-'*80}")
            print(f"[CYCLE {c:02d}] Load: Coord={coordinator.context_window_tokens:3d}/{self.max_context_cap}t | Exec={executor.context_window_tokens:3d}/{self.max_context_cap}t | Obs={observer.context_window_tokens:3d}/{self.max_context_cap}t | Total Evictions={cycle_snapshot['total_evictions']}")
            
            if cycle_evictions:
                for ev in cycle_evictions:
                    print(f"  >> EVICTION EVENT: [{ev['agent_id']}] Tokens: {ev['tokens_before']} -> {ev['tokens_after']} (-{ev['tokens_before'] - ev['tokens_after']}t, {ev['items_evicted']} item(s) evicted)")

            if verbose_inspect:
                print(f"  [Memory & Buffer Inspection]")
                print(f"    Coordinator: {coordinator.get_buffer_summary()} (Memory: {len(coordinator.working_memory)} entries)")
                print(f"    Executor:    {executor.get_buffer_summary()} (Memory: {len(executor.working_memory)} entries)")
                print(f"    Observer:    {observer.get_buffer_summary()} (Memory: {len(observer.working_memory)} entries)")

        # Render Terminal Eviction Curve & Trajectory
        self.render_eviction_curve()

    def render_eviction_curve(self):
        """Renders an ASCII eviction curve and summary table to stdout."""
        print(f"\n{'='*80}")
        print(f"=== CONTEXT LOAD & EVICTION TRAJECTORY CURVE ===")
        print(f"{'='*80}")
        print(f"{'Cycle':<7} | {'Coordinator':<18} | {'Executor':<18} | {'Observer':<18} | Evictions")
        print(f"{'-'*80}")
        
        for h in self.history:
            c = h["cycle"]
            c_bar = "#" * int(h["coordinator_tokens"] / 10)
            e_bar = "#" * int(h["executor_tokens"] / 10)
            o_bar = "#" * int(h["observer_tokens"] / 10)
            
            c_str = f"{h['coordinator_tokens']:3d}t [{c_bar:<10}]"
            e_str = f"{h['executor_tokens']:3d}t [{e_bar:<10}]"
            o_str = f"{h['observer_tokens']:3d}t [{o_bar:<10}]"
            
            print(f"C_{c:<4} | {c_str} | {e_str} | {o_str} | {h['total_evictions']}")

        print(f"{'='*80}")
        print(f"[SUMMARY] Total Cycles: {len(self.history)} | Context Cap: {self.max_context_cap} tokens | Total Eviction Triggers: {self.history[-1]['total_evictions']}")
        print(f"{'='*80}\n")


if __name__ == "__main__":
    cycles = 10
    if len(sys.argv) > 1:
        try:
            cycles = int(sys.argv[1])
        except ValueError:
            pass
    runtime = ManagedColdStartRuntime(max_context_cap=100)
    runtime.run_managed_simulation(cycles=cycles, verbose_inspect=True)
