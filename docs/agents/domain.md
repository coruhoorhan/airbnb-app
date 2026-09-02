# Domain Docs

## Before exploring, read these

- **`CONTEXT.md`** at the repo root
- **`docs/adr/`** for ADRs

These files are also accessible via `.archcore/` symlinks for archcore tooling.

## File structure

```
/
├── CONTEXT.md
├── docs/adr/
│   ├── 0001-*.md
│   └── ...
├── .archcore/
│   ├── CONTEXT.md → ../CONTEXT.md (symlink)
│   └── adr/ → ../docs/adr (symlink)
└── src/
```

## Consumer rules

- Use the glossary's vocabulary from `CONTEXT.md` in all output
- Flag ADR conflicts explicitly rather than silently overriding
- If files don't exist, proceed silently — `/domain-modeling` creates them lazily
