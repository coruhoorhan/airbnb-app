
/**
 * orchestrator.ts — uçtan uca akış: task goal → router → GitHub çekim → eject → katalog.
 *
 * Bir görev geldiğinde subagent'ın yaptığı her şeyi otomatikleştirir:
 *   1. routeTask(goal)          → hangi flow, hangi skill'ler
 *   2. her skill için kaynak bul → GitHub / catalog
 *   3. fetchSkillFile + ejectSkill → .agents/skills/<name>/SKILL.md
 *   4. buildCatalog             → SKILL-CATALOG.md (yollar + durum)
 *
 * Not: hiçbir skill AI tarafından "yazılmaz" — sadece hazır GitHub dosyası çekilir.
 */

import { join } from "node:path";
import { existsSync, mkdirSync, writeFileSync } from "node:fs";
import { routeTask } from "./ask-matt-router.js";
import {
  MATTPOCOCK_CATALOG,
  searchSkill,
  fetchSkillFile,
  ejectSkill,
  buildCatalog,
  type SkillRef,
  type CatalogEntry,
} from "./skill-registry.js";

export interface WorkflowResult {
  goal: string;
  flowType: string;
  skills: string[];
  ejected: string[];
  skipped: string[];
  failed: string[];
  catalogPath: string;
  ledgersDir: string;
}

/** Harici kaynaklardan (1000+ site / GitHub) gelen skill'ler için arama. */
export interface ExternalSkillSource {
  source: string;       // repo adı, e.g. "davila7/claude-code-templates"
  basePath: string;     // repo içindeki skill kök dizini
  description: string;
}

/**
 * Bir task goal'i alır, tüm akışı yürütür, kataloğu yazar.
 * outDir altına .agents/skills/ ve SKILL-CATALOG.md oluşturur.
 */
export async function runTaskWorkflow(
  goal: string,
  outDir: string,
  externalSources: ExternalSkillSource[] = [],
): Promise<WorkflowResult> {
  const { flowType, skills: routed } = routeTask(goal);

  const result: WorkflowResult = {
    goal,
    flowType,
    skills: routed.map((s) => s.name),
    ejected: [],
    skipped: [],
    failed: [],
    catalogPath: join(outDir, "SKILL-CATALOG.md"),
    ledgersDir: join(outDir, ".agents", "skills"),
  };

  const entries: CatalogEntry[] = [];

  // Her routed skill için:
  // 1) catalog'da ara 2) GitHub'dan çek 3) eject et
  for (const routedSkill of routed) {
    const ref = searchSkill(routedSkill.name, MATTPOCOCK_CATALOG);
    if (!ref) {
      // Model-invoked skill'ler zaten catalog'da olmalı; olmayanı harici kaynakta ara
      const externalRef = await searchExternal(externalSources, routedSkill.name);
      if (!externalRef) {
        result.failed.push(routedSkill.name);
        entries.push({
          name: routedSkill.name,
          repo: "unknown",
          path: "",
          description: routedSkill.reason,
          status: "error",
          error: "not found in any source",
        });
        continue;
      }
      try {
        const ejected = await ejectSkill(externalRef, outDir);
        result.ejected.push(routedSkill.name);
        entries.push({
          name: externalRef.name,
          repo: externalRef.repo,
          path: externalRef.path,
          description: externalRef.description,
          status: ejected ? "ejected" : "skipped",
        });
      } catch (err) {
        result.failed.push(routedSkill.name);
        entries.push({
          name: externalRef.name,
          repo: externalRef.repo,
          path: externalRef.path,
          description: externalRef.description,
          status: "error",
          error: (err as Error).message,
        });
      }
      continue;
    }

    // mattpocock catalog'da bulundu → GitHub'dan çek + eject
    try {
      const ejected = await ejectSkill(ref, outDir);
      if (ejected) result.ejected.push(ref.name);
      else result.skipped.push(ref.name);
      entries.push({
        name: ref.name,
        repo: ref.repo,
        path: ref.path,
        description: ref.description,
        status: ejected ? "ejected" : "skipped",
      });
    } catch (err) {
      result.failed.push(ref.name);
      entries.push({
        name: ref.name,
        repo: ref.repo,
        path: ref.path,
        description: ref.description,
        status: "error",
        error: (err as Error).message,
      });
    }
  }

  // Katalog yaz
  mkdirSync(outDir, { recursive: true });
  buildCatalog(entries, result.catalogPath);

  return result;
}

/**
 * Harici kaynaklarda (1000+ site, GitHub repo'ları) skill ara.
 * Şimdilik basit: description'da isim geçen ilk eşleşmeyi döner.
 * Gerçek entegrasyon: GitHub code search / skills.sh API.
 */
async function searchExternal(
  sources: ExternalSkillSource[],
  skillName: string,
): Promise<SkillRef | null> {
  const matches = sources.filter(
    (s) =>
      s.description.toLowerCase().includes(skillName) ||
      skillName.includes(s.source.split("/").pop()!.toLowerCase()),
  );
  if (matches.length === 0) return null;

  const match = matches[0];
  return {
    name: skillName,
    repo: match.source,
    path: `${match.basePath}/${skillName}/SKILL.md`,
    description: match.description,
  };
}

/* ------------------------------------------------------------------ */
/*  CLI entry point                                                    */
/* ------------------------------------------------------------------ */

// @ts-ignore — when run directly via tsx
const isMain = process.argv[1]?.endsWith("orchestrator.ts");
if (typeof isMain !== "undefined" && isMain) {
  const args = process.argv.slice(2);
  let goal = "";
  let outDir = process.cwd();
  for (let i = 0; i < args.length; i++) {
    if (args[i] === "--goal" && i + 1 < args.length) goal = args[i + 1];
    else if (args[i].startsWith("--goal=")) goal = args[i].split("=")[1];
    if (args[i] === "--out-dir" && i + 1 < args.length) outDir = args[i + 1];
    else if (args[i].startsWith("--out-dir=")) outDir = args[i].split("=")[1];
  }
  runTaskWorkflow(goal, outDir)
    .then((r) => {
      console.log(`flow=${r.flowType}`);
      console.log(`skills=${r.skills.join(",")}`);
      console.log(`ejected=${r.ejected.join(",")}`);
      console.log(`failed=${r.failed.join(",")}`);
      console.log(`catalog=${r.catalogPath}`);
    })
    .catch((e) => { console.error(e.message); process.exit(1); });
}
