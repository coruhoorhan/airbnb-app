import logging
import copy
from typing import Dict, Any, Optional

class VirtualContextEngineExtension:
    """
    Extensions to Context Engine to support virtual context isolation across multiple subagents.
    Provides sandboxing for working memory spaces during parallel task execution.
    """

    def __init__(self) -> None:
        self.sandboxed_contexts: Dict[str, Dict[str, Any]] = {}
        logging.info("Initialized VirtualContextEngineExtension")

    def create_sandbox(self, subagent_id: str, base_context: Optional[Dict[str, Any]] = None) -> None:
        """
        Creates an isolated virtual context for a subagent.

        Args:
            subagent_id: The ID of the subagent to create a sandbox for.
            base_context: Optional initial context to start with.
        """
        if subagent_id in self.sandboxed_contexts:
            logging.warning(f"Sandbox for {subagent_id} already exists.")
            return

        self.sandboxed_contexts[subagent_id] = copy.deepcopy(base_context) if base_context else {}
        logging.info(f"Created isolated context for subagent: {subagent_id}")

    def update_sandbox(self, subagent_id: str, key: str, value: Any) -> None:
        """
        Updates the virtual context for a given subagent.

        Args:
            subagent_id: The ID of the subagent.
            key: The context key to update.
            value: The new value.

        Raises:
            ValueError: If the sandbox does not exist.
        """
        if subagent_id not in self.sandboxed_contexts:
            raise ValueError(f"Sandbox not found for subagent: {subagent_id}")

        self.sandboxed_contexts[subagent_id][key] = value
        logging.debug(f"Updated context for {subagent_id}: {key} = {value}")

    def get_sandbox(self, subagent_id: str) -> Dict[str, Any]:
        """
        Retrieves the virtual context for a given subagent.

        Args:
            subagent_id: The ID of the subagent.

        Returns:
            A deep copy of the subagent's virtual context.

        Raises:
            ValueError: If the sandbox does not exist.
        """
        if subagent_id not in self.sandboxed_contexts:
            raise ValueError(f"Sandbox not found for subagent: {subagent_id}")

        return copy.deepcopy(self.sandboxed_contexts[subagent_id])

    def remove_sandbox(self, subagent_id: str) -> None:
        """
        Removes the virtual context for a given subagent.

        Args:
            subagent_id: The ID of the subagent to remove.
        """
        if subagent_id in self.sandboxed_contexts:
            del self.sandboxed_contexts[subagent_id]
            logging.info(f"Removed isolated context for subagent: {subagent_id}")
