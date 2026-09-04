#!/usr/bin/env python3
"""
Magda AI Independent PR Code Auditor & Quality Gate.
Runs in GitHub Actions or locally to review PR diffs with Mercury-2 LLM,
posts formal code reviews to GitHub PRs, and strictly enforces the merge blocker:
- If verdict is APPROVED: Exits with 0 (allows Auto-Merge).
- If verdict is CHANGES_REQUESTED or CRITICAL_FAIL: Exits with 1 (BLOCKS Auto-Merge).
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

DECISION RULES:
- If there are critical security bugs, NaN errors, unhandled exceptions, or missing authorization: Output VERDICT: CHANGES REQUESTED.
- If the code is secure, well-tested, handles edge-cases, and meets all criteria: Output VERDICT: APPROVED.

OUTPUT FORMAT (Strict Markdown):
Line 1 must be:
VERDICT: [APPROVED | CHANGES REQUESTED]

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
    
    # 5. Extract verdict
    verdict = "CHANGES_REQUESTED"
    if "VERDICT: APPROVED" in review_content.upper():
        verdict = "APPROVED"
    elif "VERDICT: CHANGES REQUESTED" in review_content.upper() or "CHANGES REQUESTED" in review_content.upper():
        verdict = "CHANGES_REQUESTED"
    
    review_body = f"## 🤖 Magda AI Independent Code Auditor Quality Gate\n\n{review_content}\n\n---\n*Audited autonomously by Inception Labs Mercury-2 Cognitive Quality Gate.*"
    
    # 6. Post review to GitHub PR
    post_review_url = f"https://api.github.com/repos/{repo}/pulls/{pr_number}/reviews"
    review_post_payload = {
        "body": review_body,
        "event": "APPROVE" if verdict == "APPROVED" else "COMMENT"
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
    
    with urllib.request.urlopen(req_post) as resp:
        print(f"✅ Review posted to PR #{pr_number}. Decision: [{verdict}] (Status: {resp.status})")
    
    # 7. Write local summary artifact
    with open("audit_verdict.json", "w", encoding="utf-8") as f:
        json.dump({
            "pr_number": pr_number,
            "verdict": verdict,
            "passed": (verdict == "APPROVED"),
            "head_ref": head_ref,
            "head_sha": head_sha
        }, f, indent=2)
    
    return verdict, review_body


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
        
    verdict, _ = review_pr(pr_num, repo, token, openai_key, openai_base, model, strict_block=strict)
    
    if verdict != "APPROVED":
        print(f"\n❌ [QUALITY GATE BLOCKED]: PR #{pr_num} received verdict '{verdict}'. Auto-merge is HALTED until issues are resolved.")
        if strict:
            sys.exit(1)
    else:
        print(f"\n🎉 [QUALITY GATE PASSED]: PR #{pr_num} APPROVED by Magda AI Auditor. Proceeding to Auto-Merge.")
        sys.exit(0)
