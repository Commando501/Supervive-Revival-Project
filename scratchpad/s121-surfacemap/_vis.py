import json,os,re
ROOT=r"G:\git\Supervive Revival Project\tools\extractor\out\catalog\wbp"
TOG="WBP_UI_ClientConfigVisbilityToggleWidget_C"
def pg(props,name):
    for k,v in props.items():
        if k==name or (k.startswith(name+"[") and k.endswith("]")): return v
    return None
for f in sorted(os.listdir(ROOT)):
    if not f.endswith('.json'): continue
    p=os.path.join(ROOT,f)
    b=open(p,'rb').read()
    if TOG.encode() not in b: continue
    d=json.loads(b.decode('utf-8','replace'))
    for o in d:
        if not isinstance(o,dict) or o.get('Type')!=TOG: continue
        if str(o.get('Name','')).startswith('Default__'): continue
        pr=o.get('Properties',{}) or {}
        ev=pg(pr,'EnabledVisibility'); dv=pg(pr,'DisabledVisibility')
        if ev is not None or dv is not None:
            print(f"{f[:-5]:42} {o.get('Name'):34} key={pg(pr,'FeatureKey')!r:28} EnabledVis={ev}  DisabledVis={dv}")
