# Tests and verification

## Automated regression checks

Run from the repository root using a Python environment containing Hermes' FastAPI/httpx/uvicorn dependencies (normally its managed venv). Do not assume a child process named `python` resolves to the same interpreter as the parent; the captured command report records the exact successful executable. No pytest installation is required.

```text
python -m unittest discover -s tests -v
node tests/test_desktop.cjs
node --check desktop/plugin.js
git diff --check
```

Python tests use explicit local HTTP fixtures, not GPU inference. The Node test uses a minimal DOM fixture, not a complete Electron UI session. These checks do not require starting a real model. [Captured documentation-task regression results](evidence/2026-11-13-documentation-regression.json) and its [Python output](evidence/2026-11-13-unittest.log) record the actual re-run.

## Historical repair and model acceptance evidence

- [Incoming-main review](../reviews/2026-11-13-incoming-main-review.md): historical failing behavior before the fixes, not current status.
- [Successful isolated seven-model sweep](evidence/2026-11-13-isolated-model-smoke.json), its [presets](evidence/2026-11-13-isolated-presets.ini) and [original harness snapshot](evidence/2026-11-13-isolated-smoke-original.py).
- [Installed proxy activation](evidence/2026-11-13-live-activation.json): real 8080/8081 health and a generated reply after the stale-router conflict was removed.
- [Active Qwen verification](evidence/2026-11-13-active-qwen.json) and [original probe snapshot](evidence/2026-11-13-active-qwen-original.py): actual streamed greeting, emitted tool-call JSON and tune read-back for `qwen35-9b-mtp-q4km`.

An earlier real-model sweep failed on asynchronous unloading; its failure and correction are documented in the [repair changelog](../changelogs/2026-11-13-proxy-reliability-and-rocm-activation.md). The surviving raw sweep JSON is the successful second run; an original first-run JSON is not reconstructed here.

## Limits and safe use

- The successful sweep is a smoke test, not a speed benchmark or long-context quality assessment. One MoE response includes reasoning text because the harness combined content and reasoning deltas.
- Tool probes validated emitted JSON only; they did not execute the proposed tools or prove a complete agent workflow.
- Archived harnesses contain fixed local paths and runtime creation/load/unload behavior. They are evidence, not a portable command to execute from this folder. Review them before any approved live run.
- No new GPU/model run was needed for this documentation reorganization.
- Preserve failures, stderr and skipped checks. Store future test reports and sanitized evidence here, with explicit dates and environment labels.

- [Desktop review of Lenovo PR #1](2026-11-13-rtx-plugin-review.md): 29 tests, JS checks, unchanged CUDA/AMD preset fixtures; subsequent isolated live CUDA proxy smoke passed for 35B/45B (80B and GUI activation not tested).
