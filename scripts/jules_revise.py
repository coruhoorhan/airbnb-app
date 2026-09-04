#!/usr/bin/env python3
"""
Magda Jules Revision Trigger.
Closes the auditor -> Jules feedback loop: when the Magda AI auditor leaves
CHANGES REQUESTED on a PR, this script opens a Jules revision session that
starts from the PR's own branch, instructs Jules to fix every finding, and
push to the SAME branch (no new PR).

Usage (env): PR_NUMBER, TARGET_REPO, GH_PAT (or GITHUB_TOKEN), JULES_API_KEY
"""

import json
import os
import sys
import urllib.request
import urllib.error

JULES_BASE = "https://jules.googleapis.com/v1alpha"
GITHUB_API = "https://api.github.com"
MAX_FINDINGS_CHARS = 9000


def gh(path, token, method="GET", payload=None):
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(
        f"{GITHUB_API}{path}", data=data, method=method,
        headers={"Authorization": f"Bearer {token}",
                 "Accept": "application/vnd.github+json",
                 "Content-Type": "application/json",
                 "User-Agent": "Magda-Revise-Trigger"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        raw = resp.read().decode("utf-8", errors="ignore")
        return json.loads(raw) if raw.strip() else {}


def main():
    pr_number = os.getenv("PR_NUMBER") or (sys.argv[1] if len(sys.argv) > 1 else "")
    repo = os.getenv("TARGET_REPO", "coruhoorhan/airbnb-app")
    gh_token = os.getenv("GH_PAT") or os.getenv("GITHUB_TOKEN", "")
    jules_key = os.getenv("JULES_API_KEY", "")
    if not pr_number or not gh_token or not jules_key:
        print("Missing PR_NUMBER, GH_PAT or JULES_API_KEY."); sys.exit(1)

    pr = gh(f"/repos/{repo}/pulls/{pr_number}", gh_token)
    if pr.get("state") == "closed":
        print(f"PR #{pr_number} is already closed; nothing to revise."); sys.exit(0)
    head_ref = (pr.get("head") or {}).get("ref", "")
    if not head_ref:
        print("Could not resolve PR head branch."); sys.exit(1)
    print(f"PR #{pr_number} head branch: {head_ref}")

    reviews = gh(f"/repos/{repo}/pulls/{pr_number}/reviews?per_page=30", gh_token)
    matches = [r for r in reviews
               if "Magda AI Independent Code Auditor" in (r.get("body") or "")
               and "CHANGES REQUESTED" in (r.get("body") or "")]
    max_rev = int(os.getenv("MAX_AUTO_REVISIONS", "3"))
    print(f"Auditor rejections so far: {len(matches)} (max auto-revisions: {max_rev})")
    if len(matches) >= max_rev:
        print(f"CIRCUIT BREAKER: PR #{pr_number} rejected {len(matches)} times. "
              "Needs human review; will not open another session.")
        sys.exit(2)
    findings = ""
    for r in matches:
        findings = r.get("body") or ""  # latest match wins
    if not findings:
        print("No CHANGES REQUESTED auditor review found; nothing to revise."); sys.exit(0)
    findings = findings[:MAX_FINDINGS_CHARS]
    print(f"Auditor findings: {len(findings)} chars.")

    prompt = (
        f"You are continuing work on PR #{pr_number} (branch {head_ref}).\n"
        "The Magda AI auditor reviewed your PR and returned CHANGES REQUESTED.\n"
        "TASK: fix EVERY finding below, commit, and push to the SAME branch "
        f"({head_ref}). Do NOT open a new PR. The existing PR updates automatically.\n"
        "RULES: implement all security fixes (httpOnly, sameSite, rate limiting, "
        "validation, helmet, CORS, JWT expiry, minimal claims). Keep tests green. "
        "Update agent_tasks.json only if the task is not yet marked done.\n"
        "FULLY AUTONOMOUS: never ask questions, never wait. Push when done.\n\n"
        f"AUDITOR FINDINGS:\n{findings}"
    )
    payload = {
        "prompt": prompt,
        "sourceContext": {"source": f"sources/github/{repo}",
                          "githubRepoContext": {"startingBranch": head_ref}},
        "automationMode": "AUTO_CREATE_PR",
        "title": f"Revise PR #{pr_number} per auditor findings",
    }
    req = urllib.request.Request(
        f"{JULES_BASE}/sessions", data=json.dumps(payload).encode("utf-8"),
        headers={"X-Goog-Api-Key": jules_key, "Content-Type": "application/json"},
        method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="ignore") or "{}")
    except urllib.error.HTTPError as e:
        print(f"Jules session creation failed: HTTP {e.code} {e.read().decode()[:300]}")
        sys.exit(1)
    print(f"Revision session created: {data.get('name')} url={data.get('url')}")


if __name__ == "__main__":
    main()
