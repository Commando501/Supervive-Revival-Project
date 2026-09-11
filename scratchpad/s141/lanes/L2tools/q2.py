import sys; sys.path.insert(0,'scratchpad/s141/lanes/L2tools')
from l2pe import L2Img; from l2dis import lin, md
from capstone.x86 import *
img = L2Img('dumps/merged14.dump.exe')

print("=== Q2: width of the zeroing store, from the ENCODING ===")
targets = {
 0x035ED973:'load  movups xmm0,[rbp+0x168]',
 0x035ED97A:'load  movsd  xmm1,[rbp+0x170]',
 0x035ED982:'mulsd xmm0,xmm0',
 0x035ED986:'mulsd xmm1,xmm1',
 0x035ED98A:'addsd xmm1,xmm0',
 0x035ED98E:'comisd xmm1,[rip]',
 0x035ED998:'xorps xmm0,xmm0',
 0x035ED9AC:'STORE movups [rbp+0x168],xmm0   <-- THE ZEROING STORE',
 0x035ED9B8:'load  movups xmm0,[rax]',
 0x035ED9BB:'STORE movups [rsi],xmm0',
 0x035ED9BE:'load  movsd  xmm1,[rax+0x10]',
 0x035ED9C3:'STORE movsd  [rsi+0x10],xmm1',
 0x035ED946:'STORE movups [rsi],xmm0   (the UPPER block)',
 0x035ED949:'STORE movsd  [rsi+0x10],xmm1 (upper block)',
}
m = md()
for rva,note in sorted(targets.items()):
    i = next(m.disasm(img.read(rva,16), rva, count=1))
    ops=[]
    for k,op in enumerate(i.operands):
        if op.type==X86_OP_MEM:
            ops.append("op%d=MEM size=%d bytes (base=%s disp=0x%X)" % (k, op.size, i.reg_name(op.mem.base) if op.mem.base else '-', op.mem.disp))
        elif op.type==X86_OP_REG:
            ops.append("op%d=REG %s size=%d" % (k, i.reg_name(op.reg), op.size))
        else:
            ops.append("op%d=IMM 0x%X" % (k, op.imm))
    isw = (i.operands and i.operands[0].type==X86_OP_MEM)
    print("0x%08X %-22s %-6s %-34s  WRITE=%s" % (rva, i.bytes.hex(), i.mnemonic, i.op_str, "YES(op0 is MEM)" if isw else "no"))
    print("            opcode=%s  %s" % (i.bytes[:3].hex(), ' | '.join(ops)))
    print("            %s" % note)
print()
print("--- the FVector at [rbp+0x168] : which stack slots are touched anywhere in PhysFalling ---")
# scan the whole engine PhysFalling extent for any memory operand with base rbp and disp in 0x160..0x188
from l2dis import cfg
insns,succ,bad = cfg(img, 0x035EC850, 0x035EC850, 0x035EE600)
print("CFG: %d insns decoded, %d undecodable" % (len(insns), len(bad)))
hits=[]
for a,i in sorted(insns.items()):
    for k,op in enumerate(i.operands):
        if op.type==X86_OP_MEM and op.mem.base==X86_REG_RBP and 0x160 <= op.mem.disp <= 0x188:
            hits.append((a,k,op.mem.disp,op.size,i))
for a,k,d,sz,i in hits:
    print("  0x%08X  %-7s %-40s  op%d MEM [rbp+0x%X] size=%d  %s" %
          (a, i.mnemonic, i.op_str, k, d, sz, "WRITE" if k==0 else "read"))
