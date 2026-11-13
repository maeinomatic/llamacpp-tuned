# Imported A3B model-evaluation records (November 11–12, 2026)

> **Source machine: RTX 3070 desktop — Intel i7-13700K, 64 GB DDR5-4800, NVIDIA RTX 3070 8 GB, Windows 10, CUDA.**
> Archive/review provenance only: external research claims are not measurements from this machine. Not Legion Go 2 results.

**Machine:** i7-13700K, 64 GB DDR5-4800, RTX 3070 8 GB, Windows 10; CUDA b12255.

- [Historical findings](findings.md) — retained as written, **not endorsed conclusions**.
- [Historical CSV](bench-results.csv) — retained; ragged rows/comment headers require
  care when parsing. Not a complete raw per-request dataset.
- [Historical plan](../../../plans/2026-11-12-rtx-3070-model-evaluation.md).

## Corrections and limits

- The supposedly unique speed prompt repeated a five-sentence block 60 times.
  The other prompt was also repetitive. N-gram rates here are **not representative
  novel-generation throughput**; no unconditional 2.4x daily-use claim is supported.
- Some baseline comparisons used different prompts and overlapping server processes.
  They do not isolate an engine/profile speedup. 262144 configured context is not
  proof of quality or memory fit with 262144 tokens actually occupied.
- One-token raw-completion outputs may simply be EOS. No model-file bug, broken MTP,
  or Kimi router incompatibility was established by those probes. Kimi loaded at
  262144 with default KV in one probe; the claimed universal 128K ceiling is unsupported.
- The 45B answered the sheep question **24**, which was incorrect; the 80B answered
  **27**, correctly. Earlier statements that both passed reasoning are withdrawn.
- Successful needle prompts held roughly 24–25K tokens, not 128K or 256K.
- One short engine reply was not a live test of the repaired plugin/proxy. The earlier
  smoke used a standalone BAT without expert-cache flags. It cannot close that gap.
- Identical `--version` output does not establish identical binary bytes; source
  AST/fixture preservation is the compatibility evidence in the current review.

The historical files contain contradictory status/default/bug claims. Use this
correction page and current plugin source rather than treating them as runbooks.
No uncensoring tests are required by the user. No new performance run was made here.
