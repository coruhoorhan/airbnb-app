#!/usr/bin/env python3
"""
Magda Autonomous Jules Responder.
Polls Jules sessions for this repo, detects sessions stuck waiting for human
input (AWAITING_USER_FEEDBACK / AWAITING_PLAN_APPROVAL), drafts an autonomous
answer via Mercury-2 LLM under a strict no-human policy, and sends it back via
the Jules API so the loop continues with no human in the loop.

Safety:
- Only touches sessions whose title matches our autonomous loop.
- Only considers recently updated sessions (default: last 2h).
- Never answers the same question twice (detects our own marker replies).
- Circuit breaker: after MAX_ANSWERS auto-answers with no progress, stops and
  opens a GitHub issue asking for human review.
- --dry-run logs decisions without POSTing anything.

Env:
  JULES_API_KEY   (required)  Jules API key (X-Goog-Api-Key header)
  OPENAI_API_KEY  (required)  Mercury-2 key for drafting answers
  OPENAI_BASE_URL (optional)  default https://api.inceptionlabs.ai/v1
  OPENAI_MODEL    (optional)  default mercury-2
  GH_PAT          (optional)  for opening escalation issues (fallback GITHUB_TOKEN)
  TARGET_TITLE    (optional)  session title substring, default "Autonomous Airbnb"
  MAX_AGE_HOURS   (optional)  default 2
  MAX_ANSWERS     (optional)  default 3
"""

import json
import os
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone

JULES_BASE = "https://jules.googleapis.com/v1alpha"
MARKER = "[Magda Auto-Responder]"
MAX_DIFF_CHARS = 6000

POLICY = (
    "You are fully autonomous. There is NO human to answer questions. "
    "Decide and proceed on your own. If ambiguous, pick the safest reasonable "
    "option, note it in the PR body, and continue. When the task is complete, "
    "open ONE complete PR immediately without asking for confirmation."
)


def jules_request(method, path, api_key, payload=None):
    url = f"{JULES_BASE}{path}"
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "X-Goog-Api-Key": api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method=method,
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        raw = resp.read().decode("utf-8", errors="ignore")
        return json.loads(raw) if raw.strip() else {}


def list_sessions(api_key, page_size=20):
    data = jules_request("GET", f"/sessions?pageSize={page_size}", api_key)
    if isinstance(data, dict):
        return data.get("sessions", [])
    return data if isinstance(data, list) else []


def get_activities(api_key, session_id, page_size=30):
    data = jules_request(
        "GET", f"/sessions/{session_id}/activities?pageSize={page_size}", api_key
    )
    if isinstance(data, dict):
        return data.get("activities", [])
    return data if isinstance(data, list) else []


def extract_texts(obj, out, depth=0):
    """Generically pull human-readable strings out of activity JSON."""
    if depth > 6:
        return
    if isinstance(obj, dict):
        for k, v in obj.items():
            kl = str(k).lower()
            if isinstance(v, str) and any(
                t in kl for t in ("text", "message", "content", "question", "prompt", "summary", "description")
            ):
                s = v.strip()
                if len(s) > 10:
                    out.append(s)
            else:
                extract_texts(v, out, depth + 1)
    elif isinstance(obj, list):
        for v in obj:
            extract_texts(v, out, depth + 1)


def latest_agent_text(activities):
    """Return (text, is_question_like) of the newest agent message, or (None, False).

    Activities are sorted newest-first by createTime. The agent message text is
    read from agentMessaged.agentMessage (falling back to generic extraction).
    NOTE: when the session state is AWAITING_USER_FEEDBACK, the state itself is
    the signal - the caller answers regardless of question-like heuristics.
    """
    def ts(act):
        try:
            return datetime.fromisoformat(
                act.get("createTime", "1970-01-01T00:00:00Z").replace("Z", "+00:00"))
        except Exception:
            return datetime(1970, 1, 1, tzinfo=timezone.utc)

    for act in sorted(activities, key=ts, reverse=True):
        if act.get("originator") != "agent":
            continue
        blob = ""
        am = act.get("agentMessaged") or {}
        if isinstance(am, dict) and am.get("agentMessage"):
            blob = am["agentMessage"]
        else:
            texts = []
            extract_texts(act, texts)
            blob = " ".join(texts)
        blob = blob.strip()
        if MARKER in blob:
            continue
        if blob:
            q = ("?" in blob) or any(
                w in blob.lower()
                for w in ("should i", "do you want", "confirm", "approve", "awaiting", "need your", "please let me know", "which one", "would you like")
            )
            return blob[:MAX_DIFF_CHARS], q
    return None, False


def our_answer_count(activities):
    n = 0
    for act in activities:
        if MARKER in json.dumps(act):
            n += 1
    return n


