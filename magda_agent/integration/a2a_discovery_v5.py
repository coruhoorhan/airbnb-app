"""
A2A Discovery Agent Card Dynamic Validation V5.

Inspired by A2A Protocol standard trends: Implements strict dynamic JSON schema
validation for incoming and discovered Agent Cards during network discovery to ensure
enterprise-ready interoperability, security, and protocol conformance.
"""

import asyncio
import json
import logging
import re
import time
import uuid
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Callable, Coroutine, Dict, List, Optional, Set, Tuple, Union

logger = logging.getLogger(__name__)


class AgentSecurityTier(str, Enum):
    STANDARD = "standard"
    ENTERPRISE = "enterprise"
    SANDBOXED = "sandboxed"
    UNTRUSTED = "untrusted"


@dataclass
class ValidationResult:
    """Outcome of validating an Agent Card against the schema."""

    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    validated_data: Optional[Dict[str, Any]] = None
    agent_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_valid": self.is_valid,
            "errors": self.errors,
            "warnings": self.warnings,
            "agent_id": self.agent_id,
        }


@dataclass
class AgentCardV5:
    """Represents a validated A2A Agent Card conforming to V5 schema."""

    agent_id: str
    name: str
    description: str
    capabilities: List[str]
    endpoints: Dict[str, str]
    protocol_version: str = "v5"
    security_tier: AgentSecurityTier = AgentSecurityTier.STANDARD
    supported_schemas: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["security_tier"] = (
            self.security_tier.value
            if isinstance(self.security_tier, AgentSecurityTier)
            else str(self.security_tier)
        )
        return d

    def to_json(self) -> str:
        return json.dumps(self.to_dict())

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentCardV5":
        sec_tier = data.get("security_tier", "standard")
        if isinstance(sec_tier, str):
            try:
                sec_tier = AgentSecurityTier(sec_tier.lower())
            except ValueError:
                sec_tier = AgentSecurityTier.STANDARD

        return cls(
            agent_id=str(data.get("agent_id") or data.get("id") or ""),
            name=str(data.get("name") or ""),
            description=str(data.get("description") or ""),
            capabilities=list(data.get("capabilities") or []),
            endpoints=dict(data.get("endpoints") or {}),
            protocol_version=str(data.get("protocol_version") or "v5"),
            security_tier=sec_tier,
            supported_schemas=dict(data.get("supported_schemas") or {}),
            metadata=dict(data.get("metadata") or {}),
        )

    @classmethod
    def from_json(cls, json_str: str) -> "AgentCardV5":
        data = json.loads(json_str)
        return cls.from_dict(data)

    def has_capability(self, capability: str) -> bool:
        cap_lower = capability.strip().lower()
        return any(
            cap_lower == c.strip().lower() or cap_lower in c.strip().lower()
            for c in self.capabilities
        )


