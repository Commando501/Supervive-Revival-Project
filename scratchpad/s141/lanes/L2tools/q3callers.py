import sys, struct
sys.path.insert(0,'scratchpad/s141/lanes/L2tools')
from l2pe import L2Img
img=L2Img('dumps/merged14.dump.exe'); buf=img.buf
t=img.sect_of(0x1000); lo=t['va']; hi=t['va']+t['vsize']
for tgt,nm in [(0x035F4620,'quatA @+0x1F0 (WorldToGravityTransform)'),
               (0x035F4770,'quatB @+0x210 (GravityToWorldTransform)')]:
    hits=[]
    i=lo
    d=buf[lo:hi]
    off=0
    while True:
        off = d.find(b'\xe8', off)
        if off<0 or off+5>len(d): break
        disp = struct.unpack_from('<i', d, off+1)[0]
        if lo+off+5+disp == tgt: hits.append(lo+off)
        off+=1
    print("%s : %d direct rel32 call sites (FLOOR - .text is ~55%% decrypted)" % (nm, len(hits)))
    for h in hits[:20]: print("     0x%08X" % h)
