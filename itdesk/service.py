"""The agent as a service: triage a new ticket and run its playbook against the simulated systems.

handle() is what the Azure ML / Microsoft Foundry endpoint calls. Inputs are checked before anything
runs; the reply carries the decision and the audit trail (tool, tier, status) but never the directory.
"""

from __future__ import annotations

from functools import lru_cache

from . import data
from .company import DOMAIN
from .gateway import Gateway
from .playbooks import run_playbook
from .systems import Systems
from .tickets import SLA_MINUTES
from .triage import Classifier, priority

MAX_TEXT = 4000
FIELDS = ("requester", "from", "subject", "body")


@lru_cache(maxsize=1)
def classifier() -> Classifier:
    return Classifier().fit([t for t in data.tickets() if t["split"] == "train"])


def check(payload: object) -> dict:
    if not isinstance(payload, dict):
        raise ValueError("body must be a JSON object")
    for f in FIELDS:
        v = payload.get(f)
        if not isinstance(v, str) or not v.strip():
            raise ValueError(f"field '{f}' (non-empty string) is required")
        if len(v) > MAX_TEXT:
            raise ValueError(f"field '{f}' is longer than {MAX_TEXT} characters")
    if payload["requester"] not in data.directory()["people"]:
        raise ValueError("unknown requester")
    sender = payload["from"].strip().lower()
    state = payload.get("state", {})
    if not isinstance(state, dict) or set(state) - {"locked", "vpn_cert_expired", "compliant", "degraded"}:
        raise ValueError("field 'state' may only set locked, vpn_cert_expired, compliant or degraded")
    return {"id": str(payload.get("id", "T-new"))[:20], "channel": str(payload.get("channel", "portal"))[:10],
            "requester": payload["requester"], "from": sender,
            "flags": [] if sender.endswith("@" + DOMAIN) else ["external_sender"],
            "subject": payload["subject"], "body": payload["body"], "_state": state, "gold": {}}


def handle(payload: object) -> dict:
    t = check(payload)
    cat, conf = classifier().predict([t])[0]
    g = Gateway(Systems(t, data.directory()), t)
    r = run_playbook(t, cat, conf, g)
    prio = priority(t)
    return {"category": cat, "confidence": round(conf, 3), "priority": prio, "sla_minutes": SLA_MINUTES[prio],
            "playbook": r.playbook, "outcome": r.outcome, "reason": r.reason, "kb": r.kb, "kb_suggested": r.suggested,
            "audit": [{"tool": e["tool"], "tier": e["tier"], "status": e["status"],
                       **({"approved": e["approved"]} if "approved" in e else {})} for e in g.audit]}
