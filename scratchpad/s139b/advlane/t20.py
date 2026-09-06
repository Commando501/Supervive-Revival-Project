import io,sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
exec(open('H.py').read())
lo,hi=0x035EC850,0x035EF1B6
n=0
for i in MD.disasm(D[lo:hi],lo):
    if (i.group(CS_GRP_CALL) or i.group(CS_GRP_JUMP)):
        op=i.operands[0]
        if op.type==X86_OP_IMM and op.imm in (0x3600990,0x055C2430): print("  DIRECT->SNP %08X %s"%(i.address,i.op_str)); n+=1
        if op.type==X86_OP_MEM and op.mem.disp==0x720: print("  VTBL+0x720 %08X %s"%(i.address,i.op_str)); n+=1
print("StartNewPhysics references in 0x35EC850..0x35EF1B6:",n)
# control: does ANY function reference 0x3600990 by rel32 in .text? (floor)
import struct
cnt=0; sites=[]
tl,tsz=TEXT
for off in range(tl, tl+tsz-5):
    if D[off]==0xE8:
        t=off+5+struct.unpack_from('<i',D,off+1)[0]
        if t==0x3600990: cnt+=1; sites.append(off)
print("rel32 E8 callers of 0x3600990 image-wide (FLOOR, 55.5%% decrypted):",cnt, [hex(s) for s in sites[:12]])
