# Cross-machine change checklist

Read this and [the AMD machine baseline](amd-890m-windows.md) before developing a shared fix from either computer. Keep both hardware paths functional; a local GPU pass is not a remote-hardware guarantee.

| Requirement | AMD 890M / ROCm | RTX 3070 / CUDA |
|---|---|---|
| Engine | Preserve explicit portable ROCm path | Preserve its own compatible CUDA engine |
| Settings | Preserve ignored machine file | Preserve its different ignored machine file |
| Dense n-grams | Enabled in the recorded AMD settings | Honor that computer's `dense_ngram` setting |
| MoE n-grams | Preserve `ngram-mod` 10/2 | Preserve `ngram-mod` 10/2 alongside expert caching |
| CUDA expert cache | No CUDA cache knobs injected | Preserve existing CUDA gating, cache ceilings and CPU share |
| Context | Recorded dense 65536 / MoE cap 131072 | Use its actual headers/settings/budget, not AMD caps |
| Memory | Shared RAM/device budget; not all RAM is VRAM | Discrete VRAM plus CPU/expert RAM and PCIe trade-offs |
| API | Public configured port / internal port + 1 | Same layout; check actual port ownership on migration |

## Before changing or publishing

- [ ] Read root AGENTS.md and preserve user edits, ignored settings and model data.
- [ ] Identify which exact functions/flags/defaults change on each backend.
- [ ] For preset/engine changes, compare generated AMD and CUDA fixture outputs before/after, including explicit backend and NVIDIA-auto-detection paths. A fixture result must be labeled as such.
- [ ] Preserve the existing CUDA expert-cache selection: qualifying MoE profiles use 2560 MiB for stems containing `35B-A3B` or `Coder-30B`, 1536 MiB for `80B-A3B`, otherwise 2048 MiB; CPU share 0.95. These are source-selection rules, not a universal memory-fit guarantee.
- [ ] Keep MoE `ngram-mod` plus expert-cache flags together on the CUDA path; do not turn one off to support the AMD path.
- [ ] Verify actual binaries accept all emitted flags. This repaired proxy uses Python 3.11+ (`asyncio.timeout`) and FastAPI/httpx/uvicorn; validate the other runtime environment before deployment.
- [ ] Run fixture regression tests and document failures/skips. For local live testing prefer Qwen; use only an approved model/test window.
- [ ] Add a dated changelog entry with AMD/CUDA impact, evidence, migration and rollback notes, and update its index.
- [ ] Scan the exact intended commit set for credentials, model/binary files and unrelated changes. Local absolute paths/machine metadata in documentation are intentionally descriptive, not deployment defaults; consider their visibility before public publication.
- [ ] Obtain explicit approval for the exact commit/push target. A push-readiness question is not push approval.

## Before merging or deploying on another computer

- [ ] Preserve that computer's settings/binary and take its own backup; do not transfer the other computer's settings.json or generated INI.
- [ ] Re-read actual generated model tunes there and compare with its known-good baseline.
- [ ] Verify enable/disable/re-enable, public/internal listeners, a cold streamed completion, model switching and emitted tool JSON on its actual GPU/model.
- [ ] Check allocation/cache-init errors in engine logs. Use a same-session A/B if unchanged performance is required.
- [ ] If real hardware cannot be tested, say so. Publish to a review branch if authorized; do not label the update universally hardware-verified or automatically deploy it to every machine.

The current evidence supports real AMD/ROCm smoke tests and CUDA source/fixture compatibility. Actual RTX 3070 inference with these repaired files remains a separate acceptance step.
