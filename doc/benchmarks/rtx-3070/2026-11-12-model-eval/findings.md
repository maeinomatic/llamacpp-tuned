# Model Evaluation Findings — A3B-class uncensored MoE candidates

> **Source machine: RTX 3070 desktop — Intel i7-13700K, 64 GB DDR5-4800, NVIDIA RTX 3070 8 GB, Windows 10, CUDA.**
> Archive/review provenance only: external research claims are not measurements from this machine. Not Legion Go 2 results.

> **Machine: DESKTOP — i7-13700K (16C/24T), 64GB DDR5-4800, RTX 3070 8GB (CUDA), Windows 10, llama.cpp b12255**

Date: 2026-11-11 · Machine: i7-13700K / 64GB RAM / RTX 3070 8GB (Ampero-class DDR4/DDR5 dual channel)
Plan reference: `plan-model-eval-2026-11-11.md` · Raw data: `bench-results-2026-11-11.csv`
Runtime: llama.cpp 0.9.0-dev (build 12255, commit 940a30ee3), CUDA on RTX 3070

## Test setup

- **Engine A** ("stock"): `C:/Users/Martin/AppData/Local/hermes/llamacpp-bench/llama-server.exe` — plain flags, spec decoding off unless noted.
- **Engine B** ("tuned nmod"): `C:/Users/Martin/AppData/Local/hermes/runtimes/llamacpp-tuned/llama-server.exe` in router mode with `presets.ini`, ngram-mod speculative decoding (`--spec-type ngram-mod`, n 2–10).
- Common profile mirrored from production: flash-attn on, ubatch 512, MoE experts on CPU (`--override-tensor blk\.\d+\.ffn_.*_exps\.weight=CPU`), q4_0 KV cache where supported, 262144 ctx (128k where noted).
- Measurement: `/v1/completions` with 2521-token "unique" prompt and 960-token "repetitive" prompt, 256 generated tokens, 3 reps each, timings from server. Rep2/3 numbers quoted (rep1 is cold).
- Production server was stopped during all benchmark runs (as agreed).

## Headline results (output tok/s)

| Model (total) | Stock | Tuned + ngram-mod | RAM | ctx max | Verdict |
|---|---|---|---|---|---|
| **Qwen3.5-35B-A3B baseline** (current prod) | 39 | 39 (73–87 on repetitive) | 18–20GB | 262k | control |
| **Qwen3.8-45B-A3B (whittle)** ⭐ | 35 | **58–93** | 20GB | 262k | best speed, stable |
| **Qwen3-Next-80B-A3B (abliterated)** | 31.5 | **58–75** | 40GB | 262k | smartest, stable |
| Kimi-Linear-48B-A3B (abliterated) | 31.5 | 92 (when it works) | 22GB | **128k max** | ⚠️ unreliable |
| Qwen3.6-35B-A3B (Huihui MTP) | 38.6 | 59 (when it works) | 15–21GB | 262k | ⚠️ unreliable |

Prefill (pp) tok/s on the 2521-token prompt, tuned engine: baseline 675 · 80B 457–503 · 45B 594–659 · Kimi 485–722 (stock) · 3.6-MTP ~540.

## Verdict

1. **Speed winner: Qwen3.8-45B-A3B (whittle)** — up to 93 tok/s (2.4x baseline), lightest RAM of the four (20GB), stable on every prompt tested. Community-merge origin has not shown any behavioral problem, but a quality spot-check is still pending.
2. **Capability winner: Qwen3-Next-80B-A3B** — beats the baseline's decode speed despite 2.3x total params; fits in 40GB RAM with full 262k context. Recommended for the "better and bigger" goal.
3. Kimi and Qwen3.6-MTP are **not production-safe in build 12255** (see bugs).

## Launch commands used (as run in this evaluation)

### Engine B — tuned nmod router (production shape)
```
C:/Users/Martin/AppData/Local/hermes/runtimes/llamacpp-tuned/llama-server.exe ^
  --host 127.0.0.1 --port 8080 --metrics --log-colors off ^
  --models-preset C:/Users/Martin/AppData/Local/hermes/runtimes/llamacpp-tuned/presets.ini --models-max 1
```
- Model selection is via the `"model"` field in API requests (on-demand load, LRU evict with models-max 1). Preset sections carry all per-model flags (see presets.ini).

