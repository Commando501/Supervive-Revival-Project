"""Map every FJsonObjectConverter::JsonObjectToUStruct (0x1f99e20) call site ->
the UScriptStruct it converts into, by resolving the StaticStruct() call that
feeds rdx.  Then classify: is rcx the TSharedRef straight out of
FJsonSerializer::Deserialize (TOP-LEVEL), or something else (ENVELOPE)?
"""
import sys, os, struct, pickle, bisect
sys.path.insert(0, os.path.dirname(__file__))
from img import Img, TEXT_LO, TEXT_HI, RDATA_LO, RDATA_HI, DATA_LO, ripdest
import capstone

img = Img(); b = img.b; BASE = 0x7FF6AF000000
JSONOBJ2USTRUCT = 0x1f99e20
DESERIALIZE = 0x11695b0
READERFAC = 0x1185580
T = pickle.load(open(os.path.join(os.path.dirname(__file__), "calltargets.pkl"), "rb"))
KEYS = sorted(T)


def fstart(rva):
    i = bisect.bisect_left(KEYS, rva)
    return KEYS[i - 1] if i else None


def rel32_callers(target):
    out = []
    i = TEXT_LO
    while True:
        i = b.find(b"\xe8", i, TEXT_HI - 5)
        if i < 0: break
        if i + 5 + struct.unpack_from("<i", b, i + 1)[0] == target:
            out.append(i)
        i += 1
    return out


# name every StaticStruct() body: it ends `lea r8,[wide name]; lea rcx,Z_Construct; call GetStaticStruct`
def struct_name_of(fn):
    """fn = a StaticStruct() function start; return the wide name it passes."""
    for insn in img.md.disasm(b[fn:fn + 0x80], fn):
        d = ripdest(insn)
        if insn.mnemonic == "lea" and d is not None and RDATA_LO <= d < RDATA_HI:
            w = img.wstr(d, 80)
            if w and all(32 <= ord(c) < 127 for c in w):
                return w
        if insn.mnemonic == "ret":
            break
    return None


if __name__ == "__main__":
    callers = rel32_callers(JSONOBJ2USTRUCT)
    print("JsonObjectToUStruct call sites:", len(callers))
    rows = []
    for c in callers:
        fn = fstart(c)
        # disassemble the enclosing function up to the call site
        ins = list(img.md.disasm(b[fn:c + 8], fn))
        calls = [i for i in ins if i.mnemonic == "call" and i.operands
                 and i.operands[0].type == capstone.x86.X86_OP_IMM]
        tgts = [i.operands[0].imm for i in calls]
        has_reader = READERFAC in tgts
        has_deser = DESERIALIZE in tgts
        # the StaticStruct call = last imm call before the converter that isn't reader/deser
        ss = None
        for i in reversed(calls[:-1]):
            t = i.operands[0].imm
            if t not in (READERFAC, DESERIALIZE):
                ss = t; break
        name = struct_name_of(ss) if ss else None
        rows.append((fn, c, ss, name, has_reader, has_deser, len(ins)))
        print("  site %08x  fn %08x  StaticStruct %s  -> %-42s reader=%d deser=%d ninsn=%d"
              % (c, fn, ("%08x" % ss) if ss else "?", name, has_reader, has_deser, len(ins)))
    pickle.dump(rows, open(os.path.join(os.path.dirname(__file__), "jconv.pkl"), "wb"))
