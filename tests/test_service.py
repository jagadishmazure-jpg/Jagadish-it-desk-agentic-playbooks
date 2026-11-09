"""The service the Azure ML / Microsoft Foundry endpoint calls, and its scoring script."""

import importlib.util
import json

import pytest
from conftest import ROOT

from itdesk import service


def payload(people, me, **kw):
    return {"requester": me, "from": people[me]["email"], "subject": "VPN issue",
            "body": "Getting error 809 on the VPN since this morning.", **kw}


def test_handle_returns_decision_and_audit(people, me):
    out = service.handle(payload(people, me, state={"vpn_cert_expired": True}))
    assert (out["category"], out["outcome"], out["kb"]) == ("vpn", "resolved", "KB-301")
    assert ["read", "read", "write", "write"] == [a["tier"] for a in out["audit"]]
    assert "people" not in json.dumps(out) and "@" not in json.dumps(out)


@pytest.mark.parametrize("bad,msg", [
    ({"body": ""}, "body"),
    ({"requester": "E9999"}, "unknown requester"),
    ({"subject": "x" * 5000}, "longer than"),
    ({"state": {"is_admin": True}}, "state"),
])
def test_bad_input_is_rejected(people, me, bad, msg):
    with pytest.raises(ValueError, match=msg):
        service.check(payload(people, me, **bad))


def test_external_sender_is_marked(people, me):
    t = service.check(payload(people, me, **{"from": "Someone@Mailbox.example"}))
    assert t["flags"] == ["external_sender"] and t["from"] == "someone@mailbox.example"


def test_scoring_script(people, me):
    spec = importlib.util.spec_from_file_location("score", ROOT / "infra/aml/score.py")
    score = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(score)
    score.init()
    assert score.run("not json") == {"error": "body must be JSON"}
    assert "error" in score.run(json.dumps({"requester": me}))
    assert score.run(json.dumps(payload(people, me)))["category"] == "vpn"
