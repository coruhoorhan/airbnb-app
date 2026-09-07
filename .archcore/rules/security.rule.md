---
title: Security Quality Gate Rules
category: security
version: 1.0
---
# Security Gate Rules

- **SEC-001 (CSRF Enforcement):** All state-changing mutation endpoints (POST, PUT, DELETE, PATCH) must validate x-csrf-token.
- **SEC-002 (SQL Injection Prevention):** Raw unescaped SQL string interpolation is strictly prohibited. All queries must use parameterized placeholders (?) with SQLite/better-sqlite3.
- **SEC-003 (Auth Security):** Auth cookies must enforce HttpOnly, SameSite=Lax/Strict, and Secure flags. JWT expiration must be bounded.
- **SEC-004 (Rate Limiting):** Public mutation and authentication endpoints must be protected with sliding-window rate limiters.
- **SEC-005 (Content Security):** CSP headers must not enforce upgrade-insecure-requests on non-HTTPS environments and must allow valid font/style/image sources.
