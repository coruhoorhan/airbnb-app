import asyncio
import logging
from typing import Dict, Any, List, Optional
import httpx

from magda_agent.integration.a2a_discovery_v3_unique import A2ADiscoveryServiceV3Unique

logger = logging.getLogger(__name__)

class A2AStatusReconciliationWorker:
    """
    An asynchronous background worker that uses A2ADiscoveryServiceV3Unique
    to query known active peer agents and reconcile the local delegator task status
    with peer remote states, handling orphaned tasks.
    """

    def __init__(
        self,
        discovery_service: Optional[A2ADiscoveryServiceV3Unique] = None,
        poll_interval: float = 60.0,
        timeout: float = 10.0
    ):
        """
        Initializes the A2AStatusReconciliationWorker.

        Args:
            discovery_service: Instance of A2ADiscoveryServiceV3Unique.
            poll_interval: Interval in seconds between reconciliation passes.
            timeout: HTTP request timeout in seconds.
        """
        self.discovery_service = discovery_service or A2ADiscoveryServiceV3Unique()
        self.poll_interval = poll_interval
        self.timeout = timeout
        self._running = False
        self._task = None
        # Format: { "task_id": {"peer_id": "...", "status": "pending", "payload": {...}} }
        self.local_tasks: Dict[str, Dict[str, Any]] = {}

    def add_task(self, task_id: str, peer_id: str, payload: Dict[str, Any]) -> None:
        """
        Registers a task to be tracked by the reconciliation worker.
        """
        self.local_tasks[task_id] = {
            "peer_id": peer_id,
            "status": "pending",
            "payload": payload,
            "retry_count": 0
        }
        logger.info(f"Task {task_id} added to reconciliation worker for peer {peer_id}.")

    async def start(self) -> None:
        """
        Starts the background reconciliation loop.
        """
        if not self._running:
            self._running = True
            self._task = asyncio.create_task(self._reconciliation_loop())
            logger.info("A2AStatusReconciliationWorker started.")

    async def stop(self) -> None:
        """
        Stops the background reconciliation loop.
        """
        if self._running:
            self._running = False
            if self._task:
                self._task.cancel()
                try:
                    await self._task
                except asyncio.CancelledError:
                    pass
            logger.info("A2AStatusReconciliationWorker stopped.")

    async def _reconciliation_loop(self) -> None:
        """
        The main loop that periodically queries peer agents for task statuses.
        """
        while self._running:
            try:
                await self.reconcile_tasks()
            except Exception as e:
                logger.error(f"Error during A2A status reconciliation: {e}")

            await asyncio.sleep(self.poll_interval)

    async def reconcile_tasks(self) -> None:
        """
        Iterates through active tasks, queries peer agents for their remote status,
        and updates local state or handles orphaned tasks.
        """
        # Create a snapshot of tasks to reconcile
        tasks_to_check = {
            tid: info for tid, info in self.local_tasks.items()
            if info["status"] in ("pending", "processing")
        }

        if not tasks_to_check:
            return

        for task_id, task_info in tasks_to_check.items():
            peer_id = task_info["peer_id"]
            agent_card = self.discovery_service.get_agent_card(peer_id)

            if not agent_card:
                logger.warning(f"Peer {peer_id} not found for task {task_id}. Marking as orphaned.")
                self._handle_orphaned_task(task_id)
                continue

            rpc_endpoint = agent_card.endpoints.get("rpc")
            if not rpc_endpoint:
                logger.warning(f"Peer {peer_id} has no RPC endpoint. Marking task {task_id} as orphaned.")
                self._handle_orphaned_task(task_id)
                continue

            status_endpoint = f"{rpc_endpoint}/status/{task_id}"

            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get(status_endpoint, timeout=self.timeout)

                    if response.status_code == 404:
                        logger.warning(f"Task {task_id} not found on peer {peer_id}. Marking as orphaned.")
                        self._handle_orphaned_task(task_id)
                        continue

                    response.raise_for_status()
                    data = response.json()

                    remote_status = data.get("status")
                    if remote_status:
                        self._update_task_status(task_id, remote_status)
            except httpx.RequestError as e:
                logger.warning(f"Network error querying task {task_id} from {peer_id}: {e}")
                self._handle_network_failure(task_id)
            except httpx.HTTPStatusError as e:
                logger.warning(f"HTTP error {e.response.status_code} querying task {task_id} from {peer_id}")
                self._handle_network_failure(task_id)

    def _update_task_status(self, task_id: str, new_status: str) -> None:
        """
        Updates the status of a tracked task.
        """
        if task_id in self.local_tasks:
            old_status = self.local_tasks[task_id]["status"]
            if old_status != new_status:
                self.local_tasks[task_id]["status"] = new_status
                logger.info(f"Task {task_id} status updated: {old_status} -> {new_status}")

    def _handle_orphaned_task(self, task_id: str) -> None:
        """
        Handles a task that is deemed orphaned (e.g., peer agent disappeared or lost the task).
        Currently marks it as failed/orphaned. In a robust system, this might trigger a re-queue.
        """
        if task_id in self.local_tasks:
            self.local_tasks[task_id]["status"] = "orphaned"
            logger.info(f"Task {task_id} has been marked as orphaned and requires re-queuing.")

    def _handle_network_failure(self, task_id: str) -> None:
        """
        Handles transient network failures when querying a task status.
        Increments retry count and marks as orphaned if it exceeds a threshold.
        """
        if task_id in self.local_tasks:
            self.local_tasks[task_id]["retry_count"] += 1
            if self.local_tasks[task_id]["retry_count"] >= 3:
                logger.warning(f"Task {task_id} exceeded max retries for status check. Marking as orphaned.")
                self._handle_orphaned_task(task_id)
