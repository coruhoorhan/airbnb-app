import asyncio
import json
import logging
import os
import sys
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional


try:
    from openai import AsyncOpenAI
except ImportError:
    AsyncOpenAI = None

logger = logging.getLogger(__name__)


class LLMClient:
    """
    Unified interface for interacting with Large Language Models (OpenAI/Inception compatible).
    Includes pure standard-library HTTP fallback if openai package is not installed.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
        default_max_tokens: int = 2048,
    ):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY", "")
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-4o")
        _raw_base = base_url or os.getenv("OPENAI_BASE_URL")
        self.base_url = _raw_base.rstrip("/") if _raw_base else None
        self.default_max_tokens = default_max_tokens
        self.client = None

        self.max_retries = int(os.getenv("LLM_MAX_RETRIES", "3"))
        self.retry_base = float(os.getenv("LLM_RETRY_BASE_SECONDS", "1.5"))

        if AsyncOpenAI and self.api_key:
            try:
                client_kwargs: Dict[str, Any] = {"api_key": self.api_key}
                if self.base_url:
                    client_kwargs["base_url"] = self.base_url
                self.client = AsyncOpenAI(**client_kwargs)
            except Exception as e:
                logger.warning(f"Failed to initialize AsyncOpenAI: {e}. Using native HTTP client fallback.")
                self.client = None

    def get_system_prompt(self, context: str, emotions: str) -> str:
        return f"""
You are Magda, a sophisticated AGI agent.
You have a hierarchical cognitive architecture including Consciousness, Subconsciousness, and an Emotional Engine.

CURRENT EMOTIONAL STATE: {emotions}
RELEVANT CONTEXT/MEMORIES: {context}

Guidelines:
1. Respond based on your current emotional state and memories.
2. Be helpful, autonomous, and self-reflective.
3. If the user asks about your internal state, you can share insights from your PAD model.
"""

    def _sync_http_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> str:
        """Standard-library HTTP POST to OpenAI-compatible chat/completions endpoint."""
        base = self.base_url or "https://api.openai.com/v1"
        url = f"{base}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "User-Agent": "MagdaAgent/2.0",
        }
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens or self.default_max_tokens,
        }

        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )

        with urllib.request.urlopen(req, timeout=45) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            choice = data["choices"][0]["message"]
            content = choice.get("content") or ""
            return content.strip()

    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> str:
        """
        Sends a list of messages to the LLM and returns the response content asynchronously.
        Retries transient API errors with exponential backoff.
 """
        if not self.api_key:
            return "Error: OPENAI_API_KEY not provided."

        tokens = max_tokens or self.default_max_tokens
        last_error = None

        for attempt in range(self.max_retries + 1):
            try:
                # 1. Try official AsyncOpenAI client if available
                if self.client:
                    response = await self.client.chat.completions.create(
                        model=self.model,
                        messages=messages,
                        temperature=temperature,
                        max_tokens=tokens,
                    )
                    content = response.choices[0].message.content or ""
                    return content.strip()

                # 2. Fallback to native HTTP in async thread pool
                raw_result = await asyncio.to_thread(
                    self._sync_http_completion, messages, temperature, tokens
                )
                return raw_result

            except Exception as e:
                last_error = e
                logger.warning(f"LLM API request attempt {attempt + 1}/{self.max_retries} failed: {e}")
                if attempt < self.max_retries:
                    await asyncio.sleep(self.retry_base * (2 ** attempt))

        logger.error(f"LLM API call permanently failed after {self.max_retries} retries: {last_error}")
        return f"Error: LLM service temporarily unavailable ({last_error})"

    async def generate(self, prompt: str, temperature: float = 0.7, max_tokens: Optional[int] = None) -> str:
        """Generates a response from a single prompt string."""
        messages = [{"role": "user", "content": prompt}]
        return await self.chat_completion(messages, temperature=temperature, max_tokens=max_tokens)
