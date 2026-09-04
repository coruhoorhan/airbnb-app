import asyncio
import logging
from typing import List, Optional

from magda_agent.integration.a2a_cards import A2ADiscoveryMeshV4

class A2ACapabilityGossipV5:
    """
    Implements a continuous gossiping background thread that dynamically syncs AgentCards
    within a localized peer mesh.
    """

    def __init__(self, mesh: A2ADiscoveryMeshV4, peer_urls: List[str], interval_seconds: float = 60.0) -> None:
        """
        Initializes the gossip protocol manager.

        Args:
            mesh: The A2ADiscoveryMeshV4 instance used to perform the gossip.
            peer_urls: A list of peer endpoint URLs to broadcast gossip to.
            interval_seconds: The frequency in seconds at which the background task should run.
        """
        self.mesh = mesh
        self.peer_urls = peer_urls
        self.interval_seconds = interval_seconds
        self._task: Optional[asyncio.Task] = None
        self._stop_event = asyncio.Event()

    async def _gossip_loop(self) -> None:
        """
        The background loop that periodically broadcasts gossip.
        """
        logging.info(f"A2ACapabilityGossipV5 background thread started, interval: {self.interval_seconds}s")
        while not self._stop_event.is_set():
            try:
                await self.mesh.broadcast_gossip(self.peer_urls)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logging.error(f"Error during A2ACapabilityGossipV5 broadcast: {e}")

            try:
                # Use wait_for on the event to allow responsive shutdown
                await asyncio.wait_for(self._stop_event.wait(), timeout=self.interval_seconds)
            except asyncio.TimeoutError:
                pass  # Timeout means the event wasn't set, so we continue the loop

        logging.info("A2ACapabilityGossipV5 background thread stopped")

    def start(self) -> None:
        """
        Starts the continuous gossiping background thread.
        """
        if self._task is not None and not self._task.done():
            logging.warning("A2ACapabilityGossipV5 background thread is already running.")
            return

        self._stop_event.clear()
        self._task = asyncio.create_task(self._gossip_loop())

    async def stop(self) -> None:
        """
        Stops the continuous gossiping background thread gracefully.
        """
        if self._task is None or self._task.done():
            return

        self._stop_event.set()
        await self._task
        self._task = None
