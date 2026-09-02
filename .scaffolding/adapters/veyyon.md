# Veyyon Adaptörü — Agent Stack

Bu belge, Veyyon runtime'ının agent-stack'in `.scaffolding/` katmanını
`task` subagent'ları ile çalıştırması için protokolü tanımlar.
Veyyon'un `task` aracına **eşdeğerdir**: `task` → `deep` subagent.

> Diğer runtime'lar (Prime Agent rlm, Claude Code Task, OpenCode) kendi mekanizmalarını kullanır.
> Bu adaptör YALNIZCA Veyyon içindir.

---

## 1. Temel Kural

**Her workflow adımı bir `task` subagent işidir.** Ana ajan (root) işi KENDİSİ yapmaz;
`.scaffolding/agents/<rol>.md` dosyasını göstererek bir `task` subagent başlatır.

```
Ana ajan:  task(context, tasks=[{name: "<rol>-<kisa-tanim>", task: "..."}])
Subagent:  .scaffolding/agents/<rol>.md dosyasını OKUR → kurallarına uyar → işi yapar
Subagent:  biter bitmez sonucu döndürür
Ana ajan:  cevabı alır → sonraki adıma geçer
```

---

## 2. Rol → Subagent Eşleşmesi

| workflow.yaml adımı | Rol dosyası | Subagent name | Ne yapar |
|---|---|---|---|
| `propose` | `.scaffolding/agents/analyst.md` | `analyst` | proposal.md yazar |
| `research` | `.scaffolding/agents/researcher.md` | `researcher` | ResearchPack yazar |
| `design` | `.scaffolding/agents/architect.md` | `architect` | design.md + tasks.md yazar |
| `implement` (IMPL-XXX) | `.scaffolding/agents/developer.md` | `developer-<IMPL-id>` | kod + test yazar, tsc/vitest geçirir |
| `implement` (REVIEW-XXX) | `.scaffolding/agents/reviewer.md` | `reviewer-<IMPL-id>` | ilgili IMPL'i inceler |
| `review` | `.scaffolding/agents/reviewer.md` | `reviewer-integration` | tüm değişikliği bütünleşik inceler |
| `document` | `.scaffolding/agents/tech-writer.md` | `tech-writer` | README/CHANGELOG günceller |
| `push` | `.scaffolding/agents/gitops.md` | `gitops` | commit + push |

---

## 3. Subagent Prompt Şablonu

```python
# context alanı (tüm task'lar için ortak)
context = f"""
# Goal
{ADIM_TANIMI}

# Constraints
- Proje: {PROJECT_NAME}
- Proje kökü: {PROJECT_ROOT}
- Çalışma dizini: {CWD}

# Contract
- Rol dosyası: {PROJECT_ROOT}/.scaffolding/agents/{ROL}.md
- Skill listesi: {SKILL_LIST}
- İş bitince: cd {PROJECT_ROOT} && ./run.sh hook post-edit
"""

# task alanı
task = f"""
[agent-stack] Görev: {ADIM_TANIMI}

Rol dosyanı OKU ve kurallarına uy:
  {PROJECT_ROOT}/.scaffolding/agents/{ROL}.md

Proje kökü: {PROJECT_ROOT}
Çalışma dizini: {CWD}

Görev detayı:
{TALIMAT}

---

ÖNCE şu skill'leri oku ve uygula:
  {SKILL_LIST}

İş bitince şu hook'ları çalıştır:
  cd {PROJECT_ROOT} && ./run.sh hook post-edit
"""
```

### Önemli kurallar:
1. **name benzersiz olmalı** — aynı rol birden çok kez çağrılabilir (`developer-IMPL-001`, `developer-IMPL-002`)
2. **Subagent'e mutlak yolları ver** — subagent kendi cwd'sinde başlar
3. **Bekleme**: sonuç otomatik gelir; `task` tool'u output'u döndürür
4. **Paralellik**: bağımsız IMPL'ler aynı `tasks[]` batch'inde toplanabilir; REVIEW'ler kendi IMPL'lerine bağımlıdır

---

## 4. Hook'lar

`.scaffolding/hooks/*.sh` dosyaları `run.sh hook` ile çalıştırılır:

```bash
./run.sh hook pre-commit        # .scaffolding/hooks/pre-commit-validation.sh
./run.sh hook post-edit         # .scaffolding/hooks/post-edit.sh
./run.sh hook file-size         # .scaffolding/hooks/file-size-warn.sh
```

