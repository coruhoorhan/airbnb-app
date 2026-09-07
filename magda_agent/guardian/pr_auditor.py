"""
Magda-Agent PR Code Auditor & Quality Gate.
Standardized module location under magda_agent.guardian.pr_auditor.
"""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.request
from typing import Any, Dict, Tuple


def auto_close_superseded_prs(repo: str, token: str, current_pr_number: int, current_title: str) -> None:
    """Automatically closes older open PRs that are superseded by current_pr_number."""
    try:
        headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "Magda-Code-Auditor",
        }
        req = urllib.request.Request(f"https://api.github.com/repos/{repo}/pulls?state=open", headers=headers)
        with urllib.request.urlopen(req, timeout=30) as resp:
            open_prs = json.load(resp)
        for opr in open_prs:
            op_num = opr.get("number")
            op_title = opr.get("title", "")
            if op_num != current_pr_number:
                if any(kw in op_title.lower() for kw in ["audit", "hardening", "pr10", "pr12", "pr15", "followup"]) or (len(op_title) > 10 and op_title[:15] in current_title):
                    req_close = urllib.request.Request(
                        f"https://api.github.com/repos/{repo}/pulls/{op_num}",
                        headers=headers,
                        data=json.dumps({"state": "closed"}).encode(),
                        method="PATCH",
                    )
                    urllib.request.urlopen(req_close, timeout=15)
                    req_com = urllib.request.Request(
                        f"https://api.github.com/repos/{repo}/issues/{op_num}/comments",
                        headers=headers,
                        data=json.dumps({"body": f"🤖 Magda: Bu PR kapatıldı. Değişiklikler PR #{current_pr_number} altında birleştirildi."}).encode(),
                        method="POST",
                    )
                    urllib.request.urlopen(req_com, timeout=15)
                    print(f"✅ Auto-closed older superseded PR #{op_num} in favor of PR #{current_pr_number}.")
    except Exception as e:
        print(f"Auto-close check error: {e}")


