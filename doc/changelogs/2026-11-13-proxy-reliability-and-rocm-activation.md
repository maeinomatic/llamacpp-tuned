# Local changelog and RTX 3070 compatibility assessment

## Status and scope

- Previous installed revision: `fdfadc0f0325e7b7a2be8c5bf137e1013ceacd04`.
- Imported main revision: `7ff358270a4dbf359de4502c46ef20f94976b599` (14 incoming commits).
- Active installed branch: `local/proxy-rocm-compat`.
- Repair worktree branch: `fix/proxy-rocm-compat`.
- Backup branch: `backup/pre-proxy-fdfadc0`.
- The fixes described below are **uncommitted local changes** on top of `7ff3582`. No commit or push was made. The RTX 3070 computer and GitHub were not modified.
- This document separates changes imported from main from changes made during the local repair. The CUDA expert-cache feature was imported, not rewritten during the repair.

## 1. Features imported from main

### CUDA-only MoE expert cache

Retained the incoming preset generator's combination of:

```ini
spec-type = ngram-mod
spec-ngram-mod-n-max = 10
spec-ngram-mod-n-min = 2
moe-cache-mib = <model-dependent value>
moe-cache-cpu-share = 0.95
```

Expert-cache flags are added only for MoE profiles on the CUDA branch with native context at least 32768. The generator's existing filename rules remain:

| Case-sensitive GGUF stem match | Cache ceiling (MiB) | CPU share |
|---|---:|---:|
| Contains `35B-A3B` | 2560 | 0.95 |
| Contains `Coder-30B` | 2560 | 0.95 |
| Contains `80B-A3B` | 1536 | 0.95 |
| Other qualifying CUDA MoE, including the source's Sakura example | 2048 | 0.95 |

These are the source's existing selection rules, not a fresh inventory or benchmark of the remote computer. `ngram-mod` is not replaced by the expert cache: both remain in the same preset. ROCm/Vulkan presets do not receive CUDA expert-cache flags.

### Idle-unload controls

- Added the incoming UNLOAD menu: 15m, 30m, 1h, 2h, 3h, never.
- Added its persisted `/idle-unload` API setting and status field.
- Retained the incoming fix that re-reads settings each sweeper cycle; `0` disables idle unload.
- Retained the incoming upward-opening menu, screen-edge positioning and click/backdrop fixes.

### Public inference proxy

Main introduced a public proxy at the configured port (normally 8080), with the actual llama.cpp router moved to configured port + 1 (normally 8081). External clients continue to use 8080. The original proxy implementation had blocking defects; the local changes below repair that implementation.

### Housekeeping

Main added `*.bak-*` to `.gitignore`. The machine-specific `dashboard/settings.json` was already ignored.

## 2. Local repair changes

Production edits relative to `7ff3582` are confined to `dashboard/plugin_api.py` and `desktop/plugin.js`.

### Proxy routing and streaming

- Registered specific chat routes before the catch-all, so `/v1/chat/completions` and `/completion` reach the intended handler.
- Replaced full-response buffering with incremental forwarding, including `/models/sse`.
- Kept the upstream HTTP response/client alive until downstream consumption ends.
- Avoided the generic non-streaming 30-second read-timeout behavior for long streams. Connect timeouts remain.
- Sent SSE comment keepalives every four seconds during waiting, cold loading and slow prefill, not merely while waiting for a lock.
- Forwarded complete SSE events before inserting keepalives, preventing a ping from being spliced into unfinished JSON split across network chunks.
- Reported an incomplete final SSE event as an error rather than silently treating it as a valid completed event.

### Loading, switching and concurrency

