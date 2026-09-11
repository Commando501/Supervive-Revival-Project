import sys, struct
sys.path.insert(0,r"G:\git\Supervive Revival Project\scratchpad\s139\adv")
from img import *
targ=int(sys.argv[1],16)
TS=SECS[0]  # .text
lo,hi = TS[1], TS[1]+TS[4]
hits=[]
i=lo
D=DATA
while i < hi-5:
    b=D[i]
    if b==0xE8 or b==0xE9:
        rel=struct.unpack_from('<i',D,i+1)[0]
        if i+5+rel==targ:
            hits.append((i, 'call' if b==0xE8 else 'jmp'))
    i+=1
print(f"target 0x{targ:08X}: {len(hits)} rel32 sites (FLOOR - .text is ~55% decrypted; a zero page can hide callers)")
for a,k in hits[:60]:
    print(f"  0x{a:08X} {k}  (page nz {page_nonzero(a)})")
