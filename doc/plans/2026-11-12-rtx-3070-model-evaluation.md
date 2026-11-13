# Model Evaluation Plan — A3B-class uncensored MoE candidates

> **Source machine: RTX 3070 desktop — Intel i7-13700K, 64 GB DDR5-4800, NVIDIA RTX 3070 8 GB, Windows 10, CUDA.**
> Archive/review provenance only: external research claims are not measurements from this machine. Not Legion Go 2 results.

> **Machine: DESKTOP — i7-13700K (16C/24T), 64GB DDR5-4800, RTX 3070 8GB (CUDA), Windows 10, llama.cpp b12255**

Date: 2026-11-11 · Machine: i7-13700K / 64GB RAM / RTX 3070 8GB · Current prod model: Huihui-Qwen3.5-35B-A3B-abliterated.i1-Q4_K_M

## Goal
Benchmark four uncensored A3B-class MoE GGUFs on both available llama.cpp builds, using a big-context config equivalent to the current production setup (262144 ctx, q4_0 KV, MoE experts on CPU), and rank them against the current 35B baseline on speed (prefill + decode), memory fit, and usability.

## 1. Models to download → `F:/AI/llama.cpp/models/`

| # | Model | Repo / file | Size | Notes |
|---|-------|-------------|------|-------|
| 1 | Kimi-Linear-48B-A3B-Instruct abliterated | `mradermacher/Kimi-Linear-48B-A3B-Instruct-abliterated-bf16-i1-GGUF` → `...i1-Q4_K_M.gguf` | 27.7 GiB | Hybrid linear attention, tiny KV |
| 2 | Qwen3-Next-80B-A3B-Instruct abliterated | `mradermacher/Huihui-Qwen3-Next-80B-A3B-Instruct-abliterated-i1-GGUF` → `...i1-IQ4_XS.gguf` | 42.7 GiB | Biggest A3B class; Expect RAM ~44GB |
| 3 | Qwen3.8-45B-A3B (experimental) | `webmp3/Sakura-Whittle-Qwen-3.8-45B-A3B-GGUF` → `...Q4_K_M.gguf` | 25.2 GiB | Community merge, quality unknown |
| 4 | Qwen3.6-35B-A3B abliterated + MTP | `huihui-ai/Huihui-Qwen3.6-35B-A3B-abliterated-MTP-GGUF` → `...Q4_K.gguf` | 20.2 GiB | Native MTP layers preserved |

Total ≈ 116 GiB. F: has 332 GiB free → OK. Downloads via `huggingface-cli download <repo> <file> --local-dir F:/AI/llama.cpp/models` (run in background, sequential, resume-safe).

Baseline for comparison (already on disk):
- `F:/AI/llama.cpp/models/Huihui-Qwen3.5-35B-A3B-abliterated.i1-Q4_K_M.gguf` (prod, 21.1 GiB)

## 2. Engines under test

| Engine | Binary | Version | Role |
|--------|--------|---------|------|
| A — Hermes stock | `C:/Users/Martin/AppData/Local/hermes/llamacpp-bench/llama-server.exe` (+ `llama-bench.exe` present) | 0.9.0-dev b12255 | Plain flags, stock defaults |
| B — Tuned nmod | `C:/Users/Martin/AppData/Local/hermes/runtimes/llamacpp-tuned/llama-server.exe` | same build, preset system | `--models-preset presets.ini`, `--override-tensor` expert-offload, tuned cache/ubatch |

Note: the old `tools/llamacpp-cuda-11671` build (0.7.0) is NOT used — too old for qwen3next/kimi-linear/hybrid archs and MTP.

## 3. Launch configuration per model (both engines)

