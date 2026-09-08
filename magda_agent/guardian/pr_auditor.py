#!/usr/bin/env python3
"""
Magda-Agent PR Code Auditor & Quality Gate.
Comprehensive CLI for PR code reviews, queue status diagnostics, and automated duplicate cleanup.
"""

import os
import sys
import json
import re
import urllib.request
import urllib.error
from typing import Tuple, Dict, Any, List, Optional

# Ensure repository root is in sys.path
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)


def _get_github_headers(token: Optional[str] = None) -> Dict[str, str]:
    auth_token = token or os.getenv("GH_PAT") or os.getenv("GITHUB_TOKEN", "")
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "Magda-Auditor/2.0",
    }
    if auth_token:
        headers["Authorization"] = f"Bearer {auth_token}"
    return headers


def get_open_prs(repo: str, token: Optional[str] = None) -> List[Dict[str, Any]]:
    """Fetches all currently open pull requests for a repository."""
    headers = _get_github_headers(token)
    url = f"https://api.github.com/repos/{repo}/pulls?state=open&per_page=100"
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"Error fetching open PRs: {e}")
        return []


def get_closed_prs(repo: str, token: Optional[str] = None, limit: int = 10) -> List[Dict[str, Any]]:
    """Fetches recently closed pull requests for a repository."""
    headers = _get_github_headers(token)
    url = f"https://api.github.com/repos/{repo}/pulls?state=closed&per_page={limit}"
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"Error fetching closed PRs: {e}")
        return []


def print_pr_status_report(repo: str, token: Optional[str] = None) -> None:
    """Prints a formatted diagnostic status report of the PR queue."""
    open_prs = get_open_prs(repo, token)
    closed_prs = get_closed_prs(repo, token, limit=5)

    print("\n" + "=" * 70)
    print(f"📊 MAGDA PULL REQUEST QUEUE STATUS: {repo}")
    print("=" * 70)
    print(f"Açık PR Sayısı: {len(open_prs)}")
    if open_prs:
        for pr in open_prs:
            num = pr.get("number")
            title = pr.get("title", "")
            user = pr.get("user", {}).get("login", "")
            branch = pr.get("head", {}).get("ref", "")
            created = pr.get("created_at", "")
            print(f" • PR #{num:2d}: [{user}] {title[:50]} (Branch: {branch}) - {created}")
    else:
        print(" ✅ Açık PR kuyruğu tertemiz (0 açık PR).")

    print("\nSon Kapanan / Merge Edilen PR'lar (İlk 5):")
    for pr in closed_prs:
        num = pr.get("number")
        title = pr.get("title", "")
        status = "MERGED ✅" if pr.get("merged_at") else "CLOSED 🛑"
        print(f" • PR #{num:2d} [{status}]: {title[:60]}")
    print("=" * 70 + "\n")


def auto_close_superseded_prs(current_pr_number: int, repo: str, token: Optional[str] = None) -> int:
    """Closes older open PRs that share similar titles or target the same feature."""
    headers = _get_github_headers(token)
    open_prs = get_open_prs(repo, token)
    if not open_prs:
        return 0

    current_pr = next((p for p in open_prs if p.get("number") == current_pr_number), None)
    if not current_pr:
        return 0

    cur_title = current_pr.get("title", "").lower()
    cur_words = set(re.findall(r"\w+", cur_title)) - {"feat", "fix", "chore", "the", "a", "and", "for", "in", "to"}

    closed_count = 0
    for pr in open_prs:
        pr_num = pr.get("number")
        if pr_num >= current_pr_number:
            continue

        p_title = pr.get("title", "").lower()
        p_words = set(re.findall(r"\w+", p_title)) - {"feat", "fix", "chore", "the", "a", "and", "for", "in", "to"}

        is_similar = len(cur_words.intersection(p_words)) >= 2
        is_jules_batch = "batch-01" in cur_title and "batch-01" in p_title
        is_push_notif = "push notification" in cur_title and "push notification" in p_title

        if is_similar or is_jules_batch or is_push_notif:
            try:
                # Add closing comment
                comment_payload = {
                    "body": f"🛑 Closed automatically by Magda AI Auditor: Superseded by PR #{current_pr_number} which contains the updated full implementation."
                }
                req_c = urllib.request.Request(
                    f"https://api.github.com/repos/{repo}/issues/{pr_num}/comments",
                    data=json.dumps(comment_payload).encode("utf-8"),
                    headers=headers,
                )
                urllib.request.urlopen(req_c, timeout=15)

                # Close PR
                close_payload = {"state": "closed"}
                req_close = urllib.request.Request(
                    f"https://api.github.com/repos/{repo}/pulls/{pr_num}",
                    data=json.dumps(close_payload).encode("utf-8"),
                    headers=headers,
                    method="PATCH",
                )
                urllib.request.urlopen(req_close, timeout=15)
                print(f"✅ Auto-closed older superseded PR #{pr_num} in favor of PR #{current_pr_number}.")
                closed_count += 1
            except Exception as e:
                print(f"Failed to auto-close PR #{pr_num}: {e}")

    return closed_count


