from typing import List, Dict, Any

class MemoryCanvasVisualizer:
    """
    Visualization handler that maps episodic memory to OpenClaw Canvas nodes.
    Converts memory events into a node-based representation suitable for live UI streaming.
    """

    def convert_to_nodes(self, events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Convert a list of EpisodicMemory events to OpenClaw Canvas node dictionaries.

        Args:
            events: A list of episodic memory event dictionaries as returned by EpisodicMemory.get_all_events.
                    Each dict should contain 'id', 'text', and 'metadata'.

        Returns:
            A list of node dictionaries representing the memory events.
        """
        nodes = []
        for event in events:
            node_id = event.get("id", "unknown-id")
            text = event.get("text", "")
            metadata = event.get("metadata", {})

            # Base node structure
            node = {
                "id": node_id,
                "type": "episodic_memory",
                "label": text[:50] + "..." if len(text) > 50 else text,
                "data": {
                    "full_text": text,
                    "metadata": metadata,
                }
            }

            nodes.append(node)

        return nodes
