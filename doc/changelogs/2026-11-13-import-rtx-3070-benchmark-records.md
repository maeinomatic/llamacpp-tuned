# 2026-11-13 — Review Lenovo PR and import desktop records

## Status and scope
Base: main at `b642ec2`, Lenovo PR #1 (`local/proxy-rocm-compat`).
This follow-up changes documentation/evidence only. **Uncommitted and unpushed.**
No source changes, activation, provider/settings/engine changes or Hermes core edits.

## Reason / observed symptom
User requested review of the pulled Lenovo changes against desktop ngram-mod and
MoE expert-cache behavior, followed by documentation migration into existing `doc/`.
Earlier session explanations and historical benchmark conclusions needed corrections.

## Changes
- Imported 25 source artifacts with source/destination hashes in
  [manifest](../benchmarks/rtx-3070/import-provenance.json).
- Original November 10–13 desktop reports, three hardware-labelled charts, public
  video transcript, scripts and eight raw JSONs in `2026-11-desktop-archive/`.
- Model-evaluation records with a separate explicit correction page; plan in
  `doc/plans/`; review and fixture evidence in `doc/tests/`.
- Desktop backend baseline; corrected Legion supplement points at the recorded
  ROCm/HIP b12110 baseline, not an assumed Vulkan setup. Relevant indexes updated.
- External originals remain intact; plugin backups/settings/binaries/weights excluded.

## Unchanged behavior and hardware impact
Preset generator and engine/settings functions are AST-identical to `7ff3582`.
CUDA, auto/NVIDIA, ROCm and Vulkan fixtures generate identical before/after output.
Desktop MoE ngram-mod 10/2 and per-model cache/share remain intact; AMD does not
inherit CUDA cache flags. No tune redesign required.

## Verification
| Executed check | Result | Evidence |
|---|---|---|
| `python -m unittest discover -s tests -v` | 29 passed | [Review](../tests/2026-11-13-rtx-plugin-review.md) |
| Desktop JS test + syntax | Passed | Same review |
| AST and four backend fixture comparisons | Identical relevant behavior | [JSON](../tests/evidence/2026-11-13-desktop-preset-review.json) |
| Import hashes, JSON and links | See validation record | [Validation](../tests/evidence/2026-11-13-desktop-import-validation.json) |

Prior pytest lacked pytest; a module-qualified unittest invocation lacked a sibling
import path. Supported unittest discovery now passes; no code change was needed.

## Migration and rollback
No restart needed for docs. Original files remain in the desktop Documents benchmark
archive and F:/AI/llama.cpp. Prior task copied PR code into the installed plugin at
user request; this follow-up neither recopies nor activates it. Preserve ignored
machine settings. Current edits remain reversible working-tree documentation edits.

## Limits / remaining work
No live repaired-proxy CUDA acceptance or throughput benchmark was performed here.
The prior standalone BAT smoke bypassed the proxy and omitted expert-cache flags;
its claimed acceptance coverage is withdrawn. Observing the pre-existing built-in
runtime while plugin activation is off does not show a plugin regression or core move.
Historical EOS probes do not prove model/MTP bugs or a Kimi router incompatibility.
The 45B sheep answer was incorrect, not a reasoning pass. See model-evaluation caveats.

## Approval / publication
**No commit or push without explicit user approval.**

## Follow-up approved live test

The user requested a live test before committing. Isolated repaired-plugin CUDA
proxy passed cold and warm 35B streaming and a switch to 45B, with ngram-mod and
expert-cache flags retained. See [review results](../tests/2026-11-13-rtx-plugin-review.md#subsequent-live-cuda-proxy-smoke-approved-by-user).
No failures, no saved settings changes, test listeners closed after cleanup.
This supplements the earlier source/fixture-only review; it does not claim 80B,
full occupied-context, GUI activation, long-run stability or performance acceptance.
Everything remains **uncommitted and unpushed** pending approval.

## Publication approval

The user subsequently explicitly approved commit and push. This publication contains
documentation, historical benchmark/chart imports and desktop review/live-smoke
evidence only; no plugin source, machine settings, engine, models or Hermes core files.

Archive preflight: original CRLF line endings are preserved for source/hash fidelity.
Plain staged `git diff --check` flags those CR bytes; the CRLF-aware check
(`git -c core.whitespace=blank-at-eol,blank-at-eof,space-before-tab,cr-at-eol diff --cached --check`) passed.
