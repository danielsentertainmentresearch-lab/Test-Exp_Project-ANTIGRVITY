"""Transport mechanisms for MCP communication."""

import asyncio
import sys
from abc import ABC, abstractmethod
from typing import Optional


class BaseTransport(ABC):
    """Abstract bidirectional MCP transport."""

    @abstractmethod
    async def send(self, message: str) -> None:
        """Send a message across the transport."""
        pass

    @abstractmethod
    async def receive(self) -> Optional[str]:
        """Receive the next message, or None if transport closed."""
        pass

    @abstractmethod
    async def close(self) -> None:
        """Close the transport cleanly."""
        pass


class InProcessTransport(BaseTransport):
    """Direct in-memory queue transport between client and server components."""

    def __init__(self, incoming: Optional[asyncio.Queue] = None, outgoing: Optional[asyncio.Queue] = None):
        self._incoming = incoming or asyncio.Queue()
        self._outgoing = outgoing or asyncio.Queue()
        self._closed = False

    def create_pair(self) -> "InProcessTransport":
        """Create the connected peer endpoint of this transport."""
        return InProcessTransport(incoming=self._outgoing, outgoing=self._incoming)

    async def send(self, message: str) -> None:
        if self._closed:
            raise ConnectionError("Transport is closed")
        await self._outgoing.put(message)

    async def receive(self) -> Optional[str]:
        if self._closed:
            return None
        return await self._incoming.get()

    async def close(self) -> None:
        self._closed = True


class StdioTransport(BaseTransport):
    """Standard IO transport reading and writing line-delimited JSON-RPC messages."""

    def __init__(self):
        self._closed = False
        self._loop = asyncio.get_event_loop()

    async def send(self, message: str) -> None:
        if self._closed:
            raise ConnectionError("Stdio transport closed")
        # Ensure single line and immediate flush
        line = message.strip() + "\n"
        sys.stdout.write(line)
        sys.stdout.flush()

    async def receive(self) -> Optional[str]:
        if self._closed:
            return None
        line = await self._loop.run_in_executor(None, sys.stdin.readline)
        if not line:
            self._closed = True
            return None
        return line.strip()

    async def close(self) -> None:
        self._closed = True
