import sys, os, collections
sys.path.insert(0, os.path.join(os.getcwd(),'scratchpad','s131','tools'))
import rectab
rectab.P['merged4']=os.path.join(os.getcwd(),'dumps','merged4.dump.exe')
recs=rectab.scan('merged4')
FOLD=rectab.FOLD
pat=[s.lower() for s in sys.argv[1:]]
seen=set()
for r in sorted(recs,key=lambda x:x['name']):
    n=r['name'].lower()
    if any(p in n for p in pat):
        k=(r['name'],r['thunk'],r['impl'])
        if k in seen: continue
        seen.add(k)
        tag=FOLD.get(r['impl'],'REAL?')
        print(f"  {r['name']:<52} thunk=0x{r['thunk']:07X} impl=0x{r['impl']:07X}  {tag}")
