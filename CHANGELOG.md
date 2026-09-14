# Changelog

## 0.2.0 — 2026-09-14

- Added a single organization self hosted profile with TLS edge authentication, scoped digest
  credentials, secret file mounts, hardened containers and an external Exasol Personal connection.
- Replaced fixed package assessment with Exasol backed evidence for arbitrary PyPI and npm package
  identities.
- Persisted Guard decisions, attempts, interventions, idempotency records and single use approvals
  in Exasol so API restarts preserve enforcement state.
- Protected `pip`, `pip3`, `python -m pip`, `uv`, Poetry, npm, pnpm, Yarn and npx entrypoints.
- Added an exact approval retry that atomically consumes the grant and removes its token before the
  real package manager starts.
- Added a fail closed registry gateway with exact metadata paths and artifact SHA-256 permits.
- Added backup, restore and production readiness commands plus authenticated private Radar routes.
- Qualified the zero cost Linux workflow with Exasol Docker Edition. Exasol Personal remains the
  production target; cloud infrastructure charges and Exasol license/deployment limits remain the
  operator's responsibility.

## 0.1.0 — 2026-09-13

- Established frozen domain, evidence, scoring, registry oracle and approval contracts.
- Added the deterministic synthetic slopsquatting fixture and terminal first protected demo.
