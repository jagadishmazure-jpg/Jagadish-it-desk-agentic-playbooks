# ADR 0005: Time-to-resolve is simulated with fixed, seeded rules

## Status

Accepted.

## Context

There are no real people or queues in this repo, but SLA effects are the main business reason for an
agent.

## Decision

`itdesk/sla.py` charges fixed minutes per tool tier, seeded log-normal approval waits, and a seeded
human-queue wait by priority plus handling time for any ticket that reaches a person. A human-only
baseline uses the same queue and approval rules.

## Consequences

- Time numbers are labelled simulated everywhere. They show how the design changes time, not what a
  real desk would see.
- Changing a constant in `sla.py` changes the numbers; CI catches that through `results/`.
