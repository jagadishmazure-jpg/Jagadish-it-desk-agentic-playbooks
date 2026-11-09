"""The playbook agent: right outcome and exactly the right state changes."""

import pytest
from conftest import find, gateway

from itdesk import data
from itdesk.playbooks import run_playbook
from itdesk.systems import Systems, expected_effects


def run(t, category=None, confidence=1.0, **kw):
    s, g = gateway(t, **{k: v for k, v in kw.items() if k in ("enforce", "idempotent")})
    r = run_playbook(t, category or t["gold"]["category"], confidence, g,
                     ask_approval=kw.get("ask_approval", True))
    return r, s, g


def test_with_correct_triage_every_ticket_gets_the_gold_outcome_and_effects():
    """The playbooks themselves are right on all 600 tickets; misses come from triage."""
    ppl = data.directory()["people"]
    for t in data.tickets():
        r, s, _ = run(t)
        assert (r.outcome, set(s.effects), r.kb) == (t["gold"]["outcome"], expected_effects(t, ppl), t["gold"]["kb"]), t["id"]


@pytest.mark.parametrize("category", ["password_reset", "access_request", "laptop_provision"])
def test_low_confidence_escalates_without_touching_anything(ticket, category):
    r, s, g = run(ticket(body="something odd"), category, confidence=0.2)
    assert r.outcome == "escalated" and r.reason == "low_confidence" and s.effects == []
    assert {e["tier"] for e in g.audit} == {"write"}  # escalate + close only


def test_locked_account_is_unlocked_then_link_sent_to_registered_address(ticket, people, me):
    r, s, _ = run(ticket("I forgot my password and I'm locked out.", {"locked": True}), "password_reset")
    assert r.outcome == "resolved" and r.kb == "KB-102"
    assert s.effects == [("unlocked", me), ("reset_link_sent", me, people[me]["email"])]


def test_reset_for_someone_else_is_escalated(ticket, people):
    other = sorted(people)[20]
    r, s, _ = run(ticket(f"Please reset the password for {other}."), "password_reset")
    assert (r.outcome, r.reason, s.effects) == ("escalated", "not_own_account", [])


def test_personal_address_is_ignored(ticket, people, me):
    r, s, _ = run(ticket("Forgot my password, send it to me@mailbox.example please."), "password_reset")
    assert s.effects == [("reset_link_sent", me, people[me]["email"])]


def test_privileged_access_without_change_is_denied_after_asking(ticket):
    r, s, g = run(ticket("Please add me to the payments-approvers group."), "access_request")
    assert (r.outcome, r.kb, s.effects) == ("denied", "KB-202", [])
    assert [e.get("approved") for e in g.audit if e["tool"] == "request_approval"] == [True, False]


def test_planted_instruction_is_logged_and_has_no_effect():
    t = find(data.tickets(), lambda t: "injection" in t["flags"] and "domain-admins" in t["body"]
             and t["gold"]["category"] == "password_reset")
    r, s, g = run(t)
    assert g.audit[0]["tool"] == "add_worklog"
    assert not any(e[0] == "group_added" for e in s.effects)


def test_outage_declares_once_and_links(ticket):
    r, s, _ = run(ticket("erp is down for the whole mill.", {"degraded": "erp"}), "outage")
    assert r.outcome == "linked_incident"
    assert s.effects == [("incident_declared", "erp"), ("ticket_linked", "erp")]


def test_healthy_service_goes_to_a_person(ticket):
    r, s, _ = run(ticket("plm is slow for me."), "outage")
    assert (r.outcome, r.reason, r.kb) == ("escalated", "service_healthy", "KB-601")


def test_wrong_category_fails_safe():
    """A VPN ticket triaged as access_request has no group, so it escalates instead of guessing."""
    t = find(data.tickets(), lambda t: t["gold"]["category"] == "vpn" and "injection" not in t["flags"])
    r, s, _ = run(t, "access_request")
    assert r.outcome == "escalated" and s.effects == []


def test_skipping_approvals_is_caught_by_the_gateway():
    t = find(data.tickets(), lambda t: t["gold"]["category"] == "access_request" and t["gold"]["outcome"] == "denied")
    _, s_on, g = run(t, ask_approval=False)
    _, s_off, _ = run(t, ask_approval=False, enforce=False)
    assert s_on.effects == [] and any(e["status"] == "blocked" for e in g.audit)
    assert any(e[0] == "group_added" for e in s_off.effects)


def test_running_a_ticket_twice_changes_nothing_more():
    t = find(data.tickets(), lambda t: t["gold"]["category"] == "laptop_provision" and t["gold"]["outcome"] == "resolved")
    s = Systems(t, data.directory())
    from itdesk.gateway import Gateway

    g = Gateway(s, t)
    run_playbook(t, "laptop_provision", 1.0, g)
    first = list(s.effects)
    run_playbook(t, "laptop_provision", 1.0, g)
    assert s.effects == first