Ana ajan şu anlarda hook çağırır:
- **Kod yazdıktan sonra**: `./run.sh hook post-edit`
- **Commit öncesi**: `./run.sh hook pre-commit`
- **İş bitiminde**: `./run.sh hook completion-nudge` (varsa)

---

## 5. Skill'ler

`.scaffolding/skills/*/SKILL.md` dosyaları Veyyon'ın kendi skill
mekanizmasına kayıtlı DEĞİLDİR. İki yol vardır:

### Yol A (önerilen): Prompt'ta skill oku talimatı
Task prompt'unda "ÖNCE şu skill'leri oku ve uygula" talimatı verilir.
Her skill'in SKILL.md dosyası `.scaffolding/skills/<name>/SKILL.md` adresindedir.
Subagent `read` aracıyla bu dosyaları okur.

### Yol B: Veyyon skill'lerine kopyala
```bash
# template kurulumunda (isteğe bağlı)
mkdir -p ~/.veyyon/profiles/default/agent/skills/agent-stack
cp -r .scaffolding/skills/* ~/.veyyon/profiles/default/agent/skills/agent-stack/
```
Bu, Veyyon'ın `skill://agent-stack/<name>` URI'leri altında erişilebilir kılar.

---

## 6. Örnek: Küçük Bir İşin Akışı (complexity: small)

1. Ana ajan: `./run.sh doctor` → `./run.sh intake <owner>` → `./run.sh plan` → `./run.sh apply <hash>`
2. Ana ajan: workflow.yaml okur → `implement-direct` (small path) → **developer rolünü** task subagent'e ver
3. Subagent (developer): rol dosyasını okur, kodu + testi yazar, tsc/vitest çalıştırır, sonucu döndürür
4. Ana ajan: `./run.sh check` → `./run.sh verify` → commit

---

## 7. Örnek: Büyük Bir İşin Akışı (complexity: large)

1. Ana ajan: doctor → intake → plan → apply
2. Ana ajan: propose (analyst subagent) → research (researcher subagent) → design (architect subagent)
3. Architect subagent: tasks.md'de IMPL-001/002 + REVIEW-001/002 çiftleri üretir
4. Ana ajan: tasks.md okur → IMPL-001 ve IMPL-002'yi **paralel** başlatır
5. Her developer bitince: ilgili REVIEW-XXX'i başlatır
6. Tüm REVIEW'ler PASS → ana ajan: reviewer-integration başlatır
7. Ana ajan: tech-writer → gitops → verify

---

## 8. Hata Yönetimi

| Durum | Davranış |
|---|---|
| Subagent yanıt vermedi (timeout) | Ana ajan `job poll` veya yeni subagent ile yeniden dener |
| Subagent "yapamadım" dedi | Hata mesajını oku, düzelt, aynı rolü yeniden başlat |
| IMPL review'da FAIL | Ana ajan developer'ı tekrar çağırır (max 2 loop) |
| run.sh hook fail | Hook çıktısını raporla, işi engelleme (WARN) |

---

## 9. ZORUNLU: Skill + Hook + Command Kullanım Protokolü

### 9.1 Subagent Prompt'u Oluşturma Kuralı

Ana ajan, her subagent'ı başlatmadan ÖNCE şu adımları uygular:

```
ADIM 1: Rol dosyasını oku → .scaffolding/agents/<rol>.md
ADIM 2: YAML frontmatter'dan skills: listesini çıkar
ADIM 3: Prompt'a şu talimatı EKLE:
   "ÖNCE şu skill'leri oku ve uygula:
    - .scaffolding/skills/<skill1>/SKILL.md
    - .scaffolding/skills/<skill2>/SKILL.md"
ADIM 4: İş bittiğinde "run.sh hook post-edit" çağrısını prompt'a EKLE
ADIM 5: Commit öncesi "run.sh hook pre-commit" çağrısını prompt'a EKLE
```

### 9.2 Rol → Zorunlu Skill Eşleşmesi

