"""L3: decode UHT FBoolPropertyParams -> (byte offset, bit mask) by
disassembling each record's SetBitFunc.

Record layout (calibrated on bForceNextFloorCheck, rec@0x07fafff0):
   +0x00 NameUTF8*   +0x08 RepNotify*  +0x10 PropertyFlags(u64)
   +0x18 GenFlags(u32) +0x1C ObjectFlags(u32) +0x20 Setter* +0x28 Getter*
   +0x30 ArrayDim(u16) +0x32 ElementSize(u16) +0x34 SizeOfOuter(u32)
   +0x38 SetBitFunc*
Calibration result: SetBitFunc(bForceNextFloorCheck) = `or byte [rcx+0x2e9], 8`
which is EXACTLY the field the engine's own PerformMovement reads/writes at
0x035E9FF2/0x035EA009 -- an independent agreement.
"""
import sys, struct, re
sys.path.insert(0, '.')
from peimg import Img
from cfg import CS

IDENT = re.compile(rb'^[A-Za-z_][A-Za-z0-9_]{1,63}\x00')

def namestr(im, va):
    r = va - im.imagebase
    if not (0 < r < im.sizeofimage): return None
    try: b = im.read(r, 72)
    except Exception: return None
    m = IDENT.match(b)
    return m.group(0)[:-1].decode() if m else None

def setbit_decode(im, fn_rva):
    """Disassemble a SetBitFunc; return (offset, mask, text) or None."""
    try: b = im.read(fn_rva, 24)
    except Exception: return None
    ins = list(CS.disasm(b, fn_rva))
    if not ins: return None
    i = ins[0]
    if i.mnemonic not in ('or','mov','bts'): return None
    ops = i.operands
    if len(ops) != 2: return None
    from capstone import x86 as X
    if ops[0].type != X.X86_OP_MEM: return None
    m = ops[0].mem
    if m.index != 0: return None
    if ops[1].type != X.X86_OP_IMM: return None
    base = i.reg_name(m.base)
    if base not in ('rcx','ecx'): return None
    return (m.disp, ops[1].imm, f"{i.mnemonic} {i.op_str}")

def scan(im, lo, hi, step=0x10):
    out = []
    for rva in range(lo, hi, step):
        try: b = im.read(rva, 0x40)
        except Exception: continue
        if len(b) < 0x40: continue
        name_va = struct.unpack_from('<Q', b, 0)[0]
        genf = struct.unpack_from('<I', b, 0x18)[0]
        if (genf & 0x3F) != 0x0C: continue          # EPropertyGenFlags::Bool
        n = namestr(im, name_va)
        if not n: continue
        arraydim, elemsz = struct.unpack_from('<HH', b, 0x30)
        sizeofouter = struct.unpack_from('<I', b, 0x34)[0]
        fnva = struct.unpack_from('<Q', b, 0x38)[0]
        d = setbit_decode(im, fnva - im.imagebase) if fnva > im.imagebase else None
        out.append((rva, n, genf, elemsz, sizeofouter, fnva, d))
    return out

if __name__ == '__main__':
    im = Img()
    lo = int(sys.argv[1],16) if len(sys.argv)>1 else 0x07fae000
    hi = int(sys.argv[2],16) if len(sys.argv)>2 else 0x07fb6000
    rows = scan(im, lo, hi)
    print(f"bool records in [{lo:#x},{hi:#x}): {len(rows)}")
    ok = [r for r in rows if r[6]]
    print(f"SetBitFunc decoded: {len(ok)} / {len(rows)}\n")
    for rva, n, genf, esz, so, fnva, d in sorted(ok, key=lambda r: (r[6][0], r[6][1])):
        off, mask, txt = d
        print(f"  [+{off:#06x}] mask {mask:#04x}  SizeOfOuter={so:#x}  {n:46s} rec@{rva:#x}  ({txt})")
    bad = [r for r in rows if not r[6]]
    if bad:
        print("\n  UNDECODED SetBitFunc (report, do not drop):")
        for rva,n,genf,esz,so,fnva,d in bad:
            print(f"    {n:46s} rec@{rva:#x} fn={fnva:#x}")
