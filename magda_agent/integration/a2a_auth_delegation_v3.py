"""
A2A Workflow Auth Delegation Manager V3.

Inspired by A2A Protocol standard trends: Implements an upgraded, centralized
active authentication token manager and token exchange mechanism for A2A mesh
network peers with cryptographic signing, token derivation, scope attenuation,
exchange handshakes, and centralized revocation.
"""

import asyncio
import hashlib
import hmac
import inspect
import json
import logging
import secrets
import time
import uuid
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Callable, Coroutine, Dict, List, Optional, Set, Tuple, Union

logger = logging.getLogger(__name__)


class TokenStatusV3(str, Enum):
    ACTIVE = "active"
    REVOKED = "revoked"
    EXPIRED = "expired"
    EXHAUSTED = "exhausted"


class DelegationScopeV3(str, Enum):
    READ = "read"
    EXECUTE = "execute"
    DELEGATE = "delegate"
    ADMIN = "admin"


@dataclass
class A2ADelegationTokenV3:
    """Represents a signed delegation token for peer agent task execution in V3 mesh."""

    token_id: str = field(default_factory=lambda: f"tok_v3_{uuid.uuid4().hex[:8]}")
    issuer_id: str = "magda_primary"
    subject_id: str = "*"  # Target peer ID
    task_id: str = ""
    scopes: List[str] = field(default_factory=lambda: [DelegationScopeV3.EXECUTE.value])
    issued_at: float = field(default_factory=time.time)
    expires_at: float = field(default_factory=lambda: time.time() + 300)
    max_delegation_depth: int = 3
    current_depth: int = 0
    parent_token_id: Optional[str] = None
    signature: str = ""
    status: TokenStatusV3 = TokenStatusV3.ACTIVE
    metadata: Dict[str, Any] = field(default_factory=dict)

    def is_valid(self, current_time: Optional[float] = None) -> bool:
        now = current_time if current_time is not None else time.time()
        if self.status != TokenStatusV3.ACTIVE:
            return False
        if now >= self.expires_at:
            return False
        if self.current_depth > self.max_delegation_depth:
            return False
        return True

    def has_scope(self, scope: str) -> bool:
        if DelegationScopeV3.ADMIN.value in self.scopes:
            return True
        return scope in self.scopes

    def to_payload_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d.pop("signature", None)
        d["status"] = self.status.value if isinstance(self.status, TokenStatusV3) else str(self.status)
        return d

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["status"] = self.status.value if isinstance(self.status, TokenStatusV3) else str(self.status)
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "A2ADelegationTokenV3":
        stat = data.get("status", "active")
        if isinstance(stat, str):
            try:
                stat = TokenStatusV3(stat.lower())
            except ValueError:
                stat = TokenStatusV3.ACTIVE
        return cls(
            token_id=str(data.get("token_id") or f"tok_v3_{uuid.uuid4().hex[:8]}"),
            issuer_id=str(data.get("issuer_id") or "magda_primary"),
            subject_id=str(data.get("subject_id") or "*"),
            task_id=str(data.get("task_id") or ""),
            scopes=list(data.get("scopes") or [DelegationScopeV3.EXECUTE.value]),
            issued_at=float(data.get("issued_at", time.time())),
            expires_at=float(data.get("expires_at", time.time() + 300)),
            max_delegation_depth=int(data.get("max_delegation_depth", 3)),
            current_depth=int(data.get("current_depth", 0)),
            parent_token_id=data.get("parent_token_id"),
            signature=str(data.get("signature") or ""),
            status=stat,
            metadata=dict(data.get("metadata") or {}),
        )


@dataclass
class TokenExchangeResult:
    """Outcome of exchanging or verifying an active delegation token between peers."""

    success: bool
    exchanged_token: Optional[A2ADelegationTokenV3] = None
    error: Optional[str] = None
    peer_agent_id: str = ""
    exchange_id: str = field(default_factory=lambda: f"exch_{uuid.uuid4().hex[:8]}")
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "exchanged_token": self.exchanged_token.to_dict() if self.exchanged_token else None,
            "error": self.error,
            "peer_agent_id": self.peer_agent_id,
            "exchange_id": self.exchange_id,
        }


