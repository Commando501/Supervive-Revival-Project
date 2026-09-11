import sys, struct; sys.path.insert(0,'scratchpad/s132')
from uht import img
from uhtdec import rec, GEN, cpf
import capstone

def decode_setbit(im, rva):
    """Disassemble a UHT SetBitFunc lambda and extract (byte_offset, mask, kind)."""
    d = im.read(rva, 32)
    if d is None: return None
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
    md.detail = True
    ins = list(md.disasm(d, im.imagebase + rva))
    txt = "; ".join(f"{i.mnemonic} {i.op_str}" for i in ins[:4])
    off=mask=None; kind=None
    for i in ins:
        if i.mnemonic in ("mov","or") and i.op_str.startswith("byte ptr [rcx"):
            ops = i.operands
            m = ops[0].mem; imm = ops[1].imm if ops[1].type==capstone.x86.X86_OP_IMM else None
            off = m.disp; mask = imm; kind = i.mnemonic
            break
        if i.mnemonic == "ret":
            break
    return dict(rva=rva, txt=txt, off=off, mask=mask, kind=kind,
                bytes=" ".join(f"{b:02x}" for b in d[:12]))

def dump_class(im, propptr_rva, count, only_bools=False, name=""):
    print(f"### {name} PropPointers rva={hex(propptr_rva)} count={count}")
    out=[]
    for i in range(count):
        prva = im.va2rva(im.u64(propptr_rva + 8*i))
        r = rec(im, prva)
        base = r['gflags'] & 0x3F
        d = r['raw']
        if base == 0x0C:  # Bool
            arrdim = struct.unpack_from("<H", d, 0x30)[0]
            elemsz = struct.unpack_from("<H", d, 0x32)[0]
            sizeouter = struct.unpack_from("<I", d, 0x34)[0]
            setbit = struct.unpack_from("<Q", d, 0x38)[0]
            sb = decode_setbit(im, im.va2rva(setbit)) if setbit else None
            out.append((i,r,arrdim,elemsz,sizeouter,setbit,sb))
            print(f"[{i:3d}] {r['name']:34s} BOOL{'|NativeBool' if r['nativebool'] else ''} "
                  f"ArrayDim={arrdim} ElementSize={elemsz} SizeOfOuter={hex(sizeouter)} "
                  f"SetBitFunc=rva {hex(im.va2rva(setbit))}")
            if sb:
                print(f"        raw12={sb['bytes']}")
                print(f"        {sb['txt']}")
                print(f"        => ByteOffset={hex(sb['off']) if sb['off'] is not None else '?'} "
                      f"imm={hex(sb['mask']) if sb['mask'] is not None else '?'} via {sb['kind']}")
        elif not only_bools:
            print(f"[{i:3d}] {r['name']:34s} {r['gname']:24s} off={hex(r['off'])} pflags=0x{r['pflags']:016x}")
    return out
