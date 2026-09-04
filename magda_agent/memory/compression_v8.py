import logging
from typing import List, Optional, Any

from magda_agent.memory.working import MemoryEntry

class ClaudeContextCompressorV8:
    """
    Claude SDK inspired context compressor V8.
    Explicitly summarizes and dynamically trims out older token windows
    using a recursive shrinking mechanism for long chunks.
    """

    def __init__(self, llm_client: Optional[Any] = None) -> None:
        """
        Initializes the V8 context compressor.

        Args:
            llm_client: Optional LLM client to use for smart summarization.
        """
        self.llm = llm_client

    async def compress_entries(self, entries: List[MemoryEntry], token_limit: int = 2000) -> MemoryEntry:
        """
        Compresses a list of memory entries into a single entry to fit within limits.
        If the combined text exceeds the limit, it recursively shrinks the chunks
        starting from the oldest tokens until the limit is respected.

        Args:
            entries: A list of MemoryEntry objects to compress.
            token_limit: The maximum allowed tokens for the combined text.

        Returns:
            A new MemoryEntry object representing the compressed content and context.
        """
        if not entries:
            raise ValueError("No entries to compress")

        user_id = entries[0].user_id

        # Calculate average importance and gather unique tags
        avg_importance = sum(e.importance for e in entries) / len(entries)

        all_tags = set()
        for e in entries:
            if e.tags:
                all_tags.update(e.tags)

        # 1. Base Working Memory Content
        # Format the combined text
        texts = [e.content for e in entries]

        char_limit = token_limit * 4

        # Recursive reduction function
        async def _recursive_shrink(current_texts: List[str]) -> str:
            combined = "\n".join(current_texts)
            if len(combined) <= char_limit:
                return combined

            if len(current_texts) == 1:
                # If only one entry left and it's too big, try summarizing it
                if self.llm:
                    try:
                        logging.info(f"Compressing large single chunk exceeding {token_limit} tokens.")
                        prompt = (
                            f"You are a memory context compressor. Output only the summarized text. "
                            f"Summarize the following memory context, maintaining key facts and semantic relationships "
                            f"within {token_limit} tokens.\n\n{current_texts[0]}"
                        )
                        compressed = await self.llm.generate(prompt, temperature=0.2)
                        return compressed.strip()
                    except Exception as e:
                        logging.error(f"Compression failed: {e}")

                # Truncation fallback
                return current_texts[0][:char_limit] + "... [TRUNCATED]"

            # More than one entry: summarize the oldest two entries together
            oldest_1 = current_texts[0]
            oldest_2 = current_texts[1]
            combined_oldest = f"{oldest_1}\n{oldest_2}"

            if self.llm:
                try:
                    logging.info("Compressing oldest memory entries to shrink context.")
                    prompt = (
                        f"You are a memory context compressor. Output only the summarized text. "
                        f"Summarize the following memory context, maintaining key facts and semantic relationships.\n\n{combined_oldest}"
                    )
                    compressed_oldest = await self.llm.generate(prompt, temperature=0.2)
                    compressed_oldest = compressed_oldest.strip()
                except Exception as e:
                    logging.error(f"Compression failed: {e}")
                    # Simple truncation fallback
                    compressed_oldest = combined_oldest[:char_limit // 2] + "... [TRUNCATED]"
            else:
                # Simple truncation fallback
                compressed_oldest = combined_oldest[:char_limit // 2] + "... [TRUNCATED]"

            # Replace the first two entries with the summarized version
            new_texts = [compressed_oldest] + current_texts[2:]

            # Recurse
            return await _recursive_shrink(new_texts)

        # 3. Compress using LLM recursively
        compressed_text = await _recursive_shrink(texts)

        return MemoryEntry(
            content=compressed_text,
            importance=avg_importance,
            emotional_state=entries[0].emotional_state,
            tags=list(all_tags),
            user_id=user_id
        )
