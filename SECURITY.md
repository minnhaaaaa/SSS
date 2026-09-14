# Security policy

## Reporting

Do not open a public issue for a suspected vulnerability. Send the maintainers a private report
containing the affected version, reproducible steps, impact and any proposed mitigation. Do not test
against package identities, registries or systems that you do not own or have permission to assess.

## Supported boundary

Version 0.2.x is the currently supported line. Its strongest enforcement boundary is the supplied
unprivileged protected container: no Docker socket, no Exasol or signing credentials, no direct
public registry route, immutable package-manager executable mappings and a fail closed gateway.

The host, container runtime, TLS keys, operator workstation, Exasol deployment and upstream model
provider remain trusted. A privileged agent on the host can bypass command shims and is outside the
guarantee. Operators must restrict production egress destinations with host or cloud firewall rules.

Only the synthetic local package may be used for demonstrations. Collectors do not execute unknown
public artifacts. Client telemetry must remain opt in and must never include prompts, source code,
environment variables, usernames, paths or repository names.
