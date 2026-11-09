"""Azure ML / Microsoft Foundry scoring script for the IT desk agent. WRITTEN, NOT RUN in Azure.

init() trains the triage classifier from the committed tickets (no pickle). run() accepts
{"requester": "E1000", "from": "...", "subject": "...", "body": "..."} and returns the triage decision,
the playbook outcome and the audit trail, run against the simulated systems. Wiring real ITSM, directory
and endpoint tools is planned work (docs/deployment.md).
"""

from __future__ import annotations

import json
import logging

from itdesk import service

log = logging.getLogger("itdesk.score")


def init() -> None:
    service.classifier()
    log.info("triage classifier ready")


def run(raw_data: str) -> dict:
    try:
        payload = json.loads(raw_data)
    except (TypeError, json.JSONDecodeError):
        return {"error": "body must be JSON"}
    try:
        out = service.handle(payload)
    except ValueError as e:
        return {"error": str(e)}
    log.info("ticket %s -> %s/%s, %d tool calls", payload.get("id", "-"), out["playbook"], out["outcome"], len(out["audit"]))
    return out
