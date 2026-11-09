"""Triage: category, priority and entities from ticket text.

Two category classifiers are compared: TF-IDF + logistic regression trained on the train split, and a
small open model (qwen2.5-1.5b) asked zero-shot on CPU, whose answers are committed. The hybrid uses the
classifier and asks the model only when the classifier is unsure. Priority comes from an impact x urgency
matrix read from the text by rules. Entities come from patterns, never from the model.
"""

from __future__ import annotations

import re

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import FeatureUnion, make_pipeline

from .company import PRIVILEGED_GROUPS, SERVICES, STANDARD_GROUPS
from .tickets import CATEGORIES, PRIORITY

INJECTION = re.compile((r"\b(ignore (your|all|previous) (rules|instructions)|note to the ai|system:|assistant,|"
                       r"pre-approved|without asking)"), re.I)
IMPACT_CUES = {"site": ("whole mill", "everyone on site", "floors"), "team": ("team", "the four of us", "shift")}
# Order matters: "not urgent" must be read before "urgent".
URGENCY_CUES = {"low": ("no rush", "whenever", "not urgent"),
                "high": ("urgent", "asap", "production has stopped", "blocking", "cannot ship")}


def text_of(t: dict) -> str:
    return f"{t['subject']}. {t['body']}"


def entities(t: dict) -> dict:
    body = t["body"]
    users = [u for u in re.findall(r"\bE\d{4}\b", body) if u != t["requester"]]
    groups = [g for g in PRIVILEGED_GROUPS + STANDARD_GROUPS if g in body]
    services = [s for s in SERVICES if re.search(rf"\b{re.escape(s)}\b", body)]
    hire = re.search(r"\bH\d{3}\b", body)
    clean = INJECTION.split(body)[0]  # the request itself, before any planted instruction
    return {"other_users": users, "group": next((g for g in groups if g in clean), groups[0] if groups else None),
            "target": next((u for u in re.findall(r"\bE\d{4}\b", clean) if u != t["requester"]), t["requester"]),
            "service": services[0] if services else None, "hire": hire.group(0) if hire else None,
            "injection_suspected": bool(INJECTION.search(body))}


def priority(t: dict) -> str:
    low = t["body"].lower()
    impact = next((k for k, cues in IMPACT_CUES.items() if any(c in low for c in cues)), "me")
    urgency = next((k for k, cues in URGENCY_CUES.items() if any(c in low for c in cues)), "normal")
    return PRIORITY[(impact, urgency)]


class Classifier:
    def __init__(self, seed: int = 0):
        feats = FeatureUnion([("w", TfidfVectorizer(ngram_range=(1, 2), min_df=1, sublinear_tf=True)),
                              ("c", TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), min_df=2, sublinear_tf=True))])
        self.model = make_pipeline(feats, LogisticRegression(C=10, max_iter=2000, random_state=seed))

    def fit(self, tickets: list[dict]) -> Classifier:
        self.model.fit([text_of(t) for t in tickets], [t["gold"]["category"] for t in tickets])
        return self

    def predict(self, tickets: list[dict]) -> list[tuple[str, float]]:
        p = self.model.predict_proba([text_of(t) for t in tickets])
        cls = self.model.classes_
        return [(str(cls[i]), float(row[i])) for row, i in zip(p, np.argmax(p, axis=1))]


def parse_llm_category(text: str) -> str | None:
    low = text.strip().lower()
    hits = [c for c in CATEGORIES if c in low or c.replace("_", " ") in low]
    return hits[0] if len(hits) == 1 else None
