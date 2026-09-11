#!/usr/bin/env python3
"""
S131 -- which of the live ALokiPlayerStates does the local PlayerController actually own?

RM_RIDEABLE refused to guess between two candidates (correctly). This answers it the principled
way rather than by picking one: read `APlayerController::PlayerState` off the live PC, which is the
same object the game itself would hand to the rider handoff.

Read-only RPM. usage: which_playerstate.py <PID> <BASE-hex>
"""
import ctypes, ctypes.wintypes as w, struct, sys

k32 = ctypes.WinDLL('kernel32', use_last_error=True)
k32.OpenProcess.restype = w.HANDLE
k32.ReadProcessMemory.argtypes = [w.HANDLE, w.LPCVOID, w.LPVOID, ctypes.c_size_t,
                                  ctypes.POINTER(ctypes.c_size_t)]

RVA_OBJOBJECTS = 0x9E38930
RVA_NAMEPOOL   = 0x9D81450
PERCHUNK, ITEMSTRIDE = 65536, 0x18
CLASS_OFF, NAME_OFF, SUPER_OFF, CHILDPROPS = 0x18, 0x20, 0x48, 0x58
FPROP_OFFSET, FIELD_NEXT = 0x44, 0x18

H = None
def rpm(a, n):
    b = (ctypes.c_char * n)(); g = ctypes.c_size_t(0)
    if not k32.ReadProcessMemory(H, ctypes.c_void_p(a), b, n, ctypes.byref(g)): return None
    return bytes(b[:g.value])

def u64(a):
    b = rpm(a, 8); return struct.unpack('<Q', b)[0] if b else 0
def u32(a):
    b = rpm(a, 4); return struct.unpack('<I', b)[0] if b else 0

def fname(nid, base):
    blk, off = nid >> 16, (nid & 0xFFFF) * 2
    bp = u64(base + RVA_NAMEPOOL + 0x10 + blk * 8)
    if not bp: return "?"
    hdr = rpm(bp + off, 2)
    if not hdr: return "?"
    h = struct.unpack('<H', hdr)[0]
    ln = h >> 6
    s = rpm(bp + off + 2, ln)
    return s.decode('utf-8', 'replace') if s else "?"

def nameof(o, base):
    return fname(u32(o + NAME_OFF), base)

def chain(cls, base):
    out, g = [], 0
    while cls and g < 12:
        out.append(nameof(cls, base)); cls = u64(cls + SUPER_OFF); g += 1
    return "<-".join(out)

def prop_off(cls, want, base):
    g = 0
    while cls and g < 12:
        f = u64(cls + CHILDPROPS); i = 0
        while f and i < 400:
            if nameof(f, base) == want:
                return u32(f + FPROP_OFFSET)
            f = u64(f + FIELD_NEXT); i += 1
        cls = u64(cls + SUPER_OFF); g += 1
    return None

def safe(x):
    return x.encode("ascii", "replace").decode("ascii")


def main():
    global H
    pid, base = int(sys.argv[1], 0), int(sys.argv[2], 16)
    H = k32.OpenProcess(0x0010 | 0x0400, False, pid)
    if not H:
        print("OpenProcess failed", ctypes.get_last_error()); return 1
    oo = base + RVA_OBJOBJECTS
    objects, num = u64(oo), struct.unpack('<i', rpm(oo + 0x14, 4))[0]
    print("NumElements=%d" % num)
    pcs, pss = [], []
    for ci in range((num + PERCHUNK - 1) // PERCHUNK):
        ch = u64(objects + ci * 8)
        if not ch: continue
        cnt = min(PERCHUNK, num - ci * PERCHUNK)
        blob = rpm(ch, cnt * ITEMSTRIDE)
        if not blob: continue
        for j in range(cnt):
            o = struct.unpack_from('<Q', blob, j * ITEMSTRIDE)[0]
            if not o or o & 7: continue
            c = u64(o + CLASS_OFF)
            if not c: continue
            n = nameof(o, base)
            if n.startswith("Default__") or "_GEN_VARIABLE" in n: continue
            ch_s = chain(c, base)
            # ⚠ EXACT segment match on "Actor", never a substring: "Actor" in "ActorComponent"
            #   is true and it is exactly the trap DpEvalClass in tutorial_launch.cpp warns about.
            #   The first cut used `in` and reported 1354 "PlayerControllers".
            segs = ch_s.split("<-")
            is_actor = "Actor" in segs
            if not is_actor: continue
            if any(x.endswith("PlayerController") or "PlayerController_" in x for x in segs):
                pcs.append((o, n, ch_s))
            elif any("LokiPlayerState" in x for x in segs):
                pss.append((o, n, ch_s))
    print("\nlive PlayerControllers: %d" % len(pcs))
    for o, n, c in pcs:
        cls = u64(o + CLASS_OFF)
        po = prop_off(cls, "PlayerState", base)
        ps = u64(o + po) if po is not None else 0
        psn = nameof(ps, base) if ps else "-"
        print("  PC 0x%X '%s'\n     chain=%s\n     PlayerState@0x%s = 0x%X '%s'  <== THIS is the one the game owns"
              % (o, safe(n), safe(c), ("%X" % po) if po is not None else "??", ps, safe(psn)))
    print("\nlive ALokiPlayerStates: %d" % len(pss))
    for i, (o, n, c) in enumerate(pss):
        print("  ps[%d] 0x%X '%s'\n        chain=%s" % (i, o, n, c))
    return 0

if __name__ == "__main__":
    sys.exit(main())
