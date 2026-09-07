"""
Magda-Agent Base Guardian Abstract Interface.
All Universal and Project-Specific Guardians inherit from this contract.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
import sqlite3
from typing import Any, Dict, List, Optional


@dataclass
class GuardianIssue:
    issue_type: str  # e.g. "security", "syntax", "data_integrity", "infra"
    severity: str    # "critical", "high", "medium", "low"
    title: str
    description: str
    suggestion: str = ""
    auto_healed: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.issue_type,
            "severity": self.severity,
            "title": self.title,
            "description": self.description,
            "suggestion": self.suggestion,
            "auto_healed": self.auto_healed,
            "metadata": self.metadata,
            "created_at": self.created_at,
        }


class BaseGuardian(ABC):
    """Abstract Base Class for all Magda Guardians."""

    def __init__(self, name: str, category: str, is_universal: bool = True):
        self.name = name
        self.category = category
        self.is_universal = is_universal

    @abstractmethod
    def run_check(
        self,
        app_root: str,
        db_conn: Optional[sqlite3.Connection] = None
    ) -> List[GuardianIssue]:
        """Executes diagnostic checks and returns detected issues."""
        pass