class AgentCardSchemaValidatorV5:
    """
    Validates raw Agent Card JSON or dictionaries against the strict A2A V5 specification.
    """

    ID_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{3,128}$")
    NAME_PATTERN = re.compile(r"^.{1,256}$")

    DEFAULT_SCHEMA = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "title": "AgentCardV5",
        "type": "object",
        "required": ["agent_id", "name", "capabilities", "endpoints"],
        "properties": {
            "agent_id": {"type": "string", "minLength": 3, "maxLength": 128},
            "name": {"type": "string", "minLength": 1, "maxLength": 256},
            "description": {"type": "string", "maxLength": 2048},
            "capabilities": {
                "type": "array",
                "items": {"type": "string", "minLength": 1},
                "minItems": 1,
            },
            "endpoints": {
                "type": "object",
                "minProperties": 1,
                "additionalProperties": {"type": "string"},
            },
            "protocol_version": {"type": "string"},
            "security_tier": {
                "type": "string",
                "enum": ["standard", "enterprise", "sandboxed", "untrusted"],
            },
            "supported_schemas": {"type": "object"},
            "metadata": {"type": "object"},
        },
    }

    def validate(self, raw_input: Union[Dict[str, Any], str, AgentCardV5]) -> ValidationResult:
        """Validate input data against Agent Card V5 specification."""
        errors: List[str] = []
        warnings: List[str] = []

        if isinstance(raw_input, AgentCardV5):
            data = raw_input.to_dict()
        elif isinstance(raw_input, str):
            try:
                data = json.loads(raw_input)
                if not isinstance(data, dict):
                    return ValidationResult(
                        is_valid=False,
                        errors=["Agent Card JSON root must be a JSON object (dictionary)."],
                    )
            except json.JSONDecodeError as e:
                return ValidationResult(
                    is_valid=False,
                    errors=[f"Malformed JSON syntax: {str(e)}"],
                )
        elif isinstance(raw_input, dict):
            data = dict(raw_input)
        else:
            return ValidationResult(
                is_valid=False,
                errors=[f"Unsupported input type '{type(raw_input).__name__}'. Must be dict, JSON string, or AgentCardV5."],
            )

        # 1. Required fields
        agent_id = data.get("agent_id") or data.get("id")
        if not agent_id:
            errors.append("Missing required field 'agent_id'.")
        elif not isinstance(agent_id, str):
            errors.append(f"Field 'agent_id' must be a string, got {type(agent_id).__name__}.")
        elif not self.ID_PATTERN.match(agent_id.strip()):
            errors.append(
                f"Invalid 'agent_id' format: '{agent_id}'. Must be 3-128 alphanumeric chars, hyphens, or underscores."
            )

        name = data.get("name")
        if not name:
            errors.append("Missing required field 'name'.")
        elif not isinstance(name, str) or not name.strip():
            errors.append("Field 'name' must be a non-empty string.")

        # 2. Capabilities validation
        capabilities = data.get("capabilities")
        if capabilities is None:
            errors.append("Missing required field 'capabilities'.")
        elif not isinstance(capabilities, list):
            errors.append(f"Field 'capabilities' must be a list of strings, got {type(capabilities).__name__}.")
        elif len(capabilities) == 0:
            errors.append("Field 'capabilities' list cannot be empty. At least one capability is required.")
        else:
            for idx, cap in enumerate(capabilities):
                if not isinstance(cap, str) or not cap.strip():
                    errors.append(f"Capability at index {idx} must be a non-empty string.")

        # 3. Endpoints validation
        endpoints = data.get("endpoints")
        if endpoints is None:
            errors.append("Missing required field 'endpoints'.")
        elif not isinstance(endpoints, dict):
            errors.append(f"Field 'endpoints' must be an object/dict mapping protocol to URL/target, got {type(endpoints).__name__}.")
        elif len(endpoints) == 0:
            errors.append("Field 'endpoints' cannot be empty. At least one endpoint mapping is required.")
        else:
            for proto, uri in endpoints.items():
                if not isinstance(proto, str) or not proto.strip():
                    errors.append(f"Endpoint protocol key '{proto}' must be a non-empty string.")
                if not isinstance(uri, str) or not uri.strip():
                    errors.append(f"Endpoint URI for '{proto}' must be a non-empty string.")

        # 4. Optional fields validation
        protocol_version = data.get("protocol_version")
        if protocol_version is not None and not isinstance(protocol_version, str):
            errors.append(f"Field 'protocol_version' must be a string if provided, got {type(protocol_version).__name__}.")

        sec_tier = data.get("security_tier")
        if sec_tier is not None:
            if isinstance(sec_tier, str):
                valid_tiers = [t.value for t in AgentSecurityTier]
                if sec_tier.lower() not in valid_tiers:
                    errors.append(
                        f"Invalid 'security_tier' '{sec_tier}'. Must be one of: {valid_tiers}"
                    )
            elif not isinstance(sec_tier, AgentSecurityTier):
                errors.append(f"Field 'security_tier' must be string, got {type(sec_tier).__name__}.")

        is_valid = len(errors) == 0
        return ValidationResult(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
            validated_data=data if is_valid else None,
            agent_id=str(agent_id) if agent_id else None,
        )


