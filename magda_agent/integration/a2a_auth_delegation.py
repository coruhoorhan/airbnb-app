"""
A2A Workflow Auth Delegation Tokens.

Inspired by A2A Protocol standard trends: Manages active authentication tokens
when passing tasks over A2A mesh network to peers with HMAC signing, scope
enforcement, delegation depth limits, token derivation, and revocation.
"""

import asyncio
import hashlib
import hmac
import json
import logging
import secrets
import time
import uuid
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Callable, Coroutine, Dict, List, Optional, Set, Tuple, Union

try:
    import httpx
except ImportError:
    httpx = None

logger = logging.getLogger(__name__)


class DelegationTokenScope(str, Enum):
    READ = "read"
    EXECUTE = "execute"
    DELEGATE = "delegate"
    ADMIN = "admin"


@dataclass
class A2ADelegationToken:
    """Represents a cryptographically signed auth delegation token for A2A task handoffs."""

    token_id: str
    issuer_id: str
    subject_id: str  # Intended target peer or '*'
    task_id: str
    scopes: List[str]
    issued_at: float
    expires_at: float
    max_delegation_depth: int = 3
    current_depth: int = 0
    signature: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    revoked: bool = False

    def is_expired(self, current_time: Optional[float] = None) -> bool:
        now = current_time if current_time is not None else time.time()
        return now >= self.expires_at

    def has_scope(self, scope: str) -> bool:
        if DelegationTokenScope.ADMIN.value in self.scopes:
            return True
        return scope in self.scopes

    def to_payload_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d.pop("signature", None)
        return d

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "A2ADelegationToken":
        return cls(**data)


