import pickle, collections, bisect, re, sys
sys.path.insert(0,'tools/strxref')
import strxref as SX
bm=open('dumps/merged5.dump.exe.textbm','rb').read(); NP=len(bm); TEXT=0x1000
ma=pickle.load(open('scratchpad/lane1/modattr.pkl','rb')); assign=ma['assign']
idx=SX.Index.load('tools/strxref/index/strxref.idx'); d=idx._dump()
BANDPG=256  # 1 MB
nb=(NP+BANDPG-1)//BANDPG
bandstr=collections.defaultdict(collections.Counter)
for site,si in zip(idx.rf_site, idx.rf_str):
    b=(site-TEXT)//0x1000//BANDPG
    bandstr[b][si]+=1
PATH=re.compile(r"[\/]([A-Za-z0-9_\-]+)[\/]([A-Za-z0-9_\-]+\.(?:cpp|h|inl|cc))\s*$", re.I)
print(f"{'band RVA':>21} {'pg':>4} {'dark':>5} {'%':>5}  modules(dark) | distinctive strings referenced by LIT code in band")
tot_dark=0
for b in range(nb):
    p0=b*BANDPG; p1=min(NP,p0+BANDPG)
    dk=sum(1 for p in range(p0,p1) if bm[p]==0)
    tot_dark+=dk
    if dk<20: continue
    mods=collections.Counter()
    for p in range(p0,p1):
        if bm[p]==0 and p in assign: mods[assign[p]]+=1
    files=collections.Counter(); msgs=[]
    for si,c in bandstr.get(b,collections.Counter()).most_common(400):
        t=idx.text_of(si,d)
        m=PATH.search(t)
        if m and ' ' not in t.strip(): files[m.group(1)+'/'+m.group(2)]+=1
        elif 10<=len(t)<=60 and not t.startswith('/Script'): msgs.append(t)
    ms=", ".join(f"{k}({v})" for k,v in mods.most_common(3)) or "-"
    fs=", ".join(k for k,_ in files.most_common(4))
    xs=" | ".join(msgs[:5])
    print(f"0x{TEXT+p0*0x1000:07X}-0x{TEXT+p1*0x1000:07X} {p1-p0:4d} {dk:5d} {100.0*dk/(p1-p0):4.0f}%  {ms}")
    if fs: print(f"{'':>21}      FILES: {fs}")
    if xs: print(f"{'':>21}      STR: {xs}")
print("total dark accounted:",tot_dark)
