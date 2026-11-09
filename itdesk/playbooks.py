"""The playbook agent: pick a playbook from triage and run its steps through the gateway.

Steps are fixed code, so text in a ticket cannot add steps. The agent never decides an approval; it asks
for one and stops if it is declined. Anything outside a playbook, unsure triage, or a failed check goes
to a person with a summary.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .company import PRIVILEGED_GROUPS
from .gateway import Gateway, identity_verified, required_approvals
from .kb import search
from .triage import entities, text_of

# Playbook -> the article it starts from (refined once the tools have looked at the systems).
PLAYBOOKS = {"password_reset": "KB-101", "access_request": "KB-201", "vpn": "KB-301",
             "laptop_provision": "KB-401", "outage": "KB-501", "other": "KB-601"}
QUEUES = {"identity_not_verified": "service-desk", "not_own_account": "service-desk",
          "device_not_compliant": "endpoint", "service_healthy": "service-desk", "not_it_service": "service-desk",
          "low_confidence": "service-desk", "missing_details": "service-desk", "tool_error": "service-desk"}


@dataclass
class Run:
    playbook: str
    outcome: str
    reason: str | None = None
    kb: str = "KB-601"
    suggested: list[str] = field(default_factory=list)
    steps: int = 0


def _approve_then(g: Gateway, tool: str, args: dict, ask: bool = True) -> bool:
    """Ask each required approver, stop at the first "no", then call the tool.

    ask=False is an ablation only: the agent skips approvals and relies on the gateway to stop it.
    """
    if ask:
        for kind in required_approvals(tool, args):
            if not g.call("request_approval", kind=kind, tool=tool, args=args).get("approved"):
                return False
    return g.call(tool, **args)["status"] in ("ok", "replayed")


def _escalate(g: Gateway, reason: str) -> tuple[str, str]:
    g.call("escalate", queue=QUEUES.get(reason, "service-desk"), reason=reason)
    g.call("close_ticket", outcome="escalated")
    return "escalated", reason


def run_playbook(t: dict, category: str, confidence: float, g: Gateway, min_confidence: float = 0.5,
                 ask_approval: bool = True) -> Run:
    """Run one ticket. The cited article is chosen by what the tools found, not by the text alone."""
    e = entities(t)
    me = t["requester"]
    suggested = search(text_of(t))
    if e["injection_suspected"]:
        g.call("add_worklog", text="Ticket contains instructions aimed at the agent; ignored.")
    if confidence < min_confidence or category == "other":
        out, why = _escalate(g, "low_confidence" if category != "other" else "not_it_service")
        return Run("escalate", out, why, "KB-601", suggested, g.calls)
    kb = PLAYBOOKS[category]
    if category == "password_reset":
        u = g.call("lookup_user", user_id=me)  # read-only, the requester's own record
        kb = "KB-102" if u.get("locked") else "KB-101"
        if not identity_verified(t):
            out, why = _escalate(g, "identity_not_verified")
        elif e["target"] != me:
            out, why = _escalate(g, "not_own_account")
        else:
            if u.get("locked"):
                g.call("unlock_account", user_id=me)
            g.call("send_reset_link", user_id=me, email=u["email"])
            g.call("close_ticket", outcome="resolved")
            out, why = "resolved", None
    elif category == "access_request":
        if not e["group"]:
            out, why = _escalate(g, "missing_details")
        else:
            kb = "KB-202" if e["group"] in PRIVILEGED_GROUPS else "KB-201"
            args = {"user_id": e["target"], "group": e["group"]}
            ok = _approve_then(g, "grant_group", args, ask_approval)
            out, why = ("resolved", None) if ok else ("denied", "approval_declined")
            g.call("close_ticket", outcome=out)
    elif category == "vpn":
        h = g.call("check_service_health", service="vpn-gateway")
        dev = g.call("get_device", user_id=me)
        if h.get("status") == "degraded":
            kb = "KB-501"
            out, why = _link_outage(g, "vpn-gateway", ask_approval)
        elif not dev.get("compliant", True):
            kb = "KB-302"
            out, why = _escalate(g, "device_not_compliant")
        elif dev.get("vpn_cert_expired"):
            g.call("reissue_vpn_profile", user_id=me)
            g.call("close_ticket", outcome="resolved")
            out, why = "resolved", None
        else:
            out, why = _escalate(g, "missing_details")
    elif category == "laptop_provision":
        if not e["hire"] or g.call("get_hire", hire_id=e["hire"])["status"] != "ok":
            out, why = _escalate(g, "missing_details")
        elif _approve_then(g, "order_laptop", {"hire_id": e["hire"]}, ask_approval):
            g.call("enroll_device", hire_id=e["hire"])
            g.call("close_ticket", outcome="resolved")
            out, why = "resolved", None
        else:
            g.call("close_ticket", outcome="denied")
            out, why = "denied", "approval_declined"
    else:  # outage
        if not e["service"]:
            out, why = _escalate(g, "missing_details")
        elif g.call("check_service_health", service=e["service"]).get("status") == "degraded":
            out, why = _link_outage(g, e["service"], ask_approval)
        else:
            kb = "KB-601"
            out, why = _escalate(g, "service_healthy")
    return Run(category, out, why, kb, suggested, g.calls)


def _link_outage(g: Gateway, service: str, ask: bool = True) -> tuple[str, str | None]:
    if not g.call("check_service_health", service=service).get("incident"):
        if not _approve_then(g, "declare_major_incident", {"service": service}, ask):
            return _escalate(g, "tool_error")
    g.call("link_incident", service=service)
    g.call("close_ticket", outcome="linked_incident")
    return "linked_incident", None
