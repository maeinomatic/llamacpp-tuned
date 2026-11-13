# AMD Radeon 890M Windows machine — compatibility baseline

**Purpose:** protect this computer when changes are developed or reviewed on the RTX 3070 computer. These are machine-specific facts and required behavior, not defaults to copy onto other machines.

**Recorded:** 2026-11-13. Hardware/settings were read locally. The successful inference records linked below were captured during the earlier activation tests, not re-created by this documentation update.

## Machine identity and runtime

| Item | This computer |
|---|---|
| CPU | AMD Ryzen Z2 Extreme |
| Physical GPU | AMD Radeon(TM) 890M Graphics, integrated/shared-memory |
| RAM | Nominal 32 GB; Windows reports 33597804544 physical bytes |
| OS | Microsoft Windows 11 Home, version `10.0.26300` |
| Inference backend | Existing portable ROCm/HIP build; not the RTX/CUDA engine |
| Engine version read-back | `0.9.0-dev`, build `12110`, commit `cd959bae9`; Clang 20.1.8, Windows x86_64 |
| Engine path | `C:/Users/jup03/llama-local/llama-rocm10/llama-server.exe` |
| Hermes home | `C:/Users/jup03/AppData/Local/hermes` |
| Plugin checkout | `<Hermes home>/plugins/llamacpp-tuned` |
| Models scanned by plugin | `<Hermes home>/models/*.gguf` |
| Generated runtime files | `<Hermes home>/runtimes/llamacpp-tuned/` |

The Parsec Virtual Display Adapter also appears in Windows GPU enumeration; it is not the inference GPU. Shared system RAM is not all usable GPU memory. Historical ROCm/Vulkan memory budgets are benchmark-session observations, not a promise of current free memory or model fit.

## Machine settings to preserve

The actual file is **ignored by Git**: `dashboard/settings.json`. This is a documented snapshot, not a tracked replacement file to deploy automatically:

```json
{
  "engine_path": "C:/Users/jup03/llama-local/llama-rocm10/llama-server.exe",
  "port": 8080,
  "idle_unload_s": 900,
  "dense_ctx": 65536,
  "moe_ctx_cap": 131072,
  "local_guard_fix": true,
  "dense_ngram": true
}
```

- Keep `engine_path` pointing at the existing assembled ROCm runtime. Do not replace it with a CUDA build or assume that a Vulkan fallback has the same memory capacity/performance.
- `backend` is intentionally absent in this snapshot. The explicit `engine_path` wins for engine resolution; it does not mean the model is served by CPU. Do not add `backend: cuda` to this machine merely because CUDA is used on the other computer.
- The configured dense window is 65536; do not regress it to the plugin's default 32768. The current Hermes integration requires a sufficiently large served context.
- The MoE cap is 131072 here, not a request to copy a 256K CUDA configuration onto shared-memory hardware.
- `dense_ngram: true` is intentional. Keep the local-model WG fix setting intact too; its implementation is outside the proxy repairs.
- `poll_s` is omitted, so the current code default applies (60 seconds). The user can change idle behavior via the UNLOAD chip; this snapshot is not an instruction to overwrite later user choices.

## Required generated model tunes

| Profile | Required behavior on this machine |
|---|---|
| Dense models in the validated working set | Context 65536; q8_0 K/V; `ngram-mod`; n-max 16, n-min 2, n-match 24 |
| Local staged gpt-oss MoE | Context 131072; q4_0 K/V; expert-weight CPU override; `load-mode none`; `ngram-mod`; n-max 10, n-min 2 |
| CUDA expert-cache knobs | Do not inject `moe-cache-mib` / `moe-cache-cpu-share` into this AMD path |
| Common requested flags | Flash attention requested on, ubatch-size 512; actual backend/kernel support must be checked in engine logs |

A requested `flash-attn=on` is not proof that every kernel uses Flash Attention: this build/device may log unsupported row operations and disable that part. Do not treat that alone as a reason to remove the working ROCm configuration.

Validated staged IDs during the repair:

- `qwen35-9b-mtp-q4km` — preferred default smoke-test target.
- `Qwen3.5-9B-Uncensored-HauhauCS-Aggressive-Q4_K_M`.
- `DeepSeek-V4-Pro-Qwen3.5-9B-UNCENSORED-heretic-Q4_K_M`.
- `Huihui-gpt-oss-20b-abliterated-v2-MXFP4_MOE`.
- `gemma4-12b-ud-q3xl`.
- `ornith-15-9b-q4km` and `ornith-15-9b-unc-q4km` — historical coverage, not preferred new test targets.

This is a validation-time inventory, not permission to add/delete model files or a guarantee that future model-directory changes match it. Preserve model-store links/data; do not copy weights into the repository.

## Serving/lifecycle contract

- Public inference proxy: `http://127.0.0.1:8080` (normal API base adds `/v1`).
- Internal llama.cpp router: `http://127.0.0.1:8081`.
- The router remains `--models-max 1`; proxy coordination serializes protected chat/load/unload work. Do not bypass it by pointing normal clients at 8081.
- Preserve loopback-only binding unless remote exposure is explicitly requested.
- A legacy direct-serving router can survive a gateway restart and still hold 8080. Confirm identity and idle state before stopping only that stale process; never blanket-kill every server or change tunes to fix a port conflict.
- A gateway restart must be performed from outside the task it hosts. No detached/scheduled workaround to evade the self-restart guard.

## What another computer's changes must not break

Before calling a shared change safe, review [the cross-machine checklist](cross-machine-checklist.md) and verify this baseline remains supported. In particular:

1. No unconditional CUDA-only flags, nvidia-smi requirement, NVIDIA memory assumptions or expert-cache defaults on the ROCm path.
2. Custom-engine resolution continues to win over downloaded/managed engines. Feature-gate by actual flag support; do not reject this known-working build solely because it is older than the CUDA machine's build.
3. The ignored settings continue to override context/default values, and both dense and MoE n-gram configurations remain intact.
4. Generated presets reflect actual GGUF headers/settings and the machine's budget; do not hardcode the other computer's IDs, paths, cache sizes or context ceilings.
5. No model deletion, runtime/DLL replacement, port ownership takeover or provider/global-base-URL change as a side effect of an update.

## Validation and limits

- [Successful isolated model sweep](../tests/evidence/2026-11-13-isolated-model-smoke.json).
- [Installed activation evidence](../tests/evidence/2026-11-13-live-activation.json).
- [Live Qwen stream and tool-call JSON verification](../tests/evidence/2026-11-13-active-qwen.json).
- [Regression test records](../tests/README.md).

These establish the recorded smoke-test behavior. They do not establish long-context output quality, sustained-load stability, unchanged throughput after future changes, or actual CUDA execution on the RTX 3070. Live free RAM/commit and device allocations must be checked again when model capacity is in question.
