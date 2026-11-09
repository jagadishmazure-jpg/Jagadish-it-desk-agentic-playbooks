#!/usr/bin/env bash
# Download the open model used for zero-shot triage and the free-form planner (about 1.1 GB) into ./models
# and verify SHA-256. Only needed to re-measure data/llm_*.jsonl; tests and the eval use the committed files.
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p models
python3 - <<'PY' | while read -r file url sha; do
import json
for m in json.load(open("scripts/models.json"))["models"]:
    print(m["file"], m["url"], m["sha256"])
PY
  [[ -f "models/$file" ]] || curl -fL --retry 3 -o "models/$file" "$url"
  echo "$sha  models/$file" | sha256sum -c -
done
