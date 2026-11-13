# RTX 3070 desktop — plugin backend baseline

> **Source machine: RTX 3070 desktop — Intel i7-13700K, 64 GB DDR5-4800, NVIDIA RTX 3070 8 GB, Windows 10, CUDA.**
> Archive/review provenance only: external research claims are not measurements from this machine. Not Legion Go 2 results.

Hardware: Intel i7-13700K, 64 GB DDR5-4800, NVIDIA RTX 3070 8 GB, Windows 10.
Historical tuned engine: llama.cpp b12255 (`940a30ee3`), CUDA.

The opt-in `llamacpp-tuned` plugin is separate from Hermes' pre-existing built-in
local runtime. Plugin activation serves a public proxy (configured port, normally
8080) and a llama.cpp router at port+1 (normally 8081). An inactive plugin and a
running built-in runtime do **not** establish a plugin regression. No Hermes core
changes were needed or made for this review. Do not infer authorship from file dates.

The plugin resolves a valid explicit `engine_path` first, then a sufficiently new
Hermes-managed engine, then its own engine. Preserve ignored `dashboard/settings.json`.
Generated `presets.ini` is output, not the durable place to edit tuning. INI ordering
or marking a model as a favorite is not evidence that a chat's selected model changed.

CUDA MoE profile retained by PR #1: `ngram-mod` (n-max 10, n-min 2), q4_0 K/V,
CPU expert override, ubatch 512, load-mode none. Expert cache: 35B-A3B/Coder-30B
2560 MiB; 80B-A3B 1536 MiB; others 2048 MiB; CPU share 0.95. Context is calculated
from actual model headers and settings, including recurrent-block accounting.
Dense n-grams remain opt-in via `dense_ngram`; AMD does not inherit CUDA cache knobs.
These constants are existing source selection rules, not universally optimal values.

See [review evidence](../../tests/2026-11-13-rtx-plugin-review.md) for what was tested.
Historical measurements and their limitations are indexed in [README](README.md).
