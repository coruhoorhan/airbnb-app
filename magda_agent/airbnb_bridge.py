"""
Automated GitHub Bridge for airbnb-app repository.

Enables Magda-Agent to automatically author tasks, dispatch events, create issues,
and trigger Jules/Codex workflows on https://github.com/coruhoorhan/airbnb-app
directly via the GitHub REST API without any manual copy-paste.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional

logger = logging.getLogger("AirbnbAutomatedBridge")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

GITHUB_API = "https://api.github.com"
AIRBNB_REPO = os.getenv("AIRBNB_REPO", "coruhoorhan/airbnb-app")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")

class AirbnbAutomatedBridge:
    """Fully automated GitHub API Bridge for dispatching tasks and managing PRs."""

    def __init__(self, repo: str = AIRBNB_REPO, token: Optional[str] = None):
        self.repo = repo
        self.token = token or GITHUB_TOKEN

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github.v3+json",
            "Content-Type": "application/json",
            "User-Agent": "MagdaAgent-AutonomousBridge",
        }

    def _gh_request(self, method: str, path: str, json_body: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        url = f"{GITHUB_API}/{path.lstrip('/')}"
        data_bytes = json.dumps(json_body).encode("utf-8") if json_body else None

        req = urllib.request.Request(
            url=url,
            data=data_bytes,
            headers=self._headers(),
            method=method,
        )

        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                raw = resp.read().decode("utf-8")
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="replace")
            logger.error(f"GitHub API HTTP {e.code} error on {method} {url}: {err_body}")
            raise RuntimeError(f"GitHub API {e.code}: {err_body}")
        except Exception as ex:
            logger.error(f"GitHub API network error on {method} {url}: {ex}")
            raise

    def create_github_issue_for_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Creates a structured, actionable GitHub Issue that automated bots and Jules can pick up."""
        title = f"[{task.get('area', 'feature').upper()}] {task.get('title')}"
        body = f"""### 🤖 Magda-Agent Autonomous Task Specification

**Task ID:** `{task.get('id')}`  
**Area:** `{task.get('area')}`  
**Risk Level:** `{task.get('risk', 'medium')}`  

#### Description
{task.get('description')}

#### Allowed Paths
{chr(10).join(f"- `{p}`" for p in task.get('allowed_paths', []))}

#### Acceptance Criteria
{chr(10).join(f"- [ ] {c}" for c in task.get('acceptance', []))}

---
*Created automatically by Magda-Agent Cognitive Bridge.*
"""

        payload = {
            "title": title,
            "body": body,
            "labels": ["autonomous-task", task.get("area", "backend"), "jules-ready"],
        }

        res = self._gh_request("POST", f"/repos/{self.repo}/issues", payload)
        logger.info(f"Created GitHub Issue #{res.get('number')} for task '{task.get('id')}' at {res.get('html_url')}")
        return res

    def list_open_issues(self) -> List[Dict[str, Any]]:
        """List open issues in the airbnb-app repository."""
        return self._gh_request("GET", f"/repos/{self.repo}/issues?state=open")

    def dispatch_workflow(self, event_type: str = "magda_task_dispatch", client_payload: Optional[Dict[str, Any]] = None) -> bool:
        """Triggers repository dispatch event for automated CI/bot runners."""
        payload = {
            "event_type": event_type,
            "client_payload": client_payload or {},
        }
        try:
            self._gh_request("POST", f"/repos/{self.repo}/dispatches", payload)
            logger.info(f"Dispatched repository event '{event_type}' to {self.repo}")
            return True
        except Exception as e:
            logger.warning(f"Could not dispatch repository event (may require repo admin scope): {e}")
            return False

    def sync_manifest_tasks_to_github(self, manifest_path: str = "/opt/airbnb-app/airbnb_tasks.json") -> List[Dict[str, Any]]:
        """Syncs all pending 'todo' tasks from local airbnb_tasks.json directly to GitHub Issues automatically."""
        if not os.path.exists(manifest_path):
            manifest_path = "airbnb_tasks.json"

        with open(manifest_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        tasks = data.get("tasks", [])
        todo_tasks = [t for t in tasks if t.get("status") == "todo"]

        created_issues = []
        for t in todo_tasks:
            try:
                issue = self.create_github_issue_for_task(t)
                created_issues.append({
                    "task_id": t.get("id"),
                    "issue_number": issue.get("number"),
                    "issue_url": issue.get("html_url"),
                })
            except Exception as e:
                logger.error(f"Failed to create issue for task {t.get('id')}: {e}")

        return created_issues


def main():
    bridge = AirbnbAutomatedBridge()
    if len(sys.argv) > 1 and sys.argv[1] == "sync":
        manifest_p = sys.argv[2] if len(sys.argv) > 2 else "/opt/airbnb-app/airbnb_tasks.json"
        res = bridge.sync_manifest_tasks_to_github(manifest_p)
        print(json.dumps({"status": "synced", "created_issues": res}, indent=2))
    else:
        issues = bridge.list_open_issues()
        print(json.dumps({"repo": bridge.repo, "open_issues_count": len(issues)}, indent=2))


if __name__ == "__main__":
    main()
