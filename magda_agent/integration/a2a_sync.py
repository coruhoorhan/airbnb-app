"""A2A Protocol Synchronization.

This module implements a synchronization mechanism over the A2A network
for distributed state sharing among peer agents.
"""

from typing import Any, Dict, Protocol


class NetworkClient(Protocol):
    """Protocol defining the required interface for a network client used in state sync."""

    async def send_state_patch(self, peer_id: str, patch: Dict[str, Any]) -> bool:
        """Send a state patch to a peer.

        Args:
            peer_id: The ID of the peer to send the patch to.
            patch: A dictionary containing the state updates.

        Returns:
            True if the patch was successfully sent, False otherwise.
        """
        ...


class A2AStateSync:
    """Manages state synchronization across distributed A2A peer agents."""

    def __init__(self, network_client: NetworkClient):
        """Initialize the A2AStateSync.

        Args:
            network_client: An implementation of NetworkClient used to broadcast state.
        """
        self.network_client = network_client
        self._local_state: Dict[str, Any] = {}
        self._peer_states: Dict[str, Dict[str, Any]] = {}

    def get_local_state(self) -> Dict[str, Any]:
        """Get the current local state.

        Returns:
            A dictionary representing the local state.
        """
        return self._local_state

    def get_peer_state(self, peer_id: str) -> Dict[str, Any]:
        """Get the current known state of a specific peer.

        Args:
            peer_id: The ID of the peer.

        Returns:
            A dictionary representing the peer's state, or an empty dict if unknown.
        """
        return self._peer_states.get(peer_id, {})

    def update_local_state(self, key: str, value: Any) -> None:
        """Update a specific key in the local state.

        Args:
            key: The state key to update.
            value: The new value for the state key.
        """
        self._local_state[key] = value

    async def broadcast_state(self, peer_id: str, state_patch: Dict[str, Any]) -> bool:
        """Broadcast a state patch to a specific peer over the A2A network.

        Args:
            peer_id: The ID of the peer to send the patch to.
            state_patch: The dictionary containing the state updates to send.

        Returns:
            True if broadcast was successful, False otherwise.
        """
        success = await self.network_client.send_state_patch(peer_id, state_patch)
        return success

    def receive_state_sync(self, peer_id: str, state_patch: Dict[str, Any]) -> None:
        """Handle receiving a state patch from a peer and update the known peer state.

        Args:
            peer_id: The ID of the peer that sent the patch.
            state_patch: The dictionary containing the state updates.
        """
        if peer_id not in self._peer_states:
            self._peer_states[peer_id] = {}
        self._peer_states[peer_id].update(state_patch)
