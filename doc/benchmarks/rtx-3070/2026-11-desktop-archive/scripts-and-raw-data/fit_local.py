"""Windows-fit for moe-cache-tune.py: replaces exit-log cache stats with
per-run replay() of the recorded routing trace, then fits and predicts
exactly like tune() does."""
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import moe_cache_tune as t


def main(out, max_mib):
    runs = []
    for p in sorted(glob.glob(os.path.join(out, "run-*.json"))):
        r = json.load(open(p))
        runs.append(r)
    if not runs:
        sys.exit("no runs in " + out)

    # per-run (up_gib, cpu_gib) from the run's own trace, skipping warm-up
    for r in runs:
        base = os.path.join(out, f"run-{r['mib']}-{r['share']:g}.trace")
        trace = t.read_trace(base)
        skip = t.trace_tokens(trace) // 2
        up, cpu = t.replay(trace, r["mib"], r["share"], skip)
        r["up_gib"], r["cpu_gib"] = up, cpu

    for r in runs:
        print(f"  {r['mib']} MiB share {r['share']:g}: {1000 * r['tokens'] / r['ms']:.1f} t/s, "
              f"up {r['up_gib']:.3f} GiB/tok, cpu {r['cpu_gib']:.3f} GiB/tok")

    m, errs, ok = t.fit(runs)
    fit_err = 100 * max(abs(e) for e in errs)
    print(f"\nfit: uploads {1000 / m['up']:.1f} GiB/s, CPU {1000 / m['cpu']:.1f} GiB/s, "
          f"CPU part {m['split']:.2f} ms, overlap {m['overlap']:.1f} ms/GiB, "
          f"rest {m['base']:.2f} ms/token, within {fit_err:.1f}%")
    if not ok or fit_err > 10:
        sys.exit("fit not physical/too loose")

    trace = t.concat_traces([os.path.join(out, f"run-{r['mib']}-{r['share']:g}.trace") for r in runs])
    groups = trace[2]
    host = sum(g.host_bytes * len(g.layers) for g in groups) / sum(len(g.layers) for g in groups)
    full = t.full_mib(trace, max(t.SHARES))
    print(f"\nexperts: {host / 2**20:.0f} MiB total; full cache = {full} MiB")

    skip = t.trace_tokens(trace) // 2
    rows, pick = [], {}
    for mib in sorted({int(round(f * host / 2**20 / 64) * 64) for f in (0.05, 0.10, 0.15, 0.20, 0.30, 0.40, 0.50)} | {full}):
        if mib > max_mib:
            continue
        ms = [t.model_ms(m, *t.replay(trace, mib, s, skip), s) for s in t.SHARES]
        k = min(i for i in range(len(ms)) if ms[i] <= 1.05 * min(ms))
        tps = [1000 / x for x in ms]
        star = "*" if t.SHARES[k] else ""
        rows.append([mib] + [f"{x:.1f}" for x in tps])
        pick[mib] = (t.SHARES[k], tps[k], tps[0])
        print(f"  cache {mib} MiB: " + ", ".join(f"share {s:g}={x:.1f}{'*' if i == k else ''}" for i, (s, x) in enumerate(zip(t.SHARES, tps))))

    share, best_tps, base_tps = pick[max(pick)]
    print(f"\nRECOMMENDED ({os.path.basename(out)}): --moe-cache-mib {max(pick)} --moe-cache-cpu-share {share:g} "
          f"-> ~{best_tps:.1f} t/s predicted ({base_tps:.1f} at share 0)")


if __name__ == "__main__":
    main(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 10**9)
