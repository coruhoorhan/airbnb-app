"""
MCP Dynamic Skill Marketplace Poller V2.

Inspired by agentskills.io and MCP dynamic marketplace standards:
Implements a periodic poller and cron synchronizer that fetches, parses,
and validates external tool and skill definitions from agentskills.io
and dynamically loads them into local registries.
"""

import asyncio
import inspect
import json
import logging
import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Coroutine, Dict, List, Optional, Set, Tuple, Union

logger = logging.getLogger(__name__)


@dataclass
class MarketplaceSkillEntryV2:
    """Represents a validated skill/tool entry parsed from agentskills.io."""

    name: str
    description: str
    version: str = "1.0.0"
    author: str = "community"
    input_schema: Dict[str, Any] = field(default_factory=lambda: {"type": "object", "properties": {}})
    category: str = "general"
    download_url: Optional[str] = None
    code: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MarketplaceSkillEntryV2":
        name = str(data.get("name") or data.get("tool_name") or data.get("skill_name") or "").strip()
        if not name:
            raise ValueError("Marketplace skill entry requires a valid 'name'")

        desc = str(data.get("description") or data.get("summary") or "").strip()
        ver = str(data.get("version") or "1.0.0").strip()
        auth = str(data.get("author") or data.get("publisher") or "community").strip()
        schema = dict(data.get("input_schema") or data.get("inputSchema") or data.get("parameters") or {"type": "object", "properties": {}})
        cat = str(data.get("category") or data.get("type") or "general").strip()
        d_url = data.get("download_url") or data.get("url")
        code_str = data.get("code") or data.get("implementation")
        tags = [str(t).strip() for t in (data.get("tags") or []) if str(t).strip()]

        return cls(
            name=name,
            description=desc,
            version=ver,
            author=auth,
            input_schema=schema,
            category=cat,
            download_url=str(d_url) if d_url else None,
            code=str(code_str) if code_str else None,
            tags=tags,
            metadata=dict(data.get("metadata") or {}),
        )


