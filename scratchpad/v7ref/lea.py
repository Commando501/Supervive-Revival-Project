exec(open('scratchpad/v7ref/lib.py').read())
import struct,sys
targets={int(a,16) for a in sys.argv[1:]}
found={t:[] for t in targets}
i=TEXT_LO
n=0
while i<TEXT_HI-7:
    if D[i]==0x48 or D[i]==0x4C:
        if D[i+1]==0x8D:
            modrm=D[i+2]
            if (modrm & 0xC7)==0x05:   # rip-relative
                disp=struct.unpack_from("<i",D,i+3)[0]
                t=i+7+disp
                if t in found:
                    found[t].append(i)
                n+=1
    i+=1
print("total rip-relative LEAs scanned:",n)
for t in targets:
    print(f"  LEA -> {t:#x}: {len(found[t])} sites {[hex(x) for x in found[t][:10]]}")
