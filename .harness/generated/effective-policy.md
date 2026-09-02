# Effective Engineering Policy

Policy digest: `c2600ed6dcfb24d621929bc4b9669056dfc047b0a8dcb24692f684b33f8126d6`
Owner: tester
Stack: typescript

This file is generated. Change `.harness/policy.yaml`, obtain owner approval, and recompile instead of editing this file.

## Stack adapter coverage

- `typescript`: built-in deterministic support.

## 1. Single implementation owner (single-implementation-owner)

Before implementation, search for an existing implementation and record the owning module; do not create a parallel implementation of the same capability.

- Severity: error
- Formalization: procedural
- Verify with: `harness-automation context --project .`
## 2. Contract-first interface changes (contract-first-change)

Change shared API, RPC, schema, database, or queue contracts before changing consumers; update compatibility tests in the same change.

- Severity: error
- Formalization: cognitive
- Verify with: owner review
## 3. Generated files are immutable (generated-files-immutable)

Never edit generated code or Harness compiler outputs directly; change their source and regenerate them.

- Severity: error
- Formalization: procedural
- Verify with: `harness-automation drift --project .`
## 4. TypeScript naming (typescript-naming)

Use camelCase for variables, functions, parameters, methods, and local properties; PascalCase for classes, interfaces, types, enums, React components, and exported Zod schemas; UPPER_SNAKE_CASE is allowed for module constants, imported constants, and static readonly class constants. Node __dirname/__filename and the exact unused-parameter placeholder _ are allowed.

- Severity: error
- Formalization: deterministic
- Verify with: `harness-automation check --project .`
