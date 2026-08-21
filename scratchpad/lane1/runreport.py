import pickle, collections, bisect, re, sys
bm=open('dumps/merged5.dump.exe.textbm','rb').read(); NP=len(bm)
TEXT=0x1000
edges=pickle.load(open('scratchpad/lane1/edges.pkl','rb'))
nm=pickle.load(open('scratchpad/lane1/namemap.pkl','rb')); names=nm['names']; mods=nm['mod']
strs=pickle.load(open('scratchpad/lane1/strs.pkl','rb'))
srva=[s[0] for s in strs]
loc=pickle.load(open('scratchpad/lane1/loc.pkl','rb'))
ft=pickle.load(open('scratchpad/lane1/ft.pkl','rb')); BEG,END,PHB=ft['BEG'],ft['END'],ft['PHB']
ext=sorted([(BEG[i],END[i]) for i in range(len(BEG)) if END[i]])
estart=[e[0] for e in ext]
# strings referenced by each caller extent: rebuild from strxref pairs
import sys as _s; _s.path.insert(0,'tools/strxref')
import strxref as SX
idx=SX.Index.load('tools/strxref/index/strxref.idx'); d=idx._dump()
site2str=collections.defaultdict(list)
for site,si in zip(idx.rf_site, idx.rf_str):
    i=bisect.bisect_right(estart,site)-1
    if i>=0 and ext[i][0]<=site<ext[i][1]:
        site2str[ext[i][0]].append(si)
PATH=re.compile(r"[\/]([A-Za-z0-9_\-]+)[\/]([A-Za-z0-9_\-]+\.(?:cpp|h|inl|cc))\s*$", re.I)
def strtext(si): return idx.text_of(si,d)
# runs
runs=[]; i=0
while i<NP:
    if bm[i]==0:
        j=i
        while j<NP and bm[j]==0: j+=1
        runs.append((i,j-i)); i=j
    else: i+=1
runs.sort(key=lambda r:-r[1])
TOPN=int(sys.argv[1]) if len(sys.argv)>1 else 20
for k,(st,ln) in enumerate(runs[:TOPN],1):
    a=TEXT+st*0x1000; b=TEXT+(st+ln)*0x1000
    print("="*100)
    print(f"RUN #{k}  RVA 0x{a:07X}-0x{b:07X}  {ln} pages  {ln*4} KB")
    # names inside
    inside=collections.Counter(); insidemod=collections.Counter()
    for r,v in names.items():
        if a<=r<b:
            for t in v:
                if t[1]: inside[t[1]]+=1
            for m in mods.get(r,()): insidemod[m]+=1
    print(f"  named symbols INSIDE: {sum(inside.values())} labels / {len(inside)} distinct owners")
    if inside: print("   inside owners:", ", ".join(f"{n}({c})" for n,c in inside.most_common(12)))
    if insidemod: print("   inside modules:", ", ".join(f"{n}({c})" for n,c in insidemod.most_common(8)))
    # lit callers into this run
    callers=collections.Counter()
    for p in range(st,st+ln):
        for f,c in edges.get(p,{}).items(): callers[f]+=c
    print(f"  lit rel32 edges into run: {sum(callers.values())} from {len(callers)} caller functions")
    cn=collections.Counter(); cm=collections.Counter()
    for f,c in callers.items():
        for t in names.get(f,()):
            if t[1]: cn[t[1]]+=c
        for m in mods.get(f,()): cm[m]+=c
    if cn: print("   caller owners:", ", ".join(f"{n}({c})" for n,c in cn.most_common(12)))
    if cm: print("   caller modules:", ", ".join(f"{n}({c})" for n,c in cm.most_common(8)))
    # strings referenced by callers -> file paths
    files=collections.Counter(); msgs=collections.Counter()
    for f,c in callers.items():
        for si in site2str.get(f,()):
            t=strtext(si)
            m=PATH.search(t)
            if m and ' ' not in t.strip(): files[m.group(1)+'/'+m.group(2)]+=1
            elif 8<=len(t)<=70: msgs[t]+=1
    if files: print("   caller __FILE__:", ", ".join(f"{n}({c})" for n,c in files.most_common(10)))
    if msgs: print("   caller strings:", " | ".join(f"{n!r}" for n,c in msgs.most_common(8)))
