/**
 * skill-advisor.ts — deterministic skill selection + decision ledger.
 *
 * Pattern source: harness-agent (tool-selector.ts P7-2) + harnex (gates.md).
 *
 * Three responsibilities:
 *  1. selectSkills  — deterministic keyword/category matching. NEVER an LLM
 *     router: a misclassification can only DROP peripheral skills, never the
 *     core set a coding task needs.
 *  2. writeLedger   — append-only decision record (SKILL-LEDGER.md). An
 *     unrecorded decision is a decision that did not fire.
 *  3. recordEffectiveness — per-skill JSONL ledger (discovered != effective).
 */

import { existsSync, appendFileSync } from "node:fs";

/** A skill as declared in the harness skill catalog. */
export interface SkillSpec {
  name: string;
  description: string;
  requiredTools?: string[];
  provenance?: "local-filesystem" | "remote";
  trust?: "trusted" | "semi-trusted" | "untrusted";
}

/** The task the advisor is selecting skills for. */
export interface AdvisorTask {
  goal: string;
  changedPaths: string[];
  cwd: string;
}

export interface SelectionResult {
  selected: SkillSpec[];
  dropped: string[];
}

export interface LedgerEntry {
  taskId: string;
  taskGoal: string;
  selected: SkillSpec[];
  dropped: string[];
  timestamp: string;
  decision: "approved" | "rejected" | "needs_revision" | "deferred";
}

export interface EffectivenessEntry {
  skillName: string;
  taskId: string;
  selectedAt: string;
  loaded: boolean;
  completed: boolean;
  tokenCount: number;
  verificationPassed: boolean;
}

/** Category -> keywords. Matching ANY keyword keeps those skills. */
interface SkillCategory {
  keywords: string[];
  skillNames: string[];
}

/**
 * Core skills always selected. Rationale (mirrors tool-selector CORE_TOOLS):
 * without these a coding task cannot be done with discipline, so a
 * misclassification must never drop them.
 */
const CORE_SKILLS = ["testing-strategy", "error-handling", "pattern-recognition"];

/** Peripheral categories — only added when the goal mentions the topic. */
const EXTRA_BY_KEYWORD: SkillCategory[] = [
  { keywords: ["http", "api", "url", "curl", "fetch", "rest", "network", "download"], skillNames: ["network-tools"] },
  { keywords: ["test", "unit", "integration", "spec", "verify", "validate"], skillNames: ["testing-strategy"] },
  { keywords: ["error", "exception", "fail", "throw", "catch"], skillNames: ["error-handling"] },
  { keywords: ["pattern", "style", "convention", "refactor", "naming"], skillNames: ["pattern-recognition"] },
];

/** Default catalog — the harness's declared skills. */
const DEFAULT_CATALOG: SkillSpec[] = [
  {
    name: "testing-strategy",
    description: "Apply test patterns: describe/it, arrange/act/assert, edge cases, TDD",
    requiredTools: ["vitest", "typescript"],
    provenance: "local-filesystem",
    trust: "semi-trusted",
  },
  {
    name: "error-handling",
    description: "Typed errors, fail-fast, meaningful messages, never silent catch",
    provenance: "local-filesystem",
    trust: "semi-trusted",
  },
  {
    name: "pattern-recognition",
    description: "Naming conventions, code style, anti-patterns, structural analysis",
    provenance: "local-filesystem",
    trust: "semi-trusted",
  },
  {
    name: "network-tools",
    description: "HTTP requests, API calls, network diagnostics",
    requiredTools: ["curl"],
    provenance: "remote",
    trust: "untrusted",
  },
];

/**
 * Deterministic selection. Every core skill is kept; a skill is additionally
 * selected when the goal mentions one of its category keywords. Everything
 * else is dropped and reported (P7-3 telemetry).
 */
export function selectSkills(
  task: AdvisorTask,
  catalog: SkillSpec[] = DEFAULT_CATALOG,
): SelectionResult {
  const goal = (task.goal ?? "").toLowerCase();
  const keep = new Set<string>(CORE_SKILLS);

  for (const category of EXTRA_BY_KEYWORD) {
    if (category.keywords.some((keyword) => goal.includes(keyword))) {
      for (const name of category.skillNames) keep.add(name);
    }
  }

  const selected = catalog.filter((skill) => keep.has(skill.name));
  const dropped = catalog.filter((skill) => !keep.has(skill.name)).map((s) => s.name);
  return { selected, dropped };
}

/**
 * Append-only decision record. One bullet per task; the history of a decision
 * is the interesting part — overwriting would keep only the last one.
 */
export function writeLedger(entry: LedgerEntry, ledgerPath: string): void {
  const header = existsSync(ledgerPath)
    ? ""
    : "# SKILL-LEDGER \u2014 Skill Selection & Decision Log\n\n";
  const line = [
    `## ${entry.taskId} (${entry.timestamp}) · decision: ${entry.decision}`,
    `- goal: ${entry.taskGoal}`,
    `- selected: ${entry.selected.map((s) => s.name).join(", ") || "(none)"}`,
    `- dropped: ${entry.dropped.join(", ") || "(none)"}`,
    "",
  ].join("\n");
  appendFileSync(ledgerPath, header + line, "utf-8");
}

/** JSONL effectiveness ledger — one line per skill use. */
export function recordEffectiveness(entry: EffectivenessEntry, effPath: string): void {
  appendFileSync(effPath, JSON.stringify(entry) + "\n", "utf-8");
}