class A2AWorkflowAuthDelegationManagerV3:
    """
    Central Active Token & Auth Delegation Manager V3.

    Centrally manages token generation, derivation, verification, and exchange
    for mesh network sub-agents.
    """

    def __init__(
        self,
        local_agent_id: str = "magda_primary",
        secret_key: Optional[str] = None,
        default_ttl_seconds: int = 300,
    ):
        self.local_agent_id = local_agent_id
        self.secret_key = secret_key or secrets.token_hex(32)
        self.default_ttl = default_ttl_seconds
        self._active_tokens: Dict[str, A2ADelegationTokenV3] = {}
        self._revocation_list: Set[str] = set()

    def _sign_payload(self, payload: Dict[str, Any]) -> str:
        canonical = json.dumps(payload, sort_keys=True)
        return hmac.new(
            self.secret_key.encode("utf-8"),
            canonical.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    def issue_token(
        self,
        subject_id: str,
        task_id: str,
        scopes: Optional[List[str]] = None,
        ttl_seconds: Optional[int] = None,
        max_delegation_depth: int = 3,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> A2ADelegationTokenV3:
        """Issue a new root delegation token."""
        now = time.time()
        ttl = ttl_seconds if ttl_seconds is not None else self.default_ttl
        token = A2ADelegationTokenV3(
            issuer_id=self.local_agent_id,
            subject_id=subject_id,
            task_id=task_id,
            scopes=scopes or [DelegationScopeV3.EXECUTE.value],
            issued_at=now,
            expires_at=now + ttl,
            max_delegation_depth=max_delegation_depth,
            current_depth=0,
            metadata=metadata or {},
        )

        sig = self._sign_payload(token.to_payload_dict())
        token.signature = sig
        self._active_tokens[token.token_id] = token
        logger.info(f"Issued active A2A token '{token.token_id}' for subject '{subject_id}' (task={task_id})")
        return token

    def derive_sub_token(
        self,
        parent_token_id: str,
        new_subject_id: str,
        sub_task_id: str,
        restricted_scopes: Optional[List[str]] = None,
        ttl_seconds: Optional[int] = None,
    ) -> A2ADelegationTokenV3:
        """
        Derive a child token with increased depth and attenuated scopes.
        """
        parent = self._active_tokens.get(parent_token_id)
        if not parent or not parent.is_valid():
            raise ValueError(f"Parent token '{parent_token_id}' is invalid or expired.")

        if parent.current_depth >= parent.max_delegation_depth:
            raise ValueError(
                f"Cannot derive sub-token: maximum delegation depth ({parent.max_delegation_depth}) reached."
            )

        if not parent.has_scope(DelegationScopeV3.DELEGATE.value) and not parent.has_scope(DelegationScopeV3.ADMIN.value):
            raise ValueError(f"Parent token lacks '{DelegationScopeV3.DELEGATE.value}' scope.")

        now = time.time()
        parent_ttl_rem = max(10, int(parent.expires_at - now))
        ttl = min(ttl_seconds or self.default_ttl, parent_ttl_rem)

        # Scopes cannot exceed parent scopes unless parent is ADMIN
        if restricted_scopes:
            for s in restricted_scopes:
                if not parent.has_scope(s):
                    raise ValueError(f"Cannot grant scope '{s}' not possessed by parent token.")
            scopes = list(restricted_scopes)
        else:
            scopes = list(parent.scopes)

        child = A2ADelegationTokenV3(
            issuer_id=self.local_agent_id,
            subject_id=new_subject_id,
            task_id=sub_task_id,
            scopes=scopes,
            issued_at=now,
            expires_at=now + ttl,
            max_delegation_depth=parent.max_delegation_depth,
            current_depth=parent.current_depth + 1,
            parent_token_id=parent.token_id,
        )

        child.signature = self._sign_payload(child.to_payload_dict())
        self._active_tokens[child.token_id] = child
        logger.info(f"Derived child token '{child.token_id}' at depth {child.current_depth}")
        return child

    def verify_token(
        self,
        token: Union[A2ADelegationTokenV3, str],
        expected_subject: Optional[str] = None,
        required_scope: Optional[str] = None,
    ) -> Tuple[bool, Optional[A2ADelegationTokenV3], str]:
        """
        Verify signature, status, expiration, subject, and scope.
        """
        if isinstance(token, str):
            tok_obj = self._active_tokens.get(token)
            if not tok_obj:
                return False, None, f"Token '{token}' not found in active token registry."
        else:
            tok_obj = token

        if tok_obj.token_id in self._revocation_list:
            tok_obj.status = TokenStatusV3.REVOKED
            return False, tok_obj, "Token has been revoked."

        if not tok_obj.is_valid():
            return False, tok_obj, f"Token is invalid or expired (status={tok_obj.status})."

        expected_sig = self._sign_payload(tok_obj.to_payload_dict())
        if not hmac.compare_digest(tok_obj.signature, expected_sig):
            return False, tok_obj, "Cryptographic signature mismatch."

        subject = expected_subject or self.local_agent_id
        if tok_obj.subject_id != subject and tok_obj.subject_id != "*":
            return False, tok_obj, f"Subject mismatch: expected '{subject}', got '{tok_obj.subject_id}'."

        if required_scope and not tok_obj.has_scope(required_scope):
            return False, tok_obj, f"Missing required scope '{required_scope}'."

        return True, tok_obj, "Token verified successfully."

    def exchange_peer_token(
        self,
        peer_agent_id: str,
        token_id_or_obj: Union[A2ADelegationTokenV3, str],
        subtask_id: str,
    ) -> TokenExchangeResult:
        """
        Exchange or validate an incoming token from a peer agent during mesh handoff.
        """
        is_ok, tok, reason = self.verify_token(token_id_or_obj, expected_subject=self.local_agent_id)
        if not is_ok or not tok:
            return TokenExchangeResult(
                success=False,
                error=f"Token exchange failed: {reason}",
                peer_agent_id=peer_agent_id,
            )

        return TokenExchangeResult(
            success=True,
            exchanged_token=tok,
            peer_agent_id=peer_agent_id,
        )

    def revoke_token(self, token_id: str, reason: str = "") -> bool:
        """Revoke an active token."""
        self._revocation_list.add(token_id)
        if token_id in self._active_tokens:
            self._active_tokens[token_id].status = TokenStatusV3.REVOKED
            logger.info(f"Revoked token '{token_id}'. Reason: {reason}")
            return True
        return False

    def list_active_tokens(self) -> List[A2ADelegationTokenV3]:
        """Return all valid, non-expired, non-revoked tokens."""
        now = time.time()
        return [
            t for t in self._active_tokens.values()
            if t.is_valid(now) and t.token_id not in self._revocation_list
        ]

    def prune_expired_tokens(self) -> int:
        """Remove expired tokens from internal store."""
        now = time.time()
        expired_ids = [
            tid for tid, tok in self._active_tokens.items()
            if now >= tok.expires_at or tok.status != TokenStatusV3.ACTIVE
        ]
        for tid in expired_ids:
            del self._active_tokens[tid]
        return len(expired_ids)
