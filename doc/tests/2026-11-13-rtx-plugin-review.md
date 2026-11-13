# 2026-11-13 — Desktop review of Lenovo PR #1

> **Source machine: RTX 3070 desktop — Intel i7-13700K, 64 GB DDR5-4800, NVIDIA RTX 3070 8 GB, Windows 10, CUDA.**
> Archive/review provenance only: external research claims are not measurements from this machine. Not Legion Go 2 results.

## Scope

Reviewed plugin revision `b642ec2` (merge of `local/proxy-rocm-compat`) against
previous shared revision `7ff3582`. Local machine: i7-13700K, 64 GB DDR5-4800,
RTX 3070 8 GB, Windows 10. No plugin activation, engine replacement, Hermes-core
edit, provider switch, commit or push performed in this review.

## Results

| Check actually executed | Result | Meaning |
|---|---|---|
| AST comparison of `_generate_presets`, `_resolve_engine`, `_settings`, `_vram_bytes`, `_engine_asset`, `_nvidia` | All unchanged | Existing tune and engine-selection logic preserved |
| AST comparison of `_idle_sweeper` | Unchanged | Idle behavior not altered by this PR |
| Before/after preset fixtures: explicit CUDA, auto/NVIDIA, ROCm, Vulkan | Identical output in all four cases | MoE ngram-mod 10/2 and CUDA-only expert cache preserved; AMD remains free of CUDA-cache flags |
| `python -m unittest discover -s tests -v` | 29 tests passed | Includes streaming, cold-load heartbeats, residency coordination, errors, activation disable/re-enable and startup cleanup with fixtures |
| `node tests/test_desktop.cjs` | Passed | UNLOAD popup cleanup |
| `node --check desktop/plugin.js` | Passed | JavaScript syntax |
| `git diff --check` | Passed at test run | Working-tree whitespace check |

[Structured preset comparison evidence](evidence/2026-11-13-desktop-preset-review.json).
The fixture check was adapted from the PR's archived check script using this repo and
Hermes scratch paths; its GGUF/model/hardware inputs were fixtures, not GPU execution.

## Review conclusion

No tuning regression was found in the pulled plugin code. It preserves this desktop's
MoE `ngram-mod` and expert-cache method without needing a parallel implementation or
source changes. The changes address HTTP streaming lifetime, route ordering, complete
SSE events, shared one-model residency coordination, load/error handling and listener
startup/shutdown. Machine-local settings and engines remain separate.

The Legion baseline records Z2 Extreme / 32 GB / Radeon 890M with a custom ROCm/HIP
b12110 engine and dense_ngram enabled. Do not replace it with the desktop's CUDA
engine/profile or describe Vulkan as its active backend.

## Initial review limits and correction of earlier session claims

The later live-test section below supersedes the initial fixture-only scope for the 35B/45B.

This is source/fixture/test-suite validation, **not a live GPU run through the repaired
installed plugin**. An earlier standalone BAT smoke replied on CUDA but bypassed the
repaired proxy and omitted expert-cache flags. It does not close live activation,
streaming or performance acceptance. No new throughput numbers are claimed.

Seeing Hermes' already-existing built-in runtime while plugin activation is off is
not evidence that the Lenovo PR moved anything into Hermes core. The plugin retains
its opt-in activation mode; this review leaves its state untouched.

Historical one-token/EOS outputs are not sufficient to diagnose broken MTP, a corrupt
model or a router incompatibility. See the imported model-evaluation corrections.

## Subsequent live CUDA proxy smoke (approved by user)

The exact repaired repo module (byte-identical to the installed plugin at the start
of this test) was imported in an isolated process. Its real `_spawn`, generator,
engine resolution and public proxy ran on 18880/18881. Only test port/output paths
were overridden in memory; saved settings, chat selection and activation were not
changed. Engine resolution selected the plugin's CUDA b12255 copy.

| Real scenario | Outcome |
|---|---|
| 35B cold load | PROXY_OK, complete SSE; 7 keepalives, first bytes ~4.03 s, total ~30.12 s |
| 35B warm request | PROXY_OK, no keepalives; total ~0.19 s |
| Switch to 45B | Previous model unloaded, PROXY_OK, complete SSE; 9 keepalives, total ~39.06 s |
| Tune read-back | Both ngram-mod; 262144 configured ctx, q4_0 K/V, CPU share 0.95; 35B cache 2560 MiB, 45B cache 2048 MiB |
| Cleanup | Both isolated ports closed, settings hash unchanged, no errors; GPU usage back to 792 MiB |

[Raw smoke results](evidence/2026-11-13-desktop-live-proxy.json),
[selected cache log](evidence/2026-11-13-desktop-live-proxy-selected.log),
[exact harness snapshot](evidence/2026-11-13-desktop-live-proxy-original.py).
The harness loads models and starts/stops its test router: archived evidence,
not an automatically runnable setup script. It contains desktop-specific paths.

This closes the **isolated repaired-proxy CUDA functional smoke** gap for the 35B
and 45B. It is not a throughput benchmark, 256K occupied-context test, GUI activation
check or sustained stability test. The 80B was not loaded in this smoke because
free physical RAM (~39 GiB) was too close to its model footprint. Its generated
flags/source fixtures are covered, not its current live generation.
