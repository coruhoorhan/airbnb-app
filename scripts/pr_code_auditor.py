#!/usr/bin/env python3
"""
Magda AI Independent PR Code Auditor & Quality Gate (tiered).
Runs in GitHub Actions or locally to review PR diffs with Mercury-2 LLM,
posts formal code reviews to GitHub PRs, and enforces the merge blocker:
- BLOCKING YES (critical/high findings remain): Exits 1 (BLOCKS Auto-Merge).
- BLOCKING NO (only polish/medium-low remain): files ONE follow-up todo
  (pr<N>-hardening-followups) into agent_tasks.json on main, exits 0.
- APPROVED: Exits 0. Rule: max ONE follow-up todo per PR (quota-safe).
Fail-closed: unparseable verdicts block.
"""

import os
import sys
import json
import urllib.request
import urllib.error
import re
from typing import Dict, Any, Tuple

def review_pr(
    pr_number: int,
    repo: str,
    token: str,
    openai_key: str,
    openai_base: str,
    model: str,
    strict_block: bool = True
) -> Tuple[str, str]:
    print(f"🔍 [Magda AI Quality Gate]: Auditing PR #{pr_number} on {repo} with {model}...")
    
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "Magda-Code-Auditor"
    }
    
    # 1. Fetch PR details
    pr_url = f"https://api.github.com/repos/{repo}/pulls/{pr_number}"
    req = urllib.request.Request(pr_url, headers=headers)
    with urllib.request.urlopen(req) as resp:
        pr_data = json.load(resp)
    
    pr_title = pr_data.get("title", "")
    pr_body = pr_data.get("body", "")
    head_ref = pr_data.get("head", {}).get("ref", "")
    head_sha = pr_data.get("head", {}).get("sha", "")
    
    # 2. Fetch PR diff
    diff_headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3.diff",
        "User-Agent": "Magda-Code-Auditor"
    }
    req_diff = urllib.request.Request(pr_url, headers=diff_headers)
    with urllib.request.urlopen(req_diff) as resp:
        diff_text = resp.read().decode("utf-8", errors="ignore")
    
    if len(diff_text) > 14000:
        diff_text = diff_text[:14000] + "\n\n...[diff truncated for audit]..."
    
    # 3. Security Boundary Check (Tokens, Secrets, Dangerous Execution)
    danger_patterns = [
        r"ghp_[a-zA-Z0-9]{36}",
        r"sk_[a-zA-Z0-9]{32,}",
        r"eval\(",
        r"exec\(",
        r"DROP\s+TABLE",
        r"DELETE\s+FROM\s+users"
    ]
    for pat in danger_patterns:
        if re.search(pat, diff_text, re.IGNORECASE):
            print(f"🚨 CRITICAL SECURITY ALERT: Dangerous pattern detected matching '{pat}'!")
    
    # 4. Request LLM review from Mercury-2
    prompt = f"""You are Magda AI Senior Principal Code Auditor & Security Inspector (independent reviewer bot).
Your role is to strictly audit and verify the Pull Request submitted by Jules Worker.

PR #{pr_number}: {pr_title}
BRANCH: {head_ref}
DESCRIPTION: {pr_body}

GIT DIFF:
```diff
{diff_text}
```

AUDIT CRITERIA:
1. Security & Input Sanitization (XSS, SQL/Command Injection, NaN/out-of-bound inputs, rate limiting, authentication/authorization).
2. Correctness & Error Handling (Unhandled promise rejections, edge cases, error message detail leaks).
3. Code Quality, Modularity & Performance (Clean structure, no avoidable overhead, sensible abstractions).
4. Manifest & Test Coverage (Does it meet acceptance criteria and include proper tests?).

DECISION RULES (tiered gate - read carefully):
- CRITICAL/HIGH = exploitable vulnerability, auth bypass, injection, secret leak,
  broken access control, data loss, unhandled crash on main paths. If ANY remain:
  Output VERDICT: CHANGES REQUESTED and BLOCKING: YES.
- MEDIUM/LOW = hardening & polish (signed cookies, CSP headers, dep pinning, log
  hygiene, docs, micro-perf, style). List them with severity, but output
  VERDICT: CHANGES REQUESTED and BLOCKING: NO. These become ONE follow-up task;
  they must NOT block this PR.
- If nothing to report: VERDICT: APPROVED and BLOCKING: NO.

OUTPUT FORMAT (Strict Markdown):
Line 1 must be:
VERDICT: [APPROVED | CHANGES REQUESTED]
Line 2 must be:
BLOCKING: [YES | NO]
Every findings table MUST have a Severity column with exactly one of
CRITICAL, HIGH, MEDIUM, LOW per row.

Then follow with:
## 🛡️ Audit Verdict: [APPROVED | CHANGES REQUESTED]
## 🔍 Security & Integrity Analysis (Table of Area, Observation, Recommendation)
## ⚡ Performance & Architecture Review (Table)
## 📝 Detailed Feedback & Fix Recommendations (with concrete code examples)
## 🎯 Conclusion"""

    llm_payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You are Magda AI Principal Code Auditor, an independent security and quality gate review bot for GitHub PRs."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.2,
        "max_tokens": 1600
    }
    
    req_llm = urllib.request.Request(
        f"{openai_base}/chat/completions",
        data=json.dumps(llm_payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {openai_key}",
            "Content-Type": "application/json",
            "User-Agent": "Magda-Auditor"
        }
    )
    
    with urllib.request.urlopen(req_llm) as resp:
        llm_resp = json.load(resp)
        review_content = llm_resp["choices"][0]["message"]["content"]
    
    # 5. Extract verdict + blocking flag (fail-closed: unparseable => block).
    upper = review_content.upper()
    verdict = "CHANGES_REQUESTED"
    if "VERDICT: APPROVED" in upper:
        verdict = "APPROVED"
    elif "VERDICT: CHANGES REQUESTED" in upper or "CHANGES REQUESTED" in upper:
        verdict = "CHANGES_REQUESTED"

    blocking = True
    m = re.search(r"^BLOCKING:\s*(YES|NO)\s*$", review_content,
                  re.MULTILINE | re.IGNORECASE)
    if m:
        blocking = (m.group(1).upper() == "YES")
    print(f"Gate decision: verdict={verdict} blocking={blocking}")
    
    review_body = f"## 🤖 Magda AI Independent Code Auditor Quality Gate\n\n{review_content}\n\n---\n*Audited autonomously by Inception Labs Mercury-2 Cognitive Quality Gate.*"
    
    # 6. Post review to GitHub PR.
    # NOTE: Always use COMMENT (never APPROVE): GitHub rejects APPROVE reviews
    # with 422 when reviewer == PR author (Jules opens PRs via the owner's
    # account). The gate decision is enforced via process exit code below,
    # not via GitHub approval state. On 422, fall back to an issue comment.
    post_review_url = f"https://api.github.com/repos/{repo}/pulls/{pr_number}/reviews"
    review_post_payload = {
        "body": review_body,
        "event": "COMMENT"
    }

    req_post = urllib.request.Request(
        post_review_url,
        data=json.dumps(review_post_payload).encode("utf-8"),
        headers={
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json",
            "Content-Type": "application/json"
        },
        method="POST"
    )

    try:
        with urllib.request.urlopen(req_post) as resp:
            print(f"✅ Review posted to PR #{pr_number}. Decision: [{verdict}] (Status: {resp.status})")
    except urllib.error.HTTPError as post_err:
        print(f"⚠️ PR review POST failed ({post_err.code}); falling back to issue comment.")
        issue_comment_url = f"https://api.github.com/repos/{repo}/issues/{pr_number}/comments"
        req_fallback = urllib.request.Request(
            issue_comment_url,
            data=json.dumps({"body": review_body}).encode("utf-8"),
            headers={
                "Authorization": f"token {token}",
                "Accept": "application/vnd.github.v3+json",
                "Content-Type": "application/json"
            },
            method="POST"
        )
        with urllib.request.urlopen(req_fallback) as resp_fb:
            print(f"✅ Fallback comment posted to PR #{pr_number}. Decision: [{verdict}] (Status: {resp_fb.status})")
    
    # 7. Write local summary artifact
    with open("audit_verdict.json", "w", encoding="utf-8") as f:
        json.dump({
            "pr_number": pr_number,
            "verdict": verdict,
            "blocking": blocking,
            "passed": (verdict == "APPROVED" or not blocking),
            "followup_filed": False,
            "head_ref": head_ref,
            "head_sha": head_sha
        }, f, indent=2)

    return verdict, review_body, blocking


