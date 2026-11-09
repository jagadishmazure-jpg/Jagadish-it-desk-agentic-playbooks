"""The fictional company: employees, managers, groups, devices and services. Seeded and deterministic.

Harrowmere Textiles is invented. Every e-mail address uses the reserved `.example` domain.
"""

from __future__ import annotations

import hashlib
import random

COMPANY = "Harrowmere Textiles"
DOMAIN = "harrowmere.example"
FIRST = ["Asha", "Bram", "Cleo", "Dev", "Edda", "Femi", "Gale", "Hugo", "Ines", "Jory", "Kaia", "Lior", "Mina",
         "Noor", "Otis", "Pria", "Quin", "Rhea", "Sami", "Tova", "Ulla", "Veda", "Wren", "Yara", "Zane"]
LAST = ["Ashby", "Brindle", "Corran", "Delacey", "Everard", "Fenwick", "Garrow", "Hollis", "Ingram", "Jessop",
        "Kettle", "Lowther", "Marchant", "Nettles", "Oakham", "Pellow", "Quarles", "Rudd", "Sowerby", "Thrale"]
DEPTS = ["Finance", "Weaving", "Dyeing", "Logistics", "Sales", "HR", "IT"]
STANDARD_GROUPS = ["sharepoint-sales", "sharepoint-finance", "erp-readonly", "plm-designers", "wifi-guest-admin",
                   "teams-logistics", "bi-dashboards"]
PRIVILEGED_GROUPS = ["domain-admins", "payments-approvers", "erp-superusers"]
SERVICES = ["erp", "email", "vpn-gateway", "plm", "wifi-mill-2", "payroll"]


def rng(*parts: object) -> random.Random:
    return random.Random(int(hashlib.sha256("|".join(map(str, parts)).encode()).hexdigest()[:12], 16))


def build_directory(n: int = 120) -> dict:
    """Employees with a manager, a registered e-mail, a laptop and group memberships."""
    r = rng("directory")
    people = {}
    names = set()
    for i in range(n):
        while True:
            name = f"{r.choice(FIRST)} {r.choice(LAST)}"
            if name not in names:
                names.add(name)
                break
        eid = f"E{1000 + i}"
        dept = DEPTS[i % len(DEPTS)]
        people[eid] = {"id": eid, "name": name, "dept": dept,
                       "email": f"{name.lower().replace(' ', '.')}@{DOMAIN}",
                       "manager": None, "groups": [], "locked": False, "vip": False,
                       "device": {"id": f"LT-{4000 + i}", "vpn_cert_expired": False, "compliant": True}}
    ids = list(people)
    managers = {d: [e for e in ids if people[e]["dept"] == d][0] for d in DEPTS}
    for e in ids:
        m = managers[people[e]["dept"]]
        people[e]["manager"] = None if e == m else m
        people[e]["groups"] = sorted(r.sample(STANDARD_GROUPS, 2))
    for m in managers.values():
        people[m]["vip"] = True
    it_admin = [e for e in ids if people[e]["dept"] == "IT"][1]
    people[it_admin]["groups"].append("domain-admins")
    return {"people": people, "managers": managers, "security_approver": it_admin,
            "on_call": [e for e in ids if people[e]["dept"] == "IT"][2]}
