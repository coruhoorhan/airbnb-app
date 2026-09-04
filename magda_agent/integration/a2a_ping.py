"""
A2A Task Status Ping

Inspired by the A2A Enterprise-ready trend, this module implements a status
ping mechanism that allows Magda to check the progress of a delegated sub-task
asynchronously over A2A without blocking.
"""

import httpx
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

class A2APingError(Exception):
    """Base exception for A2A ping errors."""
    pass

class A2APingClient:
    """
    Client for checking the progress of delegated sub-tasks asynchronously via A2A.
    """
    def __init__(self, timeout: float = 5.0):
        """
        Initializes the A2A ping client.

        Args:
            timeout (float): The timeout for the HTTP request in seconds.
        """
        self.timeout = timeout

    async def ping_task_status(self, endpoint_url: str, task_id: str) -> Dict[str, Any]:
        """
        Pings a peer agent to check the status of a specific delegated task.

        Args:
            endpoint_url (str): The HTTP(S) base URL of the remote agent.
            task_id (str): The ID of the delegated task.

        Returns:
            Dict[str, Any]: A dictionary containing the status of the task.

        Raises:
            A2APingError: If the remote agent is unreachable or returns an error.
        """
        url = f"{endpoint_url.rstrip('/')}/a2a/tasks/{task_id}/status"
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url)
                response.raise_for_status()
                data = response.json()
                logger.debug(f"Received status for task {task_id}: {data}")
                return data
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error occurred while pinging task {task_id}: {e}")
            raise A2APingError(f"Failed to ping task {task_id}: HTTP {e.response.status_code}") from e
        except httpx.RequestError as e:
            logger.error(f"Request error occurred while pinging task {task_id}: {e}")
            raise A2APingError(f"Network error while pinging task {task_id}") from e
        except Exception as e:
            logger.error(f"Unexpected error while pinging task {task_id}: {e}")
            raise A2APingError(f"Unexpected error while pinging task {task_id}") from e
