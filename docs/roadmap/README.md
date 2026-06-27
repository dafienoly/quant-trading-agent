# Roadmap Directory

This directory contains the roadmap entrypoints for Quant Trading Agent.

## Canonical entrypoint

The canonical roadmap path is:

```text
docs/roadmap/MASTER_ROADMAP.md
```

All future PM, architecture, development, test, review and acceptance work must read this file first.

## Compatibility file

The historical detailed agent-executable roadmap is preserved at:

```text
docs/roadmap/MASTER_ROADMAP_AGENT_EXECUTABLE.md
```

This file remains available for backwards compatibility with earlier Agent handoffs and existing document references. It must not become a separate source of truth.

## Priority order

When documents conflict, use the following order:

1. `docs/roadmap/MASTER_ROADMAP.md`
2. `docs/roadmap/MASTER_ROADMAP_AGENT_EXECUTABLE.md`
3. Current approved requirements in `docs/requirements/`
4. Current approved architecture in `docs/design/`
5. Historical notes, archived roadmap drafts and chat-derived plans

## R0 rule

Before expanding business features, stabilize the platform that builds and validates the software:

```text
R0.1 Roadmap Canonicalization
R0.2 AgentOps Control Tower completion
R0.3 Agent Runtime Abstraction
R0.4 Bug Auto-Fix System productization
R0.5 Logging, audit and operational visibility baseline
```

## Safety and scope

Roadmap changes must not silently expand execution capability. Any change involving restricted modules must go through the normal requirements, architecture, review and acceptance gates.
