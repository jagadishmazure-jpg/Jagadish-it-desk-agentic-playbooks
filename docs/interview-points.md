# Interview points

Short answers to the questions this project tends to raise. Numbers are measured on the 187 synthetic
test tickets; times are simulated.

**Why playbooks instead of letting the model plan?**
Because the plan is where the risk is. The fixed playbooks were right on every ticket once triage was
right. The small model's free-form plans solved no ticket exactly, and without the gateway they made
19<!-- m:agents/llm_planner.gateway_off/high_risk_effects --> high-risk changes. The model is useful for
triage on unsure tickets, not for deciding actions.

**Where do the safety rules live?**
In the gateway, so they hold for any agent. The agent also asks for approvals, so the layers check each
other. With approvals skipped and the gateway on, 73<!-- m:agents/skip_approvals.gateway_on/blocked_calls -->
calls were blocked and nothing unsafe happened. With both off, 18<!-- m:agents/skip_approvals.gateway_off/high_risk_effects -->
high-risk changes went through.

**How do approvals avoid being fooled?**
Simulated approvers decide from the directory and the ticket (who manages whom, whether a change
reference exists, who the hiring manager is, whether the service is really down). An approval covers
one exact tool and arguments, so approving one group does not approve another.

**What does idempotency buy?**
Retries are normal (timeouts, duplicate e-mails). Delivering each ticket twice made no extra changes
with idempotency keys and 108<!-- m:agents/retry_twice.no_idempotency/duplicate_effects --> duplicates
without them.

**Why is main not the best configuration?**
Main was fixed before measuring. The hybrid triage scored higher on test (99.5%<!-- m:agents/hybrid_triage/success/rate -->
against 95.2%<!-- m:agents/main/success/rate -->), but choosing it after looking at test would overstate
it. The honest next step is a fresh ticket set.

**What is "unsafe" here?**
Any state change a correct agent would not make, checked against gold expected changes per ticket.
High-risk is a commit-tier change or any change to someone else or sent elsewhere. Main had
0<!-- m:agents/main/unsafe_effects --> of either.

**What does the agent save?**
In the simulation, median time to resolve drops from 814.2<!-- m:human_only/minutes_p50 --> to
50.2<!-- m:agents/main/minutes_p50 --> minutes, and SLA breaches from 12.3%<!-- m:human_only/sla_breach/rate -->
to 3.7%<!-- m:agents/main/sla_breach/rate -->. These come from fixed queue and approval rules, so they
show direction, not a forecast.

**What would you do next?**
Connect one real system behind the gateway in a sandbox tenant, move approvals to chat, confirm the
hybrid on fresh tickets, and log every gateway decision to Application Insights with alerts on blocked
commit calls.
