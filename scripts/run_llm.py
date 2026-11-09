"""Run the small open model on CPU for (a) zero-shot triage of dev and test tickets and (b) free-form
plans for test tickets. Writes data/llm_triage.jsonl and data/llm_plans.jsonl. Resumable.

Needs llama-cpp-python==0.3.36 and the GGUF from scripts/fetch_models.sh.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from itdesk import data  # noqa: E402
from itdesk.planner import prompt as plan_prompt  # noqa: E402
from itdesk.tickets import CATEGORIES  # noqa: E402

TRIAGE_SYSTEM = ("You route IT service desk tickets. Labels: " + ", ".join(CATEGORIES) + ". "
                 "password_reset = forgotten, expired or locked passwords; access_request = adding someone to a "
                 "group or site; vpn = remote access problems; laptop_provision = laptops for new starters; "
                 "outage = a service is down or failing; other = anything else. Reply with the label only.")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--job", choices=["triage", "plan", "all"], default="all")
    ap.add_argument("--models-dir", type=Path, default=ROOT / "models")
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()
    from llama_cpp import Llama

    spec = json.loads((ROOT / "scripts" / "models.json").read_text())
    s, m = spec["sampling"], spec["models"][0]
    llm = Llama(str(a.models_dir / m["file"]), n_ctx=s["n_ctx"], n_threads=s["n_threads"], seed=s["seed"], verbose=False)
    people = data.directory()["people"]
    jobs = []
    if a.job in ("triage", "all"):
        jobs.append(("triage", data.DATA / "llm_triage.jsonl", [t for t in data.tickets() if t["split"] in ("dev", "test")]))
    if a.job in ("plan", "all"):
        jobs.append(("plan", data.DATA / "llm_plans.jsonl", [t for t in data.tickets() if t["split"] == "test"]))
    for job, path, ts in jobs:
        done = {r["id"] for r in data.read_jsonl(path)} if path.exists() else set()
        with path.open("a", encoding="utf-8") as fh:
            for t in ts[: a.limit or None]:
                if t["id"] in done:
                    continue
                if job == "triage":
                    msgs = [{"role": "system", "content": TRIAGE_SYSTEM},
                            {"role": "user", "content": f"Subject: {t['subject']}\n{t['body']}\nLabel:"}]
                    mx = s["triage_max_tokens"]
                else:
                    msgs, mx = plan_prompt(t, people[t["requester"]]), s["planner_max_tokens"]
                t0 = time.perf_counter()
                r = llm.create_chat_completion(messages=msgs, temperature=s["temperature"], max_tokens=mx)
                fh.write(json.dumps({"id": t["id"], "model": m["label"], "output": r["choices"][0]["message"]["content"],
                                     "prompt_tokens": r["usage"]["prompt_tokens"],
                                     "completion_tokens": r["usage"]["completion_tokens"],
                                     "latency_s": round(time.perf_counter() - t0, 3)}) + "\n")
                fh.flush()
            print(job, "done", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
