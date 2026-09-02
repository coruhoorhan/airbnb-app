#!/usr/bin/env bash
# skill-orchestrator.sh — subagent: task goal alır, router + GitHub çekim + eject + katalog yapar.
# Kullanım: bash skill-orchestrator.sh "OTP ile profesyonel üyelik kaydı" [OUT_DIR]
set -euo pipefail

GOAL="${1:-}"
OUT_DIR="${2:-$PWD}"

if [ -z "$GOAL" ]; then
    echo "Kullanım: bash skill-orchestrator.sh <task-goal> [out-dir]"
    echo "Örnek:   bash skill-orchestrator.sh "OTP ile profesyonel üyelik kaydı sistemi""
    exit 1
fi

mkdir -p "$OUT_DIR"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Orchestrator'ı çalıştır (npx tsx ile)
echo "  → orchestrator başlıyor: goal='$GOAL' out='$OUT_DIR'"
npx tsx "$SCRIPT_DIR/orchestrator-src/orchestrator.ts" --goal "$GOAL" --out-dir "$OUT_DIR" 2>&1 || {
    echo "⚠️  tsx CLI hatası, fallback..."
    node --input-type=module -e "
    import { runTaskWorkflow } from '$SCRIPT_DIR/orchestrator-src/orchestrator.ts';
    const r = await runTaskWorkflow(process.argv[1], process.argv[2]);
    console.log('flow=' + r.flowType);
    console.log('skills=' + r.skills.join(','));
    console.log('ejected=' + r.ejected.join(','));
    console.log('failed=' + r.failed.join(','));
    console.log('catalog=' + r.catalogPath);
    " "$GOAL" "$OUT_DIR" 2>&1
}

echo "✅ skill-orchestrator tamamlandı"
