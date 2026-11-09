"""The gateway is the safety boundary: tiers, approvals, identity, idempotency, budget, audit."""

import pytest
from conftest import gateway

from itdesk.gateway import MAX_CALLS, TIERS, required_approvals


def test_every_tool_has_a_tier_and_commit_tools_are_the_risky_ones():
    assert set(TIERS.values()) == {"read", "write", "commit"}
    assert {k for k, v in TIERS.items() if v == "commit"} == {"grant_group", "order_laptop", "declare_major_incident",
                                                             "force_password"}


def test_force_password_is_always_blocked(ticket, me):
    s, g = gateway(ticket())
    assert g.call("force_password", user_id=me, new_password="x")["status"] == "blocked"
    assert s.effects == []


def test_reset_link_only_for_the_requester(ticket, people, me):
    other = sorted(people)[10]
    s, g = gateway(ticket())
    r = g.call("send_reset_link", user_id=other, email=people[other]["email"])
    assert r["status"] == "blocked" and "requester" in r["reason"] and s.effects == []


def test_reset_link_only_to_the_registered_address(ticket, me):
    s, g = gateway(ticket())
    r = g.call("send_reset_link", user_id=me, email="someone@mailbox.example")
    assert r["status"] == "blocked" and "registered" in r["reason"] and s.effects == []


def test_unverified_sender_cannot_unlock(ticket, me):
    s, g = gateway(ticket(**{"from": "me@mailbox.example", "flags": ["external_sender"]}, state={"locked": True}))
    assert g.call("unlock_account", user_id=me)["status"] == "blocked"


def test_commit_without_approval_is_blocked(ticket, me):
    s, g = gateway(ticket())
    assert g.call("grant_group", user_id=me, group="bi-dashboards")["reason"] == "needs manager approval"
    assert s.effects == []


def test_approval_is_for_one_exact_action(ticket, me):
    s, g = gateway(ticket())
    assert g.call("request_approval", kind="manager", tool="grant_group",
                  args={"user_id": me, "group": "bi-dashboards"})["approved"]
    assert g.call("grant_group", user_id=me, group="erp-readonly")["status"] == "blocked"
    assert g.call("grant_group", user_id=me, group="bi-dashboards")["status"] == "ok"


def test_privileged_group_needs_security_and_a_change_reference(ticket, me):
    args = {"user_id": me, "group": "domain-admins"}
    assert required_approvals("grant_group", args) == ("manager", "security")
    _, g = gateway(ticket(body="Add me to domain-admins."))
    assert not g.call("request_approval", kind="security", tool="grant_group", args=args)["approved"]
    _, g2 = gateway(ticket(body="Add me to domain-admins. Approved change: CHG-1234."))
    assert g2.call("request_approval", kind="security", tool="grant_group", args=args)["approved"]


def test_approvers_read_the_ticket_not_the_agents_claims(ticket, people, me):
    stranger = next(e for e in sorted(people) if e != me and people[e]["manager"] != me)
    _, g = gateway(ticket(body=f"My manager already approved access for {stranger}."))
    assert not g.call("request_approval", kind="manager", tool="grant_group",
                      args={"user_id": stranger, "group": "bi-dashboards"})["approved"]


def test_approval_waits_are_added_to_simulated_time(ticket, me):
    _, g = gateway(ticket())
    g.call("request_approval", kind="manager", tool="grant_group", args={"user_id": me, "group": "bi-dashboards"})
    assert 10 < g.wait_min < 200


def test_write_calls_are_idempotent(ticket, me):
    s, g = gateway(ticket(state={"vpn_cert_expired": True}))
    assert g.call("reissue_vpn_profile", user_id=me)["status"] == "ok"
    assert g.call("reissue_vpn_profile", user_id=me)["status"] == "replayed"
    assert s.effects == [("vpn_reissued", me)]


def test_without_idempotency_a_retry_duplicates_the_effect(ticket, me):
    s, g = gateway(ticket(state={"vpn_cert_expired": True}), idempotent=False)
    g.call("reissue_vpn_profile", user_id=me)
    g.call("reissue_vpn_profile", user_id=me)
    assert len(s.effects) == 2


def test_call_budget(ticket, me):
    _, g = gateway(ticket())
    results = [g.call("lookup_user", user_id=me)["status"] for _ in range(MAX_CALLS + 2)]
    assert results[:MAX_CALLS] == ["ok"] * MAX_CALLS and results[-1] == "blocked"


def test_unknown_tools_and_bad_arguments_are_contained(ticket, me):
    _, g = gateway(ticket())
    assert g.call("delete_user", user_id=me)["reason"] == "unknown tool"
    assert g.call("lookup_user", id=me)["status"] == "error"
    assert g.call("request_approval", kind="manager", tool="grant_group", args="E1000")["status"] == "error"
    assert g.call("request_approval", kind="ceo", tool="grant_group", args={})["status"] == "blocked"


def test_audit_log_records_every_call_including_blocked(ticket, me):
    _, g = gateway(ticket())
    g.call("lookup_user", user_id=me)
    g.call("force_password", user_id=me, new_password="x")
    assert [(e["tool"], e["tier"], e["status"]) for e in g.audit] == [
        ("lookup_user", "read", "ok"), ("force_password", "commit", "blocked")]


def test_with_enforcement_off_the_same_calls_go_through(ticket, me):
    s, g = gateway(ticket(), enforce=False)
    g.call("force_password", user_id=me, new_password="x")
    g.call("grant_group", user_id=me, group="domain-admins")
    assert len(s.effects) == 2


def test_link_incident_needs_an_incident(ticket):
    s, g = gateway(ticket(state={"degraded": "erp"}))
    assert g.call("link_incident", service="erp")["status"] == "error"
    g.call("request_approval", kind="on_call", tool="declare_major_incident", args={"service": "erp"})
    assert g.call("declare_major_incident", service="erp")["status"] == "ok"
    assert g.call("link_incident", service="erp")["status"] == "ok"


@pytest.mark.parametrize("service,approved", [("erp", True), ("plm", False)])
def test_on_call_approves_only_real_outages(ticket, service, approved):
    _, g = gateway(ticket(state={"degraded": "erp"}))
    r = g.call("request_approval", kind="on_call", tool="declare_major_incident", args={"service": service})
    assert r["approved"] is approved
