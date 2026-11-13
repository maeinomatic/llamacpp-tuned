"""Opt-in real-model acceptance run. Uses separate ports/presets and only kills its own tree."""
import importlib.util
import json
import socket
import sys
import time
from pathlib import Path

import httpx
import psutil

HOME = Path('C:/Users/jup03/AppData/Local/hermes')
WORK = Path('C:/Users/jup03/llama-local/plugin-work/llamacpp-tuned')
OUT = HOME / 'cache/scratch/llamacpp-repaired-real-smoke'
OUT.mkdir(exist_ok=True)
sys.path.insert(0,str(HOME/'hermes-agent'))
spec = importlib.util.spec_from_file_location('real_tuned_probe',WORK/'dashboard/plugin_api.py')
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)
p.SETTINGS_FILE = HOME/'plugins/llamacpp-tuned/dashboard/settings.json'
settings = p._settings()
# Reserve/check an adjacent pair; _spawn() binds the real listeners immediately after.
for port in range(19180,19280,2):
    with socket.socket() as a, socket.socket() as b:
        try:
            a.bind(('127.0.0.1',port))
            b.bind(('127.0.0.1',port+1))
            break
        except OSError:
            continue
else:
    raise RuntimeError('No free adjacent test ports')
settings['port'] = port
p._settings = lambda: dict(settings)
p.ENGINE_DIR = OUT
p.PRESET = OUT/'presets.ini'
p.LOG = OUT/'router.log'
results={'port':port,'engine':p._resolve_engine(),'models':[]}

def save():
    (OUT/'results.json').write_text(json.dumps(results,indent=2),encoding='utf-8')

def original_idle():
    with httpx.Client(timeout=10) as client:
        live=client.get('http://127.0.0.1:8080/v1/models').json()
    active=[m['id'] for m in live['data'] if m.get('status',{}).get('value') in ('loading','loaded')]
    if active:
        raise RuntimeError('Original router has an active model; will not compete for memory: '+str(active))

original_idle()
proc=None
try:
    p._proc=p._spawn()
    proc=p._proc
    results['router_pid']=proc.pid
    if not p._wait_healthy(60):
        raise RuntimeError('Isolated repaired router failed health check')
    base=f'http://127.0.0.1:{port}'
    with httpx.Client(timeout=httpx.Timeout(600,connect=10)) as client:
        models=client.get(base+'/v1/models').json()['data']
        for model in models:
            original_idle()
            name=model['id']
            print('REAL MODEL START '+name,flush=True)
            record={'model':name,'streaming':True}
            start=time.monotonic()
            first_byte=None
            pings=0
            pieces=[]
            done=False
            try:
                with client.stream('POST',base+'/v1/chat/completions',json={
                    'model':name,'messages':[{'role':'user','content':'Reply with one short greeting in English.'}],
                    'max_tokens':80,'temperature':0,'stream':True,
                    'chat_template_kwargs':{'enable_thinking':False}}) as response:
                    record['http_status']=response.status_code
                    response.raise_for_status()
                    for line in response.iter_lines():
                        if line and first_byte is None:
                            first_byte=time.monotonic()-start
                        if line.startswith(':'):
                            pings+=1
                        if not line.startswith('data:'):
                            continue
                        payload=line[5:].strip()
                        if payload=='[DONE]':
                            done=True
                            continue
                        event=json.loads(payload)
                        if event.get('error'):
                            raise RuntimeError(json.dumps(event['error']))
                        for choice in event.get('choices',[]):
                            delta=choice.get('delta') or {}
                            pieces.append(delta.get('content') or delta.get('reasoning_content') or '')
                record.update({'done':done,'generated_text':''.join(pieces),'pings':pings,
                               'first_byte_s':first_byte,'elapsed_s':time.monotonic()-start})
                record['passed']=bool(done and ''.join(pieces))
                # Probe actual tool-call JSON transport on representative stock dense + MoE.
                if name in ('ornith-15-9b-q4km','Huihui-gpt-oss-20b-abliterated-v2-MXFP4_MOE'):
                    tool_response=client.post(base+'/v1/chat/completions',json={
                        'model':name,'messages':[{'role':'user','content':'Use the read_file tool now to read C:/test/main.py. Do not guess the file contents.'}],
                        'tools':[{'type':'function','function':{'name':'read_file','description':'Read a file from its path.','parameters':{'type':'object','properties':{'path':{'type':'string'}},'required':['path']}}}],
                        'tool_choice':'auto','max_tokens':256,'temperature':0,'stream':False,
                        'chat_template_kwargs':{'enable_thinking':False}})
                    tool_response.raise_for_status()
                    tool_data=tool_response.json()
                    calls=tool_data.get('choices',[{}])[0].get('message',{}).get('tool_calls') or []
                    record['tool_calls']=calls
                    record['tool_call_json_valid']=bool(calls) and all(isinstance(json.loads(c['function']['arguments']),dict) for c in calls)
            except Exception as exc:
                record.update({'passed':False,'error':str(exc),'elapsed_s':time.monotonic()-start})
            finally:
                try:
                    unloaded=client.post(base+'/models/unload',json={'model':name})
                    record['unload_status']=unloaded.status_code
                except Exception as exc:
                    record['unload_error']=str(exc)
                results['models'].append(record)
                save()
                print('REAL MODEL RESULT '+json.dumps(record),flush=True)
        results['isolated_health_after']=client.get(base+'/health').json()
finally:
    p._proxy_stop()
    if proc is not None:
        try:
            parent=psutil.Process(proc.pid)
            children=parent.children(recursive=True)
        except psutil.NoSuchProcess:
            children=[]
        if proc.poll() is None:
            proc.terminate()
            try: proc.wait(timeout=30)
            except Exception: proc.kill(); proc.wait(timeout=10)
        for child in children:
            try:
                child.terminate()
                child.wait(timeout=10)
            except psutil.NoSuchProcess: pass
    results['own_router_stopped']=proc is None or proc.poll() is not None
    with httpx.Client(timeout=10) as client:
        results['original_router_health_after']=client.get('http://127.0.0.1:8080/health').json()
    save()
print('REAL SMOKE COMPLETE '+str(OUT/'results.json'),flush=True)
sys.exit(0 if results['models'] and all(m['passed'] for m in results['models']) else 1)
