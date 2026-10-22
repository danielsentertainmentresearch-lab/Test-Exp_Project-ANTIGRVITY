---
name: cold-start-orchestrator
description: Bootstraps the ANTIGRVITY multi-agent swarm from a cold state, runs 5-phase health checks, resolves agent quorum, and prepares execution pipelines.
---

# Cold-Start Orchestrator Skill

This skill provides step-by-step procedures to trigger and monitor the multi-agent cold-start orchestration sequence.

## When to Use
- When initiating a new multi-agent session or after a clean reboot.
- When an agent within the swarm becomes unresponsive and a state-resync is required.
- To verify that all critical roles (Lead Orchestrator, Reviewer, Bridge Agent) have achieved quorum.

## Procedures

### 1. Triggering Full Cold-Start via CLI
Run the following command from the workspace root:
```sh
python -m antigrvity.cli coldstart --config config/coldstart.json
```

### 2. Programmatic Python Execution
```python
import asyncio
from antigrvity.orchestration.coldstart import ColdStartEngine

async def bootstrap():
    engine = ColdStartEngine.from_config("config/coldstart.json")
    result = await engine.execute_bootstrap()
    if result.is_successful:
        print("Cold-start sequence complete. Ready for task intake.")
    else:
        print(f"Cold-start degraded: {result.error_summary}")

if __name__ == "__main__":
    asyncio.run(bootstrap())
```

### 3. Verifying Health Status
Check swarm and blackboard status:
```sh
python -m antigrvity.cli status --json
```
