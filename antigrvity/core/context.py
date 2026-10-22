"""Shared Blackboard context system for multi-agent state synchronization."""

import asyncio
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional


@dataclass
class BlackboardEntry:
    """Entry stored within the shared blackboard."""
    key: str
    value: Any
    version: int = 1
    updated_at: float = field(default_factory=time.time)
    updated_by: str = "system"
    ttl_sec: Optional[float] = None

    @property
    def is_expired(self) -> bool:
        if self.ttl_sec is None:
            return False
        return (time.time() - self.updated_at) > self.ttl_sec


class Blackboard:
    """Thread-safe asynchronous shared memory blackboard for agent coordination."""

    def __init__(self):
        self._entries: Dict[str, BlackboardEntry] = {}
        self._lock = asyncio.Lock()
        self._listeners: Dict[str, List[Callable[[str, Any], None]]] = {}

    async def get(self, key: str, default: Any = None) -> Any:
        """Retrieve a value by key. Returns default if missing or expired."""
        async with self._lock:
            entry = self._entries.get(key)
            if entry is None or entry.is_expired:
                if entry and entry.is_expired:
                    del self._entries[key]
                return default
            return entry.value

    async def get_entry(self, key: str) -> Optional[BlackboardEntry]:
        """Retrieve the raw BlackboardEntry including metadata."""
        async with self._lock:
            entry = self._entries.get(key)
            if entry and entry.is_expired:
                del self._entries[key]
                return None
            return entry

    async def set(self, key: str, value: Any, agent_id: str = "system", ttl_sec: Optional[float] = None) -> BlackboardEntry:
        """Set or update a key in the blackboard."""
        async with self._lock:
            current = self._entries.get(key)
            new_version = (current.version + 1) if current else 1
            entry = BlackboardEntry(
                key=key,
                value=value,
                version=new_version,
                updated_at=time.time(),
                updated_by=agent_id,
                ttl_sec=ttl_sec,
            )
            self._entries[key] = entry

        # Trigger listeners outside lock
        if key in self._listeners:
            for cb in self._listeners[key]:
                try:
                    cb(key, value)
                except Exception:
                    pass

        return entry

    async def delete(self, key: str) -> bool:
        """Delete a key from the blackboard."""
        async with self._lock:
            if key in self._entries:
                del self._entries[key]
                return True
            return False

    async def list_keys(self, prefix: Optional[str] = None) -> List[str]:
        """List all active keys, optionally filtered by prefix."""
        async with self._lock:
            now = time.time()
            valid_keys = []
            expired_keys = []
            for k, entry in self._entries.items():
                if entry.ttl_sec and (now - entry.updated_at) > entry.ttl_sec:
                    expired_keys.append(k)
                elif prefix is None or k.startswith(prefix):
                    valid_keys.append(k)
            for k in expired_keys:
                del self._entries[k]
            return sorted(valid_keys)

    async def to_dict(self) -> Dict[str, Any]:
        """Export all active entries as a serializable dictionary."""
        async with self._lock:
            res = {}
            for k, entry in list(self._entries.items()):
                if not entry.is_expired:
                    res[k] = {
                        "value": entry.value,
                        "version": entry.version,
                        "updated_at": entry.updated_at,
                        "updated_by": entry.updated_by,
                    }
            return res

    async def save_checkpoint(self, path: Path) -> None:
        """Save a snapshot of the blackboard to a JSON file."""
        data = await self.to_dict()
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    async def load_checkpoint(self, path: Path) -> None:
        """Load state from a JSON checkpoint."""
        if not path.exists():
            return
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        async with self._lock:
            for k, item in data.items():
                self._entries[k] = BlackboardEntry(
                    key=k,
                    value=item.get("value"),
                    version=item.get("version", 1),
                    updated_at=item.get("updated_at", time.time()),
                    updated_by=item.get("updated_by", "checkpoint"),
                )