def draft_answer(openai_key, base, model, session_title, agent_text):
    prompt = (
        "You are Magda, the autonomous supervisor of an AI coding loop. "
        f"Policy: {POLICY}\n\n"
        f"Jules session title: {session_title}\n"
        f"Jules' latest message:\n{agent_text}\n\n"
        "Write the short, direct reply to send to Jules (max 5 sentences) that "
        "unblocks it autonomously. If it asks whether to open a PR, say YES and "
        "tell it to open it now. Do not ask anything back."
    )
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You are Magda, an autonomous engineering supervisor. You never ask humans anything."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
        "max_tokens": 300,
    }
    req = urllib.request.Request(
        f"{base}/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {openai_key}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=90) as resp:
        data = json.load(resp)
    return data["choices"][0]["message"]["content"].strip()


def open_escalation_issue(repo, token, session_id, session_url, answers_sent):
    url = f"https://api.github.com/repos/{repo}/issues"
    body = (
        f"Jules session `{session_id}` ({session_url}) is still waiting for input "
        f"after {answers_sent} autonomous answers. The responder circuit breaker tripped. "
        "A human should take a look."
    )
    payload = {"title": f"[magda] Jules session needs human: {session_id}", "body": body,
               "labels": ["needs-human-review", "jules"]}
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json",
                 "Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=30) as resp:
        print(f"Escalation issue opened (HTTP {resp.status}).")


def parse_age_hours(ts):
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return (datetime.now(timezone.utc) - dt).total_seconds() / 3600.0
    except Exception:
        return 999.0


def main():
    dry_run = "--dry-run" in sys.argv
    api_key = os.getenv("JULES_API_KEY", "")
    openai_key = os.getenv("OPENAI_API_KEY", "")
    base = os.getenv("OPENAI_BASE_URL", "https://api.inceptionlabs.ai/v1")
    model = os.getenv("OPENAI_MODEL", "mercury-2")
    repo = os.getenv("TARGET_REPO", "coruhoorhan/airbnb-app")
    gh_token = os.getenv("GH_PAT") or os.getenv("GITHUB_TOKEN", "")
    target_title = os.getenv("TARGET_TITLE", "Autonomous Airbnb")
    max_age = float(os.getenv("MAX_AGE_HOURS", "2"))
    max_answers = int(os.getenv("MAX_ANSWERS", "3"))

    if not api_key:
        print("Missing JULES_API_KEY."); sys.exit(1)
    if not openai_key:
        print("Missing OPENAI_API_KEY."); sys.exit(1)

    sessions = list_sessions(api_key)
    print(f"Found {len(sessions)} sessions. dry_run={dry_run}")
    acted = 0

    for s in sessions:
        sid = s.get("id") or s.get("name", "").split("/")[-1]
        title = s.get("title", "")
        state = s.get("state", "")
        update_time = s.get("updateTime", "")
        age_h = parse_age_hours(update_time)
        print(f"- {sid} | {title[:60]} | state={state} | age={age_h:.1f}h")

        if target_title.lower() not in (title or "").lower():
            continue
        if age_h > max_age:
            print("  skip: stale session."); continue
        if state not in ("AWAITING_USER_FEEDBACK", "AWAITING_PLAN_APPROVAL"):
            continue

        if state == "AWAITING_PLAN_APPROVAL":
            print("  plan approval needed.")
            if dry_run:
                print("  [dry-run] would POST approvePlan."); continue
            try:
                jules_request("POST", f"/sessions/{sid}:approvePlan", api_key, {})
                print("  plan approved."); acted += 1; continue
            except urllib.error.HTTPError as e:
                print(f"  approvePlan failed ({e.code}); falling back to sendMessage.")

        activities = get_activities(api_key, sid)
        agent_text, is_q = latest_agent_text(activities)
        sent = our_answer_count(activities)
        print(f"  our answers so far: {sent}, latest agent msg question-like: {is_q}")
        if sent >= max_answers:
            print("  circuit breaker tripped.")
            if not dry_run and gh_token:
                try:
                    open_escalation_issue(repo, gh_token, sid, s.get("url", ""), sent)
                except Exception as e:
                    print(f"  escalation failed: {e}")
            continue
        if not agent_text:
            print("  no agent text found; skipping."); continue

        try:
            answer = draft_answer(openai_key, base, model, title, agent_text)
        except Exception as e:
            print(f"  LLM draft failed ({e}); using canned policy reply.")
            answer = ("Yes — proceed autonomously per policy. Do not wait for human input. "
                      "Complete the task and open ONE complete PR immediately.")

        final = f"{MARKER}\n{answer}"
        print(f"  reply: {answer[:300]}")
        if dry_run:
            print("  [dry-run] would sendMessage."); continue
        jules_request("POST", f"/sessions/{sid}:sendMessage", api_key, {"prompt": final})
        print("  message sent."); acted += 1

    print(f"Done. Sessions acted on: {acted}")
    # Responder finding nothing to do is healthy, not a failure.
    sys.exit(0)


if __name__ == "__main__":
    main()
