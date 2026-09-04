import uuid
import logging
import httpx
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)

class A2AEnterpriseAuthTraversalV4:
    """
    Manages secure authentication traversal across an A2A network mesh.
    Provides logic to generate traversal tokens, track their path (hops),
    and forward authentication to subsequent peer nodes in a mesh.
    """

    def __init__(self) -> None:
        """
        Initializes the A2AEnterpriseAuthTraversalV4 registry.
        """
        # Maps a traversal token string to its traversal state dictionary
        self._active_traversals: Dict[str, Dict[str, Any]] = {}

    def initiate_traversal(self, origin_node_id: str, max_hops: int = 5) -> str:
        """
        Initiates a new authentication traversal session.

        Args:
            origin_node_id: The ID of the node originating the traversal.
            max_hops: The maximum number of allowed network hops.

        Returns:
            The generated traversal token.
        """
        token = f"a2a_trav_{uuid.uuid4().hex}"
        self._active_traversals[token] = {
            "origin": origin_node_id,
            "current_node": origin_node_id,
            "path": [origin_node_id],
            "max_hops": max_hops
        }
        logger.info(f"Initiated new traversal from origin {origin_node_id} (token redacted).")
        return token

    def verify_traversal_auth(self, token: str, current_node_id: str) -> bool:
        """
        Verifies if the traversal token is valid and currently at the expected node.

        Args:
            token: The traversal token to verify.
            current_node_id: The ID of the node performing the verification.

        Returns:
            True if valid and at the correct node, False otherwise.
        """
        traversal = self._active_traversals.get(token)
        if not traversal:
            logger.warning("Traversal verification failed: Invalid token.")
            return False

        if traversal["current_node"] != current_node_id:
            logger.warning(
                f"Traversal verification failed: Expected current node to be "
                f"{current_node_id}, but is {traversal['current_node']}."
            )
            return False

        if len(traversal["path"]) > traversal["max_hops"] + 1:
            logger.warning("Traversal verification failed: Max hops exceeded.")
            return False

        logger.info(f"Traversal token valid at node {current_node_id}.")
        return True

    def forward_traversal_state(self, token: str, next_node_id: str) -> bool:
        """
        Updates the internal traversal state to advance to the next node.

        Args:
            token: The traversal token.
            next_node_id: The ID of the next node.

        Returns:
            True if the state was successfully forwarded, False if invalid or max hops reached.
        """
        traversal = self._active_traversals.get(token)
        if not traversal:
            logger.warning("Cannot forward state: Invalid traversal token.")
            return False

        if len(traversal["path"]) > traversal["max_hops"]:
            logger.warning(f"Cannot forward state to {next_node_id}: Max hops ({traversal['max_hops']}) reached.")
            return False

        traversal["path"].append(next_node_id)
        traversal["current_node"] = next_node_id
        logger.info(f"Traversal state updated: Forwarded to {next_node_id}.")
        return True

    async def forward_traversal_network(self, token: str, next_node_endpoint: str) -> bool:
        """
        Asynchronously forwards the traversal token over the network mesh to a peer's endpoint.

        Args:
            token: The traversal token.
            next_node_endpoint: The HTTP RPC endpoint of the next node.

        Returns:
            True if the network request was successful, False otherwise.
        """
        payload = {
            "jsonrpc": "2.0",
            "method": "receive_traversal_auth",
            "params": {
                "traversal_token": token
            },
            "id": str(uuid.uuid4())
        }

        logger.info(f"Forwarding traversal token via network to {next_node_endpoint}")

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(next_node_endpoint, json=payload, timeout=5.0)
                response.raise_for_status()
                logger.info(f"Successfully forwarded traversal token to {next_node_endpoint}.")
                return True
        except httpx.HTTPError as e:
            logger.error(f"Network error forwarding traversal token to {next_node_endpoint}: {e}")
            return False
        except Exception as e:
            logger.error(f"Internal error forwarding traversal token to {next_node_endpoint}: {e}")
            return False
