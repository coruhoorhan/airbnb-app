import logging
import re
from typing import Optional, List, Dict, Any
from magda_agent.llm_client import LLMClient

class SubagentContextCompressorV3:
    """
    SubagentContextCompressorV3 implements smart context, payload, and message
    compression logic specifically designed for spawned subagents.
    It optimizes token usage based on task relevance while strictly preserving
    critical rules, constraints, and instructions.
    """

    def __init__(self, llm: LLMClient) -> None:
        """
        Initializes the SubagentContextCompressorV3.

        Args:
            llm: Language Model client to be used for summarization.
        """
        self.llm = llm

    def _extract_critical_constraints(self, text: str) -> List[str]:
        """
        Extracts sentences or lines that contain high-priority constraint keywords
        to guarantee they are not lost during compression.
        """
        keywords = [
            "must", "never", "strict", "required", "limit", "critical",
            "mandatory", "rule", "goal", "constraint", "shall", "always"
        ]
        pattern = re.compile(r"\b(" + "|".join(keywords) + r")\b", re.IGNORECASE)

        constraints: List[str] = []
        # Split by newline and process each line
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        for line in lines:
            if pattern.search(line):
                constraints.append(line)
        return list(dict.fromkeys(constraints))  # Deduplicate while preserving order

    async def compress_context(self, context: str, task: str, max_length: int = 2000) -> str:
        """
        Selectively compresses context based on task relevance, retaining critical constraints.

        Args:
            context: The raw context string to compress.
            task: The subagent task description.
            max_length: The maximum allowed length of the context. Triggers compression if exceeded.

        Returns:
            The compressed context string.
        """
        if len(context) <= max_length:
            logging.info("Context length is within limits. Skipping compression.")
            return context

        logging.info(f"Context length ({len(context)}) exceeds max_length ({max_length}). Compressing using V3 smart logic.")

        # Extract critical constraints as validation fallback
        constraints = self._extract_critical_constraints(context)

        # Build task-relevance directives
        task_words = [w.strip(",.?!()\"'") for w in task.split() if len(w) > 4]
        task_words_str = ", ".join(list(set(task_words))[:10])

        prompt = (
            f"You are an advanced AGI context compression engine optimizing token limits for a spawned subagent.\n"
            f"Your goal is to compress the parent context below so that it fits budget, "
            f"preserving ONLY information relevant to the subagent's assigned task, while "
            f"STRICTLY retaining all critical instructions, constraints, and rules.\n\n"
            f"--- ASSIGNED SUBAGENT TASK ---\n"
            f"{task}\n\n"
            f"--- THEMATIC FOCUS WORDS ---\n"
            f"{task_words_str}\n\n"
            f"--- PARENT CONTEXT TO COMPRESS ---\n"
            f"{context}\n\n"
            f"Instructions:\n"
            f"1. Retain all key constraints, rules, limits, and safety rules from the Parent Context.\n"
            f"2. Summarize or remove parts of the Parent Context irrelevant or secondary to the Assigned Subagent Task.\n"
            f"3. Do not lose critical formatting, identifiers, or keys needed to execute the task.\n"
            f"4. Output only the condensed, optimized context (no introductory text, e.g. 'Here is the summary...')."
        )

        messages = [
            {"role": "system", "content": "You are a specialized token compression system focusing on task-relevance and constraint safety."},
            {"role": "user", "content": prompt}
        ]

        try:
            compressed = await self.llm.chat_completion(messages, temperature=0.2)
            compressed_str = compressed.strip()

            if not compressed_str:
                return context[:max_length]

            # Verify and re-inject any missing critical constraints
            missing_constraints = []
            for const in constraints:
                const_clean = re.sub(r"\s+", " ", const.lower()).strip()
                compressed_clean = re.sub(r"\s+", " ", compressed_str.lower()).strip()
                if const_clean not in compressed_clean:
                    missing_constraints.append(const)

            if missing_constraints:
                logging.info(f"Re-injecting {len(missing_constraints)} missing critical constraints in V3.")
                constraint_header = "\n\n--- PRESERVED CRITICAL CONSTRAINTS ---\n" + "\n".join(f"- {c}" for c in missing_constraints)
                compressed_str += constraint_header

            return compressed_str
        except Exception as e:
            logging.error(f"Failed to compress context dynamically in V3: {e}")
            return context[:max_length]

    async def compress_payload(self, payload: Dict[str, Any], max_length: int = 2000) -> Dict[str, Any]:
        """
        Selectively compresses context and/or messages inside payload, retaining critical constraints.

        Args:
            payload: The dictionary representing the RPC dispatch payload.
            max_length: The maximum allowed length of the context. Triggers compression if exceeded.

        Returns:
            The optimized payload dictionary.
        """
        # Shallow copy to avoid mutating inputs
        result_payload = dict(payload)
        context = result_payload.get("context", "")
        task = result_payload.get("task", "")

        if context:
            compressed_context = await self.compress_context(context, task, max_length=max_length)
            result_payload["context"] = compressed_context

        # If payload has a list of messages, compress them as well if needed
        messages = result_payload.get("messages")
        if isinstance(messages, list):
            compressed_messages = await self.compress_messages(messages, task)
            result_payload["messages"] = compressed_messages

        return result_payload

    async def compress_messages(self, messages: List[Dict[str, Any]], task: str, max_messages: int = 5) -> List[Dict[str, Any]]:
        """
        Compresses a list of messages by summarizing older messages and keeping the recent ones.
        """
        if len(messages) <= max_messages:
            return messages

        logging.info(f"Compressing message history from {len(messages)} items to {max_messages} in V3.")

        system_messages = [msg for msg in messages if msg.get("role") == "system"]
        user_assistant_messages = [msg for msg in messages if msg.get("role") != "system"]

        if len(user_assistant_messages) <= max_messages:
            return messages

        to_compress = user_assistant_messages[:-max_messages]
        retained = user_assistant_messages[-max_messages:]

        history_text = "\n".join([f"{msg.get('role', 'user')}: {msg.get('content', '')}" for msg in to_compress])

        prompt = (
            f"The following is conversational history for a subagent.\n"
            f"Please compress and summarize this history into a single concise summary paragraph, "
            f"focusing on details, preferences, or technical guidelines relevant to the subagent task.\n\n"
            f"--- SUBAGENT TASK ---\n"
            f"{task}\n\n"
            f"--- HISTORICAL CONVERSATION TO SUMMARIZE ---\n"
            f"{history_text}"
        )

        compress_msgs = [
            {"role": "system", "content": "You are a context compression assistant. Concisely summarize old message history relevant to the current task."},
            {"role": "user", "content": prompt}
        ]

        try:
            summary = await self.llm.chat_completion(compress_msgs, temperature=0.2)
            summary_str = summary.strip()

            summary_message = {
                "role": "system",
                "content": f"[SYSTEM: Compressed Summary of Old History: {summary_str}]"
            }

            return system_messages + [summary_message] + retained
        except Exception as e:
            logging.error(f"Failed to compress message history in V3: {e}")
            return system_messages + retained