def review_pr(
    pr_number: int,
    repo: str,
    token: str,
    openai_key: str,
    openai_base: str = "https://api.inceptionlabs.ai/v1",
    model: str = "mercury-2",
) -> Tuple[str, str, bool]:
    """Audits PR diff against security, syntax, and architectural standards using LLM."""
    headers = _get_github_headers(token)

    try:
        # 1. Auto-close superseded duplicate PRs first
        try:
            auto_close_superseded_prs(pr_number, repo, token)
        except Exception as e:
            print(f"Warning auto-closing superseded PRs: {e}")

        # 2. Fetch PR diff
        diff_headers = {**headers, "Accept": "application/vnd.github.v3.diff"}
        req_diff = urllib.request.Request(
            f"https://api.github.com/repos/{repo}/pulls/{pr_number}",
            headers=diff_headers,
        )
        with urllib.request.urlopen(req_diff, timeout=30) as resp:
            diff_text = resp.read().decode("utf-8")

        # 3. Fetch PR info
        req_info = urllib.request.Request(
            f"https://api.github.com/repos/{repo}/pulls/{pr_number}",
            headers=headers,
        )
        with urllib.request.urlopen(req_info, timeout=30) as resp:
            pr_info = json.loads(resp.read().decode("utf-8"))

        pr_title = pr_info.get("title", "")
        pr_body = pr_info.get("body", "")

        # Truncate diff if extremely large
        if len(diff_text) > 40000:
            diff_text = diff_text[:40000] + "\n...[DIFF TRUNCATED FOR SIZE]..."

        print(f"🔍 [Magda AI Quality Gate]: Auditing PR #{pr_number} on {repo} with {model}...")

        prompt = f"""PR #{pr_number}: {pr_title}
Repository: {repo}
Description:
{pr_body}

DIFF:
```diff
{diff_text}
```

Evaluate this pull request strictly according to:
1. Security & Authentication (SEC-001 to SEC-004): No hardcoded secrets, no unauthenticated mutations, CSRF validated, input rate limiting.
2. Syntax & AST: Clean imports, zero AST syntax breaks, proper error handling.
3. Quality & Test Coverage: Critical paths covered with tests.
4. Minimal Diff: Allowed paths respected.

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

        with urllib.request.urlopen(req_llm, timeout=45) as resp:
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
            with urllib.request.urlopen(req_post, timeout=15) as resp:
                print(f"✅ Review posted to PR #{pr_number}. Decision: [{verdict}] (Status: {resp.status})")
        except Exception as e:
            print(f"Review comment error: {e}")

        return verdict, review_text, blocking
    except Exception as e:
        err_msg = f"Auditor exception during review of PR #{pr_number}: {e}"
        print(f"❌ {err_msg}")
        return "CHANGES REQUESTED", err_msg, True

def main():
    args = sys.argv[1:]
    if not args:
        print("Magda-Agent PR Auditor CLI")
        print("Usage:")
        print("  python -m magda_agent.guardian.pr_auditor status [<REPO>]")
        print("  python -m magda_agent.guardian.pr_auditor cleanup <PR_NUMBER> [<REPO>]")
        print("  python -m magda_agent.guardian.pr_auditor review <PR_NUMBER> [<REPO>]")
        print("  python -m magda_agent.guardian.pr_auditor <PR_NUMBER> <REPO>  (legacy compat)")
        sys.exit(0)

    token = os.getenv("GH_PAT") or os.getenv("GITHUB_TOKEN", "")
    default_repo = "coruhoorhan/airbnb-app"

    cmd = args[0].lower()

    if cmd == "status":
        repo = args[1] if len(args) > 1 else default_repo
        print_pr_status_report(repo, token)
        sys.exit(0)

    elif cmd == "cleanup":
        if len(args) < 2:
            print("Usage: python -m magda_agent.guardian.pr_auditor cleanup <KEEP_PR_NUMBER> [<REPO>]")
            sys.exit(1)
        pr_num = int(args[1])
        repo = args[2] if len(args) > 2 else default_repo
        closed = auto_close_superseded_prs(pr_num, repo, token)
        print(f"✅ Total superseded PRs closed: {closed}")
        sys.exit(0)

    elif cmd == "review" or cmd.isdigit():
        pr_num = int(args[1]) if cmd == "review" else int(args[0])
        repo = args[2] if (cmd == "review" and len(args) > 2) else (args[1] if (cmd.isdigit() and len(args) > 1) else default_repo)

        openai_key = os.getenv("OPENAI_API_KEY", "")
        openai_base = os.getenv("OPENAI_BASE_URL", "https://api.inceptionlabs.ai/v1")
        model = os.getenv("OPENAI_MODEL", "mercury-2")

        if not token or not openai_key:
            print("❌ Missing GH_PAT/GITHUB_TOKEN or OPENAI_API_KEY environment variables.")
            sys.exit(1)

        verdict, _, blocking = review_pr(pr_num, repo, token, openai_key, openai_base, model)
        if blocking:
            print(f"❌ [QUALITY GATE BLOCKED]: PR #{pr_num} has BLOCKING findings. Auto-merge is HALTED.")
            sys.exit(1)
        else:
            print(f"🎉 [QUALITY GATE PASSED]: PR #{pr_num} approved by Auditor. Proceeding to Auto-Merge.")
            sys.exit(0)
    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)


if __name__ == "__main__":
    main()
