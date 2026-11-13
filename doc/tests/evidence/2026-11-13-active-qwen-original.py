import json
from pathlib import Path
import httpx

base='http://127.0.0.1:8080'
name='qwen35-9b-mtp-q4km'
result={'model':name}
with httpx.Client(timeout=httpx.Timeout(300,connect=5)) as client:
    models=client.get(base+'/v1/models').json()['data']
    assert any(m['id']==name for m in models),'Requested Qwen is not staged'
    text=[]
    done=False
    pings=0
    with client.stream('POST',base+'/v1/chat/completions',json={
        'model':name,'messages':[{'role':'user','content':'Reply with one short greeting in English.'}],
        'max_tokens':128,'stream':True,'temperature':0,'chat_template_kwargs':{'enable_thinking':False}}) as r:
        r.raise_for_status()
        for line in r.iter_lines():
            if line.startswith(':'):pings+=1
            if not line.startswith('data:'):continue
            data=line[5:].strip()
            if data=='[DONE]':done=True;continue
            event=json.loads(data)
            if event.get('error'):raise RuntimeError(str(event['error']))
            for choice in event.get('choices',[]):
                delta=choice.get('delta') or {}
                text.append(delta.get('content') or delta.get('reasoning_content') or '')
    assert done and ''.join(text),'No completed generated response'
    result.update({'stream_done':done,'response':''.join(text),'keepalives':pings})
    r=client.post(base+'/v1/chat/completions',json={
        'model':name,'messages':[{'role':'user','content':'Use the read_file tool now to read C:/test/main.py. Do not guess the file contents.'}],
        'tools':[{'type':'function','function':{'name':'read_file','description':'Read a file from its path.','parameters':{'type':'object','properties':{'path':{'type':'string'}},'required':['path']}}}],
        'tool_choice':'auto','temperature':0,'max_tokens':256,'stream':False,
        'chat_template_kwargs':{'enable_thinking':False}})
    r.raise_for_status()
    calls=r.json()['choices'][0]['message'].get('tool_calls') or []
    result['tool_calls']=calls
    result['tool_call_json_valid']=bool(calls) and all(isinstance(json.loads(c['function']['arguments']),dict) for c in calls)
    # This probe asks the model to emit tool JSON only. No requested tool is executed.
    current=client.get(base+'/v1/models').json()['data']
    result['loaded_after']=[m['id'] for m in current if m.get('status',{}).get('value')=='loaded']
    target=next(m for m in current if m['id']==name)
    args=target['status']['args']
    result['spec_type']=args[args.index('--spec-type')+1]
    result['context']=args[args.index('--ctx-size')+1]
    result['health']=client.get(base+'/health').json()
Path('C:/Users/jup03/AppData/Local/hermes/cache/scratch/active-qwen-results.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps(result,indent=2))