- Replaced per-model chat locks with a shared residency lock because the router is configured with `--models-max 1`.
- Coordinated explicit model load/unload requests with chat generation, preventing preloads or unloads from evicting a generating model.
- Checked residency after acquiring the lock, preventing duplicate cold loads from concurrent requests.
- Explicitly unloaded a previous resident when switching models and waited for asynchronous unload completion before loading the replacement.
- Removed disconnected queued work before it can trigger generation.
- Allowed an already-started cold load to continue independently of a disconnected client, retaining residency ownership until it completes or times out.
- Added disconnect monitoring for non-streaming requests too.
- Bounded model loading to 900 seconds and rejected unknown models or malformed control requests instead of indefinite polling/false success.

**Intentional behavior change:** simultaneous chats are serialized through the proxy, including chats targeting the same model. This favors reliable single-model serving over parallel-request throughput. It does not reduce a model's context or change its decode parameters. No paired CUDA throughput benchmark was performed.

### Errors and lifecycle

- Fixed enabling tuned mode accidentally stopping its public proxy.
- Propagated upstream HTTP status for non-streaming generation responses.
- Emitted an explicit JSON error SSE event if a streaming response has already begun; HTTP status cannot be changed after headers have been sent.
- Preserved engine diagnostic messages instead of replacing them with a generic HTTPX URL/status description.
- Forwarded authorization headers along the chat path.
- Bound the proxy socket before starting its thread so port collisions surface to the caller.
- Waited for proxy shutdown before re-enabling, and created a fresh async lock for the new server event loop.
- Closed the parent log handle after spawning and terminated the newly spawned router if proxy startup fails.
- Rolled back both proxy/router state when post-spawn health checks fail.

### Desktop UNLOAD cleanup

- Added a React effect to remove the menu/backdrop and event listener on unmount.
- Added Escape-key dismissal.
- Did not rewrite the model-picker, LLM chip, WG guard hooks or other desktop plugins.

## 3. Tests and evidence

### Automated regression suite

Added:

- `tests/test_proxy.py`
- `tests/test_proxy_edges.py`
- `tests/test_review_regressions.py`
- `tests/test_desktop.cjs`

Actual result from the installed copy: **29 Python tests passed**, plus the Node desktop cleanup test. `node --check desktop/plugin.js` and `git diff --check` passed. Python tests run with standard-library `unittest`; pytest was not installed and was not needed.

The HTTP tests use explicit local fixture servers. They test routing, incremental streaming, split SSE events, heartbeats, model-switch/load coordination, cancellation, error propagation, occupied ports and startup rollback. They are not simulated model-inference results.

### Real-model tests on the AMD/ROCm computer

- An initial isolated sweep exposed the asynchronous unload race after one successful dense-model response; it failed and was not treated as a pass.
- After the race fix, the second isolated sweep completed streaming generation for all seven staged models.
- Representative dense and MoE requests returned valid tool-call JSON. The probe validated emitted tool arguments; it did not execute those requested tools or prove a complete agent workflow.
- After live activation, the installed proxy/router were verified on 8080/8081 with a genuine completion.
- Per user preference, a subsequent live test used `qwen35-9b-mtp-q4km`: streamed `Hello!`, emitted valid `read_file` tool-call JSON, and reported `ngram-mod` with context 65536. It was left loaded at the end of that test; the active chat's model selection was not changed.

These are smoke tests, not long-context quality, sustained-load or new performance benchmarks. No RTX 3070 inference was executed during this work.

## 4. Configuration and data left unchanged

- `_generate_presets`, `_resolve_engine`, `_settings`, `_vram_bytes`, `_engine_asset` and `_nvidia` are structurally identical to imported `7ff3582` (verified by comparing Python ASTs).
- No change to the imported CUDA expert-cache sizes, CPU-share value, n-gram settings, Qwen3-Next recurrent-layer KV correction, KV quantization, expert-offload rule or context-budget calculation.
- No change to `__init__.py` guard/prompt hooks or `plugin.yaml`.
- No llama.cpp binary/driver upgrade; no model download, GGUF edit, model deletion or store relocation.
- No change to this machine's `dashboard/settings.json`: custom ROCm engine, dense context 65536, MoE cap 131072, dense n-grams enabled and WG fix enabled were preserved.
- No change to the user's cloud/provider routing or another profile's configuration.

