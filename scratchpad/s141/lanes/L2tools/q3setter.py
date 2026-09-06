import sys, struct
sys.path.insert(0,'scratchpad/s141/lanes/L2tools')
from l2pe import L2Img
from l2dis import lin, fmt, md
from capstone.x86 import *
img=L2Img('dumps/merged14.dump.exe'); buf=img.buf; base=img.imagebase
t=img.sect_of(0x1000); lo=t['va']; hi=t['va']+t['vsize']; d=buf[lo:hi]

print("=== find WRITERS of the quats: any instruction storing to [reg+0x1F0] or [reg+0x210] ===")
# encode search: modrm with disp32 0x000001F0 / 0x00000210 preceded by an SSE store opcode.
# Do it properly: disassemble candidate windows around every occurrence of the disp32 bytes.
m = md()
for disp,label in [(0x1F0,'WorldToGravityTransform'), (0x210,'GravityToWorldTransform')]:
    pat = struct.pack('<I', disp)
    seen=set(); found=[]
    off=0
    while True:
        off = d.find(pat, off)
        if off<0: break
        a0 = lo+off
        # try decoding starting a few bytes back so the disp lands inside an instruction
        for back in range(1,10):
            st = a0-back
            try: g=list(m.disasm(img.read(st,16), st, count=1))
            except Exception: g=[]
            if not g: continue
            i=g[0]
            if st+i.size <= a0: continue
            if not i.operands: continue
            op=i.operands[0]
            if op.type==X86_OP_MEM and op.mem.disp==disp and op.mem.base not in (0,X86_REG_RIP):
                key=(i.address)
                if key in seen: continue
                seen.add(key); found.append(i)
        off+=1
    print("\n-- stores to [reg+0x%X] (%s): %d found (FLOOR) --" % (disp,label,len(found)))
    for i in sorted(found, key=lambda x:x.address)[:12]:
        print("   " + fmt(i))
