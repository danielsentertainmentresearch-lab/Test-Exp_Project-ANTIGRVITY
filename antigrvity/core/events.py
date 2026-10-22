"""Asynchronous Event Bus for multi-agent lifecycle events."""

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine, Dict, List, Optional
import fnmatch


@dataclass
class Event:
    """Represents a discrete event in the multi-agent framework."""
    topic: str
    sender: str
    payload: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    event_id: str = field(default_factory=lambda: f"evt_{int(time.time()*1000)}_{id(object())%10000:04d}")


EventHandler = Callable[[Event], Coroutine[Any, Any, None]]


class EventBus:
    """Central decoupled asynchronous event distributor."""

    def __init__(self, max_history: int = 1000):
        self._subscribers: Dict[str, List[EventHandler]] = {}
        self._history: List[Event] = []
        self._max_history = max_history
        self._lock = asyncio.Lock()

    def subscribe(self, topic_pattern: str, handler: EventHandler) -> None:
        """Subscribe a coroutine handler to a topic pattern (supports glob wildcards like 'agent.*')."""
        if topic_pattern not in self._subscribers:
            self._subscribers[topic_pattern] = []
        if handler not in self._subscribers[topic_pattern]:
            self._subscribers[topic_pattern].append(handler)

    def unsubscribe(self, topic_pattern: str, handler: EventHandler) -> None:
        """Unsubscribe a coroutine handler."""
        if topic_pattern in self._subscribers and handler in self._subscribers[topic_pattern]:
            self._subscribers[topic_pattern].remove(handler)
            if not self._subscribers[topic_pattern]:
                del self._subscribers[topic_pattern]

    async def publish(self, topic: str, sender: str, payload: Optional[Dict[str, Any]] = None) -> Event:
        """Publish an event to all matching pattern subscribers."""
        event = Event(topic=topic, sender=sender, payload=payload or {})
        async with self._lock:
            self._history.append(event)
            if len(self._history) > self._max_history:
                self._history.pop(0)

        # Collect matching handlers
        handlers_to_call: List[EventHandler] = []
        for pattern, handlers in list(self._subscribers.items()):
            if fnmatch.fnmatch(topic, pattern):
                handlers_to_call.extend(handlers)

        # Dispatch handlers concurrently with exception isolation
        if handlers_to_call:
            tasks = [asyncio.create_task(self._safe_invoke(h, event)) for h in handlers_to_call]
            await asyncio.gather(*tasks, return_exceptions=True)

        return event

    async def _safe_invoke(self, handler: EventHandler, event: Event) -> None:
        try:
            await handler(event)
        except Exception as exc:
            # Prevent subscriber errors from bubbling up to the publisher
            import logging
            logging.getLogger("antigrvity.events").error(
                f"Error in event handler {handler} for {event.topic}: {exc}", exc_info=True
            )

    async def wait_for(self, topic: str, timeout: Optional[float] = None) -> Event:
        """Wait until a specific topic is published, or timeout."""
        future = asyncio.get_running_loop().create_future()

        async def _capture(evt: Event):
            if not future.done():
                future.set_result(evt)

        self.subscribe(topic, _capture)
        try:
            return await asyncio.wait_for(future, timeout=timeout)
        finally:
            self.unsubscribe(topic, _capture)

    def get_history(self, topic_pattern: Optional[str] = None) -> List[Event]:
        """Retrieve historical events, optionally filtered by pattern."""
        if not topic_pattern:
            return list(self._history)
        return [e for e in self._history if fnmatch.fnmatch(e.topic, topic_pattern)]
