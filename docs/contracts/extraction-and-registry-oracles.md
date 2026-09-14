# Package extraction and registry oracle contract

## Extraction output

Both extractors return immutable `ExtractedPackage` values:

```text
ecosystem, raw, canonical_name, version_spec, source, is_direct, requested_registry
```

They parse text and manifests only. They never invoke a shell, package manager, build backend, or
unknown artifact. Shell operators are rejected before parsing. Alternate registries remain part of
the request and later package identity; they are never silently rewritten to a public registry.

Supported inputs:

| Client/input | Accepted form | Example canonical output |
|---|---|---|
| pip | `pip install Requests==2.32` | `pypi / requests / ==2.32` |
| pip3 | `pip3 install Requests==2.32` | `pypi / requests / ==2.32` |
| Python module | `python -m pip install Requests==2.32` | `pypi / requests / ==2.32` |
| uv project | `uv add Requests==2.32` | `pypi / requests / ==2.32` |
| uv pip | `uv pip install Requests==2.32` | `pypi / requests / ==2.32` |
| Poetry | main/dev/group dependency tables, including table specs | source retained |
| npm | `npm install react@19` or `npm i react@19` | `npm / react / 19` |
| pnpm | `pnpm add react@19` | `npm / react / 19` |
| Yarn | `yarn add react@19` | `npm / react / 19` |
| npx | package operand or `--package`/`-p` | only the package, not its binary arguments |

Direct URLs, VCS specs, local paths and aliases are classified, not fetched. Python imports are
reported only through the versioned standard-library exclusion and explicit import-to-distribution
alias tables; unknown imports are not guessed.

## Exact approved metadata paths

For a canonical PyPI identity `(pypi, https://pypi.org, requests)`:

```text
GET https://pypi.org/pypi/requests/json
```

The path template is `{registry_origin}/pypi/{canonical_name}/json`.

For an unscoped npm identity `(npm, https://registry.npmjs.org, react)`:

```text
GET https://registry.npmjs.org/react
```

For a scoped identity `@scope/name`, the slash is percent encoded while `@` remains literal:

```text
GET https://registry.npmjs.org/@scope%2Fname
```

The npm path template is `{registry_origin}/{percent_encoded_canonical_name}`. The same templates
apply to an explicitly approved alternate origin. Redirecting to another logical origin requires a
new identity and cannot prove a registration transition for the original origin.

## Oracle truth table

| Result | Typed outcome | Registry status | Retry |
|---|---|---|---|
| Valid `200` package metadata | `registered` | `registered` | no |
| `404` from the exact approved metadata path | `absent` | `absent` | no |
| `401` or `403` | `unknown_auth` | `unknown` | no |
| `429` | `unknown_rate_limit` | `unknown` | at most 3 total attempts |
| `5xx` | `unknown_server` | `unknown` | at most 3 total attempts |
| DNS, TLS/connect or timeout failure | `unknown_network` | `unknown` | at most 3 total attempts |
| Other status or malformed/mismatched `200` | `unknown_response` | `unknown` | no |

Each result records the exact endpoint, check time, HTTP status when available, response SHA-256
when available, error class, and first release timestamp for registered metadata. No unknown outcome
may be persisted or displayed as absence.
