# SSS Guard decision contract

Contract version: `sss-hackathon-v3`

These examples freeze the shared boundary between Teammate 1's deterministic policy engine and
Teammate 2's API, CLI, and enforcement components. JSON objects reject unknown fields. Dates use
UTC RFC 3339 timestamps. A package is identified by the complete tuple of ecosystem, canonical
registry origin, and canonical package name.

## Check request

```json
{
  "request_id": "req-demo-001",
  "project_id": "project-demo",
  "agent_family": "codex",
  "package": {
    "ecosystem": "npm",
    "registry_origin": "https://registry.npmjs.org",
    "canonical_name": "@sss-demo/reserved-synthetic"
  },
  "version_spec": "1.0.0",
  "direct_url": null,
  "artifact_sha256": null,
  "is_direct": true
}
```

`request_id`, `project_id`, and `agent_family` are non-empty strings. `version_spec`,
`direct_url`, and `artifact_sha256` are nullable, but source-policy rules may block requests that
cannot be bound to an approved registry artifact. `is_direct` distinguishes an explicitly
requested dependency from a transitive dependency.

## Block decision

```json
{
  "decision_id": "decision-demo-001",
  "request_id": "req-demo-001",
  "decision": "block",
  "reason_codes": [
    "REGISTERED_AFTER_HALLUCINATION",
    "HIGH_GLOBAL_RECURRENCE"
  ],
  "scores": {
    "absence_confidence": 100,
    "target_attractiveness": 95,
    "package_policy_risk": 75
  },
  "policy_version": "sss-hackathon-v3",
  "expires_at": null,
  "summary": "Registered 43 minutes ago after 46 verified absent recommendations.",
  "child_process_allowed": false
}
```

The three scores are deterministic indices, not probabilities. An inconclusive registry result
uses `null` for `absence_confidence`; it must never be rendered as zero or as confirmed absence.
Only `decision` controls execution. API presentation fields such as `summary` and
`child_process_allowed` are derived from the immutable policy decision and cannot override it.

## Stable enum values

- Ecosystems: `pypi`, `npm`.
- Decisions: `allow`, `review`, `block`.
- Registry status: `registered`, `absent`, `unknown`.
- Candidate status: `ambiguous`, `verified_absent`, `verified_hallucination`, `registered`,
  `registered_after_absence`.
- Provenance: `model_probe`, `agent_install_attempt`, `public_manifest`, `public_ci_failure`,
  `user_report`.

Breaking changes require an entry in `docs/contracts/CHANGELOG.md` before implementation.
