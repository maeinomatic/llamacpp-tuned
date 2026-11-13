# llamacpp-tuned MoE cache — current state (2026-11-13)

> **Source machine: RTX 3070 desktop — Intel i7-13700K, 64 GB DDR5-4800, NVIDIA RTX 3070 8 GB, Windows 10, CUDA.**
> Archive/review provenance only: external research claims are not measurements from this machine. Not Legion Go 2 results.

## Applied
- Plugin generator (`dashboard/plugin_api.py`, repo commit 7ea227f) now adds
  `moe-cache-mib` + `moe-cache-cpu-share 0.95` to **every staged MoE preset,
  CUDA only**:
  - 35B-A3B / Coder-30B: 2560 MiB
  - Sakura-45B: 2048 MiB · 80B-A3B: 1536 MiB
  - unmeasured MoE models: 2048 MiB conservative default
- Vulkan/ROCm presets (Legion Go 2) are byte-identical to before.
- Rollback: `git checkout pre-moe-cache-backup` in `source/repos/llamacpp-tuned`,
  or restore `plugins/llamacpp-tuned.bak-pre-moecache` +
  `runtimes/llamacpp-tuned/presets.ini.bak-pre-moecache`.
- NOTE: memory-store entry about these results is pending (tool issue);
  this folder is the canonical record.

## Measured (pure decode, b12255, share 0.95, load-mode none)
| Model | Cache | Baseline → With cache | Gain |
|---|---|---|---|
| 35B-A3B Q4_K_M (256K) | 2560 | 34.7 → 44.0 | +26% |
| Coder-30B-Heretic Q5_K_S (87K) | 2560 | 23.9 → 40.5 | +69% |
| Sakura-45B-A3B Q4_K_M (256K) | 2048 | 34.2 → 38.4 | +12% |
| 80B-A3B IQ4_XS (256K) | 1536 | 30.7 → 35.2 | +15% |

- Drafting stacks with the cache: code-rewrite A/B 67.2/53.9 (cache) vs
  59.0/47.9 (no cache) — +13%.
- Dense 9B/4B: no cache (experts fit in VRAM).
- VRAM ceiling at 256K ctx: 2560 MiB; 3200+ thrashes (0.9–6.2 t/s).
- Machine: PCIe uploads 14.4 GiB/s vs CPU expert read 52.8 GiB/s.

## Not yet done
- Chip is OFF in the Desktop app (user turned it off during measurements) —
  flip it back on to use the new presets; presets regenerate on next router
  spawn automatically.
- Cache sizes above are single-point measurements (baseline vs cache+0.95);
  a full 6-run tuner sweep per model would refine them but the sign and rough
  size of the gain is established.
