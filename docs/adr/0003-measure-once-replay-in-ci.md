# ADR 0003: Measure the small model once on CPU, commit its outputs, replay in CI

## Status

Accepted.

## Context

CI must be free, fast and deterministic. Running a model in CI is slow and can drift.

## Decision

`scripts/run_llm.py` ran qwen2.5-1.5b-instruct (Q4, llama.cpp, greedy, seed 0) once on CPU for
zero-shot triage of the dev and test tickets and for free-form plans on the test tickets. Outputs are
committed to `data/llm_*.jsonl` and pinned by `data/manifest.json`. Everything else is computed live.

## Consequences

- Every number in the README is recomputed in CI and must match `results/`.
- A different model or prompt means re-running the script and committing new files, which shows in
  the diff.