Base template (mirrors the production 35B profile):
```
--host 127.0.0.1 --port <P> --flash-attn on --ubatch-size 512 \
--cache-type-k q4_0 --cache-type-v q4_0 --ctx-size 262144 \
--override-tensor "blk\.\d+\.ffn_.*_exps\.weight=CPU"
```
Per-model deltas:
- **#1 Kimi-48B**: same template; expert tensor regex `ffn_.*_exps` as above. Expect RAM ≈ 30GB → comfortable; can afford q8_0 KV if RAM allows at 256K (test at test time, keep q4_0 for apples-to-apples).
- **#2 Qwen3-Next-80B**: same template; RAM ≈ 44GB + KV (hybrid ⇒ small) + overhead — should fit 64GB; watch for paging. If tight, drop ctx to 131072 and record it.
- **#3 Qwen3.8-45B (whittle)**: same template (assume Qwen3 GQA arch ⇒ KV ≈ 6–7GB at 256K q4_0); if load fails or router names differ, adapt regex at test time.
- **#4 Huihui-Qwen3.6 MTP**: template + `--spec-type draft-mtp` (flag renamed from `mtp` on 2026-05-13; our b12255 build post-dates it) and additional ngram-mod variant:
  - Run 4 twice: once with MTP only, once with ngram-mod (same flags as prod) — this isolates MTP vs ngram contribution.
- Engine B via a new `[section]` appended to `presets.ini`, launched with `--models-preset` + alias; Engine A via explicit flags on a distinct port.

Port allocation: Engine A tests 18101–18104, Engine B tests 18201–18204. Production server (64611/8080) untouched except during step 6.

## 4. Benchmark protocol

Phase 1 — micro-benchmarks (`llama-bench.exe` from `llamacpp-bench/`, Engine A only as sanity):
- `-p 512 -n 128 -r 3` per model, tuned offload flags reproduced manually.
- Output: pp512 tok/s, tg128 tok/s per model.

Phase 2 — server benchmarks (both engines, all models; run sequentially, one at a time):
- Short prompt (≈300 tokens system+user), generate 512 tokens, 3 reps → decode tok/s from server logs/`/metrics`.
- Prefill test: paste ~4000-token context, measure prompt eval tok/s.
- Medium context: 32K-token prompt prefill + 256 gen.
- Long context: fill to ~128K tokens (generated filler + needle question), measure prefill, decode, and correctness of the needle answer. 262K only if RAM allows; otherwise record max working ctx.

Metrics captured per (model × engine × run): pp tok/s @512/4K/32K/128K, tg tok/s, spec-decode accepted rate (from server log where shown), peak RAM (tasklist/get-process WS), peak VRAM (nvidia-smi), load time.

Phase 3 — quality spot-check (Engine B, each model): 5 fixed prompts (1 coding bugfix, 1 JSON extraction, 1 reasoning, 1 refusal-boundary check to confirm uncensoring worked, 1 long-context needle). Scored qualitatively side-by-side against the 35B baseline.

## 5. Memory-safety rules
- One test instance at a time (plus production server idle). If total RAM demand > ~60GB, stop the production server for that test and note it.
- Windows may page silently — record commit charge and hard-fault deltas; a paged-in "successful" run is a failed config.
- After each model: kill test server, wait for RAM/VRAM release before next.

## 6. Order of operations
1. Write this plan (done).
2. Kick off 4 downloads in background (sequential, ~116 GiB).
3. While downloading: add Engine B presets to `presets.ini`; dry-run template on the baseline 35B to validate harness.
4. Bench baseline 35B on both engines (control numbers).
5. Bench #4 Huihui-3.6 MTP (smallest) → #3 Qwen3.8-45B → #1 Kimi-48B → #2 Qwen3-Next-80B (heaviest last).
6. Phases 1–3 per model; collect into `F:/AI/llama.cpp/bench-results-2026-11-11.csv` + notes MD.
7. Summarize comparison table + recommendation vs current 35B.

## 7. Risks / known unknowns
- **#3 Qwen3.8-45B** is a community merge: may have broken tokenizer/arch; treat as opportunistic, drop on load failure without debugging more than ~15 min.
- **Whittle KV geometry** unverified — if KV exceeds estimates, reduce ctx and mark result "not comparable at 262K".
- **#2 Qwen3-Next-80B** at IQ4_XS is the closest to the 64GB ceiling: if Windows pages, fall back to ctx 131072 (still usable) rather than failing.
- Engine A and B are the same build — expected performance difference is small and comes from the tuned flags; if identical, report that honestly rather than manufacturing a spread.
- MTP + `--override-tensor` interaction on the draft layer: if the MTP layer's tensors must stay on CPU too, adjust regex; record final flags used.

## Success criteria
- All 4 models (or documented exceptions) benched on both engines at ≥131K ctx.
- Baseline control numbers reproduce roughly the known ~20–25 tok/s envelope for the 35B, else investigate before comparing.
- Final deliverable: CSV + MD summary + recommendation.
