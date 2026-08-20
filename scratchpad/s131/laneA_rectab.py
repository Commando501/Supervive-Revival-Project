import sys, os, struct, collections
sys.path.insert(0, os.path.join(os.getcwd(),'scratchpad','s131','tools'))
import rectab
ROOT = os.getcwd()
rectab.P['merged4'] = os.path.join(ROOT,'dumps','merged4.dump.exe')
rectab.P['merged3'] = os.path.join(ROOT,'dumps','merged3.dump.exe')
rectab.P['rideable'] = os.path.join(ROOT,'dumps','s131-rideable-live','SUPERVIVE-Win64-Shipping.dump.exe')

recs = rectab.scan('merged4')
print(f"records scanned (unit: records) = {len(recs)}")
by_impl = collections.Counter(r['impl'] for r in recs)
for f,lbl in rectab.FOLD.items():
    print(f"  impl==0x{f:07X} ({lbl}): {by_impl.get(f,0)} records")
print()
print("=== POSITIVE CONTROL: the target's own record ===")
for r in recs:
    if r['thunk']==0x5456380 or r['impl']==0x55CD510:
        print("  ", r)
print()
print("=== all records with impl == 0x0F7EB50 (xor eax,eax; ret) ===")
hits=[r for r in recs if r['impl']==0x0F7EB50]
print(f"count (unit: records) = {len(hits)}")
for r in sorted(hits, key=lambda x:x['name']):
    print(f"   rec=0x{r['rec']:08X} thunk=0x{r['thunk']:07X}  {r['name']}")
