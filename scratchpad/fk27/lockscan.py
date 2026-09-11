# fk27: enumerate every LOCK-prefixed RMW in .text and bucket the immediates.
# Rationale: FUObjectItem::ThisThreadAtomicallySetFlag / ClearFlag in UE compiles to either
#   lock or dword ptr [mem], imm32        (result unused)
#   lock cmpxchg dword ptr [mem], reg     (CAS loop, UE's actual implementation)
# The flag constant appears as an OR/AND immediate feeding the CAS.
# Blind spot reported alongside the result: a zero (never-decrypted) page yields nothing;
# an immediate loaded via a register from .rdata would not be seen as an immediate.
import sys, os, collections, capstone
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dumplib import load
from funcs import func_of, dis_func

md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
md.detail = True

def scan(im, want_disp=None):
    _, va, vsz, ra, rsz = im.sec(".text")
    data = im.data[ra:ra+rsz]
    hits = []
    # 0xF0 is the LOCK prefix. Brute-force each occurrence and try to decode there.
    start = 0
    while True:
        i = data.find(b"\xf0", start)
        if i < 0: break
        start = i + 1
        try:
            ins = next(md.disasm(data[i:i+16], im.rva2va(va + i), 1))
        except StopIteration:
            continue
        if "lock" not in ins.mnemonic: continue
        hits.append((va + i, ins.mnemonic, ins.op_str, ins.size))
    return hits

if __name__ == "__main__":
    im = load(sys.argv[1] if len(sys.argv) > 1 else "merged2")
    hits = scan(im)
    print(f"# LOCK-prefixed instructions decoded in .text: {len(hits)}")
    byop = collections.Counter(h[1] for h in hits)
    for k, v in byop.most_common():
        print(f"   {k:24s} {v}")
    # focus: lock or / lock and / lock xor with imm on a [reg+8] memory operand
    print("\n# lock <alu> dword ptr [reg+disp], imm32   (candidate flag writes)")
    for (rva, m, o, sz) in hits:
        if m.startswith("lock ") and ", " in o and o.split(", ")[-1].startswith("0x"):
            print(f"  +0x{rva:07X}  {m:14s} {o}")
