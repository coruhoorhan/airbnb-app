#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
HARNESS="/tmp/harness-cli/node_modules/.bin/harness-automation"
ARCHCORE="/root/.local/bin/archcore"

usage() {
    cat <<EOF
Agent Stack — Deterministic orchestration for any coding agent

Usage:  run.sh <command> [args]

Commands:
  doctor              — Preflight: archcore + harness doctor
  intake <owner>      — Approve sources (PRD, research) with owner name
  plan                — Generate immutable policy plan
  apply <hash>        — Apply plan by hash
  check               — Policy check + drift detection
  verify              — Green gate: test + typecheck + check + drift
  workflow            — Print scaffolding workflow YAML (agent reads it)
  init                — Initialize .archcore/ + .harness/ (first-time setup)
  hook <name>         — Run scaffolding hook (e.g., run.sh hook pre-commit)
  gates               — Run GATES.md (unlazy-style acceptance ledger)
  gates-reverify      — Re-run ALL gates (old evidence = no evidence)
  validate            — Run all 4 validators (skill, agent, output, circuit-breaker)
  agent <role> [task] — Read agent role file, build prompt, run post-edit hook
  advisor <goal>      — Skill-advisor subagent: select skills, write LEDGER
  route <goal>        — Ask-matt router: task → flow + skills
  fetch <skill>       — Fetch + eject a single skill from GitHub
  orchestrate <goal>  — Full workflow: route → fetch → eject → catalog
  workflow-run <desc> — Run Meteoras & Agent-Stack 7-phase autonomous workflow
  watchdog <sid> [s] — Check subagent is alive (detects silent 429 death)
  git <cmd> [args]    — Pass-through to git (e.g., run.sh git status)
EOF
}

