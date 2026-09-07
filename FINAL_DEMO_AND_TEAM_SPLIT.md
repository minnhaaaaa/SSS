# SSS — Final Demo and Three-Person Work Division

**Product:** SSS — Stop Slop Squatting (“Triple-S”)  
**Primary track:** AI Trust, Safety & Governance  
**Demo length:** 2 minutes 30 seconds  
**Policy:** `sss-hackathon-v3`

## 1. One-line pitch

SSS learns which package names coding models repeatedly recommend before those packages exist, watches for attackers registering them, and autonomously blocks Codex or Claude Code before the package can execute.

## 2. What the demo proves

The demo must prove five things visually:

1. SSS intelligence is global, not limited to the current user’s prompt.
2. Every observation has provenance and verified registry state.
3. Earlier absence remains visible after the package is registered.
4. A non-interactive coding agent does not call SSS or ask permission.
5. SSS independently blocks the actual package-install path before execution.

## 3. Fixed demo fixture

Use the same values in backend fixtures, Exasol, UI, CLI, pitch, video, and narration:

| Field | Fixed value |
|---|---|
| Package | Reserved synthetic npm name selected before rehearsal |
| Ecosystem | npm |
| Package manager | pnpm |
| Verified model recommendations | 46 |
| Model configurations | 3 |
| Opt-in protected-agent attempts | 8 |
| Observation days | 11 |
| Public failed references | 5 |
| First absence | 11 days before registration |
| Registration age at attack | 43 minutes |
| Absence confidence | 100/100 |
| Global target attractiveness | 95/100 |
| Package policy risk | 75/100 |
| Decision | Block |
| Policy | `sss-hackathon-v3` |
| Protected child starts | 0 |

All model/global events are replayed through production ingestion endpoints and labelled **Replayed synthetic evidence**. Registry transition, Guard decision, Exasol query, UI event, and protected child non-execution are live.

## 4. Main demo screen

```text
┌────────────────────────────────────────────────────────────────────┐
│ SSS / LIVE DEFENSE                         DATA AS OF 12:43:18      │
│ Global sources: Models 3 · Agents 8 · Public 6 · Registries 2     │
├───────────────────────────────┬────────────────────────────────────┤
│                               │ SELECTED PACKAGE                   │
│  GLOBAL RECURRENCE RADAR      │ synthetic-npm-name                │
│                               │                                    │
│      ·    ·                   │ VERIFIED ABSENT → REGISTERED       │
│          ◉ selected           │                                    │
│   ·               ·           │ Sep 1   46 recommendations         │
│                               │ Sep 1   npm 404 proof              │
│ size = attractiveness         │ Sep 12  registered                 │
│ color = package state         │ Sep 12  agent attempted pnpm add  │
│                               │                                    │
├───────────────────────────────┴────────────────────────────────────┤
│ [Replay global evidence] [Register] [Run unprotected] [Protect]   │
├────────────────────────────────────────────────────────────────────┤
│ SSS CRITICAL — INSTALLATION BLOCKED                               │
│ Absence 100 · Attractiveness 95 · Policy risk 75                  │
│ [Keep blocked] [Inspect evidence] [Allow once]                    │
└────────────────────────────────────────────────────────────────────┘
```

Design rules:

- Raw real-world absent names never appear; only the synthetic fixture is named.
- “Global” cards distinguish model, protected-agent, public, and registry sources.
- Absence and registration are two separate immutable events.
- The primary visual outcome is `INSTALLATION BLOCKED`, not a vague score.
- Color is never the only status indicator.
- An “allow once” dialog shows exact package, version, registry, hash, project, and expiry.

## 5. Exact demo sequence and narration

| Time | Visual/action | Narration |
|---|---|---|
| 0:00–0:12 | Start on autonomous agent terminal preparing `pnpm add <synthetic-name>`; pause before execution | “Coding agents install dependencies with access to real developer machines. Models sometimes invent package names, and attackers can register the names they invent most often.” |
| 0:12–0:28 | Open SSS Radar; show global source counters | “SSS does not depend on this user’s conversation. It continuously gathers verified evidence from controlled model probes, opted-in agent attempts, public software artifacts, and npm and PyPI.” |
| 0:28–0:46 | Click **Replay global evidence**; constellation grows and selected point reaches 95 | “This synthetic name was recommended 46 times by three model configurations while npm repeatedly proved it did not exist. SSS stores the source and timestamp of every observation in Exasol.” |
| 0:46–1:00 | Open evidence timeline; highlight the original 404 | “An internet mention alone is not called a hallucination. Only a direct model recommendation plus conclusive registry absence receives that label.” |
| 1:00–1:14 | Click **Register locally**; point pulses and transition appears | “Now our controlled attacker registers the same name. SSS preserves the old absence proof and detects the new registration 43 minutes later.” |
| 1:14–1:30 | Click **Run unprotected**; harmless local canary becomes 1 | “Without protection, the synthetic install lifecycle runs. This isolated canary safely demonstrates the moment malicious code could have accessed credentials.” |
| 1:30–1:52 | Reset protected victim, launch noninteractive agent through `sss protect`, click **Run protected** | “The agent has confirmations disabled and never calls our MCP. It runs pnpm directly—but the actual install path is independently controlled by SSS.” |
| 1:52–2:08 | Large block drawer appears; canary remains 1; terminal shows child not started | “SSS correlates global recurrence, historical absence, later registration, source, and package age. It blocks before pnpm starts, so the canary does not change.” |
| 2:08–2:20 | Click **Inspect evidence**; show 100/95/75 and reason codes | “The decision is deterministic and auditable: absence confidence 100, target attractiveness 95, policy risk 75, with the exact Exasol evidence behind every factor.” |
| 2:20–2:30 | Zoom out to architecture strip: Network → Exasol → Guard | “SSS turns model hallucinations into private threat intelligence—and stops slop squatting before package code runs.” |