class A2AAuthTokenManager:
    """
    Manages generation, signing, validation, sub-delegation, and revocation
    of active A2A delegation tokens.
    """

    def __init__(self, secret_key: Optional[str] = None, default_ttl_seconds: int = 300) -> None:
        self.secret_key = secret_key or secrets.token_hex(32)
        self.default_ttl = default_ttl_seconds
        self._revoked_tokens: Set[str] = set()
        self._token_store: Dict[str, A2ADelegationToken] = {}

    def _generate_signature(self, token_payload: Dict[str, Any]) -> str:
        canonical_str = json.dumps(token_payload, sort_keys=True)
        return hmac.new(
            self.secret_key.encode("utf-8"),
            canonical_str.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    def issue_token(
        self,
        issuer_id: str,
        subject_id: str,
        task_id: str,
        scopes: Optional[List[str]] = None,
        ttl_seconds: Optional[int] = None,
        max_delegation_depth: int = 3,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> A2ADelegationToken:
        """Issues a new signed delegation token."""
        now = time.time()
        ttl = ttl_seconds if ttl_seconds is not None else self.default_ttl
        token_id = f"a2a_tok_{uuid.uuid4().hex}"
        scopes = scopes or [DelegationTokenScope.EXECUTE.value]

        token = A2ADelegationToken(
            token_id=token_id,
            issuer_id=issuer_id,
            subject_id=subject_id,
            task_id=task_id,
            scopes=scopes,
            issued_at=now,
            expires_at=now + ttl,
            max_delegation_depth=max_delegation_depth,
            current_depth=0,
            metadata=metadata or {},
            revoked=False,
        )

        payload_dict = token.to_payload_dict()
        token.signature = self._generate_signature(payload_dict)
        self._token_store[token.token_id] = token
        logger.info(f"Issued A2A delegation token {token.token_id} from {issuer_id} to {subject_id}")
        return token

    def verify_token(
        self,
        token: Union[A2ADelegationToken, Dict[str, Any], str],
        expected_peer_id: Optional[str] = None,
        required_scope: Optional[str] = None,
    ) -> Tuple[bool, str, Optional[A2ADelegationToken]]:
        """
        Validates token signature, expiration, revocation, subject matching, and scopes.
        """
        if isinstance(token, str):
            token_obj = self._token_store.get(token)
            if not token_obj:
                try:
                    parsed = json.loads(token)
                    token_obj = A2ADelegationToken.from_dict(parsed)
                except Exception:
                    return False, "Token not found in store and could not be parsed as JSON.", None
        elif isinstance(token, dict):
            token_obj = A2ADelegationToken.from_dict(token)
        else:
            token_obj = token

        # 1. Check revocation
        if token_obj.token_id in self._revoked_tokens or token_obj.revoked:
            return False, f"Token {token_obj.token_id} is revoked.", token_obj

        # 2. Check expiration
        if token_obj.is_expired():
            return False, f"Token {token_obj.token_id} has expired.", token_obj

        # 3. Check signature
        payload_dict = token_obj.to_payload_dict()
        expected_sig = self._generate_signature(payload_dict)
        if not hmac.compare_digest(token_obj.signature, expected_sig):
            return False, "Invalid token cryptographic signature.", token_obj

        # 4. Check delegation depth limit
        if token_obj.current_depth > token_obj.max_delegation_depth:
            return False, f"Maximum delegation depth exceeded ({token_obj.current_depth} > {token_obj.max_delegation_depth}).", token_obj

        # 5. Check subject peer matching (if target specified)
        if expected_peer_id and token_obj.subject_id != "*" and token_obj.subject_id != expected_peer_id:
            return False, f"Token subject '{token_obj.subject_id}' does not match recipient '{expected_peer_id}'.", token_obj

        # 6. Check required scope
        if required_scope and not token_obj.has_scope(required_scope):
            return False, f"Token lacks required scope '{required_scope}'.", token_obj

        return True, "Token valid.", token_obj

    def derive_downstream_token(
        self,
        parent_token: A2ADelegationToken,
        downstream_peer_id: str,
        new_task_id: Optional[str] = None,
        restricted_scopes: Optional[List[str]] = None,
    ) -> A2ADelegationToken:
        """
        Derives a child token for multi-hop delegation across the A2A mesh network.
        Increments current_depth and ensures scopes are a subset of parent.
        """
        is_valid, reason, _ = self.verify_token(parent_token, required_scope=DelegationTokenScope.DELEGATE.value)
        if not is_valid:
            # If not explicitly DELEGATE, check if parent has EXECUTE
            if not parent_token.has_scope(DelegationTokenScope.EXECUTE.value):
                raise ValueError(f"Cannot derive token from invalid parent: {reason}")

        if parent_token.current_depth + 1 > parent_token.max_delegation_depth:
            raise ValueError(f"Cannot delegate: Max delegation depth {parent_token.max_delegation_depth} reached.")

        scopes = restricted_scopes or parent_token.scopes
        # Downstream scopes cannot exceed parent scopes
        for s in scopes:
            if not parent_token.has_scope(s):
                raise ValueError(f"Downstream token cannot claim scope '{s}' not present in parent token.")

        now = time.time()
        # Downstream TTL cannot outlive parent
        expires_at = min(now + self.default_ttl, parent_token.expires_at)

        child_token = A2ADelegationToken(
            token_id=f"a2a_tok_{uuid.uuid4().hex}",
            issuer_id=parent_token.subject_id if parent_token.subject_id != "*" else parent_token.issuer_id,
            subject_id=downstream_peer_id,
            task_id=new_task_id or parent_token.task_id,
            scopes=scopes,
            issued_at=now,
            expires_at=expires_at,
            max_delegation_depth=parent_token.max_delegation_depth,
            current_depth=parent_token.current_depth + 1,
            metadata={"parent_token_id": parent_token.token_id, **parent_token.metadata},
            revoked=False,
        )

        child_token.signature = self._generate_signature(child_token.to_payload_dict())
        self._token_store[child_token.token_id] = child_token
        return child_token

    def revoke_token(self, token_id: str) -> bool:
        """Revokes a token immediately."""
        self._revoked_tokens.add(token_id)
        if token_id in self._token_store:
            self._token_store[token_id].revoked = True
        logger.info(f"Revoked token {token_id}")
        return True


@dataclass
class A2ATaskDelegationPayload:
    """Standardized task delegation payload traversing the A2A mesh network."""

    task_id: str
    task_name: str
    task_data: Dict[str, Any]
    auth_token: Dict[str, Any]
    origin_peer_id: str
    destination_peer_id: str
    trace_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "A2ATaskDelegationPayload":
        return cls(**data)


class A2AWorkflowAuthDelegator:
    """
    High-level workflow coordinator that delegates tasks to peers over A2A mesh
    with active authentication tokens.
    """

    def __init__(
        self,
        local_agent_id: str,
        token_manager: Optional[A2AAuthTokenManager] = None,
        peer_dispatch_fn: Optional[Callable[[Dict[str, Any]], Coroutine[Any, Any, Dict[str, Any]]]] = None,
    ) -> None:
        self.local_agent_id = local_agent_id
        self.token_manager = token_manager or A2AAuthTokenManager()
        self.peer_dispatch_fn = peer_dispatch_fn
        self._task_handlers: Dict[str, Callable[[Dict[str, Any], A2ADelegationToken], Any]] = {}
        self.delegation_metrics = {
            "dispatched": 0,
            "received": 0,
            "authorized": 0,
            "rejected": 0,
        }

    def register_task_handler(
        self,
        task_name: str,
        handler: Callable[[Dict[str, Any], A2ADelegationToken], Any],
    ) -> None:
        """Registers a local handler for delegated tasks."""
        self._task_handlers[task_name] = handler

    async def delegate_task(
        self,
        target_peer_id: str,
        task_name: str,
        task_data: Dict[str, Any],
        scopes: Optional[List[str]] = None,
        ttl_seconds: Optional[int] = None,
        target_endpoint: Optional[str] = None,
        custom_token: Optional[A2ADelegationToken] = None,
    ) -> Dict[str, Any]:
        """
        Creates an active delegation token, packages the payload, and dispatches to target peer.
        """
        task_id = str(uuid.uuid4())
        token = custom_token or self.token_manager.issue_token(
            issuer_id=self.local_agent_id,
            subject_id=target_peer_id,
            task_id=task_id,
            scopes=scopes or [DelegationTokenScope.EXECUTE.value, DelegationTokenScope.DELEGATE.value],
            ttl_seconds=ttl_seconds,
        )

        payload = A2ATaskDelegationPayload(
            task_id=task_id,
            task_name=task_name,
            task_data=task_data,
            auth_token=token.to_dict(),
            origin_peer_id=self.local_agent_id,
            destination_peer_id=target_peer_id,
        )

        self.delegation_metrics["dispatched"] += 1
        logger.info(f"Delegating task '{task_name}' ({task_id}) to peer {target_peer_id}")

        # 1. If mock or custom in-memory dispatch function provided
        if self.peer_dispatch_fn:
            return await self.peer_dispatch_fn(payload.to_dict())

        # 2. If target network HTTP endpoint provided and httpx is available
        if target_endpoint and httpx:
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    resp = await client.post(target_endpoint, json=payload.to_dict())
                    return resp.json()
            except Exception as e:
                logger.error(f"Network error dispatching A2A task to {target_endpoint}: {e}")
                return {"status": "error", "error": f"Network transport error: {e}"}

        # Default local loopback simulation
        return await self.receive_delegated_task(payload.to_dict())

    async def receive_delegated_task(self, payload_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        Receives and processes an incoming delegated task from a peer.
        Validates token authenticity, expiration, subject, and permissions.
        """
        self.delegation_metrics["received"] += 1
        try:
            payload = A2ATaskDelegationPayload.from_dict(payload_dict)
        except Exception as e:
            self.delegation_metrics["rejected"] += 1
            return {
                "status": "rejected",
                "error": f"Invalid delegation payload format: {e}",
                "status_code": 400,
            }

        # Verify token
        is_valid, reason, token_obj = self.token_manager.verify_token(
            token=payload.auth_token,
            expected_peer_id=self.local_agent_id,
            required_scope=DelegationTokenScope.EXECUTE.value,
        )

        if not is_valid or not token_obj:
            self.delegation_metrics["rejected"] += 1
            logger.warning(f"Rejected delegated task {payload.task_id}: {reason}")
            return {
                "status": "unauthorized",
                "error": f"A2A Token Verification Failed: {reason}",
                "status_code": 401,
            }

        self.delegation_metrics["authorized"] += 1
        handler = self._task_handlers.get(payload.task_name)
        if not handler:
            # Fallback default echo handler
            return {
                "status": "completed",
                "task_id": payload.task_id,
                "result": f"Task '{payload.task_name}' processed by agent {self.local_agent_id}",
                "processed_data": payload.task_data,
                "token_id": token_obj.token_id,
                "status_code": 200,
            }

        try:
            if asyncio.iscoroutinefunction(handler):
                result = await handler(payload.task_data, token_obj)
            else:
                result = handler(payload.task_data, token_obj)

            return {
                "status": "completed",
                "task_id": payload.task_id,
                "result": result,
                "token_id": token_obj.token_id,
                "status_code": 200,
            }
        except Exception as e:
            logger.error(f"Error in task handler for '{payload.task_name}': {e}")
            return {
                "status": "error",
                "task_id": payload.task_id,
                "error": f"Execution error in delegated task: {e}",
                "status_code": 500,
            }
