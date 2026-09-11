import sys
bm=open('dumps/merged5.dump.exe.textbm','rb').read()
TEXT_RVA=0x1000
runs=[]
i=0;n=len(bm)
while i<n:
    if bm[i]==0:
        j=i
        while j<n and bm[j]==0: j+=1
        runs.append((i,j-i))
        i=j
    else: i+=1
runs.sort(key=lambda r:-r[1])
tot=sum(r[1] for r in runs)
print(f"dark pages total={tot} in {len(runs)} contiguous runs")
# histogram of run sizes
import collections
buckets=[(1,1),(2,3),(4,7),(8,15),(16,31),(32,63),(64,127),(128,255),(256,511),(512,1023),(1024,10**9)]
h=collections.OrderedDict()
for lo,hi in buckets:
    cnt=sum(1 for r in runs if lo<=r[1]<=hi)
    pg =sum(r[1] for r in runs if lo<=r[1]<=hi)
    h[f"{lo}-{hi if hi<10**9 else '+'}"]=(cnt,pg)
print("run-size histogram (pages/run -> #runs, total dark pages):")
for k,(c,p) in h.items():
    print(f"  {k:>10} : {c:5d} runs {p:6d} pages ({100.0*p/tot:5.2f}% of dark)")
print()
print("TOP 30 contiguous dark runs:")
print(f"{'#':>3} {'start_rva':>12} {'end_rva':>12} {'pages':>6} {'KB':>8}")
for k,(st,ln) in enumerate(runs[:30],1):
    a=TEXT_RVA+st*0x1000
    b=TEXT_RVA+(st+ln)*0x1000
    print(f"{k:>3} 0x{a:010X} 0x{b:010X} {ln:6d} {ln*4:8d}")
# cumulative
c=0
for k,(st,ln) in enumerate(runs,1):
    c+=ln
    if k in (10,20,50,100,200,500,1000,2000):
        print(f"cumulative top {k} runs: {c} pages ({100.0*c/tot:.2f}% of dark)")
