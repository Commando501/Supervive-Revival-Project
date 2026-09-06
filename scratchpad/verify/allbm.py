import sys, os, numpy as np
sys.path.insert(0,'scratchpad/verify')
from bm2 import bm
paths=[l.strip() for l in open('scratchpad/verify/imglist.txt') if l.strip()]
res={}
for p in paths:
    name=os.path.basename(os.path.dirname(p))
    base,rva,vsz,rawsz,rawptr,npg,b=bm(p)
    res[name]=b
    print(f"{name:32s} base=0x{base:X} pages={npg} lit={int(b.sum()):6d} {100*b.sum()/npg:6.2f}%")
np.savez_compressed('scratchpad/verify/allbm.npz', **{k:v for k,v in res.items()})
U=np.zeros(30281,bool)
for v in res.values(): U|=v
print("UNION of 26 images: lit=",int(U.sum()), "dark=",30281-int(U.sum()))
m5=np.load('scratchpad/verify/merged5.dump.exe.npy'); m6=np.load('scratchpad/verify/merged6.dump.exe.npy')
m2=np.load('scratchpad/verify/merged2.dump.exe.npy'); m1=np.load('scratchpad/verify/merged.dump.exe.npy')
print("union\merged6 =",int((U&~m6).sum()), " merged6\union =",int((m6&~U).sum()))
print("union\merged5 =",int((U&~m5).sum()), " merged5\union =",int((m5&~U).sum()))
print("merged5\merged6=",int((m5&~m6).sum()), " merged6\merged5=",int((m6&~m5).sum()))
print("merged2\union =",int((m2&~U).sum()), " merged1\union =",int((m1&~U).sum()))
print("merged2\merged6=",int((m2&~m6).sum()))
np.save('scratchpad/verify/UNION26.npy',U)
