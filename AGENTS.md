# Agent Stack — Evrensel Kod Ajanı Çalışma Kalıbı

Bu kalıp 3 katmandan oluşur (agent-agnostik, her ajan okuyabilir):
- `.archcore/`  — BAĞLAM: proje neden böyle (ADR/rule/spec). Sahibi: archcore CLI.
- `.scaffolding/` — SÜREÇ: iş hangi sırayla yapılır (workflow YAML + agent roller + skill'ler). Sahibi: bu repo.
- `.harness/`  — DENETİM: her iş bu kurallara uymak zorunda. Sahibi: harness-automation CLI.

## Katman Haritası — Tek Kaynak

Üç katman aynı repoda ama farklı iş yapar. Karışıklığın kaynağı "kim neyi zorlar" sorusunun
cevapsızlığıydı; bu tablo tek cevaptır.

| Katman | Dizin | Sahip/araç | Görevi | Aktif mi? |
|---|---|---|---|---|
| BAĞLAM | `.archcore/` | archcore CLI (v0.7.3) | Proje kararlarını tutar (ADR/rule/spec). "Bilmiyordum, görmedim" bahanesini kaldırır. | PASİF — veyyon'a hook yazmaz, kod yazmayı engellemez. Sadece okunur bağlam. |
| SÜREÇ | `.scaffolding/` | agent-stack (bu repo) | İşin SIRASINI ve KİMİN yaptığını belirler: workflow.yaml adımları → rol dosyası (`agents/<rol>.md`) → frontmatter `skills:` listesi → `run.sh`. | AKTİF — her workflow adımı bir `task` subagent işidir; rol + skill + hook protokolünü belirler. |
| DENETİM | `.harness/` + AGENTS.md + `run.sh` gates/validate | harness-automation + GATES (G1–G8) | Deterministik post-check: 4 validator + G1–G8 + `harness-automation check`/`drift`. Pipeline'ı kırar. | AKTİF — iş bitiminde çalışır, kriter karşılanmazsa engeller. |

**Zorlama zinciri (tek akış):** kullanıcı komutu → veyyon `AGENTS.md`'yi okur (bu harita + aşağıdaki workflow) →
`workflow.yaml` (small ise `implement-direct`, değilse `propose → research → design`) → her adım bir `task`
subagent: `.scaffolding/agents/<rol>.md` okunur, frontmatter `skills:` listesi çıkarılır, subagent o
`.scaffolding/skills/<ad>/SKILL.md` dosyalarını okur ve uygular → kod sonrası `run.sh hook post-edit`,
commit öncesi `run.sh hook pre-commit` → iş bitiminde `run.sh validate` (4/4) + `run.sh gates` (G1–G8) +
`harness-automation check` + `drift` → insan merge onayı. Gates/validate deterministiktir ama ajan/insan
tarafından iş sonunda çağrılır; henüz otomatik CI bağlaması yoktur.

Örnek (kupon expiry ekle): "kupon expiry ekle" → veyyon bu haritayı okur → `workflow.yaml`'de
`complexity` küçükse doğrudan `developer` rolü bir subagent'e verilir → developer `developer.md`'nin
`skills: [implement, implement-spec, tdd, code-review, to-spec]` listesini okur → kodu + testleri yazar →
`run.sh hook post-edit` → `run.sh validate` + `run.sh gates` → insan merge eder. Kuralı çiğneyen çıktı
gates'te yakalanır.

## Dizin Yapısı (Proje Kökü)

```
proje/
├── docs/
│   ├── PRD.md                 # Ürün gereksinim dokümanı — ZORUNLU (intake öncesi)
│   └── research/              # Araştırma kanıtları — ZORUNLU (intake için)
│       └── evidence.md        # En az 1 Markdown/JSON dosyası
├── src/                       # Kaynak kod (ajan yazar)
├── tests/                     # Testler (ajan yazar)
├── .archcore/                 # Archcore tarafından yönetilir
├── .scaffolding/              # Bu template'den kopyalanır
│   ├── workflows/
│   │   └── workflow.yaml      # İş akışı tanımı (ajan OKUR, scaffolding CLI İŞLETİR)
│   ├── agents/                # 13 agent rolü (analyst, developer, reviewer...)
│   ├── skills/                # 55 skill (ajan OKUMAK ZORUNDA)
│   │   └── (55 skill — ad listesi için .scaffolding/skills/ veya SKILL-CATALOG.md)
│   ├── hooks/                 # 20 hook (ajan yaşam döngüsü)
│   └── commands/              # 9 komut tanımı
├── .harness/                  # Harness-automation tarafından yönetilir
├── AGENTS.md                  # BU DOSYA — ajanın birincil rehberi
├── CLAUDE.md                  # İkincil rehber (Claude Code, Cursor uyumluluğu)
├── run.sh                     # Deterministik orkestratör (köprü)
└── .gitignore                 # Hariç listesi (node_modules, dist, .harness/changes)
```

## Routing Protokolü

- **Mühendislik işi** (kod yazma/değiştirme, tasarım, test) → `.scaffolding/workflows/workflow.yaml` sırasına göre yapılır.
- **Basit/faktüel sorular** (duvar saati kaç, şu paketin versiyonu ne) → doğrudan yanıtlanabilir.
- **Her adım sonunda** `./run.sh check` ile deterministik doğrulama yapılır.
- **run.sh** tüm ajanlar için aynıdır; ajan **yalnızca reasoning** yapar (analiz/tasarım/kod/test).

## Adım Adım Çalışma Protokolü

### HAZIRLIK

1. **Proje yapısını kontrol et:** `docs/PRD.md` var mı? `docs/research/evidence.md` var mı? Yoksa oluştur.
2. Her workflow adımının hangi skill'i okuyacağı TEK kaynaktan gelir: `.scaffolding/agents/<rol>.md` frontmatter `skills:` listesi. Bu listedeki her ad, `.scaffolding/skills/<ad>/SKILL.md` dosyasına karşılık gelir — ad listesi için `ls .scaffolding/skills/` veya `SKILL-CATALOG.md`.
3. **`.gitignore`** kontrol et (yoksa template'den kopyala).
4. `./run.sh doctor` — ortam/uyum kontrolü

### KAYNAK ONAYI

5. `./run.sh intake <owner>` — kaynak onayı
   - **Beklenen dizin yapısı:**
     - `docs/PRD.md` — ürün gereksinim dokümanı (ZORUNLU)
     - `docs/research/` — araştırma kanıtları dizini (ZORUNLU, içinde en az 1 .md/.json dosyası)
   - SHA-256 ile kaynak hash'lenir, `.harness/sources/` altına kaydedilir.
   - **DİKKAT:** `docs/research.md` dosyası değil, `docs/research/` DİZİNİ olmalı.

### PLANLAMA

6. `./run.sh plan` — deterministik plan üret (hash'li)
7. `./run.sh apply <hash>` — policy + AGENTS.md yaz

### İŞ AKIŞI (workflow.yaml)

8. **workflow.yaml OKU** ve adımları sırayla uygula:

   | Adım | Rol | Ne Yapılır |
   |---|---|---|
   | **propose** | analyst | Proje teklifi yaz → `docs/specs/proposal.md` |
   | **research** | researcher | Araştırma yap → `docs/specs/ResearchPack.md` |
   | **design** | architect | Mimari tasarım + görev dökümü → `docs/specs/design.md` + `tasks.md` |
   | **implement** | *(dynamic)* | **IMPLEMENTASYON:** `tasks.md`'deki IMPL-XXX görevlerini gerçekleştir. Her IMPL için bir DEVELOPER, bir REVIEWER atanır. IMPL-XXX → developer, REVIEW-XXX → reviewer. Paralel IMPL'ler eşzamanlı çalışır. Kod yaz + test yaz. |
   | **review** | reviewer | Tüm değişiklikleri bütünleşik incele |
   | **document** | tech-writer | CHANGELOG + README güncelle |
   | **push** | gitops | Commit + push (remote yoksa yerel commit) |

   **Dynamic implement açıklaması:** `implement` adımı `type: dynamic` olarak tanımlanmıştır. Bu, scaffolding CLI'nin runtime'da tasks.md'deki ISSUE listesini okuyup her IMPL-XXX için ayrı developer görevi başlattığı anlamına gelir. Eğer scaffolding CLI kullanılmıyorsa (örneğin ajan doğrudan çalışıyorsa), ajan tasks.md'deki görevleri sırayla veya paralel olarak manuel yürütmelidir.

   **Küçük işler için:** `complexity == 'small'` ise propose+design+dynamic implement atlanır, doğrudan `implement-direct` adımına gidilir. Bu durumda ajan tek adımda çözümü yazar.

### DOĞRULAMA

9. `./run.sh check` — policy doğrula (gerekirse düzelt)
10. `./run.sh verify` — test + typecheck + lint:size + check + drift (hepsi yeşil olmalı)
11. Git commit + push (remote varsa)
12. `./run.sh check` — son durumda policy hâlâ geçerli mi?


## Veyyon Runtime

Bu çalışma ortamı **veyyon**'dur. Tüm workflow adımları `task` subagent'ları ile yürütülür.
Detaylı protokol: `.scaffolding/adapters/veyyon.md` — ÖNCE OKU.

### Temel kural
```
Ana ajan:  task(context, tasks=[{name: "<rol>-<kisa-tanim>", task: "..."}])
Subagent:  .scaffolding/agents/<rol>.md OKUR → görevi yapar → sonucu döndürür
Ana ajan:  cevabı alır → sonraki adıma geçer
```

**Rol eşleşmesi (workflow.yaml → task):** Tablo adapters/veyyon.md §2'de.

**Subagent skill/hook protokolü:** adapters/veyyon.md §9'da.


## Skill Kullanım Protokolü

Tek kaynak: `.scaffolding/agents/<rol>.md` frontmatter `skills:` listesi. Aşağıdaki tablo 2026-09-02
pool'undan türetilmiştir; rol dosyası değişirse tablo değil, rol dosyası geçerlidir.

| Workflow adımı | Rol dosyası | skills: (frontmatter'dan) |
|---|---|---|
| propose | analyst.md | research, domain-modeling, to-spec |
| research | researcher.md | research, domain-modeling, grill-with-docs |
| design | architect.md | domain-modeling, to-spec, codebase-design, improve-codebase-architecture |
| implement / implement-direct | developer.md | implement, implement-spec, tdd, code-review, to-spec |
| review | reviewer.md | code-review, tdd, to-spec, git-guardrails-claude-code |
| document | tech-writer.md | writing-for-agents, writing-beats, writing-fragments, writing-shape |
| push | gitops.md | git-guardrails-claude-code, resolving-merge-conflicts, handoff |
| (destek) debugger | debugger.md | diagnosing-bugs, tdd, code-review |
| (destek) devops | devops.md | git-guardrails-claude-code, setup-pre-commit, setup-ts-deep-modules |
| (destek) optimizer | optimizer.md | improve-codebase-architecture, codebase-design, wayfinder |
| (destek) mcp-builder | mcp-builder.md | wizard, scaffold-exercises, ask-matt |
| (destek) coordinator | coordinator.md | handoff, claude-handoff, wayfinder |
| (destek) prompt-engineer | prompt-engineer.md | teach, writing-for-agents, to-questionnaire, grill-me |

Her skill'in dosyası: `.scaffolding/skills/<ad>/SKILL.md`. Subagent o dosyayı okur ve kurallarına uyar.

## Bilinen Sınırlamalar

1. **Stack zorlama:** `plan --stack typescript` zorlamaz; `discover` ne bulursa onu kullanır.
2. **Push:** Remote (origin) yoksa commit yerel kalır, push atlanır.
3. **Archcore sync:** `.archcore/` zaten Git'te; `archcore sync` bulut push'u "coming soon".
4. **Harness intake:** `docs/research/` DİZİNİ (klasör) bekler, `docs/research.md` dosyası değil.
5. **Dynamic implement:** scaffolding CLI yoksa, ajan tasks.md'deki ISSUE listesini manuel yürütür.
6. **AGENTS.md/CLAUDE.md drift:** Bu dosyalar harness-automation plan/apply tarafından yönetilir.
   Elle düzenleme sonrası `harness plan` + `apply` çalıştırılarak manifest güncellenir.


## Agent skills

### Issue tracker

Issues are tracked as local markdown files under `.scratch/<feature>/`. See `docs/agents/issue-tracker.md`.

### Triage labels

Five canonical labels: `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: `CONTEXT.md` at repo root + `docs/adr/` for ADRs. See `docs/agents/domain.md`.

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
