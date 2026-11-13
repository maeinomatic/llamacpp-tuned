# llama-local — local LLM benchmarking & serving setup (AMD 890M iGPU, 32 GB)

Everything here is self-contained and safe to keep. Nothing depends on Hermes's
scratch directory (which auto-prunes after 24 h).

## Contents

| Path | What it is |
|---|---|
| `llama\` | llama.cpp b12110 official **Vulkan** build (fallback backend) |
| `llama-rocm10\` | llama.cpp b12110 **ROCm/HIP** build + ROCm 10.0 runtime DLLs — **the fast one**, 12.5 GB budget |
| `llama-dflash2-pr\` | PR #31904 build (DFlash2 experiments — kept for reference) |
| `llama-vk-pr\` | master + FA-RDNA3 PR #31323 build (measured ≈ stock) |
| `amd-rocm\` | AMD's official ROCm 7.2.1 build (older arch support only) |
| `models\` | GGUF models — **hardlinks**, not copies: the canonical physical copies live in the LM Studio store (`C:\Users\jup03\.lmstudio\models\`, proper `publisher\model\file` layout). Every model file exists once on disk; `llama-local\models\`, `hermes\models\` and the LM Studio store are all names for the same data (NTFS hardlinks, `nlink` 2–3 per file). Deleting any one name never deletes the data until the last name goes. The 5 models here are the working set: qwen3-4b, qwen35-9b-mtp, ornith-15-9b (+unc), gemma4-12b — all drafter sidecars were deleted after testing confirmed them broken (dflash/mtp acceptance 0.08–0.29 on every backend). |
| `doc.txt` | benchmark document used by the repro/RAG scenario |
| `matrix_bench.py` | automated sweep: backend × model × spec → `results.json` |
| `stop-servers.bat` | force-stops all llama-server processes (the X-button doesn't always) |
| `bench.py`, `bench27.py` | single-server quick benchmarks |
| `tool_test.py` | tool-calling smoke test (needs a loaded server on :8899) |
| `BENCHMARKS.md` | results table incl. coding/tool suitability (2026-11-11 paired session) |
| `results.json`, `logs\` | raw results and server logs |
| `*-build dirs in AppData\Local\hermes\sandbox\` | source checkouts (lvk = master+FA patch, llama-pr = DFlash2 PR) — also deletable |

## Launch commands (double-clickable, in this folder)

| Launcher | Model (exact HF repo · file) | Use | Speed |
|---|---|---|---|
| `start-Qwen3-4B-Q4_K_M.bat` | unsloth/Qwen3-4B-GGUF · Qwen3-4B-Q4_K_M.gguf | Chat | 48.0 t/s |
| `start-Ornith-1.5-9B-Q4_K_M.bat` | ornith-ai/Ornith-1.5-9B-GGUF · Ornith-1.5-9B-Q4_K_M.gguf | RAG/documents | 92.3 t/s repro |
| `start-Ornith-1.5-9B-uncensored-Q4_K_M.bat` | mradermacher/Ornith-1.5-9B-uncensored-GGUF · Ornith-1.5-9B-uncensored.Q4_K_M.gguf | RAG/documents — ⚠ user-tested 2026-11-11: still censors despite the name | 94.4 t/s repro |
| `start-Qwen3.5-9B-MTP-Q4_K_M.bat` | unsloth/Qwen3.5-9B-MTP-GGUF · Qwen3.5-9B-Q4_K_M.gguf | Coding/tool usage | 12.5 t/s gen, 44-90 on file steps |
| `start-DeepSeek-V4-Pro-Qwen3.5-9B-UNCENSORED-heretic-Q4_K_M.bat` | DeepSeek-V4-Pro-Qwen3.5-9B-UNCENSORED-heretic-Q4_K_M.gguf (in hermes models dir) | Coding/tools, uncensored (heretic) | 13.0 t/s gen, 89.6 repro |
| `start-Qwen3.5-9B-Uncensored-HauhauCS-Aggressive-Q4_K_M.bat` | Qwen3.5-9B-Uncensored-HauhauCS-Aggressive-Q4_K_M.gguf (in hermes models dir) | Coding/tools, uncensored (aggressive SFT) | 12.9 t/s gen, 91.6 repro |
| `start-gemma-4-12B-UD-Q3_K_XL.bat` | unsloth/gemma-4-12b-it-GGUF · gemma-4-12b-it-UD-Q3_K_XL.gguf | Max quality | 10.3 t/s chat, 56.3 repro |

Each launcher serves the OpenAI-compatible API at `http://127.0.0.1:8899/v1`
and the built-in web UI at `http://127.0.0.1:8899`. Only run one at a time.

### Stopping a server

**Proper way:** press `Ctrl+C` inside the server window, wait for the
"Press any key" message, then close it. That fully stops the server.

**Why the web UI can stay alive:** closing the window with the X (or killing
the terminal) kills `cmd.exe` but Windows does not always kill the child
`llama-server.exe` — it survives and keeps serving on :8899. That is expected
Windows behaviour, not a stuck process.

**The fix:** double-click `stop-servers.bat` — it force-stops every
llama-server instantly. Or from any terminal:
`taskkill /IM llama-server.exe /F`. Only one server should be running at a
time anyway; `stop-servers.bat` is also the safe pre-step before launching a
different model.

## Using these models inside Hermes

