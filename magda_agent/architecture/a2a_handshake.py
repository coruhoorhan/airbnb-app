import hmac
import hashlib
import json
import time
from typing import Dict, Any, Optional

class A2AHandshakeProtocol:
    """
    Implements a cryptographically signed handshake protocol between interacting sub-agents
    to verify their identities before delegating sub-tasks, minimizing risks of context injection spoofing.
    """

    def __init__(self, secret_key: str, expiration_seconds: int = 300) -> None:
        """
        Initializes the A2AHandshakeProtocol.

        Args:
            secret_key: The secret key used for HMAC signing.
            expiration_seconds: The maximum age (in seconds) of a valid handshake signature.
        """
        self.secret_key = secret_key.encode('utf-8')
        self.expiration_seconds = expiration_seconds

    def generate_signature(self, payload: Dict[str, Any], timestamp: Optional[float] = None) -> str:
        """
        Generates an HMAC signature for the given payload and timestamp.

        Args:
            payload: The dictionary payload to sign.
            timestamp: Optional timestamp to use. If not provided, current time is used.

        Returns:
            The generated hexadecimal signature string.
        """
        if timestamp is None:
            timestamp = time.time()

        # Serialize the payload securely
        serialized_payload = json.dumps(payload, sort_keys=True)
        message = f"{timestamp}:{serialized_payload}".encode('utf-8')

        return hmac.new(self.secret_key, message, hashlib.sha256).hexdigest()

    def create_handshake(self, source_agent_id: str, target_agent_id: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Creates a signed handshake payload for delegating a task to another agent.

        Args:
            source_agent_id: The ID of the agent initiating the delegation.
            target_agent_id: The ID of the agent receiving the delegation.
            context: Additional context or task data being passed.

        Returns:
            A dictionary containing the handshake payload, timestamp, and signature.
        """
        timestamp = time.time()
        payload = {
            "source": source_agent_id,
            "target": target_agent_id,
            "context": context
        }
        signature = self.generate_signature(payload, timestamp)

        return {
            "payload": payload,
            "timestamp": timestamp,
            "signature": signature
        }

    def verify_handshake(self, handshake_data: Dict[str, Any], expected_target_id: str) -> bool:
        """
        Verifies a signed handshake from another agent.

        Args:
            handshake_data: The handshake dictionary received from the source agent.
            expected_target_id: The ID of the agent verifying the handshake (should match target).

        Returns:
            True if the handshake is valid, not expired, and securely signed. False otherwise.
        """
        try:
            payload = handshake_data.get("payload")
            timestamp = handshake_data.get("timestamp")
            signature = handshake_data.get("signature")

            if payload is None or timestamp is None or signature is None:
                return False

            # Check expiration
            current_time = time.time()
            if current_time - timestamp > self.expiration_seconds:
                return False

            # Verify target ID matches
            if payload.get("target") != expected_target_id:
                return False

            # Verify signature
            expected_signature = self.generate_signature(payload, timestamp)
            return hmac.compare_digest(signature, expected_signature)

        except (ValueError, TypeError, KeyError):
            return False
