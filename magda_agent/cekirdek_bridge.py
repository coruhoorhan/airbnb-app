"""Bridge that lets Magda author tasks directly into the cekirdek agent_tasks.json
and open a PR, so the GitHub-side loop (automerge -> jules_next_task -> Google Jules)
runs fully automatically with zero manual steps.

Design notes:
- GitHub API is used directly (no git binary, no local clone) via httpx.
- A PR is required because cekirdek main has branch protection that blocks direct
  pushes; the jules_automerge workflow auto-merges PRs authored by coruhoorhan.
- The LLM (llm_client) does the thinking: it turns a natural-language goal into a
  structured task entry matching the agent_tasks.json schema.
"""
from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
from typing import Any, Dict, List, Optional

import httpx

from magda_agent.llm_client import LLMClient

logger = logging.getLogger(__name__)

GITHUB_API = "https://api.github.com"

# Default target repository for authored tasks (overridable via env).
CEKIRDEK_REPO = os.getenv("CEKIRDEK_REPO", "coruhoorhan/cekirdek")
CEKIRDEK_PAT = os.getenv("CEKIRDEK_PAT", "")
CEKIRDEK_BRANCH = os.getenv("CEKIRDEK_BRANCH", "main")
CEKIRDEK_MANIFEST = os.getenv("CEKIRDEK_MANIFEST", "agent_tasks.json")

# Allowed task areas / risk levels (mirrors what the cekirdek loop understands).
_ALLOWED_AREAS = {"admin-panel", "auth", "classes", "students", "billing", "reports", "ui", "backend", "infra", "other"}
_ALLOWED_RISK = {"low", "medium", "high", "critical"}

_TASK_SCHEMA_PROMPT = """You are Magda, the autonomous orchestrator of the {repo} development loop.
A user wants a new task for the repository. Convert the user's request into ONE structured
task entry that matches the repository's task manifest schema.

User request:
{goal}

Return ONLY a single JSON object (no markdown, no commentary) with exactly these fields:
- "title": short Turkish imperative title (max ~70 chars), e.g. "Yeni muhasebe modulu ekle"
- "description": 1-3 sentence Turkish description of what to build
- "area": one of {areas}
- "risk": one of {risks}
- "allowed_paths": array of repo path prefixes the implementation may touch (keep narrow; never include .github/workflows or package.json)
- "acceptance": array of 3-6 concrete, testable Turkish acceptance criteria

Be specific and self-contained. The task must be implementable by an autonomous coding agent
without further clarification."""


class CekirdekBridgeError(Exception):
    """Raised when authoring a task into cekirdek fails."""