### Engine A — stock build, explicit flags (template used for every candidate)
```
C:/Users/Martin/AppData/Local/hermes/llamacpp-bench/llama-server.exe ^
  --host 127.0.0.1 --port 18101 --log-colors off --metrics ^
  --model <GGUF_PATH> ^
  --flash-attn on --ubatch-size 512 ^
  --cache-type-k q4_0 --cache-type-v q4_0 ^
  --ctx-size 262144 ^
  --override-tensor "blk\.\d+\.ffn_.*_exps\.weight=CPU" ^
  --load-mode none
```
Optional speculative decoding (Engine A spec runs):
```
  --spec-type ngram-mod --spec-ngram-mod-n-max 10 --spec-ngram-mod-n-min 2
```

### Per-model deltas from the template
| Model | model path | cache KV | ctx | notes |
|---|---|---|---|---|
| Qwen3.5-35B baseline (prod) | F:/AI/llama.cpp/models/Huihui-Qwen3.5-35B-A3B-abliterated.i1-Q4_K_M.gguf | q4_0 | 262144 | as production |
| Qwen3-Next-80B i1-IQ4_XS | F:/AI/llama.cpp/models/Huihui-Qwen3-Next-80B-A3B-Instruct-abliterated.i1-IQ4_XS.gguf | q4_0 | 262144 | same flags, works |
| Qwen3.8-45B whittle | F:/AI/llama.cpp/models/Sakura-Whittle-Qwen-3.8-45B-A3B-Q4_K_M.gguf | q4_0 | 262144 | same flags, works |
| Kimi-Linear-48B i1-Q4_K_M | F:/AI/llama.cpp/models/Kimi-Linear-48B-A3B-Instruct-abliterated-bf16.i1-Q4_K_M.gguf | **default f16 (do NOT set q4_0/q8_0)** | **131072** | KV-quant + 262k both crash context creation |
| Qwen3.6-35B MTP Q4_K | F:/AI/llama.cpp/models/Huihui-Qwen3.6-35B-A3B-abliterated-ggml-model-Q4_K.gguf | q4_0 | 262144 | draft-mtp variant adds `--spec-type draft-mtp` (unusable in b12255) |

- Do not run two routers on the same port; kill old llama-server processes first (`Get-Process llama-server | Stop-Process -Force`).

## Bugs and limitations found

