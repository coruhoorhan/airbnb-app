
/**
 * skill-registry.ts — GitHub skill arama, tekil çekim, eject, katalog.
 *
 * Asla tüm skill'leri indirmez. Sadece ihtiyaç olanı tekil çeker:
 *   1. searchSkill()  → task goal'e göre uygun skill bul (keyword match)
 *   2. fetchSkillFile() → GitHub raw'dan tek SKILL.md çek
 *   3. ejectSkill()    → .agents/skills/<name>/ altına kur
 *   4. buildCatalog()  → SKILL-CATALOG.md yaz (yollar + durum)
 *
 * Kaynak: mattpocock/skills (standart) + diğer GitHub repo'ları.
 */

import { existsSync, mkdirSync, writeFileSync, appendFileSync, readFileSync } from "node:fs";
import { join, dirname } from "node:path";

/* ------------------------------------------------------------------ */
/*  Types                                                             */
/* ------------------------------------------------------------------ */

export interface SkillRef {
  name: string;
  repo: string;       // e.g. "mattpocock/skills" or "davila7/claude-code-templates"
  path: string;       // e.g. "skills/engineering/tdd/SKILL.md"
  description: string;
  license?: string;
}

export interface CatalogEntry {
  name: string;
  repo: string;
  path: string;
  description: string;
  status: "fetched" | "ejected" | "skipped" | "error";
  error?: string;
}

/* ------------------------------------------------------------------ */
/*  built-in catalog — mattpocock/skills engineering + productivity  */
/* ------------------------------------------------------------------ */

const MATTPOCOCK_CATALOG: SkillRef[] = [
  { name: "tdd",             repo: "mattpocock/skills", path: "skills/engineering/tdd/SKILL.md",             description: "Test-driven development: red-green-refactor loop, one vertical slice at a time" },
  { name: "ask-matt",        repo: "mattpocock/skills", path: "skills/engineering/ask-matt/SKILL.md",        description: "Ask which skill or flow fits your situation. A router over the skills." },
  { name: "code-review",     repo: "mattpocock/skills", path: "skills/engineering/code-review/SKILL.md",     description: "Two-axis review: Standards and Spec, parallel sub-agents." },
  { name: "codebase-design", repo: "mattpocock/skills", path: "skills/engineering/codebase-design/SKILL.md", description: "Design deep modules: behaviour behind small interface, testable seam." },
  { name: "prototype",       repo: "mattpocock/skills", path: "skills/engineering/prototype/SKILL.md",       description: "Build a throwaway prototype to answer a design question." },
  { name: "research",        repo: "mattpocock/skills", path: "skills/engineering/research/SKILL.md",        description: "Investigate a question against high-trust primary sources." },
  { name: "domain-modeling", repo: "mattpocock/skills", path: "skills/engineering/domain-modeling/SKILL.md", description: "Build and sharpen project domain model: glossary, edge-cases, ADRs." },
  { name: "diagnosing-bugs", repo: "mattpocock/skills", path: "skills/engineering/diagnosing-bugs/SKILL.md", description: "Disciplined diagnosis loop: red → minimise → hypothesise → fix." },
  { name: "implement",       repo: "mattpocock/skills", path: "skills/engineering/implement/SKILL.md",       description: "Build work from a spec or set of tickets, driving /tdd at seams." },
  { name: "grill-with-docs", repo: "mattpocock/skills", path: "skills/engineering/grill-with-docs/SKILL.md", description: "Grilling session that builds domain model, terminology, ADRs." },
  { name: "handoff",         repo: "mattpocock/skills", path: "skills/productivity/handoff/SKILL.md",        description: "Compact conversation into handoff doc for another agent." },
  { name: "grilling",        repo: "mattpocock/skills", path: "skills/productivity/grilling/SKILL.md",       description: "Interview user relentlessly until every branch is resolved." },
  { name: "writing-for-agents", repo: "mattpocock/skills", path: "skills/productivity/writing-for-agents/SKILL.md", description: "Write documents for agents: skills, AGENTS.md, CLAUDE.md." },
  { name: "wizard",          repo: "mattpocock/skills", path: "skills/engineering/wizard/SKILL.md",          description: "Generate interactive bash wizard for human-only steps." },
  { name: "to-spec",         repo: "mattpocock/skills", path: "skills/engineering/to-spec/SKILL.md",         description: "Turn conversation into a spec and publish to issue tracker." },
  { name: "to-tickets",      repo: "mattpocock/skills", path: "skills/engineering/to-tickets/SKILL.md",      description: "Break spec into tracer-bullet tickets with blocking edges." },
  { name: "wayfinder",       repo: "mattpocock/skills", path: "skills/engineering/wayfinder/SKILL.md",       description: "Plan huge work as shared map of decision tickets." },
  { name: "triage",          repo: "mattpocock/skills", path: "skills/engineering/triage/SKILL.md",          description: "Move issues through a state machine of triage roles." },
  { name: "improve-codebase-architecture", repo: "mattpocock/skills", path: "skills/engineering/improve-codebase-architecture/SKILL.md", description: "Scan codebase for deepening opportunities, visual HTML report." },
  { name: "setup-matt-pocock-skills", repo: "mattpocock/skills", path: "skills/engineering/setup-matt-pocock-skills/SKILL.md", description: "Configure repo for engineering skills: tracker, labels, layout." },
  { name: "teach",           repo: "mattpocock/skills", path: "skills/productivity/teach/SKILL.md",          description: "Teach user a new skill over multiple sessions." },
  { name: "to-questionnaire", repo: "mattpocock/skills", path: "skills/productivity/to-questionnaire/SKILL.md", description: "Turn decision into Markdown questionnaire for decision-maker." },
  { name: "wait-what",       repo: "mattpocock/skills", path: "skills/productivity/wait-what/SKILL.md",     description: "Re-pitch message with context you are missing, plain English." },
  { name: "grill-me",        repo: "mattpocock/skills", path: "skills/productivity/grill-me/SKILL.md",       description: "Get relentlessly interviewed about a plan or design." },
];

