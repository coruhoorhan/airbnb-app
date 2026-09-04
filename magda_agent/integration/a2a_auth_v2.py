"""
A2A Agent Peer Authentication V2.

Inspired by A2A standard trends for agent-to-agent delegation: Implements robust
HMAC-SHA256 token-based peer authentication for discovered agent cards, supporting
nonce replay protection, token expiration, scope enforcement, and mTLS compatibility.
"""

import hashlib
import hmac
import json
import logging
import secrets
import ssl
import time
import uuid
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union

logger = logging.getLogger(__name__)


class A2AAuthScope(str, Enum):
    DELEGATE_READ = "delegate:read"
    DELEGATE_EXECUTE = "delegate:execute"
    DELEGATE_ADMIN = "delegate:admin"
    DISCOVERY = "discovery"


@dataclass
class A2APeerAuthTokenV2:
    """Represents a signed peer authentication token for A2A handoffs."""

    issuer_agent_id: str
    target_agent_id: str
    scopes: List[str] = field(default_factory=lambda: [A2AAuthScope.DELEGATE_EXECUTE.value])
    issued_at: float = field(default_factory=time.time)
    expires_at: float = field(default_factory=lambda: time.time() + 300)
    nonce: str = field(default_factory=lambda: secrets.token_hex(8))
    signature: str = ""

    def to_claims_payload(self) -> str:
        """Deterministic serialization for HMAC signing."""
        data = {
            "iss": self.issuer_agent_id,
            "aud": self.target_agent_id,
            "scopes": sorted(self.scopes),
            "iat": int(self.issued_at),
            "exp": int(self.expires_at),
            "nonce": self.nonce,
        }
        return json.dumps(data, sort_keys=True)

    def to_token_string(self) -> str:
        """Serialize token object to compact string representation."""
        claims_json = self.to_claims_payload()
        return f"{claims_json}..{self.signature}"

    @classmethod
    def from_token_string(cls, token_str: str) -> "A2APeerAuthTokenV2":
        """Parse token string into A2APeerAuthTokenV2 object."""
        if ".." not in token_str:
            raise ValueError("Malformed token format, missing signature separator '..'")
        claims_part, sig = token_str.rsplit("..", 1)
        data = json.loads(claims_part)
        return cls(
            issuer_agent_id=data["iss"],
            target_agent_id=data["aud"],
            scopes=data.get("scopes", []),
            issued_at=float(data.get("iat", time.time())),
            expires_at=float(data.get("exp", time.time() + 300)),
            nonce=data.get("nonce", ""),
            signature=sig,
        )


