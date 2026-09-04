#!/usr/bin/env python3
"""
Magda Queue Keeper: keeps agent_tasks.json honest without humans.
Two modes (MODE env or argv):
  reconcile - for each todo: read its acceptance + relevant code, ask Mercury-2
              DONE or OPEN with evidence. DONE verdicts flip to done (one PUT).
  ideate    - read PRD + current queue + code index, ask Mercury-2 for up to 2
              NEW product capabilities. Files them ONLY if todo pool is below
              replenishment_policy.minimum_todo_tasks (quota-safe).
--dry-run logs decisions without writing anything.

Env: TARGET_REPO, GH_PAT (or GITHUB_TOKEN), OPENAI_API_KEY, OPENAI_BASE_URL,
     OPENAI_MODEL, MODE, MAX_IDEAS (default 2)
"""

import base64
import json
import os
import sys
import urllib.request
import urllib.error

GITHUB_API = "https://api.github.com"
MAX_CODE_CHARS = 8000


def gh(path, token, method="GET", payload=None):
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(
        f"{GITHUB_API}{path}", data=data, method=method,
        headers={"Authorization": f"Bearer {token}",
                 "Accept": "application/vnd.github+json",
                 "Content-Type": "application/json",
                 "User-Agent": "Magda-Queue-Keeper"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        raw = resp.read().decode("utf-8", errors="ignore")
        return json.loads(raw) if raw.strip() else {}


def llm(openai_key, base, model, system, user, max_tokens=800):
    payload = {"model": model, "messages": [
        {"role": "system", "content": system},
        {"role": "user", "content": user}],
        "temperature": 0.2, "max_tokens": max_tokens}
    req = urllib.request.Request(
        f"{base}/chat/completions", data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {openai_key}",
                 "Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.load(resp)["choices"][0]["message"]["content"]


def get_manifest(repo, token, ref="main"):
    meta = gh(f"/repos/{repo}/contents/agent_tasks.json?ref={ref}", token)
    data = json.loads(base64.b64decode(meta["content"]).decode("utf-8"))
    return data, meta["sha"]


def put_manifest(repo, token, data, sha, message):
    content = base64.b64encode(
        (json.dumps(data, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    ).decode("utf-8")
    gh(f"/repos/{repo}/contents/agent_tasks.json", token, method="PUT",
       payload={"message": message, "content": content,
                "sha": sha, "branch": "main"})
    print(f"Queue updated on main: {message}")


def get_file(repo, token, path, ref="main", limit=4000):
    try:
        meta = gh(f"/repos/{repo}/contents/{path}?ref={ref}", token)
        if isinstance(meta, dict) and meta.get("content"):
            text = base64.b64decode(meta["content"]).decode("utf-8", errors="ignore")
            return text[:limit]
    except Exception as e:
        print(f"  (could not read {path}: {e})")
    return ""


def reconcile(repo, token, oai, base, model, dry_run):
    data, sha = get_manifest(repo, token)
    todos = [t for t in data.get("tasks", []) if t.get("status") == "todo"]
    print(f"Reconciling {len(todos)} todos.")
    flipped = []
    for t in todos:
        tid = t.get("id", "?")
        code = ""
        for p in (t.get("allowed_paths") or [])[:4]:
            if p.endswith("/"):
                continue
            code += f"\n--- {p} ---\n" + get_file(repo, token, p)
            if len(code) > MAX_CODE_CHARS:
                break
        code = code[:MAX_CODE_CHARS]
        verdict = llm(oai, base, model,
            "You are Magda, strict queue auditor. Answer with exactly one line: "
            "DONE <evidence> or OPEN <missing>. DONE only if acceptance criteria "
            "are already satisfied by the code shown. No explanations.",
            f"TASK {tid}: {t.get('title')}\nACCEPTANCE: {t.get('acceptance')}\n"
            f"CODE:\n{code}")
        print(f"- {tid}: {verdict[:160]}")
        if verdict.strip().upper().startswith("DONE"):
            t["status"] = "done"
            flipped.append(tid)
    if not flipped:
        print("Nothing to flip.")
        return
    print(f"Flipping to done: {flipped}")
    if dry_run:
        print("[dry-run] would PUT queue.")
        return
    put_manifest(repo, token, data, sha,
                 f"chore(queue): reconcile {len(flipped)} completed todos to done")


def ideate(repo, token, oai, base, model, dry_run, max_ideas):
    data, sha = get_manifest(repo, token)
    todos = [t for t in data.get("tasks", []) if t.get("status") == "todo"]
    minimum = ((data.get("replenishment_policy") or {}).get("minimum_todo_tasks")) or 3
    print(f"Todo pool: {len(todos)} (minimum {minimum})")
    prd = get_file(repo, token, "docs/PRD.md", limit=6000)
    existing = "\n".join(f"- {t.get('id')}: {t.get('title')}" for t in data.get("tasks", []))[:3000]
    tree = gh(f"/repos/{repo}/git/trees/main?recursive=1", token)
    files = [e.get("path", "") for e in (tree.get("tree") or [])
             if e.get("type") == "blob" and not e.get("path", "").startswith("node_modules")]
    index = "\n".join(files[:400])
    raw = llm(oai, base, model,
        "You are Magda, product strategist for an Airbnb clone. Propose NEW "
        "user-facing capabilities missing from the code. Reply with a JSON array "
        f"(max {max_ideas} items) of objects with keys: id, title, description, "
        "area, risk(low|medium), allowed_paths(array), acceptance(array of strings). "
        "No duplicates of existing tasks. Pure JSON, no markdown.",
        f"PRD:\n{prd}\n\nEXISTING TASKS:\n{existing}\n\nCODE INDEX:\n{index}")
    start, end = raw.find("["), raw.rfind("]")
    ideas = json.loads(raw[start:end + 1]) if start >= 0 and end > start else []
    print(f"Ideas proposed: {len(ideas)}")
    if len(todos) >= minimum:
        print(f"Pool healthy ({len(todos)} >= {minimum}); ideation parked, nothing filed.")
        return
    known = {t.get("id") for t in data.get("tasks", [])}
    added = 0
    for idea in ideas[:max_ideas]:
        if not isinstance(idea, dict) or not idea.get("id") or idea["id"] in known:
            continue
        idea.setdefault("status", "todo")
        data["tasks"].append(idea)
        known.add(idea["id"])
        added += 1
        print(f"+ {idea['id']}")
    if not added:
        print("Nothing new to file.")
        return
    if dry_run:
        print("[dry-run] would PUT queue.")
        return
    put_manifest(repo, token, data, sha, f"chore(queue): file {added} product ideas")


def main():
    args = set(sys.argv[1:])
    dry_run = "--dry-run" in args
    mode = os.getenv("MODE", "reconcile")
    if "reconcile" in args:
        mode = "reconcile"
    if "ideate" in args:
        mode = "ideate"
    repo = os.getenv("TARGET_REPO", "coruhoorhan/airbnb-app")
    token = os.getenv("GH_PAT") or os.getenv("GITHUB_TOKEN", "")
    oai = os.getenv("OPENAI_API_KEY", "")
    base = os.getenv("OPENAI_BASE_URL", "https://api.inceptionlabs.ai/v1")
    model = os.getenv("OPENAI_MODEL", "mercury-2")
    if not token or not oai:
        print("Missing GH_PAT or OPENAI_API_KEY."); sys.exit(1)
    print(f"mode={mode} dry_run={dry_run}")
    if mode == "reconcile":
        reconcile(repo, token, oai, base, model, dry_run)
    elif mode == "ideate":
        ideate(repo, token, oai, base, model, dry_run,
               int(os.getenv("MAX_IDEAS", "2")))
    else:
        print(f"Unknown MODE {mode}"); sys.exit(1)


if __name__ == "__main__":
    main()