class A2ADiscoveryRegistryV5:
    """
    Discovery Registry V5.

    Applies strict dynamic JSON schema validation to incoming Agent Cards.
    Registers conforming cards and rejects/quarantines invalid or malformed ones.
    """

    def __init__(
        self,
        validator: Optional[AgentCardSchemaValidatorV5] = None,
        on_rejection_callback: Optional[Callable[[Dict[str, Any], List[str]], None]] = None,
    ):
        self.validator = validator or AgentCardSchemaValidatorV5()
        self.on_rejection_callback = on_rejection_callback
        self._registry: Dict[str, AgentCardV5] = {}
        self._last_seen: Dict[str, float] = {}
        self._quarantined_cards: List[Dict[str, Any]] = []

    def register_agent(
        self,
        raw_card: Union[AgentCardV5, Dict[str, Any], str],
    ) -> Tuple[bool, Optional[AgentCardV5], List[str]]:
        """
        Validate and register an Agent Card.

        Returns (success, registered_card, errors).
        """
        val_res = self.validator.validate(raw_card)

        if not val_res.is_valid:
            rejection_entry = {
                "raw_card": raw_card if isinstance(raw_card, (dict, str)) else raw_card.to_dict(),
                "errors": val_res.errors,
                "timestamp": time.time(),
                "agent_id": val_res.agent_id,
            }
            self._quarantined_cards.append(rejection_entry)
            logger.warning(
                f"Rejected malformed Agent Card (id={val_res.agent_id}): {val_res.errors}"
            )
            if self.on_rejection_callback:
                try:
                    self.on_rejection_callback(rejection_entry, val_res.errors)
                except Exception as ex:
                    logger.error(f"Error in rejection callback: {ex}")
            return False, None, val_res.errors

        card = AgentCardV5.from_dict(val_res.validated_data or {})
        self._registry[card.agent_id] = card
        self._last_seen[card.agent_id] = time.time()
        logger.info(f"Successfully registered valid AgentCardV5 for agent '{card.name}' ({card.agent_id})")
        return True, card, []

    def unregister_agent(self, agent_id: str) -> bool:
        """Remove agent from active registry."""
        if agent_id in self._registry:
            del self._registry[agent_id]
            self._last_seen.pop(agent_id, None)
            return True
        return False

    def parse_and_register_cards(
        self,
        raw_cards: List[Union[str, Dict[str, Any]]],
    ) -> Tuple[List[AgentCardV5], List[Dict[str, Any]]]:
        """
        Parse a batch of raw cards, registering valid ones and quarantining invalid ones.

        Returns (valid_cards, rejected_entries).
        """
        valid_cards: List[AgentCardV5] = []
        rejected: List[Dict[str, Any]] = []

        for raw in raw_cards:
            success, card, errors = self.register_agent(raw)
            if success and card:
                valid_cards.append(card)
            else:
                rejected.append({
                    "raw": raw,
                    "errors": errors,
                })

        return valid_cards, rejected

    def get_agent_card(self, agent_id: str) -> Optional[AgentCardV5]:
        """Retrieve registered agent card by id."""
        return self._registry.get(agent_id)

    def get_all_agents(self) -> List[AgentCardV5]:
        """Return all valid registered agent cards."""
        return list(self._registry.values())

    def get_quarantined_cards(self) -> List[Dict[str, Any]]:
        """Return all rejected/quarantined card entries."""
        return list(self._quarantined_cards)

    def find_agents_by_capability(self, capability: str) -> List[AgentCardV5]:
        """Find registered agents advertising the specified capability."""
        return [card for card in self._registry.values() if card.has_capability(capability)]


class A2ADiscoveryV5:
    """
    Main A2A Discovery V5 Orchestrator.

    Wraps local card registration, broadcaster, and schema-validated peer discovery.
    """

    def __init__(
        self,
        local_card: Optional[AgentCardV5] = None,
        registry: Optional[A2ADiscoveryRegistryV5] = None,
    ):
        self.registry = registry or A2ADiscoveryRegistryV5()
        self.validator = self.registry.validator
        self.local_card = local_card
        if self.local_card:
            self.registry.register_agent(self.local_card)

    def ingest_discovered_card(
        self,
        card_data: Union[str, Dict[str, Any]],
    ) -> Tuple[bool, Optional[AgentCardV5], List[str]]:
        """Ingest and validate discovered peer card."""
        return self.registry.register_agent(card_data)

    def get_active_mesh_agents(self) -> List[AgentCardV5]:
        """Retrieve all verified mesh agents."""
        return self.registry.get_all_agents()
