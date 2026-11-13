# 2026-11-13 — Commit and push of repaired branch

## Status and scope

Per explicit user approval ("commit and push", then confirmation to use plain `git add .` given the existing ignores): committed and pushed exactly once.

- Branch: `local/proxy-rocm-compat`
- Commit: `2b256c64b682b9add07905f3170a9817340f0caa` (single commit; `--no-verify`, verified message)
- Pushed to: `origin` (`maeinomatic/llamacpp-tuned`), tracking branch set up
- Working tree after: clean
- **Not merged into `main`**; actual RTX 3070/CUDA inference acceptance remains outstanding and is the recorded gate for that merge.

## Contents

56 files: the repaired `dashboard/plugin_api.py` and `desktop/plugin.js`, README updates, `AGENTS.md` (mandatory changelog policy), `.hermes.md` bridge, the indexed `doc/` hierarchy (benchmarks, changelogs, tests, compatibility, operations, plans, reviews, templates), the AMD 890M setup baseline and cross-machine checklist, regression tests, and test/review evidence JSON/logs.

## Verification before commit/push

- Final independent candidate review: `passed=true`, no blocking security/correctness defect (`doc/reviews/evidence/2026-11-13-final-candidate-commit-review.json`).
- Publication preflight: no common credential signatures, `dashboard/settings.json` excluded by ignore rules, no model/binary payloads, documentation links and archive hashes valid (`doc/tests/evidence/2026-11-13-publication-preflight.json`).
- Staged set checked with plain `git add .` plus ignore rules (the earlier custom staging attempt was discarded before commit); staged list confirmed to contain no settings/models/binaries; whitespace check passed; production file digests matched the reviewed activated state.

## Notes and limits

- Commit message records the verified status and the explicit "not CUDA hardware tested" limitation.
- Initial push attempt was not executed; the first run aborted pre-commit on its own staging assertion, so no partial/failed remote push occurred. The second, plain-`git-add` run is the single recorded push.
- The commit record intentionally includes local machine metadata (paths/hardware) because these docs are cross-machine guidance; review the published content if you later intend broader sharing.
- No rollback needed; if the branch needs changes, commit follow-ups rather than force-rewriting this published commit.

## Approval / publication

Approved commit/push of the review branch only. After that approval, the user requested the PR: **[PR #1](https://github.com/maeinomatic/llamacpp-tuned/pull/1)** (`local/proxy-rocm-compat` → `main`) was created via `gh pr create` and read back OPEN/MERGEABLE with both commits. It was left **open, not merged** — the RTX 3070/CUDA acceptance remains the recorded gate for merging. No PR merge, RTX deployment or other remote action was performed.
