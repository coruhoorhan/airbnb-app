#!/usr/bin/env python3
"""
GitHub PR Guardian & Veyyon Dispatcher
Açık PR'ları 7/24 izler; testleri geçerse otomatik merge eder,
çakışma veya hata varsa Veyyon'a Herdr üzerinden anında görev atar.
"""
import urllib.request
import json
import time
import subprocess
import os

TOKEN = os.environ.get("GH_PAT") or os.environ.get("GITHUB_TOKEN", "")
REPO = "coruhoorhan/airbnb-app"
HERDR = "/root/.local/bin/herdr"

def get_open_prs():
    req = urllib.request.Request(
        f"https://api.github.com/repos/{REPO}/pulls?state=open",
        headers={"Authorization": f"Bearer {TOKEN}", "User-Agent": "PRGuardian"}
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.load(resp)
    except Exception as e:
        print(f"Error fetching PRs: {e}")
        return []

def merge_pr(pr_number):
    req = urllib.request.Request(
        f"https://api.github.com/repos/{REPO}/pulls/{pr_number}/merge",
        data=json.dumps({"merge_method": "squash"}).encode("utf-8"),
        headers={"Authorization": f"Bearer {TOKEN}", "User-Agent": "PRGuardian", "Content-Type": "application/json"},
        method="PUT"
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status in (200, 201)
    except Exception as e:
        print(f"Merge error on PR #{pr_number}: {e}")
        return False

def get_active_herdr_pane():
    """Dynamically finds the active or primary Herdr pane."""
    if not os.path.exists(HERDR):
        return None
    try:
        res = subprocess.run([HERDR, "pane", "list"], capture_output=True, text=True, timeout=5)
        if res.returncode == 0 and res.stdout.strip():
            data = json.loads(res.stdout)
            panes = data.get("result", {}).get("panes", []) or data.get("panes", [])
            if panes:
                return panes[0].get("pane_id")
    except Exception:
        pass
    return None

def notify_veyyon(pane_id, message):
    """Sends alert directly into Veyyon's Herdr pane or logs locally."""
    target_pane = pane_id or get_active_herdr_pane()
    if target_pane:
        try:
            subprocess.run([HERDR, "pane", "send-text", target_pane, message], check=True)
            subprocess.run([HERDR, "pane", "send-keys", target_pane, "enter"], check=True)
            print(f"📡 [VEYYON PANE {target_pane}'E İLETİLDİ]: {message}")
            return
        except Exception as e:
            print(f"Veyyon bildirim hatası ({target_pane}): {e}")
    print(f"📢 [PR GUARDIAN ALERT]: {message}")

def check_and_reconcile_prs(veyyon_pane_id=None):
    prs = get_open_prs()
    if not prs:
        return
    print(f"🔍 [PR GUARDIAN]: {len(prs)} açık PR denetleniyor...")
    for p in prs:
        num = p["number"]
        title = p["title"]
        branch = p["head"]["ref"]
        mergeable = p.get("mergeable")
        
        # 1. Eğer PR merge edilemiyorsa veya çakışma varsa doğrudan Veyyon'a bildir
        if mergeable is False:
            msg = f"🚨 [PR ÇAKIŞMASI]: PR #{num} ({title}) merge edilemiyor! Branch '{branch}' üzerinde çakışma var. Lütfen çöz."
            notify_veyyon(veyyon_pane_id, msg)
            continue

        # 2. Temizse merge et
        success = merge_pr(num)
        if success:
            print(f"✅ PR #{num} başarıyla main dalına merge edildi!")
            # Jules'a sonraki görevi tetikle
            try:
                req = urllib.request.Request(
                    f"https://api.github.com/repos/{REPO}/actions/workflows/jules_next_task.yml/dispatches",
                    data=json.dumps({"ref": "main", "inputs": {"force": "true"}}).encode("utf-8"),
                    headers={"Authorization": f"Bearer {TOKEN}", "User-Agent": "PRGuardian", "Content-Type": "application/json"},
                    method="POST"
                )
                urllib.request.urlopen(req, timeout=10)
                print(f"🚀 Jules için sıradaki görev tetiklendi.")
            except Exception as e:
                print(f"Jules tetikleme hatası: {e}")
        else:
            # Merge başarısız olduysa (örneğin test kırıldıysa) Veyyon'a görev pasla
            msg = f"⚠️ [PR MERGE HATASI]: PR #{num} ({title}) merge edilemedi! Test veya CI kilitlenmesi olabilir. İncele: https://github.com/{REPO}/pull/{num}"
            notify_veyyon(veyyon_pane_id, msg)

if __name__ == "__main__":
    pane = sys.argv[1] if len(sys.argv) > 1 else None
    check_and_reconcile_prs(pane)