class MCPMarketplacePollerV2:
    """
    MCP Marketplace Poller V2.

    Periodically queries agentskills.io endpoints and ingests tools into registries.
    """

    def __init__(
        self,
        registry: Optional[Any] = None,
        scheduler: Optional[Any] = None,
        marketplace_url: str = "https://api.agentskills.io/v2/skills",
        cron_expression: str = "0 */2 * * *",
        http_client: Optional[Any] = None,
    ):
        self.registry = registry
        self.scheduler = scheduler
        self.marketplace_url = marketplace_url
        self.cron_expression = cron_expression
        self.http_client = http_client

        self._cached_skills: Dict[str, MarketplaceSkillEntryV2] = {}
        self._sync_history: List[Dict[str, Any]] = []
        self._scheduled_task_name: Optional[str] = None

    def parse_marketplace_payload(
        self,
        raw_payload: Union[str, Dict[str, Any], List[Any]],
    ) -> Tuple[List[MarketplaceSkillEntryV2], List[str]]:
        """
        Parse raw payload into list of MarketplaceSkillEntryV2 objects.
        Handles both array formats and wrapped envelopes ({'skills': [...]}, {'items': [...]}, {'tools': [...]}).
        """
        errors: List[str] = []
        parsed_entries: List[MarketplaceSkillEntryV2] = []

        if isinstance(raw_payload, str):
            try:
                data = json.loads(raw_payload)
            except Exception as e:
                return [], [f"Failed to parse JSON string: {e}"]
        else:
            data = raw_payload

        # Unpack envelope
        items_list: List[Any] = []
        if isinstance(data, list):
            items_list = data
        elif isinstance(data, dict):
            if "skills" in data and isinstance(data["skills"], list):
                items_list = data["skills"]
            elif "tools" in data and isinstance(data["tools"], list):
                items_list = data["tools"]
            elif "items" in data and isinstance(data["items"], list):
                items_list = data["items"]
            else:
                # Might be single skill object
                if "name" in data:
                    items_list = [data]
                else:
                    errors.append("Unrecognized dictionary format: missing 'skills' or 'tools' array.")

        for idx, item in enumerate(items_list):
            if isinstance(item, dict):
                try:
                    entry = MarketplaceSkillEntryV2.from_dict(item)
                    parsed_entries.append(entry)
                    self._cached_skills[entry.name] = entry
                except Exception as ex:
                    errors.append(f"Skipping malformed entry at index {idx}: {ex}")
            else:
                errors.append(f"Skipping non-dict item at index {idx}")

        return parsed_entries, errors

    async def sync_marketplace_async(
        self,
        http_client: Optional[Any] = None,
        override_url: Optional[str] = None,
    ) -> Tuple[int, List[MarketplaceSkillEntryV2], List[str]]:
        """
        Fetch from remote marketplace endpoint, parse response, and register tools.
        """
        url = override_url or self.marketplace_url
        client = http_client or self.http_client
        start_t = time.perf_counter()

        if client is None:
            err = f"No HTTP client provided to fetch from {url}"
            logger.warning(err)
            return 0, [], [err]

        try:
            if hasattr(client, "get"):
                if inspect.iscoroutinefunction(client.get):
                    resp = await client.get(url)
                else:
                    resp = client.get(url)

                # Extract JSON payload
                if hasattr(resp, "json"):
                    payload = resp.json()
                    if inspect.iscoroutine(payload) or inspect.isawaitable(payload):
                        payload = await payload
                elif hasattr(resp, "text"):
                    payload = json.loads(resp.text)
                elif isinstance(resp, (dict, list)):
                    payload = resp
                else:
                    payload = json.loads(str(resp))

            elif callable(client):
                res = client(url)
                if inspect.isawaitable(res):
                    payload = await res
                else:
                    payload = res
            else:
                return 0, [], [f"Unsupported client type {type(client).__name__}"]

            entries, errors = self.parse_marketplace_payload(payload)

            # Register with local registry if present
            registered_count = 0
            if self.registry:
                for entry in entries:
                    try:
                        if hasattr(self.registry, "load_tool"):
                            self.registry.load_tool(entry.to_dict())
                            registered_count += 1
                        elif hasattr(self.registry, "register"):
                            self.registry.register(entry.name, entry.code or (lambda **kw: {}), entry.description)
                            registered_count += 1
                        elif hasattr(self.registry, "register_skill"):
                            self.registry.register_skill(entry.name, entry.code or (lambda **kw: {}), entry.description)
                            registered_count += 1
                    except Exception as e:
                        logger.warning(f"Failed to register '{entry.name}' into registry: {e}")
            else:
                registered_count = len(entries)

            elapsed = (time.perf_counter() - start_t) * 1000.0
            self._sync_history.append({
                "timestamp": time.time(),
                "url": url,
                "synced_count": registered_count,
                "errors": errors,
                "duration_ms": elapsed,
            })
            return registered_count, entries, errors

        except Exception as ex:
            elapsed = (time.perf_counter() - start_t) * 1000.0
            err_msg = f"Network or execution error during sync from {url}: {ex}"
            logger.error(err_msg)
            self._sync_history.append({
                "timestamp": time.time(),
                "url": url,
                "synced_count": 0,
                "errors": [err_msg],
                "duration_ms": elapsed,
            })
            return 0, [], [err_msg]

    def sync_marketplace_sync(
        self,
        http_client: Optional[Any] = None,
        override_url: Optional[str] = None,
    ) -> Tuple[int, List[MarketplaceSkillEntryV2], List[str]]:
        """Synchronous wrapper for marketplace sync."""
        return asyncio.run(self.sync_marketplace_async(http_client, override_url))

    def schedule_sync(self, cron_expr: Optional[str] = None) -> bool:
        """Register the sync job with the attached cron scheduler."""
        expr = cron_expr or self.cron_expression
        self._scheduled_task_name = "mcp_marketplace_poller_sync_v2"

        if self.scheduler:
            if hasattr(self.scheduler, "schedule"):
                try:
                    self.scheduler.schedule(expr, self.sync_marketplace_async, name=self._scheduled_task_name)
                    return True
                except Exception as ex:
                    logger.warning(f"Scheduler.schedule failed: {ex}")
            elif hasattr(self.scheduler, "add_task"):
                try:
                    self.scheduler.add_task(self._scheduled_task_name, expr, self.sync_marketplace_async)
                    return True
                except Exception as ex:
                    logger.warning(f"Scheduler.add_task failed: {ex}")
            elif hasattr(self.scheduler, "add_job"):
                try:
                    self.scheduler.add_job(self.sync_marketplace_async, "cron", id=self._scheduled_task_name)
                    return True
                except Exception as ex:
                    logger.warning(f"Scheduler.add_job failed: {ex}")

        return False

    def get_cached_skills(self) -> List[MarketplaceSkillEntryV2]:
        """Return all held skills in local cache."""
        return list(self._cached_skills.values())

    def get_sync_history(self) -> List[Dict[str, Any]]:
        """Return sync history logs."""
        return list(self._sync_history)
