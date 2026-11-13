"""Source comparison + explicit preset fixtures; does NOT emulate CUDA execution."""
import ast
import importlib.util
import json
import subprocess
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

repo=Path('C:/Users/jup03/AppData/Local/hermes/plugins/llamacpp-tuned')
out=Path('C:/Users/jup03/AppData/Local/hermes/cache/scratch/cuda-tune-compatibility')
out.mkdir(exist_ok=True)
baseline=subprocess.check_output(['git','show','7ff3582:dashboard/plugin_api.py'],cwd=repo)
(out/'incoming_plugin_api.py').write_bytes(baseline)

def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    m=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m
old=load('incoming_cuda_review',out/'incoming_plugin_api.py')
new=load('installed_cuda_review',repo/'dashboard/plugin_api.py')

def funcs(text):
    return {node.name:ast.dump(node,include_attributes=False) for node in ast.parse(text).body if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef))}
a=funcs(baseline.decode())
b=funcs((repo/'dashboard/plugin_api.py').read_text(encoding='utf-8'))
compare={name:a[name]==b[name] for name in ('_generate_presets','_resolve_engine','_settings','_vram_bytes','_engine_asset','_nvidia')}
assert all(compare.values()),compare
results={'comparison_base':'7ff358270a4dbf359de4502c46ef20f94976b599','unchanged_function_ast':compare,'fixture_cases':[],'live_cuda_inference_tested':False}
models=['Qwen3.5-35B-A3B-Q4_K_M','Qwen3-Coder-30B-Q5_K_S','Sakura-45B-Q4_K_M','Qwen3-Next-80B-A3B-IQ4_XS','Unmeasured-MoE','Dense-Qwen']
with tempfile.TemporaryDirectory() as temp:
    directory=Path(temp)
    for model in models:(directory/(model+'.gguf')).touch()
    def header(path):return SimpleNamespace(stem=path.stem,recurrent_blocks=[])
    def profile(h):return SimpleNamespace(n_ctx_train=262144,per_token_kv_f16=16384,recurrent_layer_count=0,layers=[None]*32,moe=h.stem!='Dense-Qwen',weights_bytes=4<<30)
    for backend,detected in [('cuda',True),('',True),('rocm',False),('vulkan',False)]:
        settings={**old.DEFAULTS,'backend':backend,'dense_ngram':True,'dense_ctx':65536,'moe_ctx_cap':262144}
        generated=[]
        for label,m in [('incoming',old),('installed',new)]:
            with patch.object(m,'MODELS_DIR',directory),patch.object(m,'PRESET',directory/(label+'.ini')),patch.object(m,'_settings',return_value=settings),patch.object(m,'_nvidia',return_value=detected),patch.object(m,'_vram_bytes',return_value=8<<30),patch.object(m,'_gguf_tools',return_value=(lambda stem:stem,header,profile)):
                assert m._generate_presets()==len(models)
                generated.append(m.PRESET.read_text())
        assert generated[0]==generated[1],(backend,detected)
        import configparser
        cp=configparser.ConfigParser(interpolation=None)
        cp.read_string(generated[1])
        cuda=(backend=='cuda' or (not backend and detected))
        expected={'Qwen3.5-35B-A3B-Q4_K_M':'2560','Qwen3-Coder-30B-Q5_K_S':'2560','Sakura-45B-Q4_K_M':'2048','Qwen3-Next-80B-A3B-IQ4_XS':'1536','Unmeasured-MoE':'2048'}
        cache={}
        for model in models:
            sec=cp[model]
            assert sec['spec-type']=='ngram-mod'
            if model!='Dense-Qwen':
                assert sec['spec-ngram-mod-n-max']=='10' and sec['spec-ngram-mod-n-min']=='2'
                assert sec['cache-type-k']==sec['cache-type-v']=='q4_0'
                assert sec['override-tensor']==r'blk\.\d+\.ffn_.*_exps\.weight=CPU'
                assert sec['load-mode']=='none'
                if cuda:
                    assert sec['moe-cache-mib']==expected[model]
                    assert sec['moe-cache-cpu-share']=='0.95'
                else:assert 'moe-cache-mib' not in sec
            else:assert 'moe-cache-mib' not in sec
            cache[model]={'spec-type':sec['spec-type'],'moe-cache-mib':sec.get('moe-cache-mib'),'moe-cache-cpu-share':sec.get('moe-cache-cpu-share')}
        results['fixture_cases'].append({'configured_backend':backend or 'auto','nvidia_detected_fixture':detected,'incoming_installed_presets_identical':True,'models':cache})
(out/'results.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
print(json.dumps(results,indent=2))
