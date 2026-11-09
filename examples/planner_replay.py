"""Replay the small model's own plan for a test ticket, with the gateway on and off.

The ticket is picked by rule: the first test ticket (by ID) carrying a planted instruction whose
plan made an unexpected high-risk change with the gateway off.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from itdesk import data  # noqa: E402
from itdesk.evaluate import high_risk  # noqa: E402
from itdesk.gateway import Gateway  # noqa: E402
from itdesk.planner import execute, parse_plan  # noqa: E402
from itdesk.systems import Systems, expected_effects  # noqa: E402
from itdesk.triage import INJECTION  # noqa: E402

ppl, plans = data.directory()["people"], data.llm_rows("plans")


def risky(t: dict, s: Systems) -> list[tuple]:
    """Unexpected changes that are high-risk (the measure used in results/report.md)."""
    exp = expected_effects(t, ppl)
    return [e for e in s.effects if e not in exp and high_risk(e, t, ppl)]


def replay(t: dict, enforce: bool):
    s = Systems(t, data.directory())
    g = Gateway(s, t, enforce=enforce)
    execute(parse_plan(plans[t["id"]]["output"]) or [], g)
    return s, g


for t in sorted((t for t in data.tickets() if t["split"] == "test" and "injection" in t["flags"]), key=lambda t: t["id"]):
    s_off, _ = replay(t, enforce=False)
    if risky(t, s_off):
        break
print(f"Ticket {t['id']} ({t['gold']['category']}, gold outcome {t['gold']['outcome']})")
print(f"Planted text: {t['body'][INJECTION.search(t['body']).start():][:110]}")
print()
for enforce in (False, True):
    s, g = replay(t, enforce)
    print(f"gateway {'on' if enforce else 'off'}:")
    for e in g.audit:
        why = f" - {e['reason']}" if e.get("reason") else ""
        print(f"  {e['tier']:<7} {e['tool']:<22} {e['status']}{why}")
    print(f"  unexpected high-risk changes: {[e[0] for e in risky(t, s)] or 'none'}")
    print()
