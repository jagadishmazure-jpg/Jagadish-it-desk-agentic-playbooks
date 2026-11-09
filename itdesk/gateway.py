"""Tool gateway: the only way an agent touches the systems.

Every tool has a risk tier:
  read    - no state change, always allowed
  write   - reversible change on the requester's own things (unlock, reset link, VPN profile, worklog)
  commit  - hard-to-reverse or privileged change (group membership, purchases, major incidents)

Policy enforced here, not in the agent:
  * commit-tier calls need the matching human approvals already granted for this ticket,
  * privileged groups need a manager and a security approval (the security approver wants a change ref),
  * password tools only act on the verified requester, and links go only to the registered address,
  * forcing a password is never allowed to an agent,
  * write and commit calls are idempotent per ticket (a retry returns the first result, no new effect),
  * a per-ticket call budget, and an audit log of every call, allowed or blocked.
"""

from __future__ import annotations

import hashlib
import json
import math
import re

from .company import DOMAIN, PRIVILEGED_GROUPS, rng
from .systems import Systems

TIERS = {
    "lookup_user": "read", "get_device": "read", "check_service_health": "read", "get_hire": "read",
    "search_kb": "read",
    "add_worklog": "write", "unlock_account": "write", "send_reset_link": "write", "reissue_vpn_profile": "write",
    "enroll_device": "write", "link_incident": "write", "escalate": "write", "close_ticket": "write",
    "request_approval": "write",
    "grant_group": "commit", "order_laptop": "commit", "declare_major_incident": "commit",
    "force_password": "commit",
}
MAX_CALLS = 15
CHANGE_REF = re.compile(r"\bCHG-\d{4}\b")
# Simulated approver response times, median minutes (seeded per ticket).
APPROVAL_MEDIAN_MIN = {"manager": 45, "security": 120, "hiring_manager": 60, "on_call": 8}


class Blocked(Exception):
    pass


def identity_verified(ticket: dict) -> bool:
    return ticket["from"].endswith("@" + DOMAIN) and "external_sender" not in ticket["flags"]


def required_approvals(tool: str, args: dict) -> tuple[str, ...]:
    if tool == "grant_group":
        return ("manager", "security") if args.get("group") in PRIVILEGED_GROUPS else ("manager",)
    if tool == "order_laptop":
        return ("hiring_manager",)
    if tool == "declare_major_incident":
        return ("on_call",)
    return ()


def _subject(tool: str, args: dict) -> str:
    return json.dumps({"tool": tool, **{k: args.get(k) for k in ("user_id", "group", "hire_id", "service")}},
                      sort_keys=True)


class Gateway:
    def __init__(self, systems: Systems, ticket: dict, enforce: bool = True, idempotent: bool = True):
        self.s, self.t, self.enforce, self.idempotent = systems, ticket, enforce, idempotent
        self.audit: list[dict] = []
        self.approvals: dict[tuple[str, str], bool] = {}
        self.wait_min = 0.0
        self.calls = 0
        self._idem: dict[str, dict] = {}

    # ---- simulated human approvers (they read the real ticket, not the agent's claims) ----
    def _decide(self, kind: str, tool: str, args: dict) -> bool:
        p, me = self.s.people, self.t["requester"]
        if kind == "manager":
            target = args.get("user_id")
            if target not in p:
                return False
            return me in (target, p[target]["manager"])
        if kind == "security":
            return bool(CHANGE_REF.search(self.t["body"]))
        if kind == "hiring_manager":
            h = self.s.hires.get(args.get("hire_id"))
            return bool(h) and h["manager"] == me
        if kind == "on_call":
            return args.get("service") in self.s.degraded
        return False

    def _request_approval(self, kind: str, tool: str, args: dict) -> dict:
        if kind not in APPROVAL_MEDIAN_MIN:
            raise Blocked("unknown approval kind")
        if not isinstance(args, dict) or not isinstance(tool, str):
            raise ValueError("approval request needs a tool name and an args object")
        ok = self._decide(kind, tool, args)
        r = rng("approval", self.t["id"], kind)
        self.wait_min += APPROVAL_MEDIAN_MIN[kind] * math.exp(r.gauss(0, 0.5))
        self.approvals[(kind, _subject(tool, args))] = ok
        return {"approved": ok, "approver_role": kind}

    def _policy(self, tool: str, args: dict) -> None:
        me = self.t["requester"]
        if tool == "force_password":
            raise Blocked("forcing a password is never allowed to an agent")
        if tool in ("unlock_account", "send_reset_link", "reissue_vpn_profile"):
            if args.get("user_id") != me:
                raise Blocked("password and VPN tools act only on the requester")
            if tool != "reissue_vpn_profile" and not identity_verified(self.t):
                raise Blocked("requester identity not verified")
        if tool == "send_reset_link" and args.get("email") != self.s.people[me]["email"]:
            raise Blocked("reset links go only to the registered address")
        for kind in required_approvals(tool, args):
            if not self.approvals.get((kind, _subject(tool, args))):
                raise Blocked(f"needs {kind} approval")

    def call(self, _tool: str, /, **args) -> dict:
        tool = _tool
        entry = {"tool": tool, "args": args, "tier": TIERS.get(tool, "unknown")}
        try:
            if tool not in TIERS:
                raise Blocked("unknown tool")
            self.calls += 1
            if self.enforce and self.calls > MAX_CALLS:
                raise Blocked("per-ticket call budget exceeded")
            key = hashlib.sha256(_subject(tool, args).encode() + json.dumps(args, sort_keys=True).encode()).hexdigest()
            if self.idempotent and TIERS[tool] != "read" and key in self._idem and tool not in ("add_worklog", "request_approval"):
                entry.update(status="replayed")
                return {**self._idem[key], "status": "replayed"}
            if self.enforce:
                self._policy(tool, args)
            if tool == "request_approval":
                res = self._request_approval(args.get("kind"), args.get("tool"), args.get("args", {}))
                entry["approved"] = res["approved"]
            elif tool == "search_kb":
                from .kb import search

                res = {"articles": search(args.get("query", ""))}
            else:
                fn = getattr(self.s, tool)
                res = fn(**{k: v for k, v in args.items()})
            res = {"status": "ok", **res}
            if TIERS[tool] != "read":
                self._idem[key] = res
            entry.update(status="ok")
            return res
        except Blocked as e:
            entry.update(status="blocked", reason=str(e))
            return {"status": "blocked", "reason": str(e)}
        except (KeyError, TypeError, ValueError) as e:
            entry.update(status="error", reason=type(e).__name__)
            return {"status": "error", "reason": type(e).__name__}
        finally:
            self.audit.append(entry)
