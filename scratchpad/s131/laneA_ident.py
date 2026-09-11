import sys, os, collections
sys.path.insert(0, os.path.join(os.getcwd(),'scratchpad','s131','tools'))
import rectab
ROOT=os.getcwd()
rectab.P['merged4']=os.path.join(ROOT,'dumps','merged4.dump.exe')
recs=rectab.scan('merged4')
byimpl=collections.defaultdict(list)
bythunk=collections.defaultdict(list)
for r in recs:
    byimpl[r['impl']].append(r); bythunk[r['thunk']].append(r)
tgts=[0x55DCAA0,0x55C7DD0,0x56BE0D0,0x54F8DC0,0x20B9EA0,0x10A50C0,0x56680F0,0x339A550,0x55C1B20,0x37D9D40,0x0F988D0,0x0FAC920,0x0FF9310,0x106B650,0x35AFC40,0x5453580,0x55CD510,0x55CD800,0x55CD830,0x55CCF0A,0x55E5623,0x5456380]
for t in tgts:
    ii=byimpl.get(t,[]); tt=bythunk.get(t,[])
    print(f"0x{t:07X}: as-impl={[r['name'] for r in ii]}  as-thunk={[r['name'] for r in tt]}")
print()
# fold multiplicity for the impls we care about
print("multiplicity of impl 0x35AFC40 as an impl:", len(byimpl.get(0x35AFC40,[])))