def review_pr(
    pr_number: int,
    repo: str,
    token: str,
    openai_key: str,
    openai_base: str,
    model: str,
    strict_block: bool = True,
) -> Tuple[str, str, bool]:
    print(f"🔍 [Magda AI Quality Gate]: Auditing PR #{pr_number} on {repo} with {model}...")
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "Magda-Code-Auditor",
    }

    pr_url = f"https://api.github.com/repos/{repo}/pulls/{pr_number}"
    req = urllib.request.Request(pr_url, headers=headers)
    with urllib.request.urlopen(req) as resp:
        pr_data = json.load(resp)

    pr_title = pr_data.get("title", "")
    pr_body = pr_data.get("body", "")
    head_ref = pr_data.get("head", {}).get("ref", "")
    head_sha = pr_data.get("head", {}).get("sha", "")

    # Clean up older duplicate PRs
    auto_close_superseded_prs(repo, token, pr_number, pr_title)

    diff_url = f"https://api.github.com/repos/{repo}/pulls/{pr_number}"
    diff_headers = headers.copy()
    diff_headers["Accept"] = "application/vnd.github.v3.diff"
    req_diff = urllib.request.Request(diff_url, headers=diff_headers)
    with urllib.request.urlopen(req_diff) as resp:
        diff_text = resp.read().decode("utf-8", errors="ignore")

    max_chars = 12000
    if len(diff_text) > max_chars:
        diff_text = diff_text[:max_chars] + "\n\n[... Diff truncated for context limit ...]"

    prompt = f"""PR #{pr_number}: {pr_title}
BRANCH: {head_ref}
DESCRIPTION: {pr_body}

GIT DIFF:
```diff
{diff_text}
```

DETERMINISTIC ARCHITECTURE & SECURITY RULES:
- SEC-001 (CSRF): All state-changing mutation endpoints (POST/PUT/DELETE/PATCH) must validate x-csrf-token.
- SEC-002 (SQL Injection): Raw SQL string interpolation forbidden. Prepared statements (?) mandatory.
- SEC-003 (Auth Security): Cookie flags (HttpOnly, SameSite, Secure) & JWT expiration limits.
- SEC-004 (Rate Limiting): Public mutation & auth routes protected with sliding window rate limiters.
- SEC-005 (CSP): No upgrade-insecure-requests on non-HTTPS environments; valid font/image/style sources.
- QUAL-001 (Scope Bounding): Changes strictly within allowed_paths.
- QUAL-002 (Test Coverage): New routes/engines must have corresponding tests in tests/.
- QUAL-003 (AST Integrity): No broken syntax or invalid JSX tags.
- QUAL-004 (WCAG Accessibility): Button aria-labels, click div role=button, tabIndex={{0}}, onKeyDown.

DECISION RULES:
- CRITICAL/HIGH = exploitable vulnerability, auth bypass, injection, secret leak, broken access control, unhandled crash. If ANY remain:
  Output VERDICT: CHANGES REQUESTED and BLOCKING: YES.
- MEDIUM/LOW = hardening & polish (signed cookies, dep pinning, log hygiene, docs). List them, but output:
  VERDICT: CHANGES REQUESTED and BLOCKING: NO.
- If clean: VERDICT: APPROVED and BLOCKING: NO.

OUTPUT FORMAT (Strict plain text first two lines):
Line 1: VERDICT: [APPROVED | CHANGES REQUESTED]
Line 2: BLOCKING: [YES | NO]

Then follow with Markdown review report."""

    llm_payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You are Magda AI Principal Code Auditor, an independent security and quality inspector."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
        "max_tokens": 1600,
    }

    req_llm = urllib.request.Request(
        f"{openai_base}/chat/completions",
        data=json.dumps(llm_payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {openai_key}",
            "Content-Type": "application/json",
            "User-Agent": "Magda-Auditor",
        },
    )

    with urllib.request.urlopen(req_llm) as resp:
        llm_resp = json.load(resp)

    review_text = llm_resp["choices"][0]["message"]["content"]
    v_match = re.search(r"VERDICT:\s*(APPROVED|CHANGES REQUESTED)", review_text, re.I)
    b_match = re.search(r"BLOCKING:\s*(YES|NO)", review_text, re.I)

    verdict = v_match.group(1).upper() if v_match else "CHANGES REQUESTED"
    blocking = (b_match.group(1).upper() == "YES") if b_match else True

    # Post review comment to GitHub PR
    review_payload = {
        "body": f"## 🤖 Magda AI Independent Code Auditor Quality Gate\n\n{review_text}\n\n---\n*Audited autonomously by Inception Labs Mercury-2 Cognitive Quality Gate.*",
        "event": "COMMENT",
    }
    req_post = urllib.request.Request(
        f"https://api.github.com/repos/{repo}/pulls/{pr_number}/reviews",
        data=json.dumps(review_payload).encode("utf-8"),
        headers=headers,
    )
    try:
        with urllib.request.urlopen(req_post) as resp:
            print(f"✅ Review posted to PR #{pr_number}. Decision: [{verdict}] (Status: {resp.status})")
    except Exception as e:
        print(f"Review comment error: {e}")

    return verdict, review_text, blocking


def main():
    if len(sys.argv) < 3:
        print("Usage: python -m magda_agent.guardian.pr_auditor <PR_NUMBER> <REPO>")
        sys.exit(1)

    pr_num = int(sys.argv[1])
    repo = sys.argv[2]

    token = os.getenv("GH_PAT") or os.getenv("GITHUB_TOKEN", "")
    openai_key = os.getenv("OPENAI_API_KEY", "")
    openai_base = os.getenv("OPENAI_BASE_URL", "https://api.inceptionlabs.ai/v1")
    model = os.getenv("OPENAI_MODEL", "mercury-2")

    if not token or not openai_key:
        print("❌ Missing GH_PAT or OPENAI_API_KEY environment variables.")
        sys.exit(1)

    verdict, _, blocking = review_pr(pr_num, repo, token, openai_key, openai_base, model)

    if blocking:
        print(f"❌ [QUALITY GATE BLOCKED]: PR #{pr_num} has BLOCKING findings. Auto-merge is HALTED.")
        sys.exit(1)
    else:
        print(f"🎉 [QUALITY GATE PASSED]: PR #{pr_num} approved by Auditor. Proceeding to Auto-Merge.")
        sys.exit(0)


if __name__ == "__main__":
    main()