/** All registered skill sources. */
export const ALL_CATALOGS: SkillRef[] = [...MATTPOCOCK_CATALOG];

/** mattpocock/skills standart kataloğu — harici kaynaklar da eklenebilir. */
export { MATTPOCOCK_CATALOG };

/* ------------------------------------------------------------------ */
/*  searchSkill — task goal'e göre uygun skill bul                    */
/* ------------------------------------------------------------------ */

/**
 * Deterministic keyword search across skill descriptions.
 * Returns the best-matching skill or null.
 */
export function searchSkill(
  query: string,
  catalog: SkillRef[] = ALL_CATALOGS,
): SkillRef | null {
  const q = query.toLowerCase();
  const words = q.split(/\s+/).filter((w) => w.length > 2);

  let best: SkillRef | null = null;
  let bestScore = 0;

  for (const skill of catalog) {
    const desc = skill.description.toLowerCase();
    const name = skill.name.toLowerCase();
    let score = 0;

    for (const word of words) {
      if (desc.includes(word)) score += 1;
      if (name.includes(word)) score += 2; // name match weighs more
    }

    if (score > bestScore) {
      bestScore = score;
      best = skill;
    }
  }

  return bestScore > 0 ? best : null;
}

/**
 * Find multiple skills matching a query (for router).
 */
export function searchSkills(
  query: string,
  catalog: SkillRef[] = ALL_CATALOGS,
): SkillRef[] {
  const q = query.toLowerCase();
  const words = q.split(/\s+/).filter((w) => w.length > 2);

  const scored: { skill: SkillRef; score: number }[] = [];

  for (const skill of catalog) {
    const desc = skill.description.toLowerCase();
    const name = skill.name.toLowerCase();
    let score = 0;

    for (const word of words) {
      if (desc.includes(word)) score += 1;
      if (name.includes(word)) score += 2;
    }

    if (score > 0) scored.push({ skill, score });
  }

  return scored.sort((a, b) => b.score - a.score).map((s) => s.skill);
}

/* ------------------------------------------------------------------ */
/*  fetchSkillFile — GitHub raw'dan tek SKILL.md çek                  */
/* ------------------------------------------------------------------ */

/**
 * Download a single SKILL.md from GitHub via raw.githubusercontent.com.
 * Rate limit: GitHub raw API is not rate-limited for public repos.
 */
export async function fetchSkillFile(skill: SkillRef): Promise<string> {
  const url = `https://raw.githubusercontent.com/${skill.repo}/main/${skill.path}`;
  const resp = await fetch(url);
  if (!resp.ok) {
    throw new Error(`fetchSkillFile failed: ${resp.status} ${resp.statusText} for ${url}`);
  }
  return resp.text();
}

/* ------------------------------------------------------------------ */
/*  ejectSkill — skill'i .agents/skills/<name>/ altına kur            */
/* ------------------------------------------------------------------ */

/**
 * Download a skill and eject it into the project's .agents/skills/ dir.
 * Returns true if newly ejected, false if already exists.
 */
export async function ejectSkill(
  skill: SkillRef,
  projectRoot: string,
): Promise<boolean> {
  const destDir = join(projectRoot, ".agents", "skills", skill.name);
  const destFile = join(destDir, "SKILL.md");

  if (existsSync(destFile)) {
    return false; // already ejected
  }

  const content = await fetchSkillFile(skill);
  mkdirSync(destDir, { recursive: true });
  writeFileSync(destFile, content, "utf-8");
  return true;
}

/* ------------------------------------------------------------------ */
/*  buildCatalog — SKILL-CATALOG.md yaz (yollar + durum)             */
/* ------------------------------------------------------------------ */

/**
 * Build a markdown catalog of all fetched/ejected skills.
 * Append-only: existing catalog is preserved.
 */
export function buildCatalog(
  entries: CatalogEntry[],
  catalogPath: string,
): void {
  const header = existsSync(catalogPath)
    ? ""
    : "# SKILL-CATALOG — Skill Registry & Eject Status\n\n";

  const lines = entries.map(
    (e) =>
      `| ${e.name} | ${e.repo} | ${e.path} | ${e.description} | ${e.status}${e.error ? ` (${e.error})` : ""} |`,
  );

  const table = [
    (header || undefined),
    header ? null : "| Skill | Repo | Path | Description | Status |",
    header ? null : "|---|---|---|---|---|",
    ...lines,
    "",
  ]
    .filter(Boolean)
    .join("\n");

  if (header) {
    appendFileSync(catalogPath, table, "utf-8");
  } else {
    writeFileSync(catalogPath, table, "utf-8");
  }
}
