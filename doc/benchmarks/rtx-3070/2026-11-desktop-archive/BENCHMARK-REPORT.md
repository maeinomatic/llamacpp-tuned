# Qwen3.5-35B-A3B on RTX 3070 8 GB — Benchmark Report

> **Source machine: RTX 3070 desktop — Intel i7-13700K, 64 GB DDR5-4800, NVIDIA RTX 3070 8 GB, Windows 10, CUDA.**
> Archive/review provenance only: external research claims are not measurements from this machine. Not Legion Go 2 results.

**Date:** 2026-11-10 · **Machine:** i7-13700K, RTX 3070 8 GB, 64 GB dual-channel DDR5-4800
**Model:** Huihui-Qwen3.5-35B-A3B-abliterated i1-Q4_K_M (GGUF, F:/AI/llama.cpp/models/)
**Engine:** llama.cpp b12255 (CUDA 12.4 build, `C:\Users\Martin\AppData\Local\hermes\llamacpp-bench\`)
**Method:** `llama-server` + raw `/completion` (no chat template), greedy (`temperature: 0`),
256–512 generated tokens, timings from the response `timings` object. MoE expert offload via
`-ncmoe`; baselines varied ±10% between runs.

## Background: the claim under test

A viral post claimed Qwen3.8-27B went 82 → 381 tok/s on an RTX 3090 (4.6×) via
speculative decoding (MTP/DFlash2), context lookup and prefix caching. Verified findings:
the 381 number is real but only for document-reproduction workloads (copying text already
in the prompt); ordinary chat on that setup is ~133 tok/s; the engine was vLLM, not
llama.cpp; independent llama.cpp reproductions show ~1.8×, not 4.6×. The transferable
techniques are n-gram/context-lookup drafting and prefix caching.

## Head-to-head: llama.cpp defaults vs tuned config

Doc-copy workload (model reproduces a ~1,500-token document from the prompt).

| Context | Defaults (auto-fit, fp16 KV, no spec) | Tuned¹ | Speedup |
|---|---|---|---|
| 4K   | 42.8 tok/s | 71.8 tok/s | 1.7× |
| 32K  | 39.9 tok/s | 66.1 tok/s | 1.7× |
| 128K | 38.1 tok/s | 72.6 tok/s | 1.9× |
| 256K | 22.0 tok/s | 82.3 tok/s | **3.7×** |

¹ `-ncmoe 48 -fa on -ctk q4_0 -ctv q4_0 --ubatch-size 512 --spec-type ngram-mod
--spec-ngram-mod-n-max 10 --spec-ngram-mod-n-min 2`

Prompt processing: defaults ~160–235 tok/s, tuned ~175–205 (no meaningful difference).
Tuned decode is flat 66–82 tok/s at every context (±10 run-to-run variance).

Defaults do **fit** 256K (auto-fit picks its own offload split) but degrade to 22 tok/s.

## Findings by technique

### N-gram lookup drafting (the big win, zero VRAM cost)
- Drafts tokens by matching n-grams already in the prompt; the target verifies blocks.
- Doc-copy: baseline 37–47 → **99.8 tok/s at n-max 10** (~2.4×), acceptance 214/217.
- Chat (novel text): **no gain** (44.3 → 41.9 tok/s). Lookup only helps when the answer
  reuses prompt content — RAG answers, code edits, quoting/rewriting documents.
- **Draft-length sweep is critical** on an offloaded MoE: n-max 6 → 85, **10 → 99.8**,
  12 → 90, 16 → 3.5 tok/s (collapse; big verification batches break expert-streaming
  amortization). Always sweep; don't trust the default.

### Dense draft model — fails on this card
- `--spec-type draft-simple` with the Qwen3.5-4B drafter: **1.4 tok/s (0.03×)**. The 4B Q4
  (~2.4 GB) doesn't fit in the ~2 GB left beside the offloaded target, so it runs on CPU.
- Rule: never add a dense drafter without a VRAM budget check. Community MoE speedups
  (DFlash 2.7–3.3×) use ~1 GB purpose-built drafters, not available for this model.
- DFlash on Qwen dense targets is a measured loss elsewhere too (0.63×); DSpark is the
  best Qwen dense drafter (1.6–1.9×) where VRAM allows.

### Context length on 8 GB (the 8K "cap" was a default, not a limit)
| Context | gen tok/s (tuned long-ctx split) | Notes |
|---|---|---|
| 8K   | 44–100 | original split (`-ncmoe 32`, q8 KV) fastest here (~93 at 32K) |
| 64K  | ~80    | needs the long-context split; q8 KV silently spills to shared memory here |
| 96K–160K | 75–80 | q4 KV |
| 200K | ~71 | q4 KV |
| **256K (full window)** | **60–65** | 5.5/8 GB used under load — no spilling |

- **The spill trap:** forcing `-ngl 99 -ncmoe 32` + q8 KV at 64K+ logged
  `failed to fit params to free device memory` and decode collapsed to 14–29 tok/s
  (Windows shared-memory fallback). "It ran" ≠ "it fit" — always grep the log.
- Fix: `-ncmoe 48` (all expert MLPs on CPU) + q4_0 KV + `--ubatch-size 512` frees ~3 GB
  for KV. Cost: prompt processing tops out ~200 tok/s; chat decode slightly slower than
  the short-context split.
- q4_0 KV halved KV memory with no measurable acceptance loss vs q8_0.

## Recommended launch commands

Short-context, max decode speed (≤32K):
```
llama-server.exe -m F:/AI/llama.cpp/models/Huihui-Qwen3.5-35B-A3B-abliterated.i1-Q4_K_M.gguf ^
  -ncmoe 32 -c 32768 -fa on -ctk q8_0 -ctv q8_0 -t 8 -ngl 99 ^
  --spec-type ngram-mod --spec-ngram-mod-n-max 10 --spec-ngram-mod-n-min 2 --port 8899
```

Full 256K context:
```
llama-server.exe -m F:/AI/llama.cpp/models/Huihui-Qwen3.5-35B-A3B-abliterated.i1-Q4_K_M.gguf ^
  -ncmoe 48 -c 262144 -fa on -ctk q4_0 -ctv q4_0 -t 8 -ngl 99 --ubatch-size 512 ^
  --spec-type ngram-mod --spec-ngram-mod-n-max 10 --spec-ngram-mod-n-min 2 --port 8899
```

## Hermes integration (plugin `llamacpp-tuned`)

Hermes' managed llama.cpp runtime (PM-pinned engine b11671) has no supported hook for custom
launch flags: its per-model preset INI is regenerated at every boot by the physics planner
(which already applies: all-experts-to-CPU split, q8 KV, flash-attn, a 64K window — but no
lookup drafting, no q4 KV, no 256K window). The supported alternative is documented in
Hermes' local-models guide: *if a llama-server is already running, Hermes detects it and uses
it instead of starting its own* (default probe port 8080).

So the tuned serving path is a NEW Desktop plugin, `llamacpp-tuned`
(`%LOCALAPPDATA%\hermes\plugins\llamacpp-tuned\`, modeled structurally on local-fallback-ui,
no core patches):

- **Backend** (`dashboard/plugin_api.py`): spawns the tuned llama.cpp b12255 router in
  `--models-preset` router mode on port 8080 serving all three staged Qwen3.5 GGUFs with
  per-model tuned flags (`dashboard/tuned-presets.ini`: 35B at 256K ctx / q4 KV /
  all-experts-CPU / ngram-mod n-max 10; 9B and 4B fully-sensible q8 KV 32K presets).
- **Idle unload**: a sweeper thread polls `/metrics?model=...` per loaded model
  (`llamacpp:prompt_tokens_total` + `llamacpp:tokens_predicted_total`); after 15 min with no
  token activity it POSTs `/models/unload` (same endpoint Hermes' own supervisor uses).
  Autoload on the next request is native router behavior.
- **Auto-close**: the router is spawned inside a Windows Job Object with
  JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE (ctypes, stdlib) — when the gateway process dies,
  the server dies with it. Verified by killing the supervisor and observing the child exit.
- **UI** (`desktop/plugin.js`): status-bar chip — `LLM ● n` green when the tuned router is
  up (n = models loaded), `LLM ○ off` grey when off (managed runtime serves as usual).
  Click toggles ON/OFF via the plugin API.

Verified end-to-end: router lists all three models on /v1/models, accepts every tuned INI
key, warm generation matches the benchmarks above, idle unload frees VRAM, reload happens
on demand, and the server auto-closes with the gateway.

Caveats:
- First request after a cold unload re-loads 20 GB from F: — measured ~5.5 min with a cold
  Windows file cache (seconds when warm). The managed runtime has the same physics.
- Enable in two places: `hermes plugins enable llamacpp-tuned` (done) AND the in-app
  Plugins tab toggle; then ⌘K → Reload desktop plugins.

## Bottom line

- Realistic gains on this 8 GB card: **~1.7× short context, ~2.4× on lookup-heavy work,
  ~3.7× at 256K vs defaults** — worthwhile but far from the viral 4.6× headline, which
  needs a 24 GB card, vLLM, and a copy-the-document workload.
- Best quality-per-speed config on this machine remains the 35B-A3B MoE with expert
  offload; dense 8B/9B in VRAM is faster for pure chat but noticeably less capable.