Tek kaynak: `.scaffolding/agents/<rol>.md` frontmatter `skills:` listesi (AGENTS.md → "Skill Kullanım
Protokolü" ile aynı). Aşağıdaki tablo 2026-09-02 pool'undan türetilmiştir; değişirse rol dosyası geçerlidir.

| Rol | skills: (frontmatter'dan) | Hook |
|---|---|---|
| analyst | research, domain-modeling, to-spec | — |
| architect | domain-modeling, to-spec, codebase-design, improve-codebase-architecture | — |
| developer | implement, implement-spec, tdd, code-review, to-spec | post-edit |
| reviewer | code-review, tdd, to-spec, git-guardrails-claude-code | pre-commit |
| tech-writer | writing-for-agents, writing-beats, writing-fragments, writing-shape | — |
| gitops | git-guardrails-claude-code, resolving-merge-conflicts, handoff | pre-commit |
| researcher | research, domain-modeling, grill-with-docs | — |
| debugger | diagnosing-bugs, tdd, code-review | post-edit |
| optimizer | improve-codebase-architecture, codebase-design, wayfinder | — |
| devops | git-guardrails-claude-code, setup-pre-commit, setup-ts-deep-modules | — |
| coordinator | handoff, claude-handoff, wayfinder | — |
| prompt-engineer | teach, writing-for-agents, to-questionnaire, grill-me | — |
| mcp-builder | wizard, scaffold-exercises, ask-matt | — |

### 9.3 Örnek: Developer Task (DOĞRU)

```python
# Ana ajan (Veyyon) şu task'ı gönderir:
task(
    context="Proje: my-app\nProje kökü: /tmp/my-app\nÇalışma dizini: /tmp/my-app",
    tasks=[{
        "name": "developer-IMPL-001",
        "task": """
[agent-stack] Görev: Email validation implementasyonu

Rol dosyanı OKU ve kurallarına uy:
  /tmp/my-app/.scaffolding/agents/developer.md

ÖNCE şu skill'leri oku ve uygula:
  .scaffolding/skills/implement/SKILL.md
  .scaffolding/skills/implement-spec/SKILL.md
  .scaffolding/skills/tdd/SKILL.md
  .scaffolding/skills/code-review/SKILL.md
  .scaffolding/skills/to-spec/SKILL.md

Görev: src/email.ts'ye email validation ekle:
  - regex format kontrolü
  - MX lookup (opsiyonel)
  - 3 test (valid, invalid, edge)

İş bitince şu hook'ları çalıştır:
  cd /tmp/my-app && ./run.sh hook post-edit
"""
    }]
)
```

### 9.4 Doğrulama

Her subagent'ın çıktısında şunlar KONTROL EDİLİR:
- [ ] SKILL.md dosyası okundu mu? (çıktıda "skills/xxx/SKILL.md" geçmeli)
- [ ] Hook çalıştı mı? (çıktıda "run.sh hook" veya "Hook:" geçmeli)
- [ ] Tüm zorunlu skill'ler okundu mu?
- [ ] İstenen iş yapıldı mı?

Eksik skill okuma varsa → subagent'ı yeniden başlat.

---

## 10. Matt Pocock Skill Chain

The Matt Pocock engineering skills extend the standard workflow.
They are consumed by subagents via the §9 skill protocol — no new workflow steps needed.

### Chain flow

```
setup-matt-pocock-skills (one-time) → grill-with-docs/domain-modeling (during design) → to-spec (spec production) → implement-spec/tdd (coding) → code-review (review)
```

### One-time setup (`setup-matt-pocock-skills`)
Run once per project: generates `docs/agents/issue-tracker.md`, `docs/agents/domain.md`, `docs/agents/triage-labels.md`, and `## Agent skills` block in CLAUDE.md.

### Design phase (domain-modeling / grill-with-docs)
- **architect** role reads `docs/agents/domain.md` → explores `CONTEXT.md` + `docs/adr/` before designing
- **domain-modeling** skill writes/updates `CONTEXT.md` (root) and `docs/adr/` lazily
- **grill-with-docs** skill cross-references existing docs

### Spec phase (to-spec)
- **analyst/architect** role uses `to-spec` skill to publish spec to the project issue tracker
- Reads `docs/agents/` for issue tracker and domain vocabulary

### Implementation phase (implement-spec / tdd / code-review)
- **developer** role uses `implement-spec` + `tdd` + `code-review` skills
- Tests written against existing seams (per `to-spec` output)

### .archcore connection
See §11.

---

## 11. .archcore Connection

The Matt Pocock skills write domain docs to standard locations:
- `CONTEXT.md` at repo root
- `docs/adr/` for ADRs

`.archcore/` gets symlinks to these locations so `archcore status` and future `archcore sync` see the same content:

```
.archcore/CONTEXT.md → ../CONTEXT.md
.archcore/adr        → ../docs/adr
```

These symlinks are created by `run.sh init` (or the first setup-matt-pocock-skills run).
No copy/sync step needed — the content lives in one place.