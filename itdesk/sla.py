"""Simulated time-to-resolve and SLA breach.

All times are simulated minutes from fixed, seeded rules, not measured from people:
  * each tool call takes read 0.5, write 1, commit 2 minutes (blocked calls 0.2),
  * approvals wait a seeded log-normal time around the approver's median (gateway.APPROVAL_MEDIAN_MIN),
  * a ticket that reaches a person (escalated, left open, or closed wrongly and reopened) waits in the
    human queue for the priority the agent gave it, then takes a seeded handling time.
The human-only baseline sends every ticket to that queue, with the same approval waits.
"""

from __future__ import annotations

import math

from .company import rng
from .gateway import APPROVAL_MEDIAN_MIN, required_approvals
from .tickets import SLA_MINUTES

TOOL_MIN = {"read": 0.5, "write": 1.0, "commit": 2.0}
QUEUE_MEDIAN_MIN = {"P1": 90, "P2": 240, "P3": 720, "P4": 1800}
HANDLE_MEDIAN_MIN = 25


def _lognormal(median: float, *seed, sigma: float = 0.5) -> float:
    return median * math.exp(rng(*seed).gauss(0, sigma))


def human_minutes(t: dict, priority: str) -> float:
    return _lognormal(QUEUE_MEDIAN_MIN[priority], "queue", t["id"], sigma=0.7) + _lognormal(HANDLE_MEDIAN_MIN, "handle", t["id"])


def agent_minutes(audit: list[dict], approval_wait: float) -> float:
    return approval_wait + sum(0.2 if e.get("status") == "blocked" else TOOL_MIN.get(e["tier"], 0.5) for e in audit)


def time_to_resolve(t: dict, audit: list[dict], approval_wait: float, needs_human: bool, priority: str) -> float:
    m = agent_minutes(audit, approval_wait)
    return m + human_minutes(t, priority) if needs_human else m


def human_only_minutes(t: dict) -> float:
    g = t["gold"]
    wait = 0.0
    for a, kind_args in (("grant_group", {"group": g.get("group")}), ("order_laptop", {}), ("declare_major_incident", {})):
        if a in g["actions"] or (a == "declare_major_incident" and "link_incident" in g["actions"]):
            for kind in required_approvals(a, kind_args):
                wait += _lognormal(APPROVAL_MEDIAN_MIN[kind], "approval", t["id"], kind)
    return human_minutes(t, g["priority"]) + wait


def breached(t: dict, minutes: float) -> bool:
    return minutes > SLA_MINUTES[t["gold"]["priority"]]
