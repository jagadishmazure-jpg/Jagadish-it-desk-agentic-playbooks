"""Write the synthetic directory and tickets to data/. Deterministic; CI checks the files match."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from itdesk.company import build_directory  # noqa: E402
from itdesk.tickets import build_tickets  # noqa: E402


def render() -> dict[str, str]:
    return {"directory.json": json.dumps(build_directory(), indent=1, sort_keys=True) + "\n",
            "tickets.jsonl": "".join(json.dumps(t, sort_keys=True) + "\n" for t in build_tickets())}


def main() -> int:
    check, bad = "--check" in sys.argv, []
    for name, text in render().items():
        p = ROOT / "data" / name
        if check:
            if not p.exists() or p.read_text(encoding="utf-8") != text:
                bad.append(name)
        else:
            p.write_text(text, encoding="utf-8")
    if bad:
        print("out of date:", ", ".join(bad))
        return 1
    print("dataset", "matches" if check else "written")
    return 0


if __name__ == "__main__":
    sys.exit(main())
