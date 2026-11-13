"""Plain decode measurement for engines without MoE-cache flags (e.g. b11671).
Usage: python measure_plain.py OUT N_PREDICT -- server args...
Method mirrors moe_cache_tune.run_server: 2 generations, summed timings."""
import json
import os
import subprocess
import sys
import time
import urllib.request

OUT = sys.argv[1]
N = int(sys.argv[2])
rest = sys.argv[3:]
CMD = rest[1:] if rest[:1] == ["--"] else rest

PROMPT = ("The quick brown fox jumps over the lazy dog. " * 12
          + "Write a long, detailed story about a programmer who builds a "
            "small computer in his garage, discovering along the way that "
            "simple systems often outperform complicated ones. ")

def http(port, endpoint, body=None, timeout=3600):
    req = urllib.request.Request(f"http://127.0.0.1:{port}{endpoint}",
                                 data=json.dumps(body).encode() if body else None,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())

name = os.path.join(OUT, "plain.json")
if os.path.isfile(name):
    r = json.load(open(name))
else:
    import socket
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    args = CMD + ["--host", "127.0.0.1", "--port", str(port)]
    os.makedirs(OUT, exist_ok=True)
    timings = []
    with open(os.path.join(OUT, "plain.log"), "w") as log:
        proc = subprocess.Popen(args, stdout=log, stderr=subprocess.STDOUT)
        try:
            while True:
                if proc.poll() is not None:
                    sys.exit(f"llama-server exited ({proc.returncode}), see plain.log")
                try:
                    if http(port, "/health", timeout=5).get("status") == "ok":
                        break
                except OSError:
                    pass
                time.sleep(1)
            n = min(N, http(port, "/props")["default_generation_settings"]["n_ctx"] - 256)
            timings = [http(port, "/completion", {"prompt": PROMPT, "n_predict": n, "ignore_eos": True,
                                                  "cache_prompt": False, "temperature": 0.8,
                                                  "top_p": 0.95, "seed": k})["timings"] for k in (0, 1)]
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=60)
            except subprocess.TimeoutExpired:
                proc.kill()
    r = {"ms": sum(t["predicted_ms"] for t in timings), "tokens": sum(t["predicted_n"] for t in timings),
         "runs": [t["predicted_per_second"] for t in timings]}
    json.dump(r, open(name, "w"))
print(f"RESULT plain: {1000 * r['tokens'] / r['ms']:.1f} t/s (runs: {r['runs']})")
