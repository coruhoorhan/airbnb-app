
/**
 * ask-matt-router.ts — mattpocock ask-matt skill'ini simüle eden router.
 *
 * "Hangi skill çağrılacak, ne zaman, neden?" sorusunun cevabı.
 * LLM karar vermez — deterministik kurallarla:
 *
 *   Flow tipi      → hangi skill'ler kullanılacak
 *   Invocation     → user-invoked (orchestrate) vs model-invoked (discipline)
 *
 * mattpocock/skills mimarisinden birebir türetilmiştir:
 *   - ask-matt: router over user-invoked skills
 *   - model-invoked skill'ler otomatik erişilebilir
 *   - user-invoked skill başka user-invoked skill'i çağıramaz
 */

export type FlowType = "build" | "research" | "plan" | "debug" | "default";

export interface RoutedSkill {
  name: string;
  invocation: "user" | "model";
  reason: string;
}

/* ------------------------------------------------------------------ */
/*  Keyword kuralları                                                  */
/* ------------------------------------------------------------------ */

// "plan" yalnız tam kelime ("planları" ≠ "plan"); "tasarla/mimari" stem bazlı.
// Tüm plan keyword'leri exact match: "planları" ≠ "planla", "plan" yalnız tek başına.
const PLAN_KEYWORDS_EXACT = [
  "plan", "planla", "planlı", "roadmap", "strateji", "strategy",
  "tasarla", "tasarım", "design", "mimari", "architecture",
  "spec", "ticket", "görev", "görevler",
];
const RESEARCH_KEYWORDS_STEM = [
  "araştır", "karşılaştır", "research", "compare", "investigate",
  "analiz", "benchmark", "kıyasla", "öğren",
];
const DEBUG_KEYWORDS_STEM = [
  "hata", "bug", "düzelt", "fix", "çalışmıyor", "broken", "fail", "crash",
  "yavaş", "error", "exception", "sorun", "problem", "debug",
];
const BUILD_KEYWORDS_STEM = [
  "geliştir", "yap", "kur", "oluştur", "yaz", "build", "create", "implement",
  "kayıt", "üyelik", "auth", "otp", "register", "signup", "login", "sistem",
  "api", "endpoint", "uygulama", "app", "feature", "özellik", "ekle",
  "sms", "email", "verification", "doğrulama", "abonelik",
];

/* ------------------------------------------------------------------ */
/*  Flow detection — task goal'den deterministik karar               */
/* ------------------------------------------------------------------ */

function tokenize(goal: string): string[] {
  return goal
    .toLowerCase()
    .split(/[^a-zçğıöşü0-9]+/)
    .filter((t) => t.length >= 2);
}

export function determineFlow(goal: string): FlowType {
  const tokens = tokenize(goal);

  const matchStem = (kw: string): boolean =>
    tokens.some((t) => t === kw || t.startsWith(kw));

  const matchExact = (kw: string): boolean => tokens.includes(kw);

  const score: Record<FlowType, number> = { build: 0, research: 0, plan: 0, debug: 0, default: 0 };

  for (const kw of RESEARCH_KEYWORDS_STEM) if (matchStem(kw)) score.research += 1;
  for (const kw of DEBUG_KEYWORDS_STEM) if (matchStem(kw)) score.debug += 1;
  for (const kw of PLAN_KEYWORDS_EXACT) if (matchExact(kw)) score.plan += 1;
  for (const kw of BUILD_KEYWORDS_STEM) if (matchStem(kw)) score.build += 1;

  // debug > research > plan > build — bug önceliklidir
  const order: FlowType[] = ["debug", "research", "plan", "build"];
  for (const f of order) {
    if (score[f] > 0) return f;
  }
  return "default";
}

/* ------------------------------------------------------------------ */
/*  Skill routing — flow tipine göre skill seçimi                     */
/* ------------------------------------------------------------------ */

function skill(name: string, invocation: "user" | "model", reason: string): RoutedSkill {
  return { name, invocation, reason };
}

/** Flow tipine göre temel skill seti (model-invoked = otomatik erişim). */
function skillsForFlow(flow: FlowType): RoutedSkill[] {
  switch (flow) {
    case "build":
      return [
        skill("domain-modeling", "model", "İş modelini netleştir: terminoloji, edge-case'ler, ADR'ler"),
        skill("tdd", "model", "Vertical slice ile red-green-refactor döngüsü"),
        skill("code-review", "model", "Tamamlanmadan önce Standards + Spec çift eksenli review"),
        skill("grill-with-docs", "user", "İhtiyaç netleştirme — planı sorularla dallanıp budaklandır"),
      ];
    case "research":
      return [
        skill("research", "model", "Yüksek güvenilir birincil kaynaklara karşı araştırma"),
        skill("prototype", "model", "Tasarım sorusunu yanıtlamak için atılabilir prototip"),
      ];
    case "debug":
      return [
        skill("diagnosing-bugs", "model", "Disiplinli hata teşhisi: kırmızı → küçült → hipotez → onar"),
        skill("tdd", "model", "Regression testiyle düzeltmeyi güvence altına al"),
      ];
    case "plan":
      return [
        skill("wayfinder", "user", "Büyük işi karar ticket'ları haritasına böl"),
        skill("to-spec", "user", "Konuşmayı spec'e çevir ve issue tracker'a yayınla"),
        skill("to-tickets", "user", "Spec'i blocking edge'leri bildiren ticket'lara böl"),
        skill("domain-modeling", "model", "Terminoloji ve domain modelini netleştir"),
      ];
    case "default":
    default:
      return [
        skill("grilling", "model", "Planın her dalını çözmek için görüşme primitifi"),
        skill("ask-matt", "user", "Hangi skill'in uyduğundan emin değilsek router'a danış"),
      ];
  }
}

/**
 * Goal'i bir dizi skill'e çevirir.
 * ask-matt'ın "router over user-invoked skills" davranışını simüle eder:
 * her flow, model-invoked disiplin skill'leri + gerekli user-invoked orchestration.
 */
export function routeTask(goal: string): { flowType: FlowType; skills: RoutedSkill[] } {
  const flowType = determineFlow(goal);
  return { flowType, skills: skillsForFlow(flowType) };
}
