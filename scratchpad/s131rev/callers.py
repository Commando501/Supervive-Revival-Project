# Uncapped rel32 caller scan over decrypted .text of a dump. Prints EVERY hit + coverage stats.
import sys, io, struct
sys.stdout=io.TextIOWrapper(sys.stdout.buffer,encoding='utf-8',errors='backslashreplace')
sys.path.insert(0,r"G:\git\Supervive Revival Project\scratchpad\s131rev")
from av import img
def scan(key, targets, opcodes=(0xE8,0xE9)):
    I=img(key); d=I.d
    tv,ts=[(va,vs) for nm,va,vs,ro,rs in I.secs if nm=='.text'][0]
    res={t:[] for t in targets}
    tset=set(targets)
    end=tv+ts-5
    i=tv
    while True:
        # find E8 / E9 bytes
        j=i
        # brute scan
        break
    for i in range(tv, end):
        b=d[i]
        if b not in opcodes: continue
        rel=int.from_bytes(d[i+1:i+5],'little',signed=True)
        t=i+5+rel
        if t in tset: res[t].append((i,b))
    # coverage
    zp=0; tp=0
    for p in range(tv, tv+ts, 0x1000):
        tp+=1
        if d[p:p+0x1000]==b'\x00'*0x1000: zp+=1
    return res,(tp-zp,tp)
if __name__=="__main__":
    key=sys.argv[1]; ts=[int(x,0) for x in sys.argv[2:]]
    r,cov=scan(key,ts)
    print("coverage: %d/%d .text pages non-zero (%.2f%%)"%(cov[0],cov[1],100*cov[0]/cov[1]))
    for t in ts:
        print("target 0x%08X : %d rel32 sites (UNCAPPED)"%(t,len(r[t])))
        for site,op in r[t]:
            print("    0x%08X  %s"%(site, 'call' if op==0xE8 else 'jmp'))
