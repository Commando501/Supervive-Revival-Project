import sys, struct, capstone, csv, bisect, json
sys.path.insert(0,'scratchpad/lanev5')
from pe import load, pehdr

DISP = 0x488
data = load(); IB, secs = pehdr(data)
tx = [s for s in secs if s['name']=='.text'][0]
TB, TE = tx['vaddr'], tx['vaddr']+tx['vsize']

md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
md.detail = True

needle = struct.pack('<i', DISP)   # 88 04 00 00

# ---- page decryption map -------------------------------------------------
NPAGES = (TE-TB+0xFFF)//0x1000
lit = bytearray(NPAGES)
for i in range(NPAGES):
    p = TB + i*0x1000
    if any(data[p:p+0x1000]):
        lit[i] = 1
nlit = sum(lit)
print("[.text] pages=%d  decrypted(non-zero)=%d (%.2f%%)  dark=%d" % (NPAGES, nlit, 100.0*nlit/NPAGES, NPAGES-nlit), file=sys.stderr)

# ---- pdata function attribution -----------------------------------------
prows=[]
with open('tools/strxref/index/pdata_union.csv') as f:
    for x in csv.DictReader(f):
        prows.append((int(x['begin_rva'],16), int(x['end_rva'],16)))
prows.sort()
pbeg=[a for a,_ in prows]
def func_of(rva):
    i = bisect.bisect_right(pbeg, rva)-1
    if i<0: return None
    b,e = prows[i]
    if not (b<=rva<e): return None
    j=i
    while j>0 and prows[j-1][1]==prows[j][0]: j-=1
    return prows[j][0]

# ---- scan ----------------------------------------------------------------
hits=[]
pos = TB
raw = data
seen=set()
scanned=0
while True:
    p = raw.find(needle, pos, TE)
    if p < 0: break
    pos = p+1
    scanned += 1
    # skip if page is dark (all-zero) -- can't be a real instruction
    if not lit[(p-TB)//0x1000]: continue
    # try instruction starts p-k
    for k in range(2, 13):
        st = p-k
        if st < TB: continue
        if st in seen: pass
        try:
            ins = next(md.disasm(raw[st:st+16], st, 1))
        except StopIteration:
            continue
        if ins.address + ins.size <= p+3:  # doesn't cover the disp
            continue
        ok=False
        for op in ins.operands:
            if op.type == capstone.x86.X86_OP_MEM and op.mem.disp == DISP:
                ok=True; break
        if not ok: continue
        # require the disp bytes to sit exactly at p inside the instruction
        # (capstone gives us disp value; positional check via encoding offset)
        try:
            dispoff = ins.disp_offset
        except Exception:
            dispoff = None
        if dispoff is not None and dispoff>0 and (st+dispoff)!=p:
            continue
        key=(st, ins.size)
        if key in seen: break
        seen.add(key)
        imm = None
        for op in ins.operands:
            if op.type == capstone.x86.X86_OP_IMM:
                imm = op.imm
        base = ins.reg_name(ins.operands[0].mem.base) if ins.operands[0].type==capstone.x86.X86_OP_MEM and ins.operands[0].mem.base else None
        if base is None:
            for op in ins.operands:
                if op.type==capstone.x86.X86_OP_MEM:
                    base = ins.reg_name(op.mem.base) if op.mem.base else '<none>'
        hits.append(dict(rva=st, size=ins.size,
                         bytes=' '.join('%02x'%b for b in ins.bytes),
                         mnem=ins.mnemonic, ops=ins.op_str, imm=imm, base=base,
                         fn=func_of(st)))
        break

print("[scan] raw occurrences of disp32 0x488 pattern in .text: %d" % scanned, file=sys.stderr)
print("[scan] decoded instructions with memory displacement 0x488: %d" % len(hits), file=sys.stderr)
json.dump(hits, open('scratchpad/lanev5/hits488.json','w'))
