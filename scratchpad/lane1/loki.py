import pickle, collections, csv, bisect
bm=open('dumps/merged5.dump.exe.textbm','rb').read(); NP=len(bm); TEXT=0x1000
ma=pickle.load(open('scratchpad/lane1/modattr.pkl','rb')); assign=ma['assign']
nm=pickle.load(open('scratchpad/lane1/namemap.pkl','rb')); names=nm['names']
lok=[p for p,m in assign.items() if m=='/Script/Loki']
lokd=[p for p in lok if bm[p]==0]
print(f"/Script/Loki attributed pages {len(lok)}, dark {len(lokd)} ({100.0*len(lokd)/len(lok):.1f}%) = {len(lokd)*4} KB")
# contiguous dark runs inside Loki
lokd.sort(); runs=[]; i=0
while i<len(lokd):
    j=i
    while j+1<len(lokd) and lokd[j+1]==lokd[j]+1: j+=1
    runs.append((lokd[i],lokd[j]-lokd[i]+1)); i=j+1
runs.sort(key=lambda r:-r[1])
print(f"contiguous dark runs inside Loki: {len(runs)}; top 12:")
for st,ln in runs[:12]:
    a=TEXT+st*0x1000; b=TEXT+(st+ln)*0x1000
    ins=collections.Counter()
    for r,v in names.items():
        if a<=r<b:
            for t in v:
                if t[1]: ins[t[1]]+=1
    print(f"   0x{a:07X}-0x{b:07X} {ln:4d}pg  {', '.join(f'{k}({c})' for k,c in ins.most_common(6)) or '(no named symbol inside)'}")
print()
# Loki-class UFunction impls dark
rows=list(csv.DictReader(open('scratchpad/s131/lane-d-empty-impl-census.tsv',encoding='utf-8',errors='replace'),delimiter='\t'))
per=collections.defaultdict(lambda:[0,0])
for r in rows:
    c=r['class']
    if not (c.startswith('ALoki') or c.startswith('ULoki') or c.startswith('FLoki')): continue
    try: rva=int(r['impl_rva'],16)
    except: continue
    p=(rva-TEXT)//0x1000
    if not (0<=p<NP): continue
    per[c][0 if bm[p]==0 else 1]+=1
tot_d=sum(v[0] for v in per.values()); tot_l=sum(v[1] for v in per.values())
print(f"Loki-named classes in census: {len(per)}; UFunction impl records dark {tot_d} / {tot_d+tot_l} ({100.0*tot_d/(tot_d+tot_l):.1f}%)")
print("Loki classes with >=3 dark impls:")
for c,(d,l) in sorted(per.items(), key=lambda kv:-kv[1][0]):
    if d<3: break
    print(f"   dark {d:3d} lit {l:3d}  {c}")
