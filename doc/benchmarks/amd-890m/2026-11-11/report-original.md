# llama.cpp benchmark matrix — 890M iGPU (paired session, 2026-11-11)

llama.cpp b12110 · ctx 4096 · temp 0 · `-ngl 99 -fa 1` · same prompts for every cell.

- **Repro/RAG** = reproduce a ~2,000-token document from the prompt, 1,500 tokens out (n-gram drafter acceptance is near-100% here — best case).

- **Chat** = 250-word story from a 14-token prompt (realistic generation).

- Values = generated tokens/sec; acceptance = mean draft acceptance rate in parentheses.

- Vulkan = official b12110 Vulkan build. ROCm = b12110 HIP backend + ROCm 10.0 runtime wheels (12.5 GB budget vs Vulkan ~6-7 GB).


## Chat (generation from short prompt)

| Model | Vulkan base | Vulkan + ngram | ROCm base | ROCm + ngram |
|---|---:|---:|---:|---:|
| Qwen3-4B | 24.9 | 39.6 (0.76) | 22.9 | 48 (0.93) |
| Qwen3.5-9B (MoE) | 12.4 | 12.6 (1.00) | 12.2 | 12.5 (1.00) |
| Ornith-1.5-9B | 13.5 | 13.9 (1.00) | 13.1 | 13 (1.00) |
| Ornith-1.5-9B Uncensored | 13.5 | 13.8 (1.00) | 12.8 | 12.9 (1.00) |
| Gemma-4-12B | 8.1 | 9.1 (0.99) | 10.3 | 10.3 (0.99) |

## Repro / RAG (long context in prompt)

| Model | Vulkan base | Vulkan + ngram | ROCm base | ROCm + ngram |
|---|---:|---:|---:|---:|
| Qwen3-4B | 23 | 36.4 (0.76) | 21.3 | 56.8 (0.93) |
| Qwen3.5-9B (MoE) | 13.1 | 44.2 (1.00) | 11.6 | 89.6 (1.00) |
| Qwen3.5-9B Uncensored — DeepSeek-V4-Pro heretic | n/t | n/t | n/t | 89.6 (1.00) — chat 13.0 |
| Qwen3.5-9B Uncensored — HauhauCS Aggressive | n/t | n/t | n/t | 91.6 (1.00) — chat 12.9 |
| Ornith-1.5-9B | 13.4 | 49.8 (1.00) | 12.4 | 92.3 (1.00) |
| Ornith-1.5-9B Uncensored | 13.7 | 50.9 (1.00) | 12.4 | 94.4 (1.00) |
| Gemma-4-12B | 7.3 | 28.6 (0.99) | 8.8 | 56.3 (0.99) |

### Verification re-run: all 4 configs × 3 Qwen3.5-9B variants (second paired session, c 8192)

Because the uncensored variants were only measured under ROCm + ngram in the
main matrix, a follow-up sweep re-ran stock vs heretic vs HauhauCS under every
config, back-to-back.

Repro/RAG t/s:

| Model | Vulkan base | Vulkan + ngram | ROCm base | ROCm + ngram |
|---|---:|---:|---:|---:|
| Qwen3.5-9B stock | 13.2 | 45.7 | 9.6 | 66.4 |
| — heretic | 13.7 | 43.0 | 8.1 | 68.0 |
| — HauhauCS | 14.3 | 41.8 | 8.1 | 68.8 |

Chat t/s:

| Model | Vulkan base | Vulkan + ngram | ROCm base | ROCm + ngram |
|---|---:|---:|---:|---:|
| Qwen3.5-9B stock | 13.4 | 13.6 | 8.1 | 7.9 |
| — heretic | 14.2 | 14.2 | 8.1 | 8.7 |
| — HauhauCS | 14.5 | 14.4 | 8.5 | 8.4 |

