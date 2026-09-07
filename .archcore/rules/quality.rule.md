---
title: Code Quality & Architecture Rules
category: quality
version: 1.0
---
# Architecture & Quality Rules

- **QUAL-001 (Scope Bounding):** PR changes must strictly stay within the declared allowed_paths in agent_tasks.json.
- **QUAL-002 (Test Coverage):** Every newly added route, resolver, or engine logic must include corresponding Vitest integration tests in tests/.
- **QUAL-003 (AST Integrity):** All JavaScript and Python files must parse cleanly without AST syntax errors or unclosed JSX tags.
- **QUAL-004 (WCAG Accessibility):** Iconic buttons must have aria-label; interactive click divs must have role='button', tabIndex={0}, and onKeyDown.
