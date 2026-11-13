import json, os, re, subprocess, sys, time, urllib.request

ROOT = r'C:/Users/jup03/llama-local'
DOC = open(os.path.join(ROOT, 'doc.txt')).read()
PORT = 8899
CTX = 8192
HM = r'C:/Users/jup03/AppData/Local/hermes/models'

BACKENDS = {
    'vulkan': os.path.join(ROOT, 'llama', 'llama-server.exe'),
    'rocm':   os.path.join(ROOT, 'llama-rocm10', 'llama-server.exe'),
}
MODELS = [
    ('qwen35-9b-stock', os.path.join(ROOT, 'models', 'qwen35-9b-mtp-q4km.gguf')),
    ('qwen35-9b-heretic', os.path.join(HM, 'DeepSeek-V4-Pro-Qwen3.5-9B-UNCENSORED-heretic-Q4_K_M.gguf')),
    ('qwen35-9b-hauhau', os.path.join(HM, 'Qwen3.5-9B-Uncensored-HauhauCS-Aggressive-Q4_K_M.gguf')),
]
SPECS = {
    'none':  [],
    'ngram': ['--spec-type', 'ngram-mod', '--spec-ngram-mod-n-max', '16',
              '--spec-ngram-mod-n-min', '2', '--spec-ngram-mod-n-match', '24'],
}

def kill_servers():
    subprocess.run(['taskkill', '/IM', 'llama-server.exe', '/F'], capture_output=True)
    time.sleep(3)

def wait_health(timeout=150):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f'http://127.0.0.1:{PORT}/health', timeout=5) as r:
                if json.loads(r.read()).get('status') == 'ok':
                    return True
        except Exception:
            pass
        time.sleep(2)
    return False

def run_case(prompt, n):
    body = json.dumps({"prompt": prompt, "n_predict": n, "temperature": 0,
                       "cache_prompt": True}).encode()
    r = urllib.request.urlopen(urllib.request.Request(
        f'http://127.0.0.1:{PORT}/completion', data=body,
        headers={'Content-Type': 'application/json'}), timeout=900)
    d = json.loads(r.read())
    t = d['timings']
    return {'gen_tps': round(t['predicted_per_second'], 2),
            'pp_tps': round(t['prompt_per_second'], 1)}

def main():
    logdir = os.path.join(ROOT, 'logs')
    out_path = os.path.join(ROOT, 'unc_verify.json')
    results = []
    if os.path.exists(out_path):
        results = json.load(open(out_path))
    done = {(r['backend'], r['model'], r['spec']) for r in results}

    for bname, bexe in BACKENDS.items():
        for mname, mpath in MODELS:
            for sname, sflags in SPECS.items():
                if (bname, mname, sname) in done:
                    print('skip', bname, mname, sname, flush=True)
                    continue
                logfile = os.path.join(logdir, f'unc-{bname}-{mname}-{sname}.log')
                kill_servers()
                cmd = [bexe, '-m', mpath, '-ngl', '99', '-fa', '1',
                       '-c', str(CTX), '--port', str(PORT)] + sflags
                with open(logfile, 'w') as lf:
                    subprocess.Popen(cmd, stdout=lf, stderr=lf, cwd=os.path.dirname(bexe))
                if not wait_health():
                    kill_servers()
                    results.append({'backend': bname, 'model': mname, 'spec': sname,
                                    'error': 'load failed'})
                    json.dump(results, open(out_path, 'w'), indent=1)
                    print('FAIL', bname, mname, sname, flush=True)
                    continue
                row = {'backend': bname, 'model': mname, 'spec': sname}
                try:
                    row['repro'] = run_case(
                        "Reproduce the following text exactly, word for word:\n\n" + DOC + "\n\nYour output:", 1500)
                    row['chat'] = run_case("Write a 250 word story about a lighthouse keeper.", 300)
                except Exception as e:
                    row['error'] = str(e)
                    kill_servers()
                    results.append(row)
                    json.dump(results, open(out_path, 'w'), indent=1)
                    print('RUNFAIL', bname, mname, sname, flush=True)
                    continue
                kill_servers()
                results.append(row)
                json.dump(results, open(out_path, 'w'), indent=1)
                print(f"OK {bname} {mname} {sname} repro={row['repro']['gen_tps']} chat={row['chat']['gen_tps']}", flush=True)
    kill_servers()
    print('VERIFY_DONE', flush=True)

if __name__ == '__main__':
    main()
