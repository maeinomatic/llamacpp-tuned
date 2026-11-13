# Hardware compatibility

## Required reading before shared changes

- [This AMD 890M Windows machine: exact setup and protected behavior](amd-890m-windows.md).
- [Cross-machine change and deployment checklist](cross-machine-checklist.md).
- [Legion Go 2 backend supplement](legion-go-2-backend-supplement.md) — Vulkan default, ROCm/HIP-on-Windows status, UMA tuning; complements the 890M doc.

The detailed repair assessment is in the [proxy repair changelog](../changelogs/2026-11-13-proxy-reliability-and-rocm-activation.md#6-rtx-3070-impact-assessment).

## Preserved evidence

- [CUDA preset/source comparison results](evidence/2026-11-13-cuda-preset-compatibility.json).
- [Original check script snapshot](evidence/2026-11-13-cuda-preset-check-original.py), containing fixed local source/scratch paths; inspect and adapt before reuse.

The check compared repaired versus incoming preset-generation/engine-resolution functions and executed explicit CUDA, NVIDIA-auto-detection, ROCm and Vulkan fixtures. It preserved `ngram-mod` and CUDA expert-cache settings. **It did not execute CUDA inference on an RTX 3070.**

Keep each machine's own ignored `dashboard/settings.json`, binary and memory/context caps. Never copy this AMD machine's ROCm path into an NVIDIA setup. Use the other computer's actual model headers/settings and engine flag support when accepting an update. No remote machine was modified or verified by this documentation task.