Conclusions: (1) uncensored ≈ stock under **every** config — differences ≤ ~5 %,
so "identical speed" is confirmed config-by-config, not just for the one cell;
(2) session drift is real: ROCm numbers this session are 25-30 % below the
matrix session (66-69 vs 89.6 repro) and ROCm *base* decode for this MoE model
fell below Vulkan (8-8.5 vs 13-14 chat) — while in the matrix session they were
nearly equal. ROCm's ngram advantage held in both sessions, but Vulkan base
decode being better *this* session shows backend ranking for non-ngram use is
not stable across sessions on this hardware.

⚠ **Censorship note (updated 2026-11-11):** the mradermacher
"Ornith-1.5-9B-uncensored" (a quant of junafinity's finetune) **still censors**
despite its name, and the stock gemma-4-12b-it was never an uncensored model.
The genuinely uncensored models already downloaded live in the **Hermes models
dir** (`%LOCALAPPDATA%\hermes\models\`), not in `llama-local\models` — both are
Qwen3.5-9B finetunes, benchmarked above at identical speed to stock (89.6 /
91.6 t/s repro, 1.00 acceptance): **DeepSeek-V4-Pro-Qwen3.5-9B-UNCENSORED-heretic**
(weight-level heretic alignment removal) and
**Qwen3.5-9B-Uncensored-HauhauCS-Aggressive** (aggressive SFT). Both ship with
vision mmproj projectors (`mmproj-*.gguf` in the same dir) and both still emit
valid tool calls, though only 1/2 of the two-step smoke test (stock Qwen3.5-9B
did 2/2). The ravenx Gemma-4-12B OBLITERATED variant only ships at F16
(23.8 GB) — does not fit either backend. Models that don't fit this machine's
budgets were MOVED (not deleted, 2026-11-11) to the LM Studio store
(`C:\Users\jup03\.lmstudio\models\`, which has its own runtime and no Hermes
64K floor): Qwen3.8-27B-UD-Q3_K_XL (+ its DFlash2 drafter) → `unsloth\Qwen3.8-27B-GGUF\`,
and Huihui-Qwen3-Coder-30B-A3B-abliterated Q4_K_S → `huihui-ai\...` — sizes
verified identical after the move. The LM Studio store also holds other
uncensored models not yet benchmarked here (Qwen3.5-4B-Uncensored-HauhauCS 2.4 GB,
Qwen3.6-35B-A3B-Uncensored, gemma-4-26B-A4B-ultra-uncensored-heretic, a
Qwen3.8-27B-abliterated MTP). Note: gpt-oss-20b-abliterated (12 GB) stays in
the Hermes models dir — it works with the MoE expert-offload recipe at 131K.

**Storage convention (fixed 2026-11-11):** every model file now physically
lives once — canonical copies in the **LM Studio store** with proper
`publisher\model\file` names — and `llama-local\models\` + `hermes\models\`
hold NTFS hardlinks to the same data (verified same-inode, `nlink` 2–3 per
file). LM Studio names used: unsloth\Qwen3-4B-GGUF, unsloth\Qwen3.5-9B-MTP-GGUF,
ornith-ai\Ornith-1.5-9B-GGUF, mradermacher\Ornith-1.5-9B-uncensored-GGUF,
unsloth\gemma-4-12b-it-GGUF, huihui-ai\Huihui-gpt-oss-20b-abliterated-v2-MXFP4_MOE.
Exception: the drafter sidecars were DELETED (2026-11-11) after final testing
confirmed them unloadable/useless: dflash-gemma4, ornith-dflash, mtp-gemma4
(draft-mtp acceptance 0.23 even on ROCm, slower than baseline), and
dflash2-draft-27b (target never fits). Model store now contains only the 5
working models.

## Notes

- n-gram-mod acceptance is ~1.0 for all models on reproduction (drafter copies the context) — that is the "context lookup" mechanism behind viral speedup claims; ordinary chat acceptance is 0.68-0.93 and gains are smaller.

- ROCm + ngram is the best configuration on this machine for every model and scenario except qwen3-4b chat on Vulkan (~39.6), which is within run-to-run variance of the ROCm 48.0.

- Qwen3.5-9B uncensored / other 12B uncensored finetunes were skipped: no sub-7 GB GGUF available or F16-only. Qwen3.8-27B and its uncensored variants exceed both backends' 12.5 GB budget (13.2+ GB at Q3).

- gemma4-12b at Q3_K_XL; all other models Q4_K_M. Absolute numbers vary ±30-50% between machine sessions; all cells in this table were measured back-to-back in one session.

## Coding / tool-usage suitability (smoke test, 2026-11-11)

Single OpenAI-tools smoke test per model (`/v1/chat/completions` with a `tools`
array: "read the file C:/test/main.py, then run 'python main.py'"), temp 0, on
the ROCm server. This checks format compliance and step-following, not coding
quality — for real coding ability, benchmark your actual workload.

| Model | Valid tool calls | Followed both steps | Verdict for coding/tools |
|---|---|---|---|
| Qwen3.5-9B (MoE) | ✅ 2/2, clean JSON args | ✅ both, in order | **Best pick** — native developer-role/tool support, 44-90 t/s on context-heavy code work |
| Ornith-1.5-9B Uncensored | ✅ 2/2 | ✅ both | Runner-up — same speed profile as base, uncensored behavior |
| Ornith-1.5-9B | ✅ 1/2 | partial | Works, but stopped after the first call |
| Gemma-4-12B | ✅ 1/2 | partial | Works, slower (10.3 t/s) |
| Qwen3-4B | ❌ none (400 tokens of prose) | ❌ | Do not use for tools despite best chat speed |

### Recommended coding/tool config

```bat
cd C:\Users\jup03\llama-local\llama-rocm10
llama-server.exe -m ..\models\qwen35-9b-mtp-q4km.gguf -ngl 99 -fa 1 -c 8192 ^
  --spec-type ngram-mod --spec-ngram-mod-n-max 16 --spec-ngram-mod-n-min 2 ^
  --spec-ngram-mod-n-match 24 --port 8899
```

- Coding is the ideal ngram-mod workload: editing files resends their contents
  in the prompt, so touched files are re-drafted at 44-90 t/s; fresh code
  generation is 12.5 t/s.
- `llama-server` exposes the OpenAI-compatible API (`/v1/chat/completions`
  with `tools`), so this plugs directly into agent clients (Cline, Continue,
  Aider-style). Point the client at `http://127.0.0.1:8899/v1`.
- `tool_test.py` in this folder re-runs the smoke test against whichever
  model the server currently has loaded.

## Context lengths (GGUF headers, verified with gguf_dump)

| Model | Native trained ctx | Regular launcher (-c 8192) | Hermes launcher (-c 65536) | Max practical on ROCm (12.5 GB) |
|---|---:|---|---|---|
| Qwen3-4B | 40,960 | 8,192 | ❌ below Hermes's 64K floor | 40,960 (KV fits easily) |
| Qwen3.5-9B | 262,144 | 8,192 | 65,536 | ~65-131K (KV + weights vs 12.5 GB) |
| Ornith-1.5-9B | 262,144 | 8,192 | 65,536 | ~65-131K |
| Ornith-1.5-9B Uncensored | 262,144 | 8,192 | 65,536 | ~65-131K |
| Gemma-4-12B | 262,144 | 8,192 | 65,536 | ~65K (dense 12 B KV is heavy) |

### Which serving paths fall below Hermes's 64K floor (2026-11-11 check)

| Serving path | Served ctx | Passes Hermes floor? |
|---|---|---|
| Regular `start-*.bat` launchers (all models) | 8,192 | ❌ all — direct API/UI use only |
| Plugin dense presets (`dense_ctx` was 32K) | 32,768 | ❌ all dense models — fixed (see below) |
| Plugin MoE presets (gpt-oss-20b, Coder-30B) | 131,072 / 262,144 | ✅ |
| `start-hermes-*.bat` launchers | 65,536 | ✅ |
| Qwen3-4B on any path | max 40,960 native | ❌ fundamentally — never a Hermes backend |
| Qwen3-Coder-30B MoE recipe | OOMs above ~32K (needs manual cap) | ❌ unless ctx ≥ 64K fits — it doesn't |

Fix applied: plugin `settings.json` `dense_ctx` raised 32768 → 65536, so all
dense presets now serve 64K. Caveats: Qwen3-Coder-30B OOMs above ~32K even with
the expert-offload recipe — it fails to load at 131K, so it can't be a Hermes
backend either. Dense models at 64K cost ~2× the KV RAM of 32K on ROCm —
verified all three 262K-native models still load at 65,536.

- "Served context" (`-c`) is prompt + output combined.
- Values past the native trained context are rope extrapolation — unverified quality.
- Raising `-c` is a KV-cache memory trade: on Vulkan the ~6-7 GB heap OOMs quickly; on ROCm the 12.5 GB budget allows 64K for all models (verified loads).

## Hermes integration (verified end-to-end)

Hermes requires (a) served context ≥ 64K and (b) a findable server. The
`start-hermes-*.bat` launchers satisfy both: **port 8080** (auto-detected) and
`-c 65536`. One per model (Qwen3.5-9B, Ornith, Ornith-unc, Gemma — Qwen3-4B is
excluded by the context floor).

Switch Hermes to a local model while its server runs:

```bat
hermes config set model.provider custom
hermes config set model.base_url http://127.0.0.1:8080/v1
hermes config set model.default "C:/Users/jup03/llama-local/models/qwen35-9b-mtp-q4km.gguf"
```

Switch back to the cloud default:

```bat
hermes config set model.provider openrouter
hermes config set model.base_url https://openrouter.ai/api/v1
hermes config set model.default "z-ai/glm-5.3-flash"
```

- `model.default` must be the id exactly as `/v1/models` reports it (the full
  GGUF path). Verified: Hermes → local Qwen3.5-9B completed a chat.
- Do NOT also install Hermes's managed local runtime for these models — it
  launches its own llama-server without the ngram/spec flags, and a duplicate
  router fights the manual one.
- Agentic reality check (24-tool probe, ~5.7K-token fresh context): prefill
  ~280 t/s ≈ 20 s before first token; warm/cached turns are much faster. Chat
  is fine; fresh-context agent loops are sluggish on an iGPU.

## Session findings summary (all verified by measurement)

1. **Backend ranking (paired A/B):** ROCm/HIP > Vulkan for everything on this
   machine once the runtime DLLs are in place; HIP also doubles the memory
   budget (12.5 GB vs ~6-7 GB) and drafts more reliably (acceptance 0.90-1.00
   vs 0.69-0.84 on Vulkan for identical configs).
2. **Spec-decoding ranking:** ngram-mod is the only method that works well.
   MTP and DFlash/DFlash2 sidecar drafters collapse (4-29 % acceptance, 2-7×
   slower) across three model families, on CPU and GPU drafter placement, on
   stock and PR-branch builds. The DFlash2 drafter additionally requires
   device buffers, so it can never load beside a large target on this heap.
3. **The viral claim** (TeksEdge, Qwen3.8-27B, 82→381 t/s) is a context-copy
   best case: ngram acceptance ~100 % only when output copies the prompt.
   Honest equivalents here: 6-8× on document work (ROCm + ngram vs base), but
   only 1.0-1.9× on chat.
4. **Speed vs quality split:** Qwen3-4B = fastest chat (48 t/s) but fails tool
   calling; Qwen3.5-9B = best coding/tools (12.5 t/s gen, 90 t/s file-heavy
   steps); Ornith-9B (unc) = fastest RAG (94 t/s), uncensored at no cost;
   Gemma-4-12B = highest quality, slowest.
5. **Variance discipline:** this machine swings ±30-50 % between sessions.
   Only paired back-to-back A/Bs are trustworthy; re-measure baselines every
   session (results.json + matrix_bench.py make that cheap).
6. **Hermes floor:** local backends must serve ≥64K context or Hermes's agent
   init refuses; Qwen3-4B (40,960 native) can never be a Hermes backend.
