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

Tuned recipe for the Qwen3.5-35B-A3B MoE (see "How presets are generated" below):
- **All expert MLPs offloaded to system RAM** (`--override-tensor blk\.\d+\.ffn_.*_exps\.weight=CPU`),
  attention on GPU — makes the full 256K context fit in 8 GB VRAM (~5.5 GB used under load)
- **`--load-mode none`** — a real load phase with visible progress, instead of mmap's lazy
  page-fault crawling during generation
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

1. Clone it into the Hermes plugins folder (or copy the folder there):

   ```bash
   # Windows
   git clone https://github.com/maeinomatic/llamacpp-tuned "%LOCALAPPDATA%\hermes\plugins\llamacpp-tuned"
   # Linux
   git clone https://github.com/maeinomatic/llamacpp-tuned ~/.hermes/plugins/llamacpp-tuned
   ```

   Then enable it (`hermes plugins enable llamacpp-tuned` + Desktop → Plugins toggle).
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

## Requirements

- Hermes Agent (Desktop app; agent plugin + desktop chip)
- A llama.cpp build with router mode and `ngram-mod` speculative decoding
  (b12255 is what we test — either point `engine_path` at yours or let the
  plugin download one)
- Models staged in Hermes' Local Models pane as GGUFs

## How presets are generated

At every router start the backend scans Hermes' models directory, reads each
GGUF header and writes a per-model section into
`HERMES_HOME/runtimes/llamacpp-tuned/presets.ini`:

- **MoE** (experts detected in the header): expert MLPs to RAM, attention on
  GPU, q4_0 KV, `load-mode none`, ngram lookup drafting (n-max 10), context =
  min(native window, `moe_ctx_cap`, what q4 KV fits in VRAM)
- **Dense that fits VRAM**: fully on GPU, q8_0 KV, context capped to `dense_ctx`
- **Dense too big**: FFN layers to CPU (attention split), q8_0 KV, context
  sized from the remaining VRAM

## Configuration (`dashboard/settings.json`)

Create `settings.json` next to `plugin_api.py` to override defaults (gitignored,
per-machine — it is never committed). All keys are optional:

| Key | Default | Meaning |
|---|---|---|
| `engine_path` | *(empty)* | Full path to an existing `llama-server` binary (CUDA/Vulkan/ROCm/any build). **Wins over every other engine source** — this is how you use your own llama.cpp. |
| `backend` | *(auto)* | Which llama.cpp release asset `/install` downloads: `cuda` (auto when `nvidia-smi` is present), `vulkan`, or `cpu`. `rocm` maps to the Vulkan build (no official HIP assets exist). |
| `port` | `8080` | Port for the router. 8080 is Hermes' default external-server probe port. |
| `idle_unload_s` | `900` | Seconds without token activity before a loaded model is unloaded to free VRAM. |
| `poll_s` | `60` | Idle-check interval. |
| `moe_ctx_cap` | `262144` | Context ceiling for MoE models (further capped by what q4 KV fits in VRAM). |
| `dense_ctx` | `32768` | Context ceiling for dense models. |

Example — use an existing Vulkan/ROCm build on another machine:

```json
{
  "engine_path": "D:/tools/llama.cpp/llama-server.exe",
  "idle_unload_s": 600
}
```

Nothing else is machine-specific: every other path (models directory, runtimes,
logs, preset file) is derived from Hermes' own home directory at runtime.

## Repo layout

```
plugin.yaml            Hermes agent-plugin manifest
__init__.py            package marker + no-op register()
dashboard/             agent half (FastAPI backend mounted at /api/plugins/llamacpp-tuned)
  plugin_api.py        router supervisor: engine download, preset generation, spawn/stop,
                       pre-load, idle sweeper, SSE progress, watchdog
  tuned-presets.ini    example launch flags (the live INI is generated per machine into
                       HERMES_HOME/runtimes/llamacpp-tuned/presets.ini at router start)
  manifest.json        dashboard API manifest
  settings.json        per-machine overrides (gitignored; create as needed)
desktop/               Desktop half (status-bar chip, hot-reloaded)
  plugin.js
```

## Tested setup (development machine)

Reference for what this plugin was built and validated against:

- **Machine**: RTX 3070 8 GB (desktop GPU), i7-13700K, 64 GB dual-channel DDR5-4800, Windows 10
- **llama.cpp build**: **b12255** (`0.9.0-dev`, commit `940a30ee3`), Windows x64 **CUDA 12.4**
  — installed by the plugin into `%LOCALAPPDATA%\hermes\runtimes\llamacpp-tuned\llama-server.exe`
  (a matching full unpacked copy lives in `%LOCALAPPDATA%\hermes\llamacpp-bench\` from
  benchmarking). Engine resolution prefers Hermes' own PM engine once its pin reaches b12255.
- **Models tested** (Qwen3.5 family, abliterated i1 quants, staged via symlinks from `F:`):
  - `Qwen3.5-35B-A3B` Q4_K_M — MoE recipe (experts→RAM, q4 KV, ngram-mod 10, 256K ctx);
    ~44 tok/s chat baseline → 72–100 tok/s tuned, 99.8 tok/s on lookup-heavy work (2.4×)
  - `Qwen3.5-9B` Q4_K_M — dense, doesn't fit → FFN-CPU split, q8 KV, 32K ctx
  - `Qwen3.5-4B` Q4_K_M — dense, fully in VRAM, q8 KV, 32K ctx
  - `Qwen3-Next-80B-A3B` IQ4_XS — MoE recipe generated, but the auto-computed 256K window
    needs ~15 GiB VRAM (its full-attention layers cost ~98 KB/token) — **does not fit an
    8 GB card**; cap its `ctx-size` (~64–90K) by hand or with `moe_ctx_cap` until the
    generator's cross-check lands
- **Benchmarks**: llama-server `/completion`, greedy (`temperature: 0`), 256–512 tokens,
  timings from the response object; SPEED-Bench-style chat/code/math/doc-copy prompts

## Notes & hard-won lessons

- `os.kill(pid, 0)` on Windows **terminates** the target — never use it as a liveness probe.
- Windows job objects can silently fail when the gateway already sits inside another job;
  a detached `WaitForSingleObject` watchdog is the robust way to tie a child to Hermes' life.
- The router's live child args are visible in `GET /models[].status.args` — verify tuned
  flags landed there.
- Hermes' managed runtime has no supported custom-flags hook (its preset INI is regenerated
  at every boot), which is why this plugin exists.

Not published to the Hermes community catalog. MIT licensed.