## 6. Demonstration controls

Buttons unlock sequentially and every operation is idempotent:

1. **Reset:** zero local registration, attempts, approvals, and canary events.
2. **Replay global evidence:** fixed synthetic observations enter normal APIs and Exasol.
3. **Register locally:** local npm registry publishes the synthetic fixture once.
4. **Run unprotected:** disposable victim produces exactly one canary event.
5. **Run protected:** noninteractive agent attempt is blocked; canary remains one.
6. **Inspect evidence:** ordered timeline and reason factors open.

If any action fails, later buttons stay disabled and the screen shows a specific recoverable error. No button silently substitutes prerecorded data.

## 7. Three-person division

### Teammate 1 — Intelligence and policy engineer

Builds:

- PyPI/npm identity, extraction, validation, and registry truth tables.
- PyPI baseline and timestamped npm absence evidence.
- Controlled model probe replay/live adapters.
- Public GitHub discovery and opt-in telemetry ingestion semantics.
- Exasol tables, recurrence views, temporal transition query, and policy evidence.
- Three indices and hard enforcement rules.
- Measurement holdout and detection/false-positive evaluation.

Demo responsibilities:

- Operates **Replay global evidence** and explains why provenance matters.
- Explains absence versus unknown, global recurrence, and the registration transition.
- Answers Exasol, detection, metrics, and “is this really malicious?” questions.

Must deliver to Teammate 2:

- Frozen domain types by end of Day 1.
- OpenAPI request/decision examples by midday Day 2.
- Fixed Exasol demo dataset and views by end of Day 3.
- Stable policy engine and values by midday Day 4.

### Teammate 2 — Enforcement and product engineer

Builds:

- FastAPI, authentication, REST, Server-Sent Events, and health routes.
- `sss check`, `sss guard`, `sss protect`, and command shims.
- pip/uv/npm/pnpm/Yarn/npx enforcement adapters.
- Policy-aware PyPI/npm registry gateway.
- Exact-scope signed approval flow.
- Docker protected workspace and egress restrictions.
- React implementation from approved Figma.
- Local registries, synthetic npm package, canary, E2E, and cloud/local deployment.

Demo responsibilities:

- Operates registration, unprotected install, and protected autonomous attempt.
- Proves the child package manager did not start.
- Answers bypass, MCP, Docker boundary, failure, deployment, and latency questions.

Must deliver to Teammate 3:

- Mock API fixture by end of Day 1.
- Storybook/static route shell by end of Day 2.
- Real Radar data integration by end of Day 4.
- Stable demo build for final visual QA by midday Day 6.

### Teammate 3 — Product and visual designer

Designs:

- SSS/Triple-S name treatment, logo, typography, and accessible color system.
- Radar information architecture and recurrence visualization.
- Package evidence timeline and provenance system.
- Block/review/allow states, notification, and exact-scope approval dialog.
- Coverage/collector-health view and guided demo control room.
- Loading, empty, stale, offline, redacted, and failure states.
- Responsive layout, keyboard/focus annotations, and reduced-motion behavior.
- Pitch deck, submission graphics, fallback video framing, and final narration polish.

Daily Figma outputs:

| Day | Required design output |
|---|---|
| 1 | Two identity directions, information architecture, five low-fi screens |
| 2 | Approved tokens/components and high-fi Radar at desktop and narrow width |
| 3 | Evidence timeline, notification drawer, approval dialog, all system states |
| 4 | Demo control room, motion timings, developer measurements/assets |
| 5 | Implementation comparison and prioritized visual QA report |
| 6 | Final UI approval, deck, thumbnails, submission images, recording shot list |
| 7 | Rehearsal notes and final screenshot/video quality control only |

Designer handoff checklist for every screen:

- Component/state name.
- Exact visible copy.
- Spacing and dimensions.
- Token names, not isolated hex values.
- Hover, focus, pressed, disabled, loading, error, and reduced-motion behavior.
- Desktop and narrow-width rules.
- Data sensitivity/redaction behavior.
- Exportable SVG icons/marks with licenses recorded.

