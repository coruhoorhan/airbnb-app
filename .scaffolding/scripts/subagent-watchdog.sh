#!/usr/bin/env bash
# subagent-watchdog.sh — subagent sessizce ölürse (429/donma) fark eder.
#
# Kullanım: subagent-watchdog.sh <session-id> <timeout-seconds>
# Döner:   0 = subagent mesaj gönderdi (canlı)
#          1 = subagent sessiz (timeout) — parent yeniden başlatmalı
#
# test3 dersi: 6 subagent 429 rate limit'ten sessizce öldü.
# Parent bunu ancak uzun süre sonra fark etti. Bu script erken uyarır.

SESSION_ID="${1:-}"
TIMEOUT="${2:-120}"

if [ -z "$SESSION_ID" ]; then
    echo "Usage: subagent-watchdog.sh <session-id> <timeout-seconds>"
    exit 2
fi

LOG_DIR="${PRIME_SESSION_DIR:-$HOME/.prime/agent/sessions}"
LOG_FILE=$(find "$LOG_DIR" -name "*${SESSION_ID}*" -o -path "*/${SESSION_ID}/*" 2>/dev/null | head -1)

if [ -z "$LOG_FILE" ] || [ ! -f "$LOG_FILE" ]; then
    echo "[watchdog] log bulunamadı: $SESSION_ID"
    echo "[watchdog] '$PRIME_SESSION_DIR' içinde aranıyor"
    LOG_FILE="$LOG_DIR/${SESSION_ID}.jsonl"
    [ -f "$LOG_FILE" ] || { echo "[watchdog] FATAL: log yok — subagent hiç başlamadı mı?"; exit 1; }
fi

# Son mesaj zamanını al (jsonl son satır) — epoch millis'e dönüştür
LAST_TS=$(tail -1 "$LOG_FILE" | python3 -c "
import sys, json
from datetime import datetime, timezone
d = json.loads(sys.stdin.read())
ts = d.get('timestamp', '0')
if ts == '0':
    print(0)
else:
    try:
        dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))
        print(int(dt.timestamp() * 1000))
    except (ValueError, AttributeError, TypeError):
        print(0)
" 2>/dev/null || echo "0")
NOW_TS=$(date +%s000)
DELTA=0
if [ "$LAST_TS" -gt 0 ] 2>/dev/null; then
    DELTA=$(( (NOW_TS - LAST_TS) / 1000 ))
fi
if [ "$DELTA" -gt "$TIMEOUT" ]; then
    echo "[watchdog] ⚠️ Subagent $SESSION_ID ${DELTA}s'dir sessiz (limit: ${TIMEOUT}s)"
    echo "[watchdog] Muhtemel: 429 rate limit veya takılma."
    echo "[watchdog] Son mesaj:"
    tail -3 "$LOG_FILE" | cut -c1-200
    exit 1
else
    echo "[watchdog] ✅ Subagent $SESSION_ID canlı (son mesaj ${DELTA}s önce)"
    exit 0
fi
