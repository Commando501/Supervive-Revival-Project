"""L5 HALF A: image-wide census of stores to [reg+0xE8/0xF0/0xF8] in decrypted .text."""
import sys, struct, json
sys.path.insert(0,'.')
from peimg import Img
import capstone as cs

IMG = r"G:/git/Supervive Revival Project/dumps/merged14.dump.exe"
im = Img(IMG); IB = im.imagebase
TX = [s for s in im.sections if s['name']=='.text'][0]
tlo, thi = TX['va'], TX['va']+TX['vsz']
data = im.data
praw = TX['praw']

# --- decrypted page bitmap (denominator)
NPAGES = (thi-tlo)//0x1000
lit = bytearray(NPAGES)
for p in range(NPAGES):
    off = praw + p*0x1000
    if any(data[off:off+0x1000]):
        lit[p] = 1
nlit = sum(lit)
print(f"[DENOM] .text pages total {NPAGES}, decrypted (non-zero) {nlit} = {100.0*nlit/NPAGES:.2f}%")

md = cs.Cs(cs.CS_ARCH_X86, cs.CS_MODE_64)
md.detail = True

TARGETS = {0xE8:'0xE8 Velocity.X', 0xF0:'0xF0 Velocity.Y', 0xF8:'0xF8 Velocity.Z'}

hits = []
seen = set()
for disp_val in TARGETS:
    pat = struct.pack('<i', disp_val)   # e8 00 00 00 etc
    start = praw
    end = praw + TX['vsz']
    idx = data.find(pat, start, end)
    while idx != -1:
        rva_disp = tlo + (idx - praw)
        page = (rva_disp - tlo)//0x1000
        if lit[page]:
            # try candidate instruction starts
            for back in range(3, 16):
                s_rva = rva_disp - back
                if s_rva < tlo: continue
                try:
                    b = data[praw + (s_rva - tlo): praw + (s_rva - tlo) + 20]
                except Exception:
                    continue
                got = None
                for ins in md.disasm(b, s_rva):
                    got = ins; break
                if got is None: continue
                if got.address + got.size <= rva_disp: continue
                # must have a MEM operand with this disp
                ops = got.operands
                if not ops: continue
                # WRITE = operands[0].type == MEM  (never regs_access -- S140T2 trap)
                o0 = ops[0]
                if o0.type != cs.x86.X86_OP_MEM: continue
                if o0.mem.disp != disp_val: continue
                if o0.mem.base in (0, cs.x86.X86_REG_RIP): continue
                if o0.mem.index != 0: continue
                key = got.address
                if key in seen: break
                seen.add(key)
                hits.append(dict(rva=got.address, size=got.size,
                                 mnem=got.mnemonic, op=got.op_str,
                                 disp=disp_val,
                                 base=got.reg_name(o0.mem.base),
                                 bytes=got.bytes.hex()))
                break
        idx = data.find(pat, idx+1, end)

hits.sort(key=lambda h:h['rva'])
print(f"[RAW] store instructions to [reg+0xE8/0xF0/0xF8] in decrypted .text: {len(hits)}")
from collections import Counter
print("  by disp:", Counter(TARGETS[h['disp']] for h in hits))
print("  by mnemonic:", Counter(h['mnem'] for h in hits).most_common(20))
json.dump(hits, open('storehits.json','w'))