def _headers() -> Dict[str, str]:
    if not CEKIRDEK_PAT:
        raise CekirdekBridgeError("CEKIRDEK_PAT is not set; cannot write to cekirdek.")
    return {
        "Authorization": f"Bearer {CEKIRDEK_PAT}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


async def _gh(method: str, path: str, json_body: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """One GitHub REST call, raising on non-2xx with a readable message."""
    url = f"{GITHUB_API}{path}"
    timeout = httpx.Timeout(30.0)
    async with httpx.AsyncClient(timeout=timeout, headers=_headers()) as client:
        resp = await client.request(method, url, json=json_body)
    if resp.status_code >= 400:
        detail = resp.text[:500]
        raise CekirdekBridgeError(
            f"GitHub {method} {path} -> {resp.status_code}: {detail}"
        )
    return resp.json() if resp.content else {}


async def _fetch_manifest() -> Dict[str, Any]:
    """Fetch the current agent_tasks.json from the default branch."""
    path = f"/repos/{CEKIRDEK_REPO}/contents/{CEKIRDEK_MANIFEST}?ref={CEKIRDEK_BRANCH}"
    data = await _gh("GET", path)
    content = base64.b64decode(data["content"]).decode("utf-8")
    return json.loads(content)


async def _next_task_id(tasks: List[Dict[str, Any]]) -> str:
    """Compute the next cekirdek-NNN id from the existing ones."""
    max_num = 0
    for t in tasks:
        tid = str(t.get("id", ""))
        if tid.startswith("cekirdek-") and tid[len("cekirdek-"):].isdigit():
            max_num = max(max_num, int(tid[len("cekirdek-"):]))
    return f"cekirdek-{max_num + 1:03d}"


def _validate_task(entry: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize/validate a drafted task entry against the manifest schema."""
    title = str(entry.get("title", "")).strip()
    description = str(entry.get("description", "")).strip()
    if not title or not description:
        raise CekirdekBridgeError("LLM draft missing title or description.")
    area = str(entry.get("area", "other")).strip()
    if area not in _ALLOWED_AREAS:
        area = "other"
    risk = str(entry.get("risk", "medium")).strip()
    if risk not in _ALLOWED_RISK:
        risk = "medium"
    paths = entry.get("allowed_paths") or []
    if not isinstance(paths, list):
        paths = ["src/"]
    paths = [p for p in paths if isinstance(p, str) and p.strip()]
    if not paths:
        paths = ["src/"]
    acceptance = entry.get("acceptance") or []
    if not isinstance(acceptance, list):
        acceptance = []
    acceptance = [str(a).strip() for a in acceptance if str(a).strip()]
    if not acceptance:
        acceptance = [f"{title} calisir ve kullanicilara sunulur"]
    return {
        "title": title,
        "description": description,
        "area": area,
        "risk": risk,
        "allowed_paths": paths,
        "acceptance": acceptance,
    }


def _fallback_draft(goal: str) -> Dict[str, Any]:
    """Build a valid structured task entry without the LLM.
    Used when the model is rate-limited or otherwise unavailable, so task
    authoring still works end-to-end."""
    title = goal.strip()
    if len(title) > 70:
        title = title[:69].rstrip() + "…"
    return {
        "title": title,
        "description": (
            f"{goal} — bu gorev Telegram uzerinden Magda'ya verilen istekten "
            f"olusturuldu. LLM erisimi gecici olarak kisitli oldugu icin detay "
            f"yapilandirmasi otomatik tamamlanmistir."
        ),
        "area": "other",
        "risk": "medium",
        "allowed_paths": ["src/"],
        "acceptance": [f"{title} calisir ve kullanicilara sunulur"],
    }


async def draft_task(llm: LLMClient, goal: str) -> Dict[str, Any]:
    """Use Magda's LLM to turn a natural-language goal into a structured task entry.
    Falls back to a deterministic entry when the LLM is unavailable, so the
    authoring flow never blocks on a transient model outage."""
    prompt = _TASK_SCHEMA_PROMPT.format(
        repo=CEKIRDEK_REPO,
        goal=goal,
        areas=", ".join(sorted(_ALLOWED_AREAS)),
        risks=", ".join(sorted(_ALLOWED_RISK)),
    )
    try:
        raw = await llm.generate(prompt, temperature=0.4)
    except Exception as e:
        logger.warning("LLM unavailable (%s); using fallback draft for goal %r", e, goal)
        return _fallback_draft(goal)
    # Tolerate stray markdown fences the model sometimes wraps around JSON.
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        cleaned = cleaned.removeprefix("json").strip()
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1 or end <= start:
        logger.warning("LLM did not return JSON; using fallback draft for goal %r", goal)
        return _fallback_draft(goal)
    try:
        parsed = json.loads(cleaned[start:end + 1])
    except json.JSONDecodeError as e:
        logger.warning("LLM JSON parse failed (%s); using fallback draft for goal %r", e, goal)
        return _fallback_draft(goal)
    try:
        return _validate_task(parsed)
    except CekirdekBridgeError as e:
        logger.warning("LLM draft failed validation (%s); using fallback draft for goal %r", e, goal)
        return _fallback_draft(goal)


async def author_task(llm: LLMClient, goal: str, task_id: Optional[str] = None) -> Dict[str, Any]:
    """Draft a task, append it to cekirdek agent_tasks.json on a feature branch,
    and open a PR. Returns {task_id, pr_number, pr_url, title}."""
    draft = await draft_task(llm, goal)

    manifest = await _fetch_manifest()
    tasks = manifest.get("tasks", [])
    if not isinstance(tasks, list):
        raise CekirdekBridgeError("cekirdek agent_tasks.json has no 'tasks' list.")
    was_empty = not any(isinstance(t, dict) and t.get("status") == "todo" for t in tasks)
    new_id = task_id or await _next_task_id(tasks)

    entry = {"id": new_id, "status": "todo", **draft}
    tasks.append(entry)
    manifest["tasks"] = tasks
    new_content = base64.b64encode(
        json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8")
    ).decode("utf-8")

    # Branch created from the current default branch head.
    head = await _gh("GET", f"/repos/{CEKIRDEK_REPO}/git/ref/heads/{CEKIRDEK_BRANCH}")
    branch_name = f"magda/add-{new_id}"
    await _gh(
        "POST",
        f"/repos/{CEKIRDEK_REPO}/git/refs",
        {"ref": f"refs/heads/{branch_name}", "sha": head["object"]["sha"]},
    )

    # Commit the new manifest onto that branch.
    manifest_data = await _gh(
        "GET", f"/repos/{CEKIRDEK_REPO}/contents/{CEKIRDEK_MANIFEST}?ref={CEKIRDEK_BRANCH}"
    )
    await _gh(
        "PUT",
        f"/repos/{CEKIRDEK_REPO}/contents/{CEKIRDEK_MANIFEST}",
        {
            "message": f"add task {new_id}: {entry['title']}",
            "content": new_content,
            "branch": branch_name,
            "sha": manifest_data["sha"],
        },
    )

    # Open the PR; jules_automerge will validate and merge it.
    title = f"{new_id}: {entry['title']}"
    body_lines = [
        f"**{new_id}** — {entry['title']}",
        "",
        entry["description"],
        "",
        f"Area: `{entry['area']}`  ·  Risk: `{entry['risk']}`",
        "",
        "**Acceptance criteria:**",
        *[f"- {a}" for a in entry["acceptance"]],
        "",
        "Authored automatically by Magda from a Telegram command.",
    ]
    pr = await _gh(
        "POST",
        f"/repos/{CEKIRDEK_REPO}/pulls",
        {
            "title": title,
            "head": branch_name,
            "base": CEKIRDEK_BRANCH,
            "body": "\n".join(body_lines),
        },
    )
    logger.info("Authored %s -> PR #%s (%s)", new_id, pr["number"], pr["html_url"])

    # If the queue was empty before adding, kickstart the chain after merge.
    if was_empty:
        pr_num = pr["number"]
        asyncio.create_task(_dispatch_next_after_merge(pr_num))
        logger.info("Queue was empty; scheduled dispatch after PR #%s merge.", pr_num)

    return {
        "task_id": new_id,
        "title": entry["title"],
        "pr_number": pr["number"],
        "pr_url": pr["html_url"],
    }


async def _dispatch_next_after_merge(pr_number: int, timeout_s: float = 1200.0) -> None:
    """Poll a task-authoring PR until it merges, then trigger the cekirdek
    jules_next_task workflow so a fresh task in an otherwise empty queue starts
    without any manual step. Only safe when no other task is in flight, which is
    guaranteed by the caller passing was_empty (no 'todo' tasks existed before)."""
    loop = asyncio.get_event_loop()
    deadline = loop.time() + timeout_s
    while loop.time() < deadline:
        await asyncio.sleep(10.0)
        try:
            pr = await _gh("GET", f"/repos/{CEKIRDEK_REPO}/pulls/{pr_number}")
        except CekirdekBridgeError:
            logger.warning("Could not poll PR #%s state; retrying.", pr_number)
            continue
        if pr.get("merged"):
            await _gh(
                "POST",
                f"/repos/{CEKIRDEK_REPO}/actions/workflows/jules_next_task.yml/dispatches",
                {"ref": CEKIRDEK_BRANCH},
            )
            logger.info("Dispatched jules_next_task after PR #%s merged.", pr_number)
            return
        if pr.get("state") == "closed":  # closed without merge -> never dispatches
            logger.warning("PR #%s closed without merge; not dispatching.", pr_number)
            return
    logger.warning("PR #%s did not merge within %.0fs; skipping dispatch.", pr_number, timeout_s)


async def main_cli(goal: str) -> None:
    """Standalone entrypoint for quick manual testing."""
    logging.basicConfig(level=logging.INFO)
    llm = LLMClient()
    result = await author_task(llm, goal)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("usage: python -m magda_agent.cekirdek_bridge '<goal>'")
        sys.exit(1)
    asyncio.run(main_cli(sys.argv[1]))
