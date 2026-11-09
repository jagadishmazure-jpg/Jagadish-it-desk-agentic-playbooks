# ADR 0001: Fixed playbooks run the tools; the model only helps with triage

## Status

Accepted.

## Context

An agent that writes its own plan can be steered by ticket text, and a small model often writes
plans that do not parse or do the wrong thing. Service desk work is mostly a handful of known
procedures.

## Decision

Each category has a playbook written as code (`itdesk/playbooks.py`). Ticket text decides only which
playbook runs and supplies entities found by patterns (employee IDs, group names, hire IDs, services).
The free-form planner is kept as a measured comparison, not as the product.

## Consequences

- Text in a ticket cannot add steps. The planted instructions had no effect on the playbook agent.
- Anything outside the playbooks goes to a person. New procedures need code and tests.
- The planner comparison shows what the gateway has to catch when an agent plans freely.
