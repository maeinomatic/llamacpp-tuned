# 2026-11-13 — Documentation layout and changelog policy

## Status and scope

Documentation-only maintenance on local branch `local/proxy-rocm-compat`, based on `7ff3582` plus existing uncommitted proxy fixes. No production Python/JavaScript, model tune, machine setting or live server is changed by this task. Nothing is committed or pushed.

## Reason

Benchmark notes, test evidence, the repair plan and the local changelog were spread across the repo root, the local benchmark workspace and auto-pruned scratch storage. Future fixes also needed a persistent repository rule requiring a changelog without repeated user reminders.

## Changes

- Created `doc/` with benchmarks, changelogs, tests, compatibility, operations, plans, reviews and templates, each indexed from the documentation landing page.
- Moved the existing root changelog to [the dated proxy-repair entry](2026-11-13-proxy-reliability-and-rocm-activation.md) and the loose plan to [plans](../plans/2026-11-13-proxy-repair-plan.md).
- Copied historical AMD benchmark reports, raw matrix/variant results, reproduction input and script snapshots into a hardware/date-specific archive. External originals were retained.
- Preserved incoming-review findings, CUDA fixture/source-comparison evidence, successful isolated model smoke results, live activation results and active Qwen verification inside the repo.
- Added a provenance manifest with SHA-256 values and an archive caveat wrapper. Historical contradictory labels/recommendations are flagged instead of silently changing old measurements.
- Added canonical `AGENTS.md` requiring a dated changelog per change, evidence/limits, hardware impact and index updates. Added `.hermes.md` as a bridge to those same rules for Hermes working from subdirectories.
- Added changelog/benchmark templates and README navigation; clarified public proxy versus internal router ports in the README.
- Kept executable regression implementation under root `tests/`; documentation and results belong in `doc/tests/`.
- Mirror the documentation/rules into the existing local repair worktree so subsequent work there sees the same policy. This does not publish or update the RTX computer.

## Unchanged behavior and hardware impact

No inference behavior changes on AMD or CUDA. No GPU measurements are re-run for documentation import. The other computer's raw CUDA benchmark files are not available here; its section explicitly records that evidence gap rather than inventing results.

## Verification

- Re-ran the existing suite using the installed Hermes virtual-environment interpreter: **29 Python regression tests passed**. The Node desktop cleanup test, JavaScript syntax check and `git diff --check` also passed. [Commands and exit codes](../tests/evidence/2026-11-13-documentation-regression.json), [Python output](../tests/evidence/2026-11-13-unittest.log).
- Verified imported archive bytes against all 19 recorded SHA-256 values, parsed the JSON evidence and checked local Markdown file links. [Validation results](../tests/evidence/2026-11-13-documentation-validation.json).
- The first test-launch attempt selected a child Python environment without `httpx`, producing import errors rather than product-test failures. That [failed launch output](../tests/evidence/2026-11-13-default-python-import-failure.log) is retained. The explicit existing Hermes venv resolved it; no package installation or production-code change was needed.
- No model/GPU load, engine restart, setting change or throughput measurement was performed for this documentation task.

## Migration and rollback

Follow [doc/README.md](../README.md) instead of loose root notes. Machine-specific benchmark paths inside archived scripts remain historical snapshots, not portable launch commands. The archive manifest records original source locations; outside-repo originals remain intact. To undo this reorganization, restore only these documentation paths after preserving any subsequent edits; do not reset the existing uncommitted proxy repair or touch model/settings data.

## Limits

Historical material may contain stale conclusions; wrapper caveats identify known conflicts. Large raw server logs, binaries, models and credentials were not imported. Root `AGENTS.md` is an agent/contributor instruction, not a Git hook or guarantee that arbitrary third-party tools enforce it. The documentation/rules must later be committed and transferred with explicit approval to apply on another computer.

## Approval / publication

No commit, push, release or remote-machine change was requested or performed.
