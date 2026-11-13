"""Prompt-processing measurement: feed a long prompt, read timings.prompt_per_second.
Usage: python measure_pp.py OUT N_PROMPT -- server args..."""
import json
import os
import socket
import subprocess
import sys
import time
import urllib.request

OUT = sys.argv[1]
NPROMPT = int(sys.argv[2])
CMD = sys.argv[3:]
CMD = CMD[1:] if CMD[:1] == ["--"] else CMD

def http(port, endpoint, body=None, timeout=3600):
    req = urllib.request.Request(f"http://127.0.0.1:{port}{endpoint}",
                                 data=json.dumps(body).encode() if body else None,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())

with socket.socket() as s:
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
os.makedirs(OUT, exist_ok=True)
args = CMD + ["--host", "127.0.0.1", "--port", str(port)]
prompt = ("The history of computing is a history of trade-offs between memory, "
          "compute and bandwidth. Every generation of hardware reshapes which "
          "architectures win. " * (NPROMPT // 40))
results = []
with open(os.path.join(OUT, "pp.log"), "w") as log:
    proc = subprocess.Popen(args, stdout=log, stderr=subprocess.STDOUT)
    try:
        while True:
            if proc.poll() is not None:
                sys.exit(f"llama-server exited ({proc.returncode}), see pp.log")
            try:
                if http(port, "/health", timeout=5).get("status") == "ok":
                    break
            except OSError:
                pass
            time.sleep(1)
        for k in range(2):
            t = http(port, "/completion", {"prompt": prompt, "n_predict": 8, "ignore_eos": True,
                                           "cache_prompt": False, "temperature": 0.0})["timings"]
            results.append({"pp_s": t["prompt_per_second"], "n_prompt": t["prompt_n"]})
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=60)
        except subprocess.TimeoutExpired:
            proc.kill()
print(f"RESULT prompt-processing: {results[0]['pp_s']:.0f} / {results[1]['pp_s']:.0f} tok/s "
      f"(prompt {results[0]['n_prompt']} tokens, run1/run2)")
