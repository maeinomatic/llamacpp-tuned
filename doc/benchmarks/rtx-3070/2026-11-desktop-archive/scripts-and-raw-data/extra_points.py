"""Measure single extra (mib, share) points reusing moe_cache_tune.run_server."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import moe_cache_tune as t

OUT = sys.argv[1]
CMD = sys.argv[2:]
CMD = CMD[1:] if CMD[:1] == ["--"] else CMD
os.makedirs(OUT, exist_ok=True)
warmed = []

def warm():
    if not warmed:
        model = next(CMD[i + 1] for i, a in enumerate(CMD[:-1]) if a in ("-m", "--model"))
        for p in t.model_files(model):
            with open(p, "rb") as f:
                while f.read(64 << 20):
                    pass
        warmed.append(True)

for mib, share in [(3200, 0.95), (3584, 0.95)]:
    r = t.run_server(CMD, OUT, mib, share, t.N_CALIB, hash(str(mib)) % 1000, f"{mib}", warm)
    print(f"RESULT {mib} MiB share {share}: {1000 * r['tokens'] / r['ms']:.1f} t/s, hit {r['hit']:.0f}%")
