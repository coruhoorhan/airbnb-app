# Agent Stack — Evrensel Kod Ajanı Kalıbı

3 katmanlı, agent-agnostik çalışma kalıbı. Prime Agent, OpenCode, OMP, Claude Code,
Cursor, Codex — hepsi aynı dosyaları okur, aynı komutları çalıştırır.

## Katmanlar

| Katman | Dizin | Sahibi | Rolü |
|---|---|---|---|
| BAĞLAM | `.archcore/` | archcore CLI | Proje neden böyle (ADR/rule/spec) |
| SÜREÇ | `.scaffolding/` | bu repo | İş hangi sırayla (workflow.yaml + agent roller) |
| DENETİM | `.harness/` | harness-automation CLI | Her iş kurallara uymalı (hash/check/drift) |

## Kurulum

```bash
# Yeni proje
mkdir my-project && cd my-project
cp -r /path/to/agent-stack/* .
./run.sh init

# Veya mevcut projeye
git clone <agent-stack-repo> .agent-stack
cp .agent-stack/AGENTS.md .agent-stack/CLAUDE.md .agent-stack/run.sh .
cp -r .agent-stack/.scaffolding .
./run.sh init
```

## Kullanım (herhangi bir ajan için)

```bash
./run.sh doctor           # ortam kontrolü
./run.sh intake <owner>   # PRD/research SHA-256 onayı
./run.sh plan             # immutable plan + hash
./run.sh apply <hash>     # policy + AGENTS.md yaz
# workflow.yaml'i oku → reasoning adımları (propose→research→design→implement→review)
./run.sh check            # policy doğrula
./run.sh verify           # test + typecheck + lint:size + check + drift
```

## Nasıl çalışır (akış)

veyyon = runtime + enforcement host: `AGENTS.md`'yi okur (plan mode, `task` subagent'lar). İşin
SIRASI `.scaffolding/workflows/workflow.yaml`'den gelir; her workflow adımı bir `task` subagent işidir.
Rol + skill eşleşmesinin TEK kaynağı `.scaffolding/agents/<rol>.md` frontmatter `skills:` listesidir
(ad listesi: `ls .scaffolding/skills/` veya `SKILL-CATALOG.md`). İş bitiminde deterministik doğrulama
çalışır: `run.sh validate` (4/4) + `run.sh gates` (G1–G8) + `harness-automation check` — ardından insan
merge onayı.

Örnek (kupon expiry ekle): "kupon expiry ekle" → veyyon AGENTS.md'yi okur → `workflow.yaml`'de
`complexity` küçükse doğrudan `developer` rolü bir subagent'e verilir → developer kodu + testleri yazar →
`run.sh validate` + `run.sh gates` → insan merge eder.

## Bilinen Sınırlamalar

1. **Stack zorlama:** `plan --stack typescript` auto-detect'i geçersiz kılmaz;
   dosyalar oluşturulduktan sonra `discover` ne bulursa onu kullanır.
2. **Push:** Remote (origin) yoksa commit yerel kalır; push adımı atlanır ve raporlanır.
3. **Harness install:** Skill'ler `~/.agents/skills/` altına kurulur (istediğinde),
   CLI binary'si her zaman çalışır.
4. **Archcore sync:** `.archcore/` zaten Git'te; `archcore sync` bulut push'u
   henüz "coming soon" durumunda.

## Responsive UI Implementations & Breakpoints

To ensure optimal layout across various screen sizes, this project uses specific Tailwind responsive breakpoints and utilities:
- **Mobile (`<640px`)**: Uses standard base classes. Width constraints like `w-[calc(100vw-2rem)]` are used to prevent overflow.
- **Tablet (`sm`, `md` breakpoints)**: Adjusts layout elements (e.g. `sm:w-[380px]`, `md:w-[420px]`).
- **Desktop (`lg`, `xl` breakpoints)**: Restores expansive views, like `lg:flex` for the navbar search pill to avoid clutter on smaller screens.

### Recent Accessibility Adjustments
- Dynamic focus management and ARIA standard roles/labels have been added to Modals (e.g., `ChatModal`, `MagdaConciergeWidget`).
- Adjusted gradient backgrounds to meet the 4.5:1 contrast ratio (`from-rose-600 via-pink-600 to-rose-700`).
