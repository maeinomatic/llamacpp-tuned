# 2026-11-13 — Machine baseline and cross-machine release checks

## Status and reason

Documentation-only addition on `local/proxy-rocm-compat`, based on `7ff3582` plus the existing uncommitted repair. The user asked whether publication was safe and whether work from the RTX computer would know how to protect this AMD setup. That question is not approval to commit or push.

## Changes

- Added a dedicated [AMD 890M Windows setup baseline](../compatibility/amd-890m-windows.md), consolidating verified hardware/OS, engine build/path, ignored settings snapshot, model tunes, ports, lifecycle constraints and evidence limits.
- Added a [cross-machine change/deployment checklist](../compatibility/cross-machine-checklist.md) covering both AMD/ROCm and RTX/CUDA behavior.
- Made that reading mandatory in root AGENTS.md before shared backend/preset/engine/lifecycle changes, with compatibility and review index links.
- Preserved a fresh [independent final review](../reviews/2026-11-13-final-push-readiness-review.md).

## Unchanged behavior and hardware impact

No production code, runtime binary, machine setting or model data was changed by this documentation addition. No inference or throughput benchmark was run. The other computer was neither updated nor accessed. Existing real AMD test evidence and CUDA fixture evidence remain explicitly distinguished.

## Verification and publication assessment

- Live read-only hardware/OS/settings and engine-version discovery established the recorded local baseline.
- Git remote main was read-only checked and still resolved to `7ff358270a4dbf359de4502c46ef20f94976b599` during the assessment.
- Independent reviewer found no remaining blocking correctness/security issue in the repaired production changes and recommended review-branch publication only after explicit approval; real CUDA smoke remains recommended before main merge.
- A final file-set audit checks common credential signatures, forbidden settings/model/binary payloads, local documentation links and diff whitespace; its results are in [the preflight evidence](../tests/evidence/2026-11-13-publication-preflight.json). Pattern scanning is not a guarantee that all sensitive information is absent. Machine paths/metadata in these documents are intentional and would become visible with publication.
- The existing recorded 29-test pass and live Qwen verification were not mislabeled as a new CUDA test. No new Python production change required a new model sweep.

## Migration, rollback and limits

These instructions protect subsequent work only when they are included in the eventual commit and transferred/read on the other computer. They are contributor/agent rules, not an automatic guard that makes arbitrary future edits safe. Preserve each machine's ignored settings and actual compatible engine. Review/test a transferred branch on the RTX before merging or deploying broadly.

Undoing this documentation addition means restoring only its named documentation/rule changes after preserving subsequent edits. Do not reset the existing uncommitted repair or overwrite runtime/model/settings data.

## Approval / publication

No files were staged, committed, pushed or published by this assessment. The current work needs an explicitly approved commit and push to carry it to another computer; pushing the existing base commit alone would not transfer the uncommitted fixes/docs.