def file_followup_todo(repo: str, token: str, pr_number: int) -> bool:
    """Append ONE polish follow-up todo (pr<N>-hardening-followups) to main's
    queue. Deduplicated by id. Returns True if a new todo was filed.
    Writer failures must never block the merge (caller wraps in try/except)."""
    import base64
    todo_id = f"pr{pr_number}-hardening-followups"
    api_headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "Content-Type": "application/json",
        "User-Agent": "Magda-Followup-Writer"
    }
    meta_url = f"https://api.github.com/repos/{repo}/contents/agent_tasks.json?ref=main"
    with urllib.request.urlopen(
            urllib.request.Request(meta_url, headers=api_headers)) as resp:
        meta = json.load(resp)
    data = json.loads(base64.b64decode(meta["content"]).decode("utf-8"))
    tasks = data.get("tasks", [])
    if any(t.get("id") == todo_id for t in tasks):
        print(f"Follow-up {todo_id} already in queue; skipping.")
        return False

    files_url = f"https://api.github.com/repos/{repo}/pulls/{pr_number}/files?per_page=30"
    with urllib.request.urlopen(
            urllib.request.Request(files_url, headers=api_headers)) as resp:
        files = json.load(resp)
    paths = set()
    for f in files:
        name = f.get("filename", "")
        top = name.split("/")[0] if "/" in name else name
        if top and not top.startswith("."):
            paths.add(top if "/" in name else name)
    allowed = sorted(paths)[:6] or ["src/"]

    review_url = f"https://github.com/{repo}/pull/{pr_number}"
    tasks.append({
        "id": todo_id,
        "status": "todo",
        "area": "security",
        "risk": "low",
        "title": f"PR #{pr_number} auditor polish follow-ups",
        "description": (
            f"Address the non-blocking (MEDIUM/LOW) polish findings from the "
            f"Magda AI auditor review on {review_url}. Read the latest auditor "
            f"review on that PR and implement every MEDIUM/LOW item. Do NOT "
            f"re-litigate BLOCKING items; those gate the original PR."),
        "allowed_paths": allowed,
        "acceptance": [
            f"All MEDIUM/LOW auditor findings on PR #{pr_number} addressed",
            "Repo test suite green",
            "No new BLOCKING findings"
        ]
    })
    data["tasks"] = tasks
    new_content = base64.b64encode(
        (json.dumps(data, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    ).decode("utf-8")
    put_payload = {
        "message": f"chore(queue): add {todo_id} polish follow-ups for PR #{pr_number}",
        "content": new_content,
        "sha": meta["sha"],
        "branch": "main"
    }
    with urllib.request.urlopen(urllib.request.Request(
            f"https://api.github.com/repos/{repo}/contents/agent_tasks.json",
            data=json.dumps(put_payload).encode("utf-8"),
            headers=api_headers, method="PUT")) as resp:
        print(f"Follow-up todo filed on main (HTTP {resp.status}).")
    return True


if __name__ == "__main__":
    pr_num = int(sys.argv[1]) if len(sys.argv) > 1 else 8
    repo = sys.argv[2] if len(sys.argv) > 2 else "coruhoorhan/airbnb-app"
    token = os.getenv("GH_PAT") or os.getenv("GITHUB_TOKEN")
    openai_key = os.getenv("OPENAI_API_KEY")
    openai_base = os.getenv("OPENAI_BASE_URL", "https://api.inceptionlabs.ai/v1")
    model = os.getenv("OPENAI_MODEL", "mercury-2")
    strict = "--no-block" not in sys.argv
    
    if not token or not openai_key:
        print("Missing required tokens (GH_PAT or OPENAI_API_KEY).")
        sys.exit(1)
        
    verdict, _, blocking = review_pr(pr_num, repo, token, openai_key, openai_base, model, strict_block=strict)

    if verdict != "APPROVED" and blocking:
        print(f"\n❌ [QUALITY GATE BLOCKED]: PR #{pr_num} has BLOCKING findings. Auto-merge is HALTED until issues are resolved.")
        if strict:
            sys.exit(1)
    elif verdict != "APPROVED" and not blocking:
        print(f"\n⚠️ [QUALITY GATE PASSED WITH FOLLOW-UPS]: PR #{pr_num} has only polish findings. Filing ONE follow-up todo.")
        try:
            filed = file_followup_todo(repo, token, pr_num)
            if filed:
                with open("audit_verdict.json", "w", encoding="utf-8") as f:
                    json.dump({"pr_number": pr_num, "verdict": verdict,
                               "blocking": False, "passed": True,
                               "followup_filed": True}, f, indent=2)
        except Exception as e:
            print(f"⚠️ Follow-up writer failed ({e}); merge proceeds anyway.")
        print(f"🎉 Proceeding to Auto-Merge.")
        sys.exit(0)
    else:
        print(f"\n🎉 [QUALITY GATE PASSED]: PR #{pr_num} APPROVED by Magda AI Auditor. Proceeding to Auto-Merge.")
        sys.exit(0)