## 8. Collaboration contracts

### Evidence contract

Teammate 1 owns the meaning of:

- `EvidenceProvenance`
- `RegistryStatus`
- `CandidateStatus`
- `EvidenceScores`
- `Decision`
- reason codes and policy version

No UI copy may collapse `UNKNOWN` into `ABSENT` or “suspected” into “malicious.”

### API contract

Teammates 1 and 2 jointly approve the OpenAPI fixture. Breaking changes go into `docs/contracts/CHANGELOG.md` before implementation.

### Visual contract

Teammate 3 owns user-facing hierarchy and copy after technical fact review. Teammate 2 implements from named tokens/components and does not substitute generic dashboard components without review.

### Demo contract

All three approve the fixed values in §3. Changing a number requires updating fixtures, SQL expectations, UI snapshots, narration, deck, and fallback video together.

## 9. Rehearsal gates

### Technical gate

- Clean `docker compose --profile demo up` succeeds.
- Reset/replay/register/unprotected/protected sequence passes twice.
- Protected path starts zero package-manager children.
- Public routes reveal no private absent names.
- Telemetry fixture contains no forbidden fields.
- Browser receives the live block SSE event.
- Demo still works with model provider keys removed.

### Visual gate

- Text is readable at recorded resolution.
- Selected package, transition, and block remain visible without relying on color.
- No clipped tooltip, accidental horizontal scroll, or unreadable terminal output.
- Data-as-of time and synthetic/replayed labels are visible.
- Loading/error states do not resemble successful evidence.
- Recording cursor path follows the scripted order.

### Narrative gate

- Say “global public intelligence,” not “we crawl every private agent conversation.”
- Say “suspected slopsquat/high risk,” not “malicious,” until behavior is actually demonstrated.
- Say “blocked before the package manager started,” not merely “warned.”
- Explicitly say MCP is optional and not the enforcement boundary.
- Explicitly state the strong guarantee applies inside the protected workspace.

## 10. Judge questions

| Question | Answer owner | Short answer |
|---|---|---|
| How do you know a package did not exist? | Teammate 1 | A conclusive approved-registry 404 is timestamped and hashed; PyPI also has a reproducible baseline. Network failures remain unknown. |
| How do you know the model hallucinated it? | Teammate 1 | Only direct controlled model evidence plus absence earns that label. Agent/public observations retain different provenance. |
| Why is later registration important? | Teammate 1 | Existence checks become useless after an attacker registers the name; SSS preserves proof that demand existed before registration. |
| Why Exasol? | Teammate 1 | The core product is a temporal analytical join across high-volume model, registry, public, client, release, and enforcement evidence. |
| Why not only MCP? | Teammate 2 | MCP is agent-controlled. SSS enforces the actual command and registry traffic independently. |
| Can an agent bypass it? | Teammate 2 | The demo guarantee is an unprivileged protected container with controlled PATH, registries, and egress. Host root remains out of scope. |
| Does it support pnpm? | Teammate 2 | Yes. pnpm is an npm-registry client; SSS supports npm, pnpm, Yarn, and npx through the npm ecosystem adapter. |
| Are you publishing attacker targets? | Teammate 3/1 | No. Raw absent names remain restricted; public mode shows aggregate metrics and synthetic examples only. |
| Is the demo fake? | Teammate 2 | Global observations are deterministic replay labelled synthetic; Exasol ingestion, transition, install attempt, block, notification, and non-execution are live. |
| Is every later package malicious? | Teammate 1 | No. It is a high-risk temporal signal. SSS blocks by policy and shows evidence rather than making unsupported attribution. |

## 11. Fallback strategy

Prepare:

- A locally cached deterministic evidence fixture.
- Local npm and PyPI registries.
- A prebuilt protected-agent container.
- A recorded fallback video.
- Static screenshots of each critical state.
- A read-only SQL result export proving Exasol queries.

The fallback may replace unreliable internet/model calls, but it must not misrepresent replay as live observation. The protected install and block should still run locally.

## 12. Final submission checklist

- [ ] Product is named SSS consistently in every artifact.
- [ ] Track is AI Trust, Safety & Governance.
- [ ] Two ecosystems and supported clients are stated accurately.
- [ ] Global sources and evidence provenance are visible.
- [ ] Synthetic/replayed data is labelled.
- [ ] Temporal transition is the central insight.
- [ ] Agent does not invoke MCP during the protected demo.
- [ ] Block happens before package-manager execution.
- [ ] Public UI reveals no real absent-name watchlist.
- [ ] Protected/unprotected canary counts are correct.
- [ ] Exasol and its analytical value are visible.
- [ ] Deployment instructions work from a clean machine.
- [ ] Designer approves implementation screenshots.
- [ ] All team members can deliver their assigned judge answers.
