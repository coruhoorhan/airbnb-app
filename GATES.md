# Gates: Agent Stack Runtime

OWNS: .scaffolding/, src/, tests/, run.sh

Scope: Agent Stack altyapısının çalışır ve doğrulanabilir olması

- [ ] G1: Tüm skill dosyaları geçerli SKILL.md içeriyor
  CHECK: ls .scaffolding/skills/*/SKILL.md | wc -l
  EXPECT: 55

- [ ] G2: Tüm ajan rol dosyaları geçerli frontmatter içeriyor
  CHECK: bash run.sh validate
  EXPECT: AGENT frontmatter: ALL VALID

- [ ] G3: Tüm 4 validator geçiyor (circuit-breaker dahil)
  CHECK: bash run.sh validate
  EXPECT: CIRCUIT BREAKER

- [ ] G4: run.sh komut yüzeyi eksiksiz (32 komut dispatch)
  CHECK: bash run.sh --help
  EXPECT: orchestrate

- [ ] G5: Tüm hook'lar mevcut ve listelenebilir (20)
  CHECK: ls .scaffolding/hooks/*.sh | wc -l
  EXPECT: 20

- [ ] G6: gates-check.py sözdizimi geçerli
  CHECK: python3 -c "import ast; ast.parse(open('.scaffolding/scripts/gates-check.py').read()); print('SYNTAX_OK')"
  EXPECT: SYNTAX_OK

- [ ] G7: Vitest testleri geçiyor (58/58)
  CHECK: node node_modules/vitest/vitest.mjs run
  EXPECT: 58 passed

- [ ] G8: TypeScript strict temiz
  CHECK: node node_modules/typescript/bin/tsc --noEmit && echo TSC_OK
  EXPECT: TSC_OK
