import importlib.util,json,time,sys,urllib.request,urllib.error,subprocess,socket,hashlib,traceback
from pathlib import Path
ROOT=Path('C:/Users/Martin/source/repos/llamacpp-tuned')
OUT=Path(__file__).parent/'live';OUT.mkdir(exist_ok=True)
INST=Path('C:/Users/Martin/AppData/Local/hermes/plugins/llamacpp-tuned/dashboard/settings.json')
original=INST.read_bytes()
spec=importlib.util.spec_from_file_location('isolated_tuned_review',ROOT/'dashboard/plugin_api.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
settings={**m.DEFAULTS,**json.loads(original)}
for port in (18880,18881):
    with socket.socket() as s:s.bind(('127.0.0.1',port))
m.ENGINE_DIR=OUT;m.PRESET=OUT/'presets.ini';m.LOG=OUT/'router.log'
m._settings=lambda:{**settings,'port':18880}
BASE='http://127.0.0.1:18880'
MODELS=['Huihui-Qwen3.5-35B-A3B-abliterated.i1-Q4_K_M','Sakura-Whittle-Qwen-3.8-45B-A3B-Q4_K_M']
report={'base_revision':'b642ec2','scope':'Real CUDA inference through isolated repaired plugin proxy; not gateway activation or benchmark','public_port':18880,'router_port':18881,'runs':[],'errors':[]}
def req(path,body=None,timeout=30):
    data=None if body is None else json.dumps(body).encode()
    return urllib.request.urlopen(urllib.request.Request(BASE+path,data=data,headers={'Content-Type':'application/json'}),timeout=timeout)
def get(path):
    with req(path) as r:return json.load(r)
def status(model):
    return next(x['status']['value'] for x in get('/models')['data'] if x['id']==model)
def stream(model,label):
    start=time.monotonic();first=None;heartbeats=0;chunks=0;done=False;content='';reason=''
    payload={'model':model,'messages':[{'role':'user','content':'Reply with exactly PROXY_OK and nothing else. Do not think or explain.'}],'max_tokens':160,'temperature':0,'stream':True,'chat_template_kwargs':{'enable_thinking':False}}
    with req('/v1/chat/completions',payload,timeout=900) as response:
        for raw in response:
            line=raw.decode().strip()
            if line and first is None:first=time.monotonic()-start
            if line.startswith(':'):heartbeats+=1
            if not line.startswith('data:'):continue
            data=line[5:].strip()
            if data=='[DONE]':done=True;continue
            j=json.loads(data)
            if 'error' in j:raise RuntimeError(j['error'])
            for c in j.get('choices',[]):
                delta=c.get('delta',{});content+=delta.get('content') or '';reason+=delta.get('reasoning_content') or '';chunks+=1
    result={'label':label,'model':model,'first_bytes_seconds':first,'heartbeats':heartbeats,'chunks':chunks,'done':done,'content':content,'reasoning_chars':len(reason),'wall_seconds':time.monotonic()-start,'resident_after':status(model)}
    report['runs'].append(result);(OUT/'results.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(result),flush=True)
    assert done and content.strip()=='PROXY_OK',result
try:
    report['resolved_engine']=m._resolve_engine()
    print('ENGINE '+report['resolved_engine'],flush=True)
    m._proc=m._spawn()
    report['router_pid']=m._proc.pid
    deadline=time.monotonic()+90
    while True:
        try:
            if get('/health').get('status')=='ok':break
        except Exception:pass
        if time.monotonic()>deadline:raise TimeoutError('router health')
        time.sleep(.5)
    listing=get('/models')['data']
    for model in MODELS:
        item=next(x for x in listing if x['id']==model);args=item['status']['args']
        flags={args[i]:args[i+1] for i in range(len(args)-1) if args[i].startswith('--')}
        expected={'--spec-type':'ngram-mod','--moe-cache-cpu-share':'0.95','--ctx-size':'262144','--cache-type-k':'q4_0','--cache-type-v':'q4_0','--moe-cache-mib':'2560' if '35B-A3B' in model else '2048'}
        for k,v in expected.items():assert flags.get(k)==v,(k,v,flags)
        report.setdefault('model_flags',{})[model]=expected
    print('FLAGS_VERIFIED',flush=True)
    stream(MODELS[0],'cold-35B')
    stream(MODELS[0],'warm-35B')
    stream(MODELS[1],'switch-to-45B')
    assert status(MODELS[0])=='unloaded'
    report['model_switch_evicted_previous']=True
    report['success']=True
except Exception as e:
    report['success']=False;report['errors'].append(repr(e));traceback.print_exc()
finally:
    try:
        loaded=[x['id'] for x in get('/models')['data'] if x['status']['value']=='loaded']
        for model in loaded:
            with req('/models/unload',{'model':model},timeout=120) as r:r.read()
            deadline=time.monotonic()+45
            while status(model)!='unloaded' and time.monotonic()<deadline:time.sleep(.2)
        m._stop_router()
    except Exception as e:
        report['errors'].append('cleanup '+repr(e))
        if m._proc is not None:subprocess.run(['taskkill','/PID',str(m._proc.pid),'/T','/F'],capture_output=True)
    report['settings_unchanged']=INST.read_bytes()==original
    report['test_ports_closed']={}
    for port in (18880,18881):
        with socket.socket() as s:report['test_ports_closed'][str(port)]=s.connect_ex(('127.0.0.1',port))!=0
    report['gpu_after']=subprocess.run(['nvidia-smi','--query-gpu=memory.used','--format=csv,noheader'],capture_output=True,text=True).stdout.strip()
    (OUT/'results.json').write_text(json.dumps(report,indent=2))
    print('FINAL '+json.dumps(report),flush=True)
sys.exit(0 if report.get('success') and report['settings_unchanged'] and all(report['test_ports_closed'].values()) else 1)
