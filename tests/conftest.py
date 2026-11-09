import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from itdesk import data  # noqa: E402
from itdesk.gateway import Gateway  # noqa: E402
from itdesk.systems import Systems  # noqa: E402


@pytest.fixture(scope="session")
def metrics():
    return json.loads((ROOT / "results/metrics.json").read_text())


@pytest.fixture(scope="session")
def people():
    return data.directory()["people"]


@pytest.fixture(scope="session")
def me(people):
    return sorted(people)[3]


@pytest.fixture
def ticket(people, me):
    """A plain, verified ticket from one employee; tests override fields."""

    def make(body="Hi IT.", state=None, **kw):
        t = {"id": "T-test", "channel": "portal", "requester": me, "from": people[me]["email"], "flags": [],
             "subject": "Help", "body": body, "_state": state or {}, "gold": {}}
        t.update(kw)
        return t

    return make


def gateway(t, **kw):
    s = Systems(t, data.directory())
    return s, Gateway(s, t, **kw)


def find(tickets, pred):
    return next(t for t in tickets if pred(t))
