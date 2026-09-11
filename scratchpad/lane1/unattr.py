import pickle, collections
bm=open('dumps/merged5.dump.exe.textbm','rb').read(); NP=len(bm); TEXT=0x1000
ma=pickle.load(open('scratchpad/lane1/modattr.pkl','rb')); assign=ma['assign']; tot=ma['tot']; dk=ma['dark']
FIRST=(0x0F7E000-TEXT)//0x1000; LAST=(0x6ABC000-TEXT)//0x1000
una=[p for p in range(NP) if p not in assign]
below=[p for p in una if p<FIRST]; above=[p for p in una if p>LAST]; mid=[p for p in una if FIRST<=p<=LAST]
def d(x): return sum(1 for p in x if bm[p]==0)
print(f"UNATTRIBUTED pages {len(una)} (dark {d(una)})")
print(f"  BELOW first module label (RVA < 0x0F7E000): {len(below)} pages, dark {d(below)} ({100.0*d(below)/len(below):.1f}%)")
print(f"  BETWEEN module segments               : {len(mid)} pages, dark {d(mid)} ({100.0*d(mid)/len(mid):.1f}%)")
print(f"  ABOVE last module label (RVA > 0x6ABC000): {len(above)} pages, dark {d(above)} ({100.0*d(above)/len(above):.1f}%)")
print()
print("full module table (all modules), sorted by dark pages:")
rows=sorted(tot.items(), key=lambda kv:-dk.get(kv[0],0))
print(f"{'dark':>6} {'total':>6} {'%dark':>6}  module")
s=0
for m,t in rows:
    if dk.get(m,0)==0: continue
    print(f"{dk[m]:6d} {t:6d} {100.0*dk[m]/t:5.1f}%  {m}")
    s+=dk[m]
print("modules with 0 dark pages:",sum(1 for m in tot if dk.get(m,0)==0),"of",len(tot))
print("sum dark attributed:",s)
