# Teammate 1 contract handoff

Contract and policy version: `sss-hackathon-v3`.

## Stable imports

Application code may import the frozen types below either from `sss_core` or from their defining
modules. The package-root path is the compatibility boundary:

```python
from sss_core import (
    CandidateStatus,
    Decision,
    Ecosystem,
    EvidenceProvenance,
    EvidenceScores,
    InstallRequest,
    PackageIdentity,
    PolicyDecision,
    ReasonCode,
    RegistryStatus,
)
```

Adding an enum member is backward compatible. Renaming/removing a member or changing a dataclass
field is breaking and requires a changelog entry plus a policy-version decision.

## Policy callable

The stable callable is:

```python
PolicyEngine().assess(request: InstallRequest, context: PolicyContext) -> PolicyDecision
```

`PolicyContext` carries evidence state, the typed oracle outcome, the three separately labelled
indices, source approval, strict-mode and interactivity flags, and whether the immutable historical
absence was attributable model evidence. `PolicyDecision.decision` alone controls execution.

- A conclusive `ABSENT`, unapproved source, or high-recurrence registration transition blocks.
- An unavailable assessment blocks in strict mode.
- A `REVIEW` condition becomes `BLOCK` for a noninteractive agent and adds
  `NONINTERACTIVE_REVIEW_BLOCKED`.
- The output always records `sss-hackathon-v3`; callers cannot select a policy version.
- Unknown registry outcomes never become absence and never receive an absence score of zero.

## Demo identity decision

The reserved synthetic package identity is:

- package: `@sss-demo/reserved-synthetic`
- ecosystem: `npm`
- logical registry origin: `https://npm.demo.sss.test`

Reset, absence checks, registration, releases, Guard requests and evidence queries must all use
that same origin. Deployments may route that hostname to a local or cloud registry, but must not
change the identity between the absent and registered events. Replayed observations are always
labelled `Replayed synthetic evidence`.

## Approval claims

The signed claims are exactly: `package` (full identity), `version`, `registry_origin`,
`artifact_sha256` (64 lowercase hex characters), `project_id`, `expires_at`, `nonce`, and
`policy_version`. Grants are single use. The registry claim must equal the package identity origin.
Consumption is atomic and must fail closed for any mismatch, expiry, reused nonce or inactive
policy version. Signing and storage remain Teammate 2-owned; `ApprovalScope` is the semantic
verifier.

## Score decision: why the narrated value is 75, not 85

The fixed `75` is the pre-execution Guard score: registration after verified absence (45), release
age at most 72 hours (15), and attractiveness at least 60 (15). The demo canary lifecycle is
controlled behavior in the synthetic artifact, but no static-finding record is ingested before the
Guard decision. Therefore `suspicious_static_finding=false` at decision time and no additional ten
points are claimed. If bounded static inspection later records the lifecycle hook, the same scoring
function returns `85`; the product must show that later score with a new data-as-of timestamp rather
than rewriting the earlier decision. The hook is never described as undiscovered or harmless
production behavior.

## Examples

`openapi-components.yaml` indexes the approved JSON payloads under `examples/`. Teammate 2 may
compose these into endpoint request/response bodies but must not change their evidence semantics.