### 1. One-token stall bug (blocks Kimi + Qwen3.6-MTP)
- Both models occasionally generate **exactly 1 token and stop** on some longer prompts. Deterministic per prompt content: e.g. a 1621-token prompt works, a 1801-token one fails (non-monotonic in length → content/routing dependent, not a simple size threshold).
- Reproduced on **both** engines, with **and without** speculative decoding → the trigger is in the model GGUF itself (both carry nextn/MTP-era weights or hybrid layers), not the launch config.
- ngram-mod and draft-mtp spec decoding do not cause it, but spec variants can hit it on their own prompts too (80B, notably, never stalls — it's per-model).
- **Not fixed within the time-box** (plan §7: ~15 min debug limit). Likely fixed by a newer llama.cpp build or a re-quant without nextn tensors. Kimi & 3.6-MTP presets exist but are marked experimental.

### 2. draft-mtp speculative decoding is unusable in b12255
- `--spec-type draft-mtp` builds the draft context fine but produces 1-token outputs on many prompts (same stall class as above). MTP speedups are theoretical here; ngram-mod remains the production draft.

### 3. Kimi-Linear specifics
- **Quantized KV cache crashes context creation** for kimi-linear arch: q4_0 *and* q8_0 KV at 131072 ctx → `common_fit_params ... failed to create llama_context`. With f16 KV it loads. So Kimi must run with default (f16) KV — the earlier plan goal of q4_0 KV parity doesn't apply to it. (Counterintuitive but reproducible; f16 KV works at 128k.)
- **Context ceiling ~128k on the 8GB GPU**: 262144 ctx + q4_0 KV also fails the VRAM fit (its full-attention layers' KV is heavier than advertised).
- **nmod router rejects kimi-linear**: `common_fit_params` fails at any ctx size even where the stock binary loads the same file fine. Router-mode preset for Kimi removed; Kimi only loads via explicit `llama-server` flags.
- When it works, it's fast: **92 tok/s with ngram-mod** on the repetitive prompt — the fastest single measurement of the whole set.

### 4. Spec-decode VRAM overhead
- Speculative decoding (ngram-mod) adds ~2.6GB VRAM vs spec-off (7.7GB vs 5.1GB peak on the 8GB card). With the 80B (IQ4_XS, spec on) VRAM peaked ~5.4GB — fine — but smaller cards should budget for it.

### 5. Tuned-vs-stock prefill gap
- The tuned config roughly **doubles prefill** (baseline 35B: 340 → 675 tok/s) via the tuned flag set; decode differences come almost entirely from speculative decoding. ngram-mod acceptance is strongly content-dependent (repetitive/structured outputs benefit most), consistent with the pre-benchmark discussion.

## Infrastructure notes
- HF downloads: anonymous mode throttles; setting `HF_TOKEN` (user registry → read inside the child process) restored full speed (~120MB/s, 116GB across 4 models in ~25 min).
- The nmod router (`--models-preset`) selects models on demand via the `"model"` field in API requests; it evicts LRU when `--models-max 1`. It reads `presets.ini` **only at startup** — edits require a router restart.
- Two router processes binding the same port silently splits traffic (first binder wins per connection) — ensure old instances are dead before restarting.

## Final states on disk
- All four GGUFs in `F:/AI/llama.cpp/models/` (Kimi 29.7GB Q4_K_M · 80B 42.6GB IQ4_XS · whittle-45B 27.1GB Q4_K_M · 3.6-MTP 21.7GB Q4_K).
- `presets.ini` production sections untouched; six `Bench-*` sections added (Kimi 128k f16-KV section is the working one; 262k/64k/32k sections are experimental remnants).
- Production tuned router restored on port 8080 with all presets registered; the prod 35B reloads on demand.

## Final state (updated after the switch, 2026-11-12)

**Qwen3-Next-80B-A3B (abliterated, IQ4_XS) is now the production model.**

- `presets.ini`: 80B section is FIRST (router default); 45B whittle is second; the 35B baseline stays third as fallback. Bench-* sections for Kimi/3.6-MTP retained as experimental.
- Symlinks in `C:/Users/Martin/AppData/Local/hermes/models/`:
  - `Huihui-Qwen3-Next-80B-A3B-abliterated.i1-IQ4_XS.gguf -> F:\AI\llama.cpp\models\Huihui-Qwen3-Next-80B-A3B-Instruct-abliterated.i1-IQ4_XS.gguf`
  - `Sakura-Whittle-Qwen-3.8-45B-A3B-Q4_K_M.gguf -> F:\AI\llama.cpp\models\...`
  - NOTE the 80B symlink target includes `-Instruct-` — the real file name has it; a first symlink without it pointed nowhere and caused a failed load.
- Verified end-to-end through the production router (port 8080): model loads via the symlinked path (~2–4 min cold start, 39.3GB RAM) and generates.
- Hermes desktop favorites still name the 35B (`llamacpp::...` in `ui-preferences.json`); user switches model in the chat UI picker, or edits the favorite entry.
- Per-model launch .bat files (tuned engine + ngram-mod): `F:/AI/llama.cpp/launch/{45b-whittle,80b-qwen3next,kimi-48b,35b-qwen36-mtp}-tuned.bat`, ports 18301–18304. Written once with LF endings — cmd needs CRLF for `^` continuations (fixed).
- Quality spot-checks (chat API, not raw completions — raw completions made the models behave badly): JSON extraction ✅ both, reasoning ✅ both, coding bugfix ✅ both, 20k-token needle ✅ both (`PINE-APPLE-77` found). Uncensor testing intentionally skipped per user.

## Outstanding (not yet done from the plan)
- User picks the 80B in the Hermes chat model picker (UI action).
- Revisit Kimi-48B and Qwen3.6-MTP with a newer llama.cpp build (1-token stall bug).
- Optional: prune broken Kimi 64k/32k preset sections (q4_0 KV can never load on kimi-linear).
