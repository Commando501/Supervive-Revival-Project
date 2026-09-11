import csv, collections, sys
bm=open('dumps/merged5.dump.exe.textbm','rb').read()
TEXT_RVA=0x1000; TEXT_END=0x1000+0x7649000
def page(r): return (r-TEXT_RVA)//0x1000
def dark(r):
    if not (TEXT_RVA<=r<TEXT_END): return None
    return bm[page(r)]==0
rows=list(csv.DictReader(open('scratchpad/s131/lane-d-empty-impl-census.tsv',encoding='utf-8',errors='replace'),delimiter='\t'))
FOLDS={0x0F7EC20,0x0F7EB50,0x0F7EB60,0x0FC6CF0,0x0B9E1F0}
n_out=0
stat=collections.Counter()
percls=collections.defaultdict(lambda:[0,0])   # class -> [dark, lit]
recs=[]
for r in rows:
    try: rva=int(r['impl_rva'],16)
    except: stat['bad_rva']+=1; continue
    d=dark(rva)
    if d is None: stat['outside_text']+=1; n_out+=1; continue
    stat['DARK' if d else 'LIT']+=1
    percls[r['class']][0 if d else 1]+=1
    recs.append((r['class'],r['func'],rva,d,r['verdict']))
print("lane-d census join vs merged5 .text page bitmap")
print("records:",len(rows), dict(stat))
# agreement with census's own verdict column (built vs merged4)
agree=collections.Counter()
for r in rows:
    try: rva=int(r['impl_rva'],16)
    except: continue
    d=dark(rva)
    if d is None: continue
    agree[(r['verdict'],'DARK' if d else 'LIT')]+=1
print("verdict x merged5-page:",dict(agree))
print()
# distinct impl RVAs (folds collapse many records)
distinct=collections.OrderedDict()
for c,f,rva,d,v in recs: distinct.setdefault(rva,d)
dd=sum(1 for v in distinct.values() if v)
print(f"distinct impl RVAs: {len(distinct)}  dark {dd} ({100.0*dd/len(distinct):.2f}%)  lit {len(distinct)-dd}")
print()
print("=== per-CLASS dark counts (records), classes with >=8 dark ===")
rowsx=sorted(percls.items(), key=lambda kv:-kv[1][0])
print(f"{'dark':>5} {'lit':>5} {'%dark':>6}  class")
shown=0
for k,(dk,lt) in rowsx:
    if dk<8: break
    print(f"{dk:5d} {lt:5d} {100.0*dk/(dk+lt):5.1f}%  {k}")
    shown+=1
print(f"({shown} classes listed)")
