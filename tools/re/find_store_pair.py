# find_store_pair.py -- locate a function on a STRIPPED binary by the pair of fields it writes.
# OFFLINE. Reads a dumpimage capture; touches no process.
#
#   usage: find_store_pair.py <dumpFile> <dispA-hex> <dispB-hex> [window-hex]
#   e.g.:  find_store_pair.py dumps/tutorial-hero/SUPERVIVE-Win64-Shipping.dump.exe 408 410
#
# WHY (S111). UAbilitySystemComponent::InitAbilityActorInfo has no UFunction, no reflection name, no
# RTTI and no usable .pdata in this build -- but it is the only thing that writes BOTH OwnerActor
# (ASC+0x408) and AvatarActor (ASC+0x410). Searching by NAME failed three times this session; searching
# by BEHAVIOUR found it in one pass. The technique generalises: pick two adjacent fields a function is
# known to set, and let the encoding do the identification.
#
# Filters, in the order that made 98 candidates into 1:
#   1. both stores are REX.W `mov [reg+disp32], reg` (64-bit pointer stores, not immediates);
#   2. within `window` bytes of each other;
#   3. SAME base register (it is the same object);
#   4. DIFFERENT source registers (the two fields take different parameters).
# Then read the survivors -- (3) and (4) together are what cut it, and neither needs a symbol.
#
# ⚠ Finding the function START on this build has no cheap oracle, so the printed start is a HINT:
#   * .pdata is ENTIRELY ZERO -- the unwind table gives nothing. (The dumpimage manifest's
#     ".pdata 100.0%" counts READABLE PAGES, not content, and is misleading here.)
#   * there is NO int3 padding between functions (MEASURED: 171 0xCC bytes in a 2 MB .text sample), so
#     a backward 0xCC scan just runs to its limit and returns an address that decodes mid-instruction.
# What works is 16-byte alignment plus a shadow-space argument spill; see prologue(). Always
# disassemble from the hint and confirm by eye before citing or calling an address.
import sys

REGS = ['rax','rcx','rdx','rbx','rsp','rbp','rsi','rdi','r8','r9','r10','r11','r12','r13','r14','r15']

def stores(d, disp, lo, hi):
    """every `REX.W 89 /r [base+disp32], src` -> (addr, base, src)."""
    pat = disp.to_bytes(4, 'little'); out = []; i = lo
    while True:
        i = d.find(pat, i, hi)
        if i < 0: break
        rex, op, m = d[i-3], d[i-2], d[i-1]
        if 0x48 <= rex <= 0x4F and op == 0x89 and (m & 0xC0) == 0x80 and (m & 7) not in (4, 5):
            out.append((i - 3, (m & 7) | ((rex & 1) << 3), ((m >> 3) & 7) | ((rex & 4) << 1)))
        i += 1
    return out

# ⚠ Do NOT look for int3 (0xCC) padding in this build: MEASURED 171 0xCC bytes in a 2 MB .text sample,
# i.e. functions are NOT int3-padded here, and a backward 0xCC scan just runs to its limit and returns
# a garbage address that disassembles as mid-instruction. (It did exactly that to me once.) And .pdata
# is entirely zero, so the unwind table is no help either. What DOES work: functions are 16-byte
# aligned and open with a recognisable MSVC prologue.
# STRONG openers spill an incoming register argument to its shadow-space slot -- that essentially only
# happens in the first instructions of a function. WEAK ones (a bare push) occur mid-prologue too, so
# they are only a fallback: matching a weak opener first is how this returned base+0x447F420, sixteen
# bytes into a function that really starts at base+0x447F410.
_STRONG = (b'\x48\x89\x5c\x24', b'\x48\x89\x4c\x24', b'\x48\x89\x54\x24',
           b'\x48\x89\x74\x24', b'\x48\x89\x7c\x24')
_WEAK = (b'\x40\x53', b'\x40\x55', b'\x40\x56', b'\x40\x57', b'\x41\x54', b'\x41\x55',
         b'\x41\x56', b'\x41\x57', b'\x55', b'\x53', b'\x56', b'\x57',
         b'\x48\x83\xec', b'\x48\x81\xec')
def _frames(w):
    return (b'\x48\x83\xec' in w[:24] or b'\x48\x81\xec' in w[:24]
            or b'\x48\x8d\x6c\x24' in w[:24] or b'\x48\x8b\xec' in w[:24])
def prologue(d, addr, back=0x600):
    """Best-effort function start: nearest 16-byte-aligned MSVC prologue at or before addr.

    ⚠ A HINT, NOT AN ANSWER -- always disassemble from it and confirm by eye. This build gives the
    usual anchors nothing to work with: .pdata is entirely zero and there is no int3 padding between
    functions (MEASURED: 171 0xCC bytes in a 2 MB .text sample). Verified correct on
    UAbilitySystemComponent::InitAbilityActorInfo -> base+0x447F410."""
    for openers in (_STRONG, _WEAK):
        i = addr & ~0xF
        while i > addr - back:
            w = d[i:i+32]
            if any(w.startswith(o) for o in openers) and _frames(w):
                return i
            i -= 16
    return None

def main():
    if len(sys.argv) < 4:
        print(__doc__.split("# WHY")[0]); sys.exit(1)
    path = sys.argv[1]
    a_disp, b_disp = int(sys.argv[2], 16), int(sys.argv[3], 16)
    win = int(sys.argv[4], 16) if len(sys.argv) > 4 else 0x100
    d = open(path, 'rb').read()
    import struct
    pe = struct.unpack_from('<I', d, 0x3C)[0]
    ns = struct.unpack_from('<H', d, pe + 6)[0]; opt = struct.unpack_from('<H', d, pe + 20)[0]
    off = pe + 24 + opt
    lo = hi = None
    for i in range(ns):
        s = d[off+i*40:off+(i+1)*40]
        if s[0:8].rstrip(b'\x00') == b'.text':
            lo = struct.unpack_from('<I', s, 12)[0]; hi = lo + struct.unpack_from('<I', s, 8)[0]
    if lo is None: print("no .text section"); sys.exit(1)
    print("%s  .text 0x%X..0x%X" % (path, lo, hi))

    A = stores(d, a_disp, lo, hi); B = stores(d, b_disp, lo, hi)
    print("stores to [reg+0x%X]: %d      stores to [reg+0x%X]: %d" % (a_disp, len(A), b_disp, len(B)))
    cand = []
    for (xa, ba, sa) in A:
        for (xb, bb, sb) in B:
            if abs(xb - xa) <= win and ba == bb and sa != sb:
                cand.append((min(xa, xb), xa, xb, ba, sa, sb))
    cand.sort()
    print("same-base, different-source pairs within 0x%X: %d" % (win, len(cand)))
    print()
    seen = set()
    for (lowest, xa, xb, base, sa, sb) in cand:
        st = prologue(d, lowest)
        key = st if st else lowest
        if key in seen: continue
        seen.add(key)
        print("  pair +0x%-9X  [%s+0x%X] <- %-4s   [%s+0x%X] <- %-4s"
              % (lowest, REGS[base], a_disp, REGS[sa], REGS[base], b_disp, REGS[sb]))
        print("       function start HINT (confirm by disassembling): %s"
              % ("base+0x%X" % st if st else "not found within 0x400"))

if __name__ == "__main__":
    main()
