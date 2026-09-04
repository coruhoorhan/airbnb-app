import asyncio
import logging
from typing import Dict, Any, Optional
import httpx

logger = logging.getLogger(__name__)

class A2ADelegator:
    """
    A2A Delegator that handles peer-to-peer task delegation with automatic
    retries for transient network failures. Inspired by A2A Protocol trends.
    """

    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 10.0,
        timeout: float = 10.0
    ) -> None:
        """
        Initializes the A2ADelegator with retry parameters.

        Args:
            max_retries (int): Maximum number of retry attempts.
            base_delay (float): Initial delay before the first retry in seconds.
            max_delay (float): Maximum delay for backoff in seconds.
            timeout (float): Request timeout in seconds.
        """
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.timeout = timeout

    async def delegate_task(
        self,
        endpoint: str,
        payload: Dict[str, Any],
        headers: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Delegates a task to a peer agent asynchronously with exponential backoff retries.

        Args:
            endpoint (str): The URL endpoint of the peer agent.
            payload (Dict[str, Any]): The task payload to send.
            headers (Optional[Dict[str, str]]): Optional HTTP headers for the request.

        Returns:
            Dict[str, Any]: A dictionary containing the response from the peer.

        Raises:
            httpx.HTTPError: If the HTTP request fails after all retries.
        """
        headers = headers or {}
        attempt = 0

        while attempt <= self.max_retries:
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        endpoint,
                        json=payload,
                        headers=headers,
                        timeout=self.timeout
                    )
                    # Raise an exception for 4xx and 5xx status codes
                    response.raise_for_status()
                    return response.json()
            except (httpx.RequestError, httpx.HTTPStatusError) as e:
                # Determine if the error is transient
                is_transient = False

                if isinstance(e, httpx.RequestError):
                    # Network errors, timeouts, etc., are usually transient
                    is_transient = True
                elif isinstance(e, httpx.HTTPStatusError):
                    status = e.response.status_code
                    # 408 Request Timeout, 429 Too Many Requests
                    # 500 Internal Server Error, 502 Bad Gateway, 503 Service Unavailable, 504 Gateway Timeout
                    if status in {408, 429, 500, 502, 503, 504}:
                        is_transient = True

                if not is_transient or attempt >= self.max_retries:
                    logger.error(f"Failed to delegate task to {endpoint} after {attempt} retries: {e}")
                    raise

                attempt += 1
                delay = min(self.base_delay * (2 ** (attempt - 1)), self.max_delay)
                logger.warning(
                    f"Transient error delegating to {endpoint}: {e}. "
                    f"Retrying in {delay}s (Attempt {attempt}/{self.max_retries})"
                )
                await asyncio.sleep(delay)

        # Fallback raise (should not reach here ideally)
        raise httpx.RequestError("Maximum retries exceeded", request=httpx.Request("POST", endpoint))
