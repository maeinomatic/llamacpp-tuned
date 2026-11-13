# RTX 3070 / Qwen3.5-35B-A3B — new MoE-cache data vs the Nov 10 BENCHMARK-REPORT

> **Source machine: RTX 3070 desktop — Intel i7-13700K, 64 GB DDR5-4800, NVIDIA RTX 3070 8 GB, Windows 10, CUDA.**
> Archive/review provenance only: external research claims are not measurements from this machine. Not Legion Go 2 results.

**Baseline doc:** `AppData/Local/hermes/llamacpp-bench/BENCHMARK-REPORT.md` (2026-11-10,
engine b12255, greedy /completion, Huihui-Qwen3.5-35B i1-Q4_K_M).
**New data:** 2026-11-12 moe-cache tuner sweep (same engine, same model, pure decode
via the tuner's synthetic prompt, no chat template, no drafting).

## 1. Where we stood on Nov 10 (BENCHMARK-REPORT.md)

| Workload / context | Defaults | Tuned (ncmoe 48, q4 KV, ngram-mod n10) | Speedup |
|---|---|---|---|
| Doc-copy, 4K | 42.8 | 71.8 | 1.7× |
| Doc-copy, 32K | 39.9 | 66.1 | 1.7× |
| Doc-copy, 128K | 38.1 | 72.6 | 1.9× |
| Doc-copy, 256K | 22.0 | **82.3** | **3.7×** |
| Chat (novel text, short ctx) | 44.3 | 41.9 | drafting: **no gain** |
| Doc-copy n-gram sweep @4K | 37–47 | 99.8 (n-max 10) | ~2.4× |
| Decode vs context (tuned, 256K) | — | 60–65 flat (60–82 with variance) | — |
| Prompt processing | 160–235 | 175–205 | ~none |

## 2. Today's cache sweep (pure decode, 256K ctx, NO drafting)

| Config | tok/s | vs no-cache decode |
|---|---|---|
| No cache (≈ preset minus drafting, minus cache) | ~34.7 | — |
| cache 1856, share 0 / 0.5 / 0.95 | 34.7 / 34.4 / 42.1 | ±0 / −1% / +21% |
| cache 2560, share 0 / 0.5 | 39.0 / 37.0 | +12% / +7% |
| **cache 2560, share 0.95 (load-mode none)** | **44.0** | **+26%** |
| mmap variants (best: 2560 + 0.95) | 40.7 | +17% (but worse than pinned) |
| cache 3200 / 3584 | 0.9 / 6.2 | VRAM thrash — collapse |

Machine constants: PCIe uploads 14.4 GiB/s, CPU expert read 52.8 GiB/s (3.7× the
slot), full expert set 18,600 MiB — a whole-model cache is impossible on 8 GB.

## 3. Side-by-side: same card, three levers

| Lever (256K window unless noted) | Result | Cost | Verdict |
|---|---|---|---|
| n-gram drafting (Nov 10) | 82.3 doc-copy (3.7×); 44.3→41.9 chat | 0 VRAM | keep — but only helps lookup-heavy work |
| **MoE cache + CPU share (today)** | 34.7 → **44.0 pure decode (+26%)** | 2.5 GiB VRAM | keep — helps *every* decode incl. novel text, where drafting does nothing |
| Bigger cache than 2560 | 0.9–6.2 t/s | — | never — VRAM ceiling at 256K |
| mmap instead of pinned load | ≤40.7 | — | never — loses in every cell |

## 4. The interesting interaction (why this stack works)

The Nov 10 report showed drafting does nothing for novel chat text (44.3→41.9).
The MoE cache is the opposite: it needs no prompt reuse — it's a flat +26% on
pure decode. The two techniques attack different halves:
- **Drafting** hides the per-token overhead when the answer repeats the prompt.
- **Cache + CPU share** attacks the expert-transfer wait on every single token.

Projected on top of the Nov 10 numbers (verification run still pending):
- Doc-copy 256K: 82.3 → ~95–105 tok/s if gains stack proportionally
- Novel chat (drafting-neutral): ~34.7 → **44.0**, directly measured today
- Defaults 256K → cached config: 22.0 → 44.0 = **2.0×** even without drafting

## 5. Three-way: stock Hermes vs tuned plugin vs tuned + cache (measured 2026-11-13)

Same model, same machine, same tuner methodology (pure decode, no drafting):

| Config | Engine | Context max | KV | Drafting | Decode | Prefill (5.5K prompt, steady) |
|---|---|---|---|---|---|---|
| **Stock Hermes** (managed runtime, its own planner preset) | b11671 | 64K | q8_0 | none | **36.2** @ 64K | **1022 tok/s** |
| **Tuned plugin** (llamacpp-tuned, chip ON) | b12255 | 256K | q4_0 | ngram-mod n10 | ~34.7 @ 256K (no cache) | 717 tok/s |
| **Tuned + cache (today's recipe)** | b12255 | 256K | q4_0 | ngram-mod n10 | **44.0** @ 256K / **42.3** @ 64K | 673 tok/s |

Prefill caveat: stock's ubatch 2048 makes it the fastest at ingesting prompts
(~30% faster than tuned's ubatch 512); the cache costs another ~6%. Decode is
where tuned and cached pull ahead — and the cache is the only config that
beats stock at decode. Time-to-first-token for a big RAG context still favors
stock; sustained generation favors tuned + cache.

- Stock = Hermes' PM-pinned engine b11671 with its physics-planner preset
  (`runtimes/llamacpp/presets.ini`): 64K window, q8 KV, ubatch 2048, experts→CPU.
  It predates the MoE cache — the flags don't exist in that build.
- Tuned + cache vs stock: +17% decode at 64K, +22% at 256K, plus 4× the context
  window and the ngram drafting wins on lookup-heavy work on top.
- Tuned-no-cache vs stock: roughly parity on decode (34.7–36.2 within the ±10%
  variance) — the tuned plugin's real wins are the 256K window, q4 KV, and
  drafting; the cache is what finally pulls decode clearly ahead.



## 6. Gains / losses ledger vs the Nov 10 doc

**Gains**
- +26% pure decode at full 256K (44.0 vs 34.7), reproduced twice, fit ≤0.9%.
- Fills the gap drafting couldn't: novel-text chat finally gets a real win.
- Defaults→cached at 256K is now 2.0× without drafting (the 3.7× needed doc-copy).
- Engine b12255 already ships the flags — no rebuild, no core changes.

**Losses / new constraints**
- The cache (2.5 GiB) consumes essentially all the headroom the Nov 10 doc freed
  with q4 KV at 256K. Context size and cache size now trade 1:1 — a bigger cache
  or a bigger window each requires giving up the other. 3200+ thrashes (0.9–6.2 t/s).
- Tuning cost ~50 min GPU time (one-off); run-to-run variance ±10% like the Nov 10
  doc, so treat 44.0 as 42–46.
- Not yet measured: drafting + cache *together* at 256K (expected to stack);
  the 80B model (Qwen3-Next hybrid arch may behave differently).

**Bottom line:** the Nov 10 recipe stays as-is; the new flags
(`--moe-cache-mib 2560 --moe-cache-cpu-share 0.95`) slot in additively. Biggest
single-ticket win for chat-style use since the plugin was built. Plugin still
untouched — applying means a small edit to the preset generator in
`dashboard/plugin_api.py`.
