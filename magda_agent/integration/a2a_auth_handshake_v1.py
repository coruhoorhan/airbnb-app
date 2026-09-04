import uuid
import logging
from typing import Dict, Optional

class A2AAuthHandshake:
    """
    Implements a secure token exchange handshake between peer agents
    to ensure enterprise-grade authorization before task delegation.
    """

    def __init__(self) -> None:
        """
        Initializes the A2AAuthHandshake with an empty registry of authorized peers
        and an empty set of active handshake tokens.
        """
        self._authorized_peers: Dict[str, str] = {}
        self._active_tokens: Dict[str, str] = {}

    def generate_handshake_token(self, agent_id: str) -> str:
        """
        Generates a secure token for an agent to initiate a handshake.

        Args:
            agent_id (str): The ID of the agent requesting the token.

        Returns:
            str: The generated handshake token.
        """
        token = f"a2a_hs_{uuid.uuid4().hex}"
        self._active_tokens[token] = agent_id
        logging.info(f"Generated handshake token for agent {agent_id}.")
        return token

    def verify_handshake(self, agent_id: str, token: str) -> bool:
        """
        Verifies a handshake token and authorizes the agent if valid.

        Args:
            agent_id (str): The ID of the agent attempting the handshake.
            token (str): The token provided by the agent.

        Returns:
            bool: True if the handshake is successful, False otherwise.
        """
        if token in self._active_tokens and self._active_tokens[token] == agent_id:
            self._authorized_peers[agent_id] = token
            # In a real scenario, we might want to expire or single-use the token,
            # but for this basic handshake, keeping it in active_tokens is fine,
            # or we remove it to make it single use for the initial handshake.
            # Let's make it single-use for the handshake process itself.
            del self._active_tokens[token]
            logging.info(f"Handshake successful for agent {agent_id}.")
            return True

        logging.warning(f"Handshake failed for agent {agent_id} with invalid token.")
        return False

    def is_peer_authorized(self, agent_id: str) -> bool:
        """
        Checks if a peer agent is currently authorized.

        Args:
            agent_id (str): The ID of the peer agent to check.

        Returns:
            bool: True if authorized, False otherwise.
        """
        return agent_id in self._authorized_peers

    def revoke_authorization(self, agent_id: str) -> bool:
        """
        Revokes the authorization for a peer agent.

        Args:
            agent_id (str): The ID of the agent to revoke.

        Returns:
            bool: True if successfully revoked, False if the agent was not authorized.
        """
        if agent_id in self._authorized_peers:
            del self._authorized_peers[agent_id]
            logging.info(f"Revoked authorization for agent {agent_id}.")
            return True
        return False
