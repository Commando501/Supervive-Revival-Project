"""L3: who ELSE writes the candidate receipt fields?

Bounded, sound sweep over the ULokiCharacterMovementComponent VTABLE
(.rdata 0x088F8570, 413 slots). Every slot is a genuine function entry, so
recursive descent is valid; no byte-pattern scan, no linear sweep.

SCOPE LIMIT (state it): this covers the CLASS'S VIRTUAL SURFACE ONLY, and only
functions on DECRYPTED pages. Non-virtual members and free functions that touch
these fields are NOT covered. It is a FLOOR on "other writers", never a proof of
uniqueness.
"""
import sys, struct, collections
sys.path.insert(0, '.')
import capstone
from capstone import x86 as X
from peimg import Img
from cfg import CFG
from thistrack import analyse, mem_this_off

VT   = 0x088F8570
NSLOT= 413
AC_W = capstone.CS_AC_WRITE
FORCE_STORE = {'movups','movdqu','movnps','movntps','movntdq'}
WATCH = {0x340,0x350,0x360,0x368,0x370,0x378,0x388,0x390,0x3dc,0x2e8,0x2e9,0x554,0x598,0x5a8,0x703,0xe8,0xf0,0xf8}

def is_store(i):
    if not i.operands: return None
    o = i.operands[0]
    if o.type != X.X86_OP_MEM: return None
    if (o.access & AC_W) or i.mnemonic in FORCE_STORE: return o
    return None

def main():
    im = Img()
    slots = []
    for k in range(NSLOT):
        va = struct.unpack_from('<Q', im.read(VT + 8*k, 8), 0)[0]
        if va == 0: slots.append((k, None)); continue
        rva = va - im.imagebase
        s = im.sec_of(rva)
        slots.append((k, rva if (s and s['name'] == '.text') else None))
    live = [(k,r) for k,r in slots if r]
    print(f"vtable {VT:#x}: {NSLOT} slots, {len(live)} resolve into .text")

    dark = 0; done = 0; failed = []
    hits = collections.defaultdict(list)
    for k, rva in live:
        if im.page_nonzero(rva) == 0:
            dark += 1; continue
        try:
            c, IN, OUT = analyse(im, rva)
        except Exception as e:
            failed.append((k, rva, str(e)[:60])); continue
        done += 1
        for a in sorted(c.insns):
            i = c.insns[a]; o = is_store(i)
            if o is None: continue
            st = IN.get(a)
            if st is None: continue
            t = mem_this_off(i, st, o)
            if t is None: continue
            if t in WATCH:
                hits[t].append((k, rva, a, f"{i.mnemonic} {i.op_str}"))
    print(f"analysed {done} functions; {dark} on DARK pages (unanalysable); {len(failed)} failures")
    for k,r,e in failed: print(f"   FAIL slot {k} {r:#x}: {e}")
    print()
    for off in sorted(hits):
        print(f"[+{off:#06x}] {len(hits[off])} store site(s):")
        seen = set()
        for k, fr, a, txt in hits[off]:
            key = (fr, a)
            if key in seen: continue
            seen.add(key)
            print(f"    slot {k:3d} fn {fr:#010x}  @{a:#010x}  {txt}")
    for off in sorted(WATCH):
        if off not in hits:
            print(f"[+{off:#06x}] NO store site found on the virtual surface")

if __name__ == '__main__':
    main()
