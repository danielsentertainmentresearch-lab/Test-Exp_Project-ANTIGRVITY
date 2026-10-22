import time
import json
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

    def ingest_stimulus(self, sender: str, payload: Dict[str, Any]) -> Dict[str, Any]:
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
        self.apply_eviction_policy()
        
        return entry

    def generate_response(self, action: str, output_data: Dict[str, Any]) -> Dict[str, Any]:
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
        self.apply_eviction_policy()
        
        return response_payload


class ManagedColdStartRuntime:
    """
    Orchestrates the deployment of models starting from technical zero context load
    with active context window eviction policies.
    """
    def __init__(self, max_context_cap: int = 100):
        self.max_context_cap = max_context_cap
        self.agents: Dict[str, ZeroContextAgentWithEviction] = {}

    def deploy_agent_cold_start(self, agent_id: str, role: str, system_directive: str) -> ZeroContextAgentWithEviction:
        agent = ZeroContextAgentWithEviction(agent_id, role, system_directive, max_context_tokens=self.max_context_cap)
        self.agents[agent_id] = agent
        return agent

    def run_managed_simulation(self, cycles: int = 10):
        print(f"=== RUNNING MANAGED COLD-START SIMULATION ({cycles} Cycles | Cap: {self.max_context_cap} Tokens) ===\n")
        
        coordinator = self.deploy_agent_cold_start("Coordinator_Zero", "Orchestrator", "Coordinate multi-agent workflows.")
        executor = self.deploy_agent_cold_start("Executor_Zero", "Execution_Node", "Execute dApp verification actions.")
        observer = self.deploy_agent_cold_start("Observer_Zero", "Fine_Tuning_Observer", "Observe drift and evaluate real-time tuning.")

        print(f"{'Cycle':<8} | {'Coordinator':<15} | {'Executor':<15} | {'Observer':<15} | {'Total Evictions'}")
        print("-" * 75)

        for c in range(1, cycles + 1):
            # Coordinator dispatch
            coord_resp = coordinator.generate_response("DISPATCH", {"task": f"TASK_{c}", "cycle": c})
            
            # Executor ingest and output
            executor.ingest_stimulus(coordinator.agent_id, coord_resp)
            exec_resp = executor.generate_response("EXECUTE", {"status": "SUCCESS", "cycle": c})
            
            # Observer ingest and output
            observer.ingest_stimulus(executor.agent_id, exec_resp)
            obs_resp = observer.generate_response("FINE_TUNE", {"drift": False, "cycle": c})
            
            total_evictions = sum(len(a.eviction_logs) for a in self.agents.values())
            print(f"Cycle {c:<3} | {coordinator.context_window_tokens:<15} | {executor.context_window_tokens:<15} | {observer.context_window_tokens:<15} | {total_evictions}")


if __name__ == "__main__":
    runtime = ManagedColdStartRuntime(max_context_cap=100)
    runtime.run_managed_simulation(cycles=10)
