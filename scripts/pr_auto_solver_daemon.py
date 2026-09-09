#!/usr/bin/env python3
"""
Arka Planda Sessizce Çalışan PR & Hata Çözücü (Headless Veyyon)
Hiçbir terminal sekmesi veya pane ID'sine bağımlı olmadan:
1. GitHub PR'larını izler.
2. Çakışma veya test hatası varsa izole bir şekilde `veyyon -p --yolo` ile arka planda çözer.
3. PR'ı yeşil yapıp otomatik merge eder.
"""
import urllib.request
import json
import subprocess
import time
import os

TOKEN = os.environ.get("GH_PAT") or os.environ.get("GITHUB_TOKEN", "")
REPO = "coruhoorhan/airbnb-app"
APP_ROOT = "/root/airbnb-app"

def get_open_prs():
    req = urllib.request.Request(
        f"https://api.github.com/repos/{REPO}/pulls?state=open",
        headers={"Authorization": f"Bearer {TOKEN}", "User-Agent": "PRAutoSolver"}
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.load(resp)
    except:
        return []

def merge_pr(pr_number):
    req = urllib.request.Request(
        f"https://api.github.com/repos/{REPO}/pulls/{pr_number}/merge",
        data=json.dumps({"merge_method": "squash"}).encode("utf-8"),
        headers={"Authorization": f"Bearer {TOKEN}", "User-Agent": "PRAutoSolver", "Content-Type": "application/json"},
        method="PUT"
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status in (200, 201)
    except:
        return False

def solve_pr_conflict_in_background(pr):
    num = pr["number"]
    branch = pr["head"]["ref"]
    title = pr["title"]
    print(f"⚙️ [ARKA PLAN ÇÖZÜCÜ]: PR #{num} ({branch}) için headless Veyyon başlatılıyor...")

    # Headless (penceresiz) Veyyon çağrısı:
    cmd = [
        "/root/.local/bin/veyyon", "-p", "--yolo",
        f"Git branch '{branch}' üzerindeki çakışmayı ve test hatalarını çöz, npm test çalıştır ve branch'e pushla."
    ]
    subprocess.run(cmd, cwd=APP_ROOT, capture_output=True, text=True)

def run_guardian_loop():
    prs = get_open_prs()
    for p in prs:
        # Önce doğrudan merge dene
        if merge_pr(p["number"]):
            print(f"✅ PR #{p['number']} doğrudan merge edildi.")
        else:
            # Hata varsa arka planda sessizce Veyyon çözer
            solve_pr_conflict_in_background(p)

if __name__ == "__main__":
    run_guardian_loop()
