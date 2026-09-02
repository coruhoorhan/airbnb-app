# Gates: {task-name}

OWNS: {repository-relative-globs-this-leaf-may-write}

Scope: {one-sentence-deliverable}

- [ ] G1: {observable-outcome-measured-from-the-artifact}
  CHECK: {command-that-verifies}
  EXPECT: {expected-success-marker}
  EVIDENCE: pending

- [ ] G2: {second-observable-outcome}
  CHECK: {command-2}
  EXPECT: {expected-success-marker-2}
  CWD: {working-directory-if-not-root}
  EVIDENCE: pending

<!--
Kurallar (unlazy'den uyarlandı, AGENTS.md §15):
1. Her IMPL görevi için GATES.md işe başlamadan ÖNCE yazılır.
2. CHECK: komutu + EXPECT: başarı marker'ı zorunlu (manuel gate hariç).
3. Gate ancak komut exit=0 VE EXPECT eşleşirse methedir.
4. EVIDENCE: pending → çalıştırınca kanıt yazılır.
5. İmkansız gate: ABANDON: G<n> <sebep> — bu başarı değil, HANDOFF'tur.
6. Eski kanıt = kanıt değil → run.sh verify --reverify ile yeniden çalıştır.
-->

# Örnek (Math Utils Service'ten):
# - [ ] G1: string-utils testleri geçiyor
#   CHECK: npx vitest run tests/string-utils.test.ts
#   EXPECT: passed
#   EVIDENCE: pending
# - [ ] G2: tsc temiz derliyor
#   CHECK: npx tsc --noEmit
#   EXPECT: TSC_OK
#   EVIDENCE: pending
