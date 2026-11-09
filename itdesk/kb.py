"""Knowledge-base articles and BM25 search over them (the agent cites the article it followed)."""

from __future__ import annotations

import math
import re
from collections import Counter
from functools import lru_cache

ARTICLES = {
    "KB-101": ("Password self-service reset", ("Forgot or expired password. Verify the requester signed in to the "
               "portal or wrote from their company address. Send a reset link to the registered company e-mail "
               "only. Never send passwords or links to personal addresses. Never set a password for someone.")),
    "KB-102": ("Account locked out", ("Locked account after too many sign-in attempts. Unlock the account for "
               "the verified requester, then send a reset link to the registered address.")),
    "KB-201": ("Standard group access", ("Access to a shared folder, site, team, dashboards or read-only ERP (for example sharepoint-sales, "
               "bi-dashboards). "
               "Request approval from the person's line manager. Grant only after approval.")),
    "KB-202": ("Privileged access", ("domain-admins, payments-approvers or erp-superusers membership (domain admin, payments approver, ERP superuser). Needs the "
               "line manager and the security approver, and an approved change reference CHG-####.")),
    "KB-301": ("VPN certificate expired", ("Remote access fails with error 809 or authentication failed. Check "
               "the laptop: if the VPN certificate expired, reissue the VPN profile.")),
    "KB-302": ("VPN blocked for non-compliant laptop", ("Laptops missing updates or encryption are blocked from "
               "VPN. Escalate to the endpoint team; do not bypass compliance.")),
    "KB-401": ("New starter laptop", ("Laptop for a new hire. Check the HR record, get the hiring manager's "
               "approval, order the standard laptop and enrol it.")),
    "KB-501": ("Service outage and major incidents", ("Several people report a service down, error pages, "
               "nothing loads. Check service health. If degraded, declare or join the major incident (on-call "
               "approval) and link the ticket.")),
    "KB-601": ("Escalate to the service desk team", ("Facilities, HR questions, printers, local issues on a "
               "healthy service, or anything outside the playbooks: hand to a person with a short summary.")),
}
TOKEN = re.compile(r"[a-z0-9]+")
STOP = set("a an the of in on at to for and or is are be by with my me i it can can't cannot not "
           "please this that our we you your from as".split())


def tokenize(text: str) -> list[str]:
    return [t for t in TOKEN.findall(text.lower()) if t not in STOP]


@lru_cache(maxsize=1)
def _index():
    docs = {k: Counter(tokenize(t + " " + b)) for k, (t, b) in ARTICLES.items()}
    n = len(docs)
    df = Counter(w for d in docs.values() for w in d)
    idf = {w: math.log(1 + (n - f + 0.5) / (f + 0.5)) for w, f in df.items()}
    avg = sum(sum(d.values()) for d in docs.values()) / n
    return docs, idf, avg


def search(query: str, k: int = 3) -> list[str]:
    docs, idf, avg = _index()
    q = tokenize(query)
    scores = {}
    for key, d in docs.items():
        ln = sum(d.values())
        scores[key] = sum(idf.get(w, 0) * d[w] * 2.5 / (d[w] + 1.5 * (0.25 + 0.75 * ln / avg)) for w in q if w in d)
    return sorted(scores, key=lambda x: (-scores[x], x))[:k]