Hermes needs (a) a served context of **at least 64K tokens** and (b) a server
it can find. The regular launchers above run at `-c 8192`, so use the dedicated
`start-hermes-*.bat` launchers instead: they listen on **port 8080**
(Hermes auto-detects user-run servers there) and serve **-c 65536**.

| Hermes launcher | Model | Native trained ctx |
|---|---|---|
| `start-hermes-Qwen3.5-9B-MTP-Q4_K_M.bat` | Qwen3.5-9B | 262,144 |
| `start-hermes-Ornith-1.5-9B-Q4_K_M.bat` | Ornith-1.5-9B | 262,144 |
| `start-hermes-Ornith-1.5-9B-uncensored-Q4_K_M.bat` | Ornith-1.5-9B Unc. | 262,144 |
| `start-hermes-gemma-4-12B-UD-Q3_K_XL.bat` | Gemma-4-12B | 262,144 |

Qwen3-4B is trained to only 40,960 — below Hermes's 64K floor — so it cannot
be used as a Hermes backend (it stays a great direct-API chat model).

### Switching Hermes to the local model (verified end-to-end)

With a `start-hermes-*.bat` server running:

```bat
hermes config set model.provider custom
hermes config set model.base_url http://127.0.0.1:8080/v1
hermes config set model.default "C:/Users/jup03/llama-local/models/qwen35-9b-mtp-q4km.gguf"
```

`model.default` must be the model id exactly as `/v1/models` reports it (the
full GGUF path). To switch back to the cloud default:

```bat
hermes config set model.provider openrouter
hermes config set model.base_url https://openrouter.ai/api/v1
hermes config set model.default "z-ai/glm-5.3-flash"
```

Measured with this setup: Hermes → local Qwen3.5-9B completed a chat
end-to-end ("LOCAL MODEL OK"). Honest agentic note: prefill for a fresh
~5.7K-token agent context (system prompt + 24 tool schemas) runs at ~280 t/s
≈ 20 s before the first token; warm/cached contexts are much faster. Chat is
fine; heavy agentic loops on a fresh context each time are sluggish.

### Context-length summary

| Launchers | Served context (-c) | Native trained ctx |
|---|---|---|
| regular `start-*.bat` | 8,192 (prompt + output combined) | 40,960 (Qwen3-4B) / 262,144 (others) |
| `start-hermes-*.bat` | 65,536 | same |
| absolute max on ROCm | ~12.5 GB budget decides | gemma-4-12b at 262K needs ~4-6 GB KV — test before raising |

## Best configurations (measured)

- **Chat:** ROCm + ngram-mod, Qwen3-4B — 48 t/s
- **RAG / document work:** ROCm + ngram-mod, Ornith-1.5-9B — 92-94 t/s (uncensored twin: 94.4)
- **Coding / tool usage:** ROCm + ngram-mod, Qwen3.5-9B — best tool-calling compliance (2/2 smoke test), 44-90 t/s on context-heavy code edits, 12.5 t/s fresh generation. Uncensored variants of the same family (heretic / HauhauCS-Aggressive, in the hermes models dir) run identically fast but emitted only 1/2 tool calls in the smoke test.

```bat
cd C:\Users\jup03\llama-local\llama-rocm10
llama-server.exe -m ..\models\qwen3-4b-q4km.gguf -ngl 99 -fa 1 -c 8192 ^
  --spec-type ngram-mod --spec-ngram-mod-n-max 16 --spec-ngram-mod-n-min 2 ^
  --spec-ngram-mod-n-match 24 --port 8899
```

Swap `-m` to `..\models\ornith-15-9b-q4km.gguf` (or `-unc`) for RAG work.
Vulkan fallback: same command with `..\llama\llama-server.exe`.

## Re-running the benchmark matrix in the future

```bat
cd C:\Users\jup03\llama-local
python matrix_bench.py
```

- Reads `doc.txt`, loops every backend × model × spec (edit `MODELS` /
  `BACKENDS` / `SPECS` at the top of the script), writes `results.json` and
  server logs under `logs\`.
- Resumable: completed (backend, model, spec) triples are skipped; delete
  `results.json` to re-run everything, or delete single entries to re-test.
- Add a new model: drop the GGUF into `models\` and add its line to `MODELS`.
- Memory limits: Vulkan fully offloads models up to ~6 GB; ROCm up to ~12 GB
  (minus KV cache headroom — use `-c 4096` or smaller for the big ones).
- The server must be started from its own directory (DLLs are resolved from
  the exe folder) — `matrix_bench.py` handles this via `cwd=`.

## llamacpp-tuned plugin (installed & configured)

- Location: `%LOCALAPPDATA%\hermes\plugins\llamacpp-tuned` (cloned from
  github.com/maeinomatic/llamacpp-tuned)
- `dashboard/settings.json` points `engine_path` at our ROCm build
  (`llama-local\llama-rocm10\llama-server.exe`), port 8080 (Hermes
  auto-detect), `dense_ctx` 65536, `moe_ctx_cap` 131072.
- **Fixed a plugin bug 2026-11-12:** `_generate_presets()` read the hardcoded
  `DEFAULTS["dense_ctx"/"moe_ctx_cap"]` instead of `_settings()`, so
  settings.json overrides of those two keys were ignored (presets always
  generated at 32K dense / 256K MoE). Patched to read `_settings()` — presets
  now regenerate with dense 65536 / MoE 131072. Commit this to the repo.
- All preset flags verified present in the b12110 ROCm binary; models staged
  via hardlinks into the Hermes models dir.
- The chip respawns the router on next model load after any settings change.
