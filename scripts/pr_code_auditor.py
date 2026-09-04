#!/usr/bin/env python3
"""
Magda AI PR Code Auditor & Reviewer.
Runs in GitHub Actions or locally to review PR diffs with Mercury-2 LLM
and post formal code review comments to GitHub Pull Requests.
"""

import os
import sys
import json
import urllib.request
import urllib.error
import re

def review_pr(pr_number: int, repo: str, token: str, openai_key: str, openai_base: str, model: str):
    print(f"Auditing PR #{pr_number} on {repo} with {model}...")
    
    # 1. Fetch PR details
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "Magda-Code-Auditor"
    }
    
    pr_url = f"https://api.github.com/repos/{repo}/pulls/{pr_number}"
    req = urllib.request.Request(pr_url, headers=headers)
    with urllib.request.urlopen(req) as resp:
        pr_data = json.load(resp)
    
    pr_title = pr_data.get("title", "")
    pr_body = pr_data.get("body", "")
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
    
    # Truncate diff if too large
    if len(diff_text) > 12000:
        diff_text = diff_text[:12000] + "\n\n...[diff truncated for audit]..."
    
    # 3. Request LLM review from Mercury-2
    prompt = f"""You are Magda AI Senior Principal Code Auditor & Security Inspector (independent reviewer bot).
Review the following Pull Request submitted by Jules Worker.

PR #{pr_number}: {pr_title}
DESCRIPTION: {pr_body}

GIT DIFF:
```diff
{diff_text}
```

AUDIT CRITERIA:
1. Security & Input Sanitization (XSS, Injection, Rate Limiting, Token tampering).
2. Correctness & Error Handling (Unhandled promise rejections, edge cases, off-by-one errors).
3. Code Quality, Modularity & Performance (Clean code, zero unnecessary overhead).
4. Manifest & Test Coverage (Does it meet the acceptance criteria and include proper tests?).

Output a structured Markdown review with:
- 🛡️ **Audit Verdict:** [APPROVED | CHANGES REQUESTED]
- 🔍 **Security & Integrity Analysis:** (Key observations)
- ⚡ **Performance & Architecture Review:** (Key observations)
- 📝 **Detailed Feedback & Suggestions:** (Specific points or code recommendations)
- 🎯 **Conclusion:** Summary verdict.

Keep it professional, rigorous, concise, and formatted with clean markdown tables/bullet points."""

    llm_payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You are Magda AI Principal Code Auditor, an automated independent code review bot for GitHub PRs."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.2,
        "max_tokens": 1500
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
    
    review_body = f"## 🤖 Magda AI Independent Code Auditor Review\n\n{review_content}\n\n---\n*Audited autonomously by Inception Labs Mercury-2 Cognitive Engine.*"
    
    # 4. Post review to GitHub PR
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
    
    with urllib.request.urlopen(req_post) as resp:
        print(f"Review successfully posted to PR #{pr_number}! Status: {resp.status}")
    
    return review_body

if __name__ == "__main__":
    pr_num = int(sys.argv[1]) if len(sys.argv) > 1 else 8
    repo = sys.argv[2] if len(sys.argv) > 2 else "coruhoorhan/airbnb-app"
    token = os.getenv("GH_PAT") or os.getenv("GITHUB_TOKEN")
    openai_key = os.getenv("OPENAI_API_KEY")
    openai_base = os.getenv("OPENAI_BASE_URL", "https://api.inceptionlabs.ai/v1")
    model = os.getenv("OPENAI_MODEL", "mercury-2")
    
    review_pr(pr_num, repo, token, openai_key, openai_base, model)
