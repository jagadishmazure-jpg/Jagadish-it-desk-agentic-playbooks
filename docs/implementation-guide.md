# Implementation guide

For a team that wants to put an agent on its service desk using this pattern.

## 1. Start with the gateway, not the agent

Write the tool list with a tier for each tool: read (no change), write (reversible, own things),
commit (privileged or costly). Put approvals, identity rules, idempotency keys, a call budget and an
audit log in the gateway. Then any agent, good or bad, is bounded by it.

## 2. Turn your top procedures into playbooks

Take the five or six ticket types that make most of the volume. Write each as code: which read checks
come first, which approvals, which write or commit calls, and when to hand to a person. Everything
else escalates with a short summary.

## 3. Build a labelled ticket set before tuning anything

Label a few hundred real or synthetic tickets with the category, the expected outcome and the exact
state changes. Include traps: resets for others, external senders, privileged access, planted
instructions. Keep wordings in the test set that the classifier never saw.

## 4. Measure safety separately from success

Count unexpected state changes per ticket, duplicates after a retry, and blocked calls. Run ablations
(skip approvals, gateway off, no idempotency) so you can show each control matters. Gate CI on zero
unsafe changes for the main configuration.

## 5. Use a model only where it earns its place

Here the classifier is the main triage. A small model as fallback on unsure tickets raised success on
the test set; confirm that on fresh tickets before adopting it. A free-form planner needed the gateway
to stay safe and rarely produced a usable plan.

## 6. Connect real systems one at a time

Replace one `Systems` method with a real connector, keep the gateway in front, read secrets from Key
Vault with the endpoint identity, and re-run this eval against a sandbox tenant before any live use.

## 7. Watch it in production

Log every gateway decision to Application Insights. Alert on blocked commit calls, budget hits and
escalation rate changes. Review a sample of auto-resolved tickets every week.
