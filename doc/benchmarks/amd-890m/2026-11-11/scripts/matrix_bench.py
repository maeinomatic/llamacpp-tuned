import json, os, re, subprocess, sys, time, urllib.request, urllib.error

ROOT = r'C:/Users/jup03/llama-local'
DOC = open(os.path.join(ROOT, 'doc.txt')).read()
PORT = 8899
CTX = 4096

BACKENDS = {
    'vulkan': os.path.join(ROOT, 'llama', 'llama-server.exe'),
    'rocm':   os.path.join(ROOT, 'llama-rocm10', 'llama-server.exe'),
}

MODELS = [
    ('qwen3-4b',        os.path.join(ROOT, 'models', 'qwen3-4b-q4km.gguf')),
    ('qwen35-9b',       os.path.join(ROOT, 'models', 'qwen35-9b-mtp-q4km.gguf')),
    ('ornith-9b',       os.path.join(ROOT, 'models', 'ornith-15-9b-q4km.gguf')),
    ('gemma4-12b',      os.path.join(ROOT, 'models', 'gemma4-12b-ud-q3xl.gguf')),
    ('ornith-9b-unc',   os.path.join(ROOT, 'models', 'ornith-15-9b-unc-q4km.gguf')),
]

SPECS = {
    'none':  [],
    'ngram': ['--spec-type', 'ngram-mod', '--spec-ngram-mod-n-max', '16',
              '--spec-ngram-mod-n-min', '2', '--spec-ngram-mod-n-match', '24'],
}

def kill_servers():
    subprocess.run(['taskkill', '/IM', 'llama-server.exe', '/F'],
                   capture_output=True)
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

def run_case(label, prompt, n):
    body = json.dumps({"prompt": prompt, "n_predict": n, "temperature": 0,
                       "cache_prompt": True}).encode()
    r = urllib.request.urlopen(urllib.request.Request(
        f'http://127.0.0.1:{PORT}/completion', data=body,
        headers={'Content-Type': 'application/json'}), timeout=900)
    d = json.loads(r.read())
    t = d['timings']
    return {'gen_tps': round(t['predicted_per_second'], 1),
            'pp_tps': round(t['prompt_per_second'], 1),
            'gen_n': t['predicted_n']}

def parse_acceptance(logfile):
    try:
        txt = open(logfile, encoding='utf8', errors='replace').read()
        accs = re.findall(r'acceptance(?: rate)? = ([0-9.]+)', txt)
        if accs:
            return round(sum(float(a) for a in accs) / len(accs), 3)
    except Exception:
        pass
    return None

def main():
    logdir = os.path.join(ROOT, 'logs')
    os.makedirs(logdir, exist_ok=True)
    out_path = os.path.join(ROOT, 'results.json')
    results = []
    if os.path.exists(out_path):
        results = json.load(open(out_path))
    done = {(r['backend'], r['model'], r['spec']) for r in results}

    for bname, bexe in BACKENDS.items():
        for mname, mpath in MODELS:
            if not os.path.exists(mpath):
                continue
            for sname, sflags in SPECS.items():
                if (bname, mname, sname) in done:
                    print(f'skip done {bname} {mname} {sname}', flush=True)
                    continue
                logfile = os.path.join(logdir, f'{bname}-{mname}-{sname}.log')
                kill_servers()
                cmd = [bexe, '-m', mpath, '-ngl', '99', '-fa', '1',
                       '-c', str(CTX), '--port', str(PORT)] + sflags
                with open(logfile, 'w') as lf:
                    proc = subprocess.Popen(cmd, stdout=lf, stderr=lf,
                                            cwd=os.path.dirname(bexe))
                if not wait_health():
                    kill_servers()
                    results.append({'backend': bname, 'model': mname, 'spec': sname,
                                    'error': 'load failed/timeout'})
                    print(f'FAIL load {bname} {mname} {sname}', flush=True)
                    json.dump(results, open(out_path, 'w'), indent=1)
                    continue
                row = {'backend': bname, 'model': mname, 'spec': sname}
                try:
                    row['repro'] = run_case('repro',
                        "Reproduce the following text exactly, word for word:\n\n" + DOC + "\n\nYour output:", 1500)
                    row['chat'] = run_case('chat',
                        "Write a 250 word story about a lighthouse keeper.", 300)
                except Exception as e:
                    row['error'] = f'run failed: {e}'
                    kill_servers()
                    results.append(row)
                    print(f'FAIL run {bname} {mname} {sname}: {e}', flush=True)
                    json.dump(results, open(out_path, 'w'), indent=1)
                    continue
                row['acceptance'] = parse_acceptance(logfile)
                kill_servers()
                results.append(row)
                json.dump(results, open(out_path, 'w'), indent=1)
                print('OK', bname, mname, sname,
                      'repro', row['repro']['gen_tps'], 'chat', row['chat']['gen_tps'],
                      'acc', row['acceptance'], flush=True)
    kill_servers()
    print('MATRIX_DONE', flush=True)

if __name__ == '__main__':
    main()