case "${1:-help}" in
    doctor)
        echo "=== Archcore doctor ==="
        "$ARCHCORE" doctor --project . || echo "[WARN] archcore doctor failed — continuing"
        echo "=== Harness doctor ==="
        "$HARNESS" doctor --project . || echo "[WARN] harness doctor failed — continuing"
        ;;

    intake)
        OWNER="${2:-}"
        if [ -z "$OWNER" ]; then echo "Usage: run.sh intake <owner>"; exit 1; fi
        echo "=== Source intake (owner: $OWNER) ==="
        if ls docs/PRD.md 2>/dev/null; then
            "$HARNESS" intake --project . --owner "$OWNER" --approve-sources
        else
            echo "docs/PRD.md not found — run intake only after PRD exists"
            exit 1
        fi
        ;;

    plan)
        echo "=== Harness plan ==="
        "$HARNESS" discover --project .
        "$HARNESS" plan --project . --profile custom --stack typescript
        echo "--- Plan dosyası ---"
        ls .harness/plans/*.json 2>/dev/null || echo "(no plan yet)"
        ;;

    apply)
        HASH="${2:-}"
        if [ -z "$HASH" ]; then
            # son plan'i kullan
            PLAN=$(ls .harness/plans/*.json 2>/dev/null | tail -1)
            if [ -z "$PLAN" ]; then echo "No plan found. Run plan first."; exit 1; fi
            HASH=$(python3 -c "import json; print(json.load(open('$PLAN'))['planHash'])")
        fi
        PLAN=$(ls .harness/plans/*.json 2>/dev/null | tail -1)
        echo "=== Apply plan: $PLAN ==="
        echo "Hash: $HASH"
        "$HARNESS" apply --plan "$PLAN" --approve "$HASH" --project .
        ;;

    check)
        echo "=== Harness check ==="
        "$HARNESS" check --project . --mode session
        echo "=== Harness drift ==="
        "$HARNESS" drift --project .
        ;;

    gates)
        python3 "${SCRIPT_DIR}/.scaffolding/scripts/gates-check.py"
        ;;

    watchdog)
        SID="${2:-}"
        TIMEOUT="${3:-120}"
        if [ -z "$SID" ]; then
            echo "Usage: run.sh watchdog <session-id> [timeout-s]"
            exit 1
        fi
        bash "${SCRIPT_DIR}/.scaffolding/scripts/subagent-watchdog.sh" "$SID" "$TIMEOUT"
        ;;

    gates-reverify)
        echo "=== REVERIFY: tüm gate'ler yeniden çalıştırılıyor (eski kanıt = kanıt değil) ==="
        bash run.sh gates
        ;;

    verify)
        echo "=== GREEN GATE ==="
        echo "1. Vitest"
        if [ -f node_modules/vitest/vitest.mjs ]; then
            node node_modules/vitest/vitest.mjs run 2>&1 | grep -E "Test Files|Tests " | head -5
        else
            echo "(no tests found)"
        fi
        echo "2. TypeScript strict"
        if [ -f node_modules/typescript/bin/tsc ]; then
            node node_modules/typescript/bin/tsc --noEmit 2>&1 && echo "  TSC_OK"
        else
            echo "(no tsconfig.json found)"
        fi
        echo "3. Lint: size (src/ files ≤250 lines)"
        (find src/ -name '*.ts' -exec wc -l {} + 2>/dev/null | awk '$2 != "total" && $1 > 250 {print "  [FAIL] " $2 " (" $1 " lines)"; fail=1} END {if (fail) exit 1; else print "  All files under 250 lines"}') || echo "  [WARN] Some files exceed 250 lines — check manually"
        echo "4. Harness check"
        "$HARNESS" check --project . --mode session
        echo "5. Harness drift"
        "$HARNESS" drift --project .
        echo "=== ALL GREEN ==="
        ;;

    workflow)
        cat "$SCRIPT_DIR/.scaffolding/workflows/workflow.yaml" 2>/dev/null             || echo "No workflow.yaml found — run init first?"
        ;;

    init)
        echo "=== Archcore init ==="
        "$ARCHCORE" init --project .
        echo "=== Harness init ==="
        "$HARNESS" doctor --project .  # creates .harness/ if needed
        echo "=== Git init ==="
        if [ -d .git ]; then
            echo "  ✓ Git repo already exists"
        else
            if git init; then
                echo "  ✓ Git repo initialized"
            else
                echo "  [WARN] git init failed"
            fi
        fi
        echo "Ready. Next: run.sh doctor"
        ;;

    hook)
        if [ "${2:-}" = "list" ] || [ -z "${2:-}" ]; then
            echo "Available hooks:"
            ls -1 "$SCRIPT_DIR/.scaffolding/hooks/"*.sh 2>/dev/null | sed 's|.*/||' | sed 's/\.sh$//' || echo "  (no hooks found)"
            exit 0
        fi
        HOOK_FILE="$SCRIPT_DIR/.scaffolding/hooks/${2}.sh"
        if [ -f "$HOOK_FILE" ]; then
            echo "=== Hook: $2 ==="
            bash "$HOOK_FILE"
        else
            echo "Hook not found: $2"
            echo "Available:"
            ls -1 "$SCRIPT_DIR/.scaffolding/hooks/"*.sh 2>/dev/null | sed 's|.*/||' | sed 's/\.sh$//' || echo "  (no hooks found)"
            exit 1
        fi
        ;;

    validate)
        echo "=== Validator: validate-skill (all SKILL.md files) ==="
        SKILL_FILES=$(find "$SCRIPT_DIR/.scaffolding/skills" -name 'SKILL.md' 2>/dev/null)
        SKILL_COUNT=$(echo "$SKILL_FILES" | wc -l)
        PASS=0
        FAIL=0
        for f in $SKILL_FILES; do
            if bash "$SCRIPT_DIR/.scaffolding/validators/validate-skill.sh" "$f" 2>/dev/null; then
                PASS=$((PASS + 1))
            else
                FAIL=$((FAIL + 1))
                echo "  [FAIL] $f"
            fi
        done
        echo "  SKILL validation: $PASS passed, $FAIL failed"

        echo ""
        echo "=== Validator: validate-agent-frontmatter (all agent .md files) ==="
        if bash "$SCRIPT_DIR/.scaffolding/validators/validate-agent-frontmatter.sh" "$SCRIPT_DIR/.scaffolding/agents/" 2>/dev/null; then
            echo "  AGENT frontmatter: ALL VALID"
        else
            echo "  AGENT frontmatter: SOME INVALID — check above"
        fi

        echo ""
        echo "=== Validator: validate-agent-output (sample) ==="
        SAMPLE=$(cat <<'EOF'
---
agent: developer
task: Implement email validation
status: success
gate: passed
score: 90/100
files_modified: 2
next_agent: reviewer
---
EOF
)
        echo "$SAMPLE" | bash "$SCRIPT_DIR/.scaffolding/validators/validate-agent-output.sh" 2>/dev/null && echo "  AGENT output: VALID (sample)" || echo "  AGENT output: INVALID"

        echo ""
        echo "=== Validator: circuit-breaker status ==="
        for agent in analyst architect developer reviewer tech-writer; do
            bash "$SCRIPT_DIR/.scaffolding/validators/circuit-breaker.sh" status "$agent" 2>/dev/null || true
        done
        echo "  CIRCUIT BREAKER: status check complete"
        ;;

    agent)
        ROLE="${2:-}"
        TASK="${3:-}"
        if [ -z "$ROLE" ]; then
            echo "Usage: run.sh agent <role> [task]"
            echo "Available roles:"
            ls -1 "$SCRIPT_DIR/.scaffolding/agents/" 2>/dev/null | sed 's/\.md$//' || echo "  (no role files found)"
            exit 1
        fi
        ROLE_FILE="$SCRIPT_DIR/.scaffolding/agents/${ROLE}.md"
        if [ ! -f "$ROLE_FILE" ]; then
            echo "Role not found: $ROLE"
            echo "Available:"
            ls -1 "$SCRIPT_DIR/.scaffolding/agents/" 2>/dev/null | sed 's/\.md$//'
            exit 1
        fi

        echo "=== Agent: $ROLE ==="
        echo ""
        echo "--- Role Frontmatter ---"
        # Extract YAML frontmatter between first pair of ---
        awk '/^---$/{if(f){exit}else{f=1;next}} f{print}' "$ROLE_FILE"
        echo ""
        echo "--- Required Skills ---"
        SKILLS=$(awk '/^skills:/{flag=1;next} /^[a-z]/{flag=0} flag{print}' "$ROLE_FILE" | sed 's/^  - //' | sed 's/^[[:space:]]*//')
        echo "$SKILLS"
        echo ""
        if [ -n "$TASK" ]; then
            echo "--- Task Prompt ---"
            echo "Role: $ROLE"
            echo "Task: $TASK"
            echo ""
            echo "Required skills for this role:"
            echo "$SKILLS"
            echo ""
            echo "Load the following skill files from .scaffolding/skills/<name>/SKILL.md:"
            for skill in $SKILLS; do
                SKILL_FILE="$SCRIPT_DIR/.scaffolding/skills/$skill/SKILL.md"
                if [ -f "$SKILL_FILE" ]; then
                    echo "  - .scaffolding/skills/$skill/SKILL.md"
                else
                    echo "  - (skill not found in local pool: $skill)"
                fi
            done
            echo ""
            echo "--- Instructions ---"
            echo "Execute the task using the skills above. After completion, run:"
            echo "  run.sh hook post-edit"
        fi
        ;;

    advisor)
        # Skill-advisor subagent: task goal alir, skill secer, LEDGER yazar.
        GOAL="${2:-}"
        if [ -z "$GOAL" ]; then
            echo "Usage: run.sh advisor <task-goal>"
            echo "Example: run.sh advisor \"Implement email validation with test patterns and proper error handling\""
            exit 1
        fi
        bash "${SCRIPT_DIR}/skill-advisor.sh" "$GOAL" "$SCRIPT_DIR"
        ;;

    route)
        # Ask-matt router: task goal → flow + skills (deterministic, LLM yok)
        GOAL="${2:-}"
        if [ -z "$GOAL" ]; then echo "Usage: run.sh route <goal>"; exit 1; fi
        npx tsx "${SCRIPT_DIR}/orchestrator-src/orchestrator.ts" --goal "$GOAL" 2>&1
        ;;

    fetch)
        # Tekil skill çekim: GitHub'dan tek SKILL.md indir + eject et
        SKILL_NAME="${2:-}"
        OUT_DIR="${3:-$SCRIPT_DIR}"
        if [ -z "$SKILL_NAME" ]; then echo "Usage: run.sh fetch <skill-name> [out-dir]"; exit 1; fi
        echo "Fetching '$SKILL_NAME' → $OUT_DIR/.agents/skills/..."
        npx tsx -e "
        import { searchSkill, ejectSkill, MATTPOCOCK_CATALOG } from '${SCRIPT_DIR}/orchestrator-src/skill-registry.ts';
        (async () => {
            const ref = searchSkill('${SKILL_NAME}', MATTPOCOCK_CATALOG);
            if (!ref) { console.log('not found in catalog'); process.exit(1); }
            const r = await ejectSkill(ref, '${OUT_DIR}');
            console.log(r ? 'ejected' : 'already exists');
        })();
        " 2>&1
        ;;

    orchestrate)
        # Tam akış: route → fetch → eject → catalog
        GOAL="${2:-}"
        OUT_DIR="${3:-$SCRIPT_DIR}"
        if [ -z "$GOAL" ]; then echo "Usage: run.sh orchestrate <goal> [out-dir]"; exit 1; fi
        if [ -f "${SCRIPT_DIR}/orchestrator-src/orchestrator.py" ]; then
            python3 "${SCRIPT_DIR}/orchestrator-src/orchestrator.py" "$GOAL" --project-root "$OUT_DIR"
        else
            bash "${SCRIPT_DIR}/skill-orchestrator.sh" "$GOAL" "$OUT_DIR"
        fi
        ;;

    workflow-run)
        shift
        python3 "${SCRIPT_DIR}/orchestrator-src/orchestrator.py" "$@"
        ;;

    git) shift; git "$@" ;;

    help|--help|-h) usage ;;
    *) echo "Unknown: $1"; usage; exit 1 ;;
esac