## 5. Activation incident: environment cleanup, not another code change

The first activation returned the chip to OFF because the old direct-serving router (PID 68708) survived the gateway restart and still owned 8080. The traceback showed WinError 10048.

The stale process was identified by its exact executable, preset path and port. All its models were confirmed unloaded and it had no child model process. Only that stale router was stopped; model files and the serving gateway were not killed. The next chip activation succeeded, and the public proxy plus internal router and a real completion were verified.

**Not implemented:** automatic termination of arbitrary processes occupying the proxy port. Port conflicts still fail explicitly; identifying/stopping a stale legacy instance is a migration/operations step, not a blanket kill policy.

## 6. RTX 3070 impact assessment

### Immediate impact

**None on the other computer.** These edits exist only on this machine and were not committed or pushed. Pulling the GitHub main branch on the RTX 3070 will not retrieve these uncommitted fixes.

### If these repairs are later transferred to the RTX 3070

**Expected to preserve its MoE + ngram-mod + expert-cache configuration**, provided it retains its own machine settings and the existing compatible CUDA engine. Evidence:

1. The entire preset-generation function is unchanged from imported main, as are engine resolution, budget probing and backend detection.
2. Both revisions were executed with identical explicit CUDA preset fixtures. Explicit CUDA and NVIDIA auto-detection paths generated identical presets, with both `ngram-mod` and expert-cache flags present together.
3. The 35B/30B/80B/fallback cache ceilings and CPU share shown above were asserted. ROCm/Vulkan fixture cases generated identical non-CUDA presets without expert-cache flags.

**Limit:** this is source equivalence and fixture execution, not proof that a particular large GGUF fits or runs at a particular speed on the other computer. Its actual models, settings, installed Python environment, engine and free VRAM were not inspected remotely.

### Safe transfer/acceptance checklist

- Preserve the RTX machine's `dashboard/settings.json`; **do not copy the AMD machine's ROCm path or context caps**.
- Preserve its compatible CUDA binary and verify its `--help` includes `--moe-cache-mib`, `--moe-cache-cpu-share`, `--spec-type` and the needed n-gram flags. A version label alone is not sufficient evidence of flag support.
- Ensure backend selection is CUDA (`backend: cuda` or the existing successful NVIDIA auto-detection path). Auto-detection here checks for `nvidia-smi` on PATH; it does not inspect a custom engine's backend.
- The repaired code uses `asyncio.timeout`, requiring Python 3.11 or later, plus the FastAPI/httpx/uvicorn runtime dependencies. Keep this in mind for a separately installed/older environment.
- Use public port 8080; 8081 is the internal router and bypasses proxy coordination. If migrating from pre-proxy direct serving, check for a stale 8080 router before enabling.
- Regenerate presets using that computer's own model headers/settings and compare its actual MoE sections before/after. Confirm the cache/n-gram flags coexist and contexts/cache ceilings are unchanged.
- Run enable/disable/re-enable, cold-load streaming, a second-model switch and a tool-call JSON smoke test with its actual CUDA MoE model. Check the engine log for successful GPU/cache initialization and allocation errors.
- Validate decode/prefill performance with a paired same-session benchmark if performance is an acceptance requirement; this repair does not establish unchanged tok/s.
- No commit, push or transfer to the other computer without explicit approval.

## Backup locations

- Git: `backup/pre-proxy-fdfadc0`.
- Machine settings/preset/desktop backup and original code archive:
  `C:/Users/jup03/AppData/Local/hermes/backups/llamacpp-tuned-pre-proxy-fdfadc0`.
- Installed source: `C:/Users/jup03/AppData/Local/hermes/plugins/llamacpp-tuned`.
- Repair worktree: `C:/Users/jup03/llama-local/plugin-work/llamacpp-tuned`.
