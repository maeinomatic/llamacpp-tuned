"""Measure arbitrary (mib, share) points: extra_points.py OUT -- cmd... (reuses tuner run_server)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import moe_cache_tune as t

OUT = sys.argv[1]
rest = sys.argv[2:]
points = []
CMD = []
for i, a in enumerate(rest):
    if ":" in a and a.replace(":", "").replace(".", "").isdigit() and all(
            p.replace(".", "").isdigit() for p in a.split(":")):
        mib, share = a.split(":")
        points.append((int(mib), float(share)))
        CMD = rest[i + 1:]
        CMD = CMD[1:] if CMD[:1] == ["--"] else CMD
        break
else:
    sys.exit("no mib:share points given")
if not CMD:
    sys.exit("no server command")
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

for mib, share in points:
    r = t.run_server(CMD, OUT, mib, share, t.N_CALIB, (mib * 7 + int(share * 100)) % 997, f"{mib}-{share}", warm)
    print(f"RESULT {mib} MiB share {share}: {1000 * r['tokens'] / r['ms']:.1f} t/s, hit {r['hit']:.0f}%")
