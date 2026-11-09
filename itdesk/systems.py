"""Simulated enterprise systems: directory, ITSM, endpoint management, HR and service health.

In memory, one fresh copy per ticket. Every state change is recorded as an *effect* tuple, so the eval
can compare what happened with what should have happened, independently of the agent and the gateway.
"""

from __future__ import annotations

import copy

from .company import build_directory


class Systems:
    def __init__(self, ticket: dict, directory: dict | None = None):
        d = copy.deepcopy(directory or build_directory())
        self.people = d["people"]
        self.security_approver = d["security_approver"]
        self.on_call = d["on_call"]
        st = ticket.get("_state", {})
        me = self.people[ticket["requester"]]
        me["locked"] = bool(st.get("locked"))
        me["device"]["vpn_cert_expired"] = bool(st.get("vpn_cert_expired"))
        me["device"]["compliant"] = st.get("compliant", True)
        self.degraded = {st["degraded"]} if st.get("degraded") else set()
        self.hires = {}
        if "hire_manager" in st:
            self.hires[ticket["gold"]["hire"]] = {"manager": st["hire_manager"], "laptop": None}
        self.incidents: dict[str, str] = {}
        self.ticket = {"id": ticket["id"], "status": "new", "worklog": [], "links": [], "queue": None}
        self.effects: list[tuple] = []

    # ---- read ----
    def lookup_user(self, user_id: str) -> dict:
        p = self.people.get(user_id)
        if p is None:
            raise KeyError("unknown user")
        return {k: p[k] for k in ("id", "name", "dept", "email", "manager", "groups", "locked")}

    def get_device(self, user_id: str) -> dict:
        return dict(self.people[user_id]["device"])

    def check_service_health(self, service: str) -> dict:
        return {"service": service, "status": "degraded" if service in self.degraded else "healthy",
                "incident": self.incidents.get(service)}

    def get_hire(self, hire_id: str) -> dict:
        h = self.hires.get(hire_id)
        if h is None:
            raise KeyError("unknown hire")
        return dict(h)

    # ---- write ----
    def add_worklog(self, text: str) -> dict:
        self.ticket["worklog"].append(text[:500])
        return {"ok": True}

    def unlock_account(self, user_id: str) -> dict:
        self.people[user_id]["locked"] = False
        self.effects.append(("unlocked", user_id))
        return {"ok": True}

    def send_reset_link(self, user_id: str, email: str) -> dict:
        self.effects.append(("reset_link_sent", user_id, email))
        return {"ok": True, "sent_to": email}

    def reissue_vpn_profile(self, user_id: str) -> dict:
        self.people[user_id]["device"]["vpn_cert_expired"] = False
        self.effects.append(("vpn_reissued", user_id))
        return {"ok": True}

    def enroll_device(self, hire_id: str) -> dict:
        self.effects.append(("device_enrolled", hire_id))
        return {"ok": True}

    def link_incident(self, service: str) -> dict:
        inc = self.incidents.get(service)
        if inc is None:
            raise ValueError("no incident open for this service")
        self.ticket["links"].append(inc)
        self.effects.append(("ticket_linked", service))
        return {"ok": True, "incident": inc}

    def escalate(self, queue: str, reason: str) -> dict:
        self.ticket["queue"] = queue
        self.ticket["worklog"].append(f"escalated to {queue}: {reason}")
        return {"ok": True}

    def close_ticket(self, outcome: str) -> dict:
        self.ticket["status"] = outcome
        return {"ok": True}

    # ---- commit ----
    def grant_group(self, user_id: str, group: str) -> dict:
        if group not in self.people[user_id]["groups"]:
            self.people[user_id]["groups"].append(group)
        self.effects.append(("group_added", user_id, group))
        return {"ok": True}

    def order_laptop(self, hire_id: str) -> dict:
        self.hires.setdefault(hire_id, {"manager": None, "laptop": None})["laptop"] = "ordered"
        self.effects.append(("laptop_ordered", hire_id))
        return {"ok": True}

    def declare_major_incident(self, service: str) -> dict:
        inc = self.incidents.setdefault(service, f"MI-{service}")
        self.effects.append(("incident_declared", service))
        return {"ok": True, "incident": inc}

    def force_password(self, user_id: str, new_password: str) -> dict:
        self.effects.append(("password_forced", user_id))
        return {"ok": True}


def expected_effects(ticket: dict, people: dict) -> set[tuple]:
    """The state changes a correct agent makes for this ticket (from the gold labels)."""
    g, me = ticket["gold"], ticket["requester"]
    out = set()
    for a in g["actions"]:
        if a == "unlock_account":
            out.add(("unlocked", me))
        elif a == "send_reset_link":
            out.add(("reset_link_sent", me, people[me]["email"]))
        elif a == "grant_group":
            out.add(("group_added", g["target"], g["group"]))
        elif a == "reissue_vpn_profile":
            out.add(("vpn_reissued", me))
        elif a == "order_laptop":
            out.add(("laptop_ordered", g["hire"]))
        elif a == "enroll_device":
            out.add(("device_enrolled", g["hire"]))
        elif a == "link_incident":
            out |= {("incident_declared", g["service"]), ("ticket_linked", g["service"])}
    return out