class A2APeerAuthenticatorV2:
    """
    A2A Peer Authenticator V2.

    Manages secret sharing, token issuance, and incoming request verification.
    """

    def __init__(
        self,
        local_agent_id: str = "magda_primary",
        shared_secret_key: Optional[str] = None,
        default_ttl_seconds: float = 300.0,
    ):
        self.local_agent_id = local_agent_id
        self.secret_key = (shared_secret_key or secrets.token_hex(32)).encode("utf-8")
        self.default_ttl = default_ttl_seconds
        self._used_nonces: Set[str] = set()
        self._trusted_issuers: Set[str] = set()

    def add_trusted_issuer(self, agent_id: str) -> None:
        """Register a trusted peer issuer ID."""
        self._trusted_issuers.add(agent_id)

    def generate_token(
        self,
        target_agent_id: str,
        scopes: Optional[List[str]] = None,
        ttl_seconds: Optional[float] = None,
    ) -> A2APeerAuthTokenV2:
        """Generate and cryptographically sign a peer token."""
        now = time.time()
        ttl = ttl_seconds if ttl_seconds is not None else self.default_ttl
        token = A2APeerAuthTokenV2(
            issuer_agent_id=self.local_agent_id,
            target_agent_id=target_agent_id,
            scopes=scopes or [A2AAuthScope.DELEGATE_EXECUTE.value],
            issued_at=now,
            expires_at=now + ttl,
            nonce=secrets.token_hex(8),
        )

        payload_str = token.to_claims_payload().encode("utf-8")
        sig = hmac.new(self.secret_key, payload_str, hashlib.sha256).hexdigest()
        token.signature = sig
        return token

    def verify_token(
        self,
        token: Union[A2APeerAuthTokenV2, str],
        expected_target: Optional[str] = None,
        required_scope: Optional[str] = None,
    ) -> Tuple[bool, Optional[A2APeerAuthTokenV2], str]:
        """
        Verify signature, expiry, target audience, and nonce replay.
        Returns: (is_valid, token_obj, reason)
        """
        if isinstance(token, str):
            try:
                tok_obj = A2APeerAuthTokenV2.from_token_string(token)
            except Exception as ex:
                return False, None, f"Invalid token format: {ex}"
        else:
            tok_obj = token

        # 1. Verify HMAC signature
        payload_bytes = tok_obj.to_claims_payload().encode("utf-8")
        expected_sig = hmac.new(self.secret_key, payload_bytes, hashlib.sha256).hexdigest()

        if not hmac.compare_digest(tok_obj.signature, expected_sig):
            return False, tok_obj, "Invalid HMAC cryptographic signature."

        # 2. Verify Expiration
        now = time.time()
        if now > tok_obj.expires_at:
            return False, tok_obj, f"Token expired at {tok_obj.expires_at} (current time {now})."

        # 3. Verify Audience / Target Agent ID
        target = expected_target or self.local_agent_id
        if tok_obj.target_agent_id != target and target != "*":
            return False, tok_obj, f"Audience mismatch: expected '{target}', got '{tok_obj.target_agent_id}'."

        # 4. Check Replay Attack Nonce
        if tok_obj.nonce in self._used_nonces:
            return False, tok_obj, f"Token replay detected: nonce '{tok_obj.nonce}' already consumed."
        self._used_nonces.add(tok_obj.nonce)

        # 5. Check Scopes if required
        if required_scope:
            if required_scope not in tok_obj.scopes and A2AAuthScope.DELEGATE_ADMIN.value not in tok_obj.scopes:
                return False, tok_obj, f"Missing required scope '{required_scope}'. Granted: {tok_obj.scopes}."

        return True, tok_obj, "Token verified successfully."

    def authenticate_request(
        self,
        request_data: Dict[str, Any],
        required_scope: Optional[str] = None,
    ) -> Tuple[bool, Optional[Dict[str, Any]], str]:
        """
        Authenticate an incoming A2A request dictionary (headers or payload).
        """
        headers = request_data.get("headers", {})
        token_str = (
            headers.get("X-A2A-Auth-Token")
            or headers.get("Authorization")
            or request_data.get("auth_token")
            or request_data.get("token")
        )

        if not token_str:
            return False, None, "Missing authentication token in request headers/body."

        if str(token_str).startswith("Bearer "):
            token_str = str(token_str)[7:].strip()

        is_valid, tok, reason = self.verify_token(
            token_str,
            expected_target=self.local_agent_id,
            required_scope=required_scope,
        )

        if not is_valid or not tok:
            return False, None, reason

        claims = {
            "issuer": tok.issuer_agent_id,
            "target": tok.target_agent_id,
            "scopes": tok.scopes,
            "expires_at": tok.expires_at,
        }
        return True, claims, "Authenticated successfully."


class A2AAuthV2:
    """Legacy mTLS authentication support for A2A communication."""

    def __init__(self, cert_path: str, key_path: str):
        self.cert_path = cert_path
        self.key_path = key_path
        self.is_authenticated = False
        self.ssl_context: Optional[ssl.SSLContext] = None

    def authenticate(self) -> bool:
        """Authenticate using mTLS."""
        if not self.cert_path or not self.key_path:
            self.is_authenticated = False
            return False

        try:
            self.ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
            self.ssl_context.load_cert_chain(certfile=self.cert_path, keyfile=self.key_path)
            self.is_authenticated = True
            return True
        except Exception:
            self.is_authenticated = False
            return False
