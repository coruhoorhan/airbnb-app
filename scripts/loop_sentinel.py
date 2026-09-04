#!/usr/bin/env python3
"""
Magda Loop Sentinel: finds loop failures BEFORE humans do.
Read-only health probe over the autonomous loop. Run hourly via cron or
manually. Exits 1 (red) when something needs attention, 0 when healthy.

RED conditions:
- expected workflow missing or inactive
- required secret name missing (names only, never values)
- agent_tasks.json invalid (parse / schema / duplicate ids / empty)
- a Jules session AWAITING input for >30min with no auto-responder reply
Everything else is informational.

Env: TARGET_REPO, GH_PAT (or GITHUB_TOKEN), JULES_API_KEY,
     OPENAI_API_KEY (presence NOT required; only GH + Jules are checked here)
"""

import json
import os
import sys
import urllib.request
import urllib.error
from datetime import datetime, timezone

GITHUB_API = "https://api.github.com"
JULES_BASE = "https://jules.googleapis.com/v1alpha"

EXPECTED_WORKFLOWS = [
    ".github/workflows/ci.yml",
    ".github/workflows/jules_automerge.yml",
    ".github/workflows/jules_next_task.yml",
    ".github/workflows/jules_responder.yml",
    ".github/workflows/jules_revise.yml",
    ".github/workflows/jules_queue_keeper.yml",
]
REQUIRED_SECRETS = {"JULES_API_KEY", "GH_PAT", "OPENAI_API_KEY"}
MARKER = "[Magda Auto-Responder]"
AWAIT_MINUTES = int(os.getenv("AWAIT_MINUTES", "30"))
TARGET_TITLES = [t.strip().lower()
                 for t in os.getenv("TARGET_TITLE",
                                    "Autonomous Airbnb,Revise airbnb-app PR,Revise PR #").split(",")]

red, info = [], []


def gh(path, token):
    req = urllib.request.Request(
        f"{GITHUB_API}{path}",
        headers={"Authorization": f"Bearer {token}",
                 "Accept": "application/vnd.github+json",
                 "User-Agent": "Magda-Loop-Sentinel"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read().decode("utf-8", errors="ignore")
        return json.loads(raw) if raw.strip() else {}


def jules(path, key):
    req = urllib.request.Request(
        f"{JULES_BASE}{path}",
        headers={"X-Goog-Api-Key": key, "Accept": "application/json"},
        method="GET")
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read().decode("utf-8", errors="ignore")
        return json.loads(raw) if raw.strip() else {}


def age_minutes(ts):
    try:
        dt = datetime.fromisoformat((ts or "").replace("Z", "+00:00"))
        return (datetime.now(timezone.utc) - dt).total_seconds() / 60.0
    except Exception:
        return 99999.0


def check_workflows(repo, token):
    try:
        data = gh(f"/repos/{repo}/actions/workflows", token)
        have = {w.get("path"): w.get("state") for w in data.get("workflows", [])}
        for path in EXPECTED_WORKFLOWS:
            if path not in have:
                red.append(f"workflow missing: {path}")
            elif have[path] != "active":
                red.append(f"workflow not active: {path} ({have[path]})")
            else:
                info.append(f"workflow OK: {path}")
    except Exception as e:
        red.append(f"workflow check failed: {e}")


def check_secrets(repo, token):
    try:
        data = gh(f"/repos/{repo}/actions/secrets", token)
        names = {s.get("name") for s in data.get("secrets", [])}
        missing = REQUIRED_SECRETS - names
        if missing:
            red.append(f"secrets missing: {sorted(missing)}")
        else:
            info.append(f"secrets OK: {sorted(names)}")
    except Exception as e:
        red.append(f"secret check failed: {e}")


def check_queue(repo, token):
    try:
        data = gh(f"/repos/{repo}/contents/agent_tasks.json?ref=main", token)
        import base64
        manifest = json.loads(base64.b64decode(data["content"]).decode("utf-8"))
        tasks = manifest.get("tasks", [])
        ids = [t.get("id") for t in tasks]
        if not tasks:
            red.append("queue empty: no tasks")
        if len(ids) != len(set(ids)):
            red.append("queue has duplicate task ids")
        bad = [t.get("id") for t in tasks
               if t.get("status") not in ("todo", "in_progress", "done", "blocked")]
        if bad:
            red.append(f"queue has invalid statuses: {bad[:5]}")
        todos = sum(1 for t in tasks if t.get("status") == "todo")
        info.append(f"queue OK: {len(tasks)} tasks, {todos} todo")
    except Exception as e:
        red.append(f"queue check failed: {e}")


def check_sessions(key):
    try:
        data = jules("/sessions?pageSize=20", key)
        sessions = data.get("sessions", []) if isinstance(data, dict) else []
        for s in sessions:
            state = s.get("state", "")
            title = s.get("title", "") or ""
            if not any(tt in title.lower() for tt in TARGET_TITLES):
                continue  # not our loop's session; out of scope
            if state not in ("AWAITING_USER_FEEDBACK", "AWAITING_PLAN_APPROVAL"):
                continue
            sid = s.get("id") or s.get("name", "").split("/")[-1]
            mins = age_minutes(s.get("updateTime", ""))
            try:
                acts = jules(f"/sessions/{sid}/activities?pageSize=10", key)
                act_list = acts.get("activities", []) if isinstance(acts, dict) else []
                answered = any(MARKER in json.dumps(a) for a in act_list)
            except Exception:
                answered = False
            if mins > AWAIT_MINUTES and not answered:
                red.append(f"session {sid} awaiting {mins:.0f}min with no auto-reply: "
                           f"{(s.get('title') or '')[:50]}")
            else:
                info.append(f"session {sid}: {state}, age {mins:.0f}min, answered={answered}")
    except Exception as e:
        red.append(f"session check failed: {e}")


def check_recent_failures(repo, token):
    try:
        data = gh(f"/repos/{repo}/actions/runs?per_page=10", token)
        for r in data.get("workflow_runs", []):
            if r.get("conclusion") == "failure" and age_minutes(r.get("created_at", "")) < 120:
                info.append(f"recent failure: {r.get('name', '')[:40]} "
                            f"{(r.get('display_title') or '')[:40]}")
    except Exception as e:
        info.append(f"failure scan skipped: {e}")


def main():
    repo = os.getenv("TARGET_REPO", "coruhoorhan/airbnb-app")
    token = os.getenv("GH_PAT") or os.getenv("GITHUB_TOKEN", "")
    key = os.getenv("JULES_API_KEY", "")
    if not token or not key:
        print("Missing GH_PAT or JULES_API_KEY."); sys.exit(1)
    check_workflows(repo, token)
    check_secrets(repo, token)
    check_queue(repo, token)
    check_sessions(key)
    check_recent_failures(repo, token)
    print("=== INFO ===")
    for line in info:
        print(f"  {line}")
    if red:
        print("=== RED (exit 1) ===")
        for line in red:
            print(f"  !! {line}")
        sys.exit(1)
    print("=== GREEN: loop healthy ===")
    sys.exit(0)


if __name__ == "__main__":
    main()
