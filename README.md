# llamacpp-tuned

A [Hermes Agent](https://github.com/NousResearch/hermes-agent) plugin (agent backend +
Desktop status-bar chip) that runs a **tuned llama.cpp router** on a small-VRAM GPU.

Built and benchmarked on an RTX 3070 8 GB / i7-13700K / 64 GB DDR5 with Qwen3.5 staged
GGUFs. It serves a llama.cpp router (b12255+) on port 8080, which the Hermes desktop app
auto-detects and uses instead of its managed runtime — no core patches, regular update
path preserved.

## What "tuned" means here

Measured on the RTX 3070 (see BENCHMARK notes below), versus llama.cpp defaults:

| Workload | Defaults | Tuned | Gain |
|---|---|---|---|
| Chat, 4K–32K ctx | ~40–43 tok/s | 66–72 tok/s | ~1.7× |
| Document/RAG (lookup-heavy), 128K | 38 tok/s | 73 tok/s | ~1.9× |
| Full 256K window | 22 tok/s | 60–82 tok/s | ~3.7× |

Tuned recipe for the Qwen3.5-35B-A3B MoE (see `dashboard/tuned-presets.ini`):
- **All expert MLPs offloaded to system RAM** (`--override-tensor blk\.\d+\.ffn_.*_exps\.weight=CPU`),
  attention on GPU — makes the full 256K context fit in 8 GB VRAM (~5.5 GB used under load)
- **`--no-mmap`** — a real load phase instead of lazy page-fault crawling during generation
- **q4_0 KV cache**, flash attention, ubatch 512
- **n-gram lookup speculative drafting** (`--spec-type ngram-mod`, n-max 10) — ~2.4× on
  answers that reuse prompt text (RAG, code edits, quoting); no help on novel chat text
- Smaller dense models (9B / 4B) get their own sane presets (q8 KV, 32K)

## Features

- **Status-bar chip** in the Desktop app: `LLM ○ off` / `LLM ⏳ 42%` (live load percent) /
  `LLM ● n` (loaded models). Click toggles ON/OFF; OFF hands back to Hermes' managed runtime.
- **Auto-preload**: selecting a staged local model in a chat fires the load immediately, so
  the chat request arrives warm (Hermes times out during multi-minute cold loads, and the
  router would otherwise discard the half-loaded model on cancel).
- **Idle unload**: after 15 min without token activity (per-model `/metrics`), models are
  unloaded to free VRAM; they auto-reload on the next request.
- **Auto-close**: a detached watchdog kills the router tree when the Hermes gateway dies.

## Install on another machine

The plugin is backend-agnostic: any llama.cpp build with router mode and
`ngram-mod` speculative decoding works (b11671+ has ngram-mod; router preset
flags need roughly b12000+; b12255 is what we test).

1. Copy this folder to `%LOCALAPPDATA%\hermes\plugins\llamacpp-tuned\`
   (Linux: `~/.hermes/plugins/llamacpp-tuned/`) and enable it
   (`hermes plugins enable llamacpp-tuned` + Desktop → Plugins toggle).
2. **Use your existing llama.cpp build** — write `settings.json` next to
   `plugin_api.py`:

   ```json
   { "engine_path": "D:/tools/llama.cpp/llama-server.exe" }
   ```

   The preset generator, preload, idle unload, progress feed and watchdog all
   work with whatever binary you point at — Vulkan, ROCm (or CUDA), any vendor.
3. Or let the plugin fetch an engine: click the chip ON without an engine and
   it will tell you to run `/install`; backend auto-detects from `nvidia-smi`
   (CUDA vs Vulkan), or force it with `"backend": "vulkan"` / `"cpu"` in
   `settings.json` (no official HIP builds exist in llama.cpp releases — AMD
   cards ride Vulkan, or point `engine_path` at your own ROCm build).
4. Models: any GGUFs staged in Hermes' Local Models pane get a tuned preset
   generated automatically (MoE vs dense detected from the GGUF header); edit
   the generated `presets.ini` behavior via `settings.json` caps
   (`moe_ctx_cap`, `dense_ctx`, `port`, `idle_unload_s`).

## Install (reference, original machine)

Requirements: Windows, NVIDIA GPU + CUDA-capable llama.cpp build at
`%LOCALAPPDATA%\hermes\llamacpp-bench\llama-server.exe` (any recent build with router mode,
`ngram-mod` spec decoding and `--models-sse`; b12255 used here), models staged in
`%LOCALAPPDATA%\hermes\models\` as GGUFs.

1. Copy/symlink this folder into `%LOCALAPPDATA%\hermes\plugins\llamacpp-tuned\`
   (`mklink /J` works well so the repo stays the single source of truth).
2. `hermes plugins enable llamacpp-tuned` **and** flip it on in Desktop → Plugins.
3. ⌘K → *Reload desktop plugins*; click the chip ON.

Adapt `dashboard/tuned-presets.ini` to your own models: one INI section per GGUF with any
llama.cpp flags in kebab-case (`ctx-size`, `cache-type-k`, `spec-type`, `override-tensor`, …).

## Repo layout

```
plugin.yaml            Hermes agent-plugin manifest
__init__.py            package marker + no-op register()
dashboard/             agent half (FastAPI backend mounted at /api/plugins/llamacpp-tuned)
  plugin_api.py        router supervisor: spawn/stop, pre-load, idle sweeper, SSE progress
  tuned-presets.ini    per-model llama.cpp launch flags
  manifest.json        dashboard API manifest
desktop/               Desktop half (status-bar chip, hot-reloaded)
  plugin.js
```

## Notes & hard-won lessons

- `os.kill(pid, 0)` on Windows **terminates** the target — never use it as a liveness probe.
- Windows job objects can silently fail when the gateway already sits inside another job;
  a detached `WaitForSingleObject` watchdog is the robust way to tie a child to Hermes' life.
- The router's live child args are visible in `GET /models[].status.args` — verify tuned
  flags landed there.
- Hermes' managed runtime has no supported custom-flags hook (its preset INI is regenerated
  at every boot), which is why this plugin exists.

Not published to the Hermes community catalog. MIT licensed.
