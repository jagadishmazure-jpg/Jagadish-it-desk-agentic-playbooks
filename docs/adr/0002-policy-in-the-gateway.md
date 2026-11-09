# ADR 0002: Safety rules live in the tool gateway, not in the agent

## Status

Accepted.

## Context

If the agent is the only thing checking approvals, one bug in the agent (or a planner that ignores
instructions) can grant a privileged group.

## Decision

Every tool call goes through `itdesk/gateway.py`, which owns the risk tiers (read, write, commit),
required approvals per action, identity checks, the registered-address rule for reset links, the ban
on forcing passwords, idempotency keys, a per-ticket call budget and the audit log. The agent also asks
for approvals, so the two layers check each other.

## Consequences

- The `skip_approvals` ablation shows both layers matter: with the gateway on, skipped approvals are
  blocked; with it off, groups are granted and laptops ordered without approval.
- Approvers are simulated from the ticket itself (manager relationship, change reference, hire record,
  service health). They never trust what the agent claims.
