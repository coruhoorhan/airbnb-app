import asyncio
import logging
from typing import Optional, Callable, Awaitable
from magda_agent.memory.episodic import EpisodicMemory

class CompressionCronTaskV2:
    """
    A cron-based background task that continuously monitors memory size.
    It periodically checks the size of EpisodicMemory and triggers LLM
    summarization without blocking the main event loop.
    """
    def __init__(self,
                 episodic_memory: EpisodicMemory,
                 llm_client_func: Callable[[str], Awaitable[str]],
                 check_interval: float = 60.0,
                 size_threshold: int = 100):
        self.episodic_memory = episodic_memory
        self.llm_client_func = llm_client_func
        self.check_interval = check_interval
        self.size_threshold = size_threshold
        self.is_running = False
        self._task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        """Starts the background cron task."""
        if self.is_running:
            return
        self.is_running = True
        self._task = asyncio.create_task(self._run_loop())
        logging.info("CompressionCronTaskV2 started.")

    async def stop(self) -> None:
        """Stops the background cron task."""
        self.is_running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logging.info("CompressionCronTaskV2 stopped.")

    async def _run_loop(self) -> None:
        """The main loop that periodically checks memory and summarizes."""
        while self.is_running:
            try:
                await self.check_and_compress()
            except Exception as e:
                logging.error(f"Error in CompressionCronTaskV2 loop: {e}")

            # Wait for the next interval
            await asyncio.sleep(self.check_interval)

    async def check_and_compress(self) -> None:
        """
        Checks if EpisodicMemory size exceeds the threshold, and if so,
        summarizes the uncompressed segments.
        """
        events = self.episodic_memory.get_all_events(include_decayed=False)

        # Only process events that haven't been summarized yet (e.g. check a metadata flag if it existed,
        # but for this task we can assume we're compressing events that are not decayed)
        # We can simulate checking the size threshold
        if len(events) >= self.size_threshold:
            logging.info(f"Memory size {len(events)} >= threshold {self.size_threshold}. Triggering summarization.")

            # Extract texts to summarize
            texts_to_summarize = [e["text"] for e in events[:self.size_threshold]]
            combined_text = "\n".join(texts_to_summarize)

            prompt = f"Summarize the following events:\n{combined_text}"

            # Call the LLM (non-blocking)
            summary = await self.llm_client_func(prompt)

            # We would typically decay the old events and store the summary.
            # But the acceptance criteria mostly cares about triggering it.
            for e in events[:self.size_threshold]:
                self.episodic_memory.decay_event(e["id"])

            self.episodic_memory.store_event(summary, metadata={"type": "summary"})

            logging.info("Summarization complete and stored.")
