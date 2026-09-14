# Contract changelog

## 2026-09-14

- Added digest backed scoped credentials for `radar:read`, `agent:check`, `collector:write`,
  `approval:write` and `operator:intervene`; production rejects legacy shared bearer-token mode.
- Added authenticated private Radar repositories with bounded pagination while retaining redacted
  public aggregates.
- Added explicit `test`, `demo` and `production` runtime composition. Production requires Exasol,
  the frozen policy version and durable operational repositories.
- Persisted decision attestations, install attempts, interventions, idempotency claims and approval
  consumption in Exasol. Approval state survives process restart and nonce consumption is atomic.
- Added agent retry consumption for the frozen exact approval claim set. The token and nonce are
  accepted only for one exact request and are removed before child execution.

## 2026-09-13

- Integrated the enforcement API, CLI, gateway and canary apps as consumers of the frozen
  Teammate 1 domain, approval and fixture contracts; no contract semantics changed.
- Published stable `sss_core` package-root imports and the complete shared JSON/OpenAPI example
  set for observations, registry evidence, Radar, Guard, attempts, approvals and public aggregates.
- Froze extractor outputs for each supported Python/npm client and the exact approved PyPI/npm
  metadata endpoint and truth-table behavior.
- Froze the synthetic demo identity as `@sss-demo/reserved-synthetic` at the single logical origin
  `https://npm.demo.sss.test` for both absence and later registration.
- Froze the exact single-use approval claims and documented why the narrated pre-execution package
  risk is `75`; a later ingested static lifecycle finding produces a new score of `85`.

## 2026-09-07

- Froze the initial package identity, install request, evidence score, and policy decision
  contracts for `sss-hackathon-v3`.
