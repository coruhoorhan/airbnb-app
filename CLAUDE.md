## Protocol

Bu proje **veyyon** runtime ile çalışır. AGENTS.md birincil talimat dosyasıdır.
CLAUDE.md, Claude Code / Cursor ile veyyon dışı kullanım için uyumluluk katmanıdır.

**Engineering work:** workflow.yaml akışını takip eder. Tüm iş `task` subagent'ları ile yürütülür.
Detay: `.scaffolding/adapters/veyyon.md`

**Trivial/factual questions:** Doğrudan yanıtlanabilir.
**Multi-step engineering:** Doğrudan kod yazma — her adım bir subagent'e devredilir.

Katman haritası ve zorlama zinciri: AGENTS.md → "Katman Haritası — Tek Kaynak".

**BEHAVIOR:**
1. **Auto-route** - Treat engineering requests as tasks. Route to the right agent.
2. **No confirmation** - For real work, don't ask. Just delegate.
3. **Concise responses** - Short status. No verbose explanations unless asked.

**Delegate via:** `task(context, tasks=[{name, task}])` — bkz. adapters/veyyon.md §3
**Response format:** `[Agent: name] Task -> Result (1-2 lines)`

---

## Agents (13)

| Agent | Tier | When to Use |
|-------|------|-------------|
| **scaffolding:analyst** | opus | Ambiguous requests, requirements, scope assessment, feasibility, proposal writing |
| **scaffolding:architect** | opus | System design, API design, implementation planning, multi-file refactoring, agent orchestration |
| **scaffolding:researcher** | sonnet | New API integration, library questions, best practices (gate: score >= 80) |
| **scaffolding:developer** | sonnet | Implementation, bug fixes, features, tests, UI/styling (gate: validation passes) |
| **scaffolding:debugger** | opus | Bug reports, unexpected behavior, errors |
| **scaffolding:reviewer** | sonnet | After code changes, security analysis, threat modeling (gate: no criticals) |
| **scaffolding:optimizer** | sonnet | Performance issues, database design, schema, migrations, queries |
| **scaffolding:prompt-engineer** | sonnet | System prompts, prompt templates, guardrail rules, prompt evals, LLM-judge rubrics, injection defense |
| **scaffolding:mcp-builder** | sonnet | Build/modify MCP servers, tool schema design, stdio/http transport, MCP auth/secret launchers |
| **scaffolding:tech-writer** | haiku | Documentation, CHANGELOG updates |
| **scaffolding:devops** | sonnet | CI/CD, deployment, infrastructure |
| **scaffolding:gitops** | haiku | Branch management, conflict resolution, git history, worktree recovery, push to remote |
| **scaffolding:coordinator** | sonnet | Analyzes tasks, decomposes into agent step sequences for dynamic execution |

---

## Decision Tree

**Delegate real engineering work; trivial/factual/conversational questions may be answered directly.** Tüm zincirler `task` subagent'ları olarak çalışır (rol → subagent eşleşmesi: adapters/veyyon.md §2). Multi-step chains:

- Bug fix -> debugger -> developer
- Complex feature (multi-file / new system) -> analyst -> architect -> developer
- Small change (single file, clear scope) -> developer directly (skip analyst/architect)
- Docs / library -> researcher -> tech-writer
- Simple feature / tests / UI / code question -> developer
- Architecture question -> architect
- Requirements / scope / planning / ambiguous -> analyst
- Routine review -> reviewer (sonnet); security/threat-model -> reviewer with opus model override · CI/CD -> devops · DB / perf -> optimizer
- Prompt / guardrail / system-prompt / eval / LLM-judge -> prompt-engineer
- MCP server build / tool schema / transport -> mcp-builder
- Git / commit / merge / push -> gitops
- After ANY worktree agent completes -> gitops (commit + merge + push)
- Multi-agent coordination -> coordinator
- Default -> developer if scope is clear and small; analyst only when genuinely ambiguous

---

## Key Rules

1. **Files < 500 lines**; split any single Edit > 200 lines into sequential edits (large edits crash the CLI)
2. **Types in types/index.ts** - Centralized TypeScript types
3. **Validate before commit** - enforced by `hooks/pre-commit-validation.sh` (framework-agnostic: runs the first detected validation entrypoint — Makefile/justfile/package.json/pytest/cargo/go/etc.; warns and passes if none found)
4. **tech-writer owns docs** - Only tech-writer modifies README/CHANGELOG
5. **developer owns code** - Only developer modifies source files

---

## Detailed protocols (auto-loaded skills — not duplicated here)

Detail lives in skills and loads on demand (progressive disclosure), so it stays out of static context:

- **Worktree delegation** (the developer-writes / gitops-commits sequence): `git-guardrails-claude-code` + `resolving-merge-conflicts` + `handoff` skills
- **MCP tool selection & fallback**: `wizard` + `ask-matt` skills
- **Spec-driven dev / OpenSpec, conversation UUID path**: `to-spec` + `implement-spec` skills

## Agent skills

### Issue tracker

Issues are tracked as local markdown files under `.scratch/<feature>/`. See `docs/agents/issue-tracker.md`.

### Triage labels

The five canonical labels: `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context layout: `CONTEXT.md` at repo root, ADRs in `docs/adr/`, symlinked into `.archcore/`. See `docs/agents/domain.md`.

<!-- harness-automation:v2:start -->
## Harness engineering continuity

Effective policy digest: `21eec4901a346c95fc036bfc9fda059c203fe21670afb9a13497048177350d11`

Before editing code in a new session:

1. Run `harness-automation context --project .` and read `.harness/generated/effective-policy.md`.
2. Search for the existing implementation and identify the owning module before adding a new one.
3. Treat shared APIs, RPC, database schemas, queues, and generated code as contracts.
4. Run `harness-automation check --project .` before declaring work complete.
5. Never edit `.harness/generated/**` or this managed block directly.

<!-- harness-automation:v2:end -->
