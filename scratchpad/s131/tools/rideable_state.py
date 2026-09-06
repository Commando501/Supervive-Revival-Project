#!/usr/bin/env python3
"""
S131 -- read a live ULokiRideableComponent's PlayersInside array and its neighbours.

WHY: `AuthPlayerEnterWorld` (impl 0x55CCE70) bails SILENTLY unless the PlayerState is already IN
that array. Disassembled from dumps/merged4.dump.exe:

    0x055CCEC2  mov    rcx, [rcx + 0x120]        ; PlayersInside.Data
    0x055CCEC9  movsxd rax, dword [rdi + 0x128]  ; PlayersInside.Num
    0x055CCED0  lea    rdx, [rcx + rax*8]
    0x055CCED4  cmp    rcx, rdx
    0x055CCED7  je     <bail>                    ; EMPTY  -> silent bail
    0x055CCEE0  cmp    [rcx], r12                ; *it == PlayerState ?
    0x055CCEE3  je     <continue>
    0x055CCEE5  add    rcx, 8
    0x055CCEEC  jne    <loop>
    0x055CCEEE  jmp    <bail>                    ; NOT FOUND -> silent bail

This confirms the offsets BY NAME against the live reflection data before anything is written to
them. usage: rideable_state.py <PID> <BASE-hex> <COMP-ADDR-hex> [PlayerState-hex ...]
"""
import ctypes, ctypes.wintypes as w, struct, sys

k32 = ctypes.WinDLL('kernel32', use_last_error=True)
k32.OpenProcess.restype = w.HANDLE
k32.ReadProcessMemory.argtypes = [w.HANDLE, w.LPCVOID, w.LPVOID, ctypes.c_size_t,
                                  ctypes.POINTER(ctypes.c_size_t)]
RVA_NAMEPOOL = 0x9D81450
CLASS_OFF, NAME_OFF, SUPER_OFF, CHILDPROPS = 0x18, 0x20, 0x48, 0x58
FPROP_OFFSET, FPROP_ELEMSIZE, FIELD_NEXT, FFIELD_CLASS = 0x44, 0x34, 0x18, 0x08
H = None; BASE = 0


def rpm(a, n):
    b = (ctypes.c_char * n)(); g = ctypes.c_size_t(0)
    if not k32.ReadProcessMemory(H, ctypes.c_void_p(a), b, n, ctypes.byref(g)): return None
    return bytes(b[:g.value])


def u64(a):
    b = rpm(a, 8); return struct.unpack('<Q', b)[0] if b else 0
def u32(a):
    b = rpm(a, 4); return struct.unpack('<I', b)[0] if b else 0


# ⚠ FIRST CUT WAS WRONG AND PRODUCED PLAUSIBLE GARBAGE. It had `NAMEPOOL + 0x10 + blk*8` and
#   decoded as utf-8 with no wide-string handling; the block table starts at NAMEPOOL + blk*8 with
#   NO +0x10, and bit 0 of the header selects UTF-16. Copied verbatim from the known-good decoder in
#   tools/re/obj_by_class.py rather than re-derived -- the wrong version only announced itself
#   because a mojibake byte hit a print-encoding error, i.e. by luck.
def fname(nid):
    bp = u64(BASE + RVA_NAMEPOOL + (nid >> 16) * 8)
    if not (0x10000 <= bp < 0x0001000000000000 and (bp & 7) == 0): return "?"
    off = (nid & 0xFFFF) << 1
    h = rpm(bp + off, 2)
    if not h: return "?"
    hd = struct.unpack('<H', h)[0]
    ln, wide = hd >> 6, hd & 1
    if not (0 < ln < 200): return "?"
    b = rpm(bp + off + 2, ln * (2 if wide else 1))
    if not b: return "?"
    if wide:
        return "".join(chr(b[i * 2] | (b[i * 2 + 1] << 8)) for i in range(ln))
    return b.decode("latin1", "replace")


def nameof(o): return fname(u32(o + NAME_OFF))


def props(cls):
    """every property on cls + supers: (name, offset, elemsize, typename)"""
    out, g = [], 0
    while cls and g < 12:
        cn = nameof(cls)
        f, i = u64(cls + CHILDPROPS), 0
        while f and i < 400:
            fc = u64(f + FFIELD_CLASS)
            tn = fname(u32(fc)) if fc else "?"
            out.append((nameof(f), u32(f + FPROP_OFFSET), u32(f + FPROP_ELEMSIZE), tn, cn))
            f = u64(f + FIELD_NEXT); i += 1
        cls = u64(cls + SUPER_OFF); g += 1
    return out


def main():
    global H, BASE
    pid, BASE, comp = int(sys.argv[1], 0), int(sys.argv[2], 16), int(sys.argv[3], 16)
    H = k32.OpenProcess(0x0010 | 0x0400, False, pid)
    if not H:
        print("OpenProcess failed", ctypes.get_last_error()); return 1
    cls = u64(comp + CLASS_OFF)
    print("component 0x%X  class '%s'" % (comp, nameof(cls)))
    print()
    print("%-34s %-8s %-6s %-18s %s" % ("property", "offset", "size", "type", "owner"))
    for n, o, e, t, c in props(cls):
        mark = ""
        if o in (0x11C, 0x120, 0x128): mark = "   <== the AuthPlayerEnterWorld guard reads 0x120/0x128"
        print("%-34s 0x%-6X %-6d %-18s %s%s" % (n, o, e, t, c, mark))
    print()
    print("--- RAW at the guard's own offsets (what 0x55CCEC2/0x55CCEC9 actually read) ---")
    data = u64(comp + 0x120); num = u32(comp + 0x128); cap = u32(comp + 0x12C)
    cnt = u32(comp + 0x11C)
    print("  +0x11C PlayersInsideCount = %d" % cnt)
    print("  +0x120 Data = 0x%X   +0x128 Num = %d   +0x12C Max = %d" % (data, num, cap))
    if data and num:
        for i in range(min(num, 8)):
            p = u64(data + i * 8)
            print("     [%d] 0x%X '%s'" % (i, p, nameof(p) if p else "-"))
    else:
        print("     => ARRAY IS EMPTY. `cmp rcx,rdx / je` at 0x55CCED7 fires and the function")
        print("        bails SILENTLY -- which is exactly the null R4 produced.")
    for a in sys.argv[4:]:
        ps = int(a, 16)
        present = any(u64(data + i * 8) == ps for i in range(num)) if (data and num) else False
        print("  PlayerState 0x%X in PlayersInside? %s" % (ps, "YES" if present else "NO"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
