# Qwen locally on the 8GB RTX 3070 — collected info (research only, no action taken)

> **Source machine: RTX 3070 desktop — Intel i7-13700K, 64 GB DDR5-4800, NVIDIA RTX 3070 8 GB, Windows 10, CUDA.**
> Archive/review provenance only: external research claims are not measurements from this machine. Not Legion Go 2 results.

Collected 2026-11-12 from:
- Video: "llama.cpp vs Ollama: the new MoE cache runs big models 2x faster.." (KernelBrief, 17:04, https://www.youtube.com/watch?v=OWhgJjePORk) — transcript saved alongside this file as `transcript_OWhgJjePORk.txt`
- llama.cpp PR #30966 (merged 2026-11-07, author am17an): commit e95426f "llama_moe_cache: run missed experts on CPU, add tuning script"
- Official docs: https://github.com/ggml-org/llama.cpp/blob/master/docs/moe-cache.md
- Tuner: https://github.com/ggml-org/llama.cpp/blob/master/scripts/moe-cache-tune.py

## Why our 3070 (8GB) is the headline case

The video's machine #1 is exactly an 8GB RTX 3070 running a Qwen-3.6-35B-based
35B MoE coding model from a 4-bit file:

| Config | tok/s |
|---|---|
| Experts in RAM, no cache (≈ what Ollama gives today) | ~35 |
| October's cache alone (~3 GiB, `moe-cache-mib`) | ~41 |
| Cache + new CPU share at 0.95 | **62.4** (1.78x) |

Why: 35B-A3B MoE = 40 layers × 256 experts, 8 active per token (320 reads/word).
A 4-bit 35B file spills — experts live in system RAM, everything else on the card
(our card can't hold ~20GB of 4-bit weights). On the 3070 the ~3GiB cache held a
sixth of the experts but answered ~75% of lookups; the remaining misses were the
bottleneck.

## The two flags (llama.cpp, defaults are OFF)

- `--moe-cache-mib N` — MoE expert cache in MiB, split across GPUs (Oct 2026).
- `--moe-cache-cpu-share F` — fraction of cache *misses* the CPU computes from
  host experts instead of uploading over PCIe (merged 7 Nov 2026, PR #30966).
- Expert offload itself uses `-cmoe` (experts stay in host memory).

## Video's settings for the 3070-class machine

- Cache: ~3 GiB (`--moe-cache-mib 3000`)
- CPU share: `0.95` (CPU handles 95% of misses)
- Load mode: default mmap — this matters. The share helps because mmap'd
  (unpinned) experts upload well below PCIe speed; with `-lm mlock` / `-lm dio`
  (pinned/direct-IO) uploads run at full link speed and the share adds little.

Napkin check from the video: 1 expert ≈ 1.71 MiB in that file, 320 reads/word,
~77 misses ≈ 131 MiB from RAM per word; PCIe at ~9.8 GiB/s ≈ 13 ms wait → 41 t/s;
CPU reading RAM at ~35.9 GiB/s (3.7x the measured slot rate) → <5 ms → ~62.8
predicted, 62.4 measured.

## The universal rule (video)

CPU share helps when: CPU reads RAM faster than the PCIe slot copies to the card,
AND the model spills, AND the file is mmap'd (not pinned).
It *hurts* on PCIe 5 x16 slots or with slow RAM. Trap seen on a 5060 Ti
(x8, 6.5 GiB/s slot but 75 GiB/s RAM): cache alone = 44→18.7 t/s (!), cache+share
0.95 = 61 t/s. October's cache without the share was the regression.

## The right way to pick numbers: the tuning script

```bash
python3 scripts/moe-cache-tune.py -- build/bin/llama-server -m model.gguf -cmoe -t 8 -c 32768
```
- Starts the server 6× (2 cache sizes × shares 0, 0.5, 0.95), fits the machine's
  upload rate + CPU read rate, predicts all other size/share combos.
- Recommends the *lowest* share within 5% of fastest (leans conservative → 0).
- `--max-mib N` to cap the cache; runs are reused while the server command is
  unchanged.
- Warning from the thread: vision (mmproj) files aren't counted yet — use a
  smaller max cache if the model has one.

## Ollama status (relevant if we want to stay on Ollama)

- Ollama spawns llama-server with a minimal hardcoded flag list; the MoE cache
  flags are NOT passed. But llama.cpp reads settings from env vars named
  `LLAMA_ARG_*`, and Ollama hands its environment to llama-server — so on paper
  setting system env vars works. Untested by the author; verify via the
  "MoE cache size" line in Ollama's log.
- Catch: stable Ollama ships a llama.cpp from before Nov 7 → only October's
  cache, NOT the cpu-share. That's exactly the combination that made the 5060 Ti
  slower. The Nov 10 pre-release has both halves. So on Ollama today:
  pre-release + env vars, or don't bother.
- LM Studio: forces experts onto CPU but no cache-size setting found. No auto
  tuning flag was merged upstream either (PR closed unmerged).

## Verdict matrix (video, 16:57)

- 8 GB card (us): **switch to llama.cpp + tuner — biggest gain of all** (35→62);
  bring 32 GB system RAM.
- 11–12 GB: switch for any 35B-class model (42→64.5 measured on a 2080 Ti).
- 16 GB: switch (44→61 on a 5060 Ti; tuner predicts ~74 with bigger cache).
- 24 GB: 35B @ 4-bit fits → stay on Ollama; but for Flash Next 125B switch
  (19.5→32.4 on a 3090; note most of that gain there came from direct-IO loading).
- PCIe 5 x16 (R9 7000-class): use the cache, expect tuner to say share 0.
- Mac: N/A (unified memory).

## Model sizing context (from model-info sites)

- Qwen 3.6 35B-A3B: MoE, 256 experts/layer, 8 routed + 1 shared active; 4-bit
  build ≈ 20 GB weights → never fits 8GB VRAM; must offload experts to RAM
  (CPU inference of ~3B active params is why it's viable at all).
- On our 8GB card: non-expert weights + KV cache on GPU, ~13+ GB of experts in
  system RAM (Ollama already does this split today, just without the cache).

## Our setup — verified on this PC (2026-11-12)

**Machine** (read live): RTX 3070 8 GB, i7-13700K, 64 GB DDR5 @ 4800 MT/s
(2×32 GB). Matches the video's machine #1 profile: RAM read (~35–50 GiB/s
practical at DDR5-4800) well above the 3070's effective mmap upload rate
(~9.8 GiB/s measured on the video's 3070) → **the CPU share should help us**,
not hurt. We are NOT the 5060 Ti / PCIe-5 case.

**tuned-llama plugin** = `llamacpp-tuned` (Hermes plugin, repo at
`C:/Users/Martin/source/repos/llamacpp-tuned`). Launches llama.cpp router
**b12255** (commit 940a30ee3, built Nov 10) from
`AppData/Local/hermes/runtimes/llamacpp-tuned/llama-server.exe` on port 8080.

**Key finding: our b12255 build ALREADY contains both flags.** `--help` lists
`--moe-cache-mib` and `--moe-cache-cpu-share` (env `LLAMA_ARG_MOE_CACHE_MIB`,
`LLAMA_ARG_MOE_CACHE_CPU_SHARE`). No rebuild needed — the Nov 7 merge (e95426f)
predates our Nov 10 build. Current presets simply don't pass them yet.

**Current preset** (Huihui-Qwen3.5-35B-A3B-abliterated.i1-Q4_K_M):
- `override-tensor blk\.\d+\.ffn_.*_exps\.weight=CPU` (experts in RAM — same
  effect as `-cmoe`; consider switching to the official `-cmoe`/`--cpu-moe`)
- ctx 262144, q4_0 KV, flash-attn, ubatch 512, ngram-mod spec drafting (n 2–10)
- **`--load-mode none`** ← this is the big interaction. Per docs/moe-cache.md,
  experts loaded with `-lm none`/`mlock`/`dio` are *pinned*, so PCIe uploads run
  at full link speed and "the CPU share often does not help then". Our preset's
  measured 66–72 tok/s already comes from a pinned-load + q4-KV + spec-drafting
  recipe. So the expected outcome is NOT the video's 35→62 (that was default
  mmap); it's "cache alone may add some, share adds little — or the mmap recipe
  (default load-mode) + cache + share 0.95 beats our current recipe outright".
  This is exactly what the tuner will decide — run it with both load modes
  (its `--max-mib` also matters, see VRAM note below).
- **VRAM budget conflict**: with the full 256K ctx we already use ~5.5 GB of 8.
  A 3 GiB cache (video's number) won't fit alongside it. Either cap the cache
  (`--max-mib` ~1200–1500, tuner runs would then favor a smaller share) or tune
  at a smaller ctx window.

**Second model** — `Huihui-Qwen3-Next-80B-A3B-abliterated.i1-IQ4_XS.gguf`:
bigger spill (IQ4_XS, ~45 GB class), so much more of every token's expert reads
come from RAM — proportionally larger headroom for cache + CPU share than the
35B. No preset for it yet in `tuned-presets.ini` (only 35B/9B/4B exist);
its architecture is Qwen3-Next (hybrid linear attention), so verify cache
support applies to its MoE blocks before investing in tuning.

**Plugin-side route if we want it**: the plugin launches llama-server directly,
so we can pass the two flags as plain args (no Ollama env-var workaround needed
— that section above is only relevant to Ollama). Cleanest test path: run
`moe-cache-tune.py` as a prefix on the plugin's exact server command.

## Tuner results — MEASURED on our machine (2026-11-12)

Ran ggml-org `scripts/moe-cache-tune.py` (Windows-patched copy at
`AppData/Local/hermes/llamacpp-tune/`: graceful-shutdown + truncated-trace fixes,
`fit_local.py` replays traces for the fit since Windows can't dump exit stats)
against the plugin's exact 35B command, 256K ctx, pure decode (no spec drafting):

**load-mode none (our current recipe):**
| cache | share 0 | 0.5 | 0.95 |
|---|---|---|---|
| 1856 MiB | 34.7 | 34.4 | 42.1 |
| 2560 MiB | 39.0 | 37.0 | **44.0** ← best |

**default mmap:**
| cache | share 0 | 0.5 | 0.95 |
|---|---|---|---|
| 1856 MiB | 24.5 | 25.4 | 39.2 |
| 2560 MiB | 27.5 | 27.7 | 40.7 |

- Machine constants (pinned load): uploads **14.4 GiB/s** over PCIe, CPU expert
  read **52.8 GiB/s**, CPU part 6.8 ms/token, rest 10.7 ms/token (fit 0.8%).
  Mmap variant: uploads 10.5 GiB/s, fit 0.9%. Both models physical and tight.
- **Winner: keep `--load-mode none`, add `--moe-cache-mib 2560 --moe-cache-cpu-share 0.95`
  → 44.0 t/s pure decode vs ~34.7 today (+26%).** Unlike the video's general
  claim, pinned experts do NOT kill the share on our machine — full PCIe line
  rate (14.4 GiB/s) is still 3.7x slower than our DDR5 CPU path.
- mmap loses on cache-only (24.5 t/s — the lazy page-fault crawling the plugin
  was built to avoid) and even with the share only reaches 40.7.
- 3200 MiB cache does NOT fit at 256K ctx: llama.cpp projects 7209 MiB vs 7113
  free (its 1024 MiB safety target) and, with `-ngl 99` pinned, it loads anyway
  and  thrashes to 0.9 t/s; 3584 MiB confirms it at 6.2 t/s (hit 0% — VRAM thrash).
  **2560 MiB is the ceiling at the full 256K window**
  (options: smaller ctx → more cache room, or `--max-mib` philosophy).
- Prediction (replay) at cap 1536 said 1408/0.9 → but direct measurement showed
  bigger caches keep winning; trust the measured 2560/0.95.
- Expert side: file has 18600 MiB host experts (9300 MiB unique after
  gate/up/dedup accounting in the replay), full-cache would need 18634 MiB.
- These numbers are pure decode. Our preset's ngram-mod drafting (66–72 t/s on
  draft-friendly workloads) stacks on top and is unchanged; a combined final
  verification at the winning settings is still pending.
- State after tests: 80B was unloaded for VRAM, reloaded afterwards; router
  untouched; nothing in presets.ini or plugin code changed.

## Open questions (not yet checked / not actioned)

- Tuner run with OUR command line (both `-lm none` and default mmap variants)
  → let it pick cache-mib + cpu-share; don't hand-pick.
- Expert size in our exact i1-Q4_K_M file (video's 1.71 MiB was a different
  quant) — affects cache hit rate.
- Whether Qwen3-Next-80B (hybrid attention) gets the full MoE-cache benefit.
- VRAM split at 256K ctx: how much cache actually fits with our KV settings.
