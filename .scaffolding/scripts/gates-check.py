#!/usr/bin/env python3
"""GATES.md checker — unlazy-style acceptance ledger runner."""
import re, subprocess, sys, os

def main():
    ledger_path = "GATES.md"
    if not os.path.exists(ledger_path):
        print(f"GATES.md yok. Şablon: .scaffolding/templates/GATES.template.md")
        print("İşe başlamadan ÖNCE kabul kriterlerini yaz.")
        sys.exit(1)

    ledger = open(ledger_path).read()
    # Blokları ayır: her "- [ ] G<n>:" bir blok
    blocks = re.split(r'\n- \[ \] ', f'\n{ledger}')
    blocks = [b for b in blocks if b.strip() and b.startswith('G')]

    passed = 0
    failed = 0
    manual = 0

    for b in blocks:
        lines = b.split('\n')
        first = lines[0].strip()
        gid = first.split(':', 1)[0].strip() if ':' in first else first[:8]
        title = first.split(':', 1)[1].strip() if ':' in first else ''

        check = None
        expect = None
        cwd = '.'
        for line in lines[1:]:
            m = re.match(r'  CHECK: (.+)', line)
            if m: check = m.group(1).strip()
            m = re.match(r'  EXPECT: (.+)', line)
            if m: expect = m.group(1).strip()
            m = re.match(r'  CWD: (.+)', line)
            if m: cwd = m.group(1).strip()

        if not check or not expect:
            print(f"  [{gid}] MANUAL — {title}")
            manual += 1
            continue

        print(f"  [{gid}] {title}")
        print(f"    CHECK: {check}")
        try:
            proc = subprocess.run(check, shell=True, cwd=cwd, capture_output=True, text=True, timeout=300)
            out = proc.stdout + proc.stderr
            matched = expect in out
            if proc.returncode == 0 and matched:
                print(f"    ✅ MET (exit=0, EXPECT eşleşti)")
                passed += 1
            else:
                print(f"    ❌ NOT MET (exit={proc.returncode}, EXPECT={'✓' if matched else '✗'})")
                failed += 1
        except subprocess.TimeoutExpired:
            print(f"    ❌ TIMEOUT (300s)")
            failed += 1
        except Exception as e:
            print(f"    ❌ ERROR: {e}")
            failed += 1

    print(f"\n=== SONUÇ: {passed} MET, {failed} NOT MET, {manual} MANUAL ===")
    sys.exit(1 if failed else 0)

if __name__ == '__main__':
    main()
