#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""FK-22 LINE 1 -- grade ULokiBlueprintLibrary::ServerOnly. Part 2."""
import os, struct, sys, glob
import capstone

ROOT = r"G:\git\Supervive Revival Project"
COOKIE = 0x751DEB0
FOLDS = {0x0F7EC20: "ret 0 (c2 00 00)",
         0x0F7EB50: "xor eax,eax; ret (33 c0 c3)",
         0x0F7EB60: "xor al,al; ret (32 c0 c3)"}

PDATA = os.path.join(ROOT, "tools", "strxref", "index", "pdata_union.csv")


def load_pdata():
    rows = []
    with open(PDATA) as f:
        next(f)
        for ln in f:
            p = ln.strip().split(",")
            if len(p) < 3:
                continue
            rows.append((int(p[0], 16), int(p[1], 16)))
    rows.sort()
    return rows


PD = load_pdata()


def extent(rva):
    lo, hi = 0, len(PD) - 1
    best = None
    while lo <= hi:
        m = (lo + hi) // 2
        if PD[m][0] <= rva:
            best = PD[m]
            lo = m + 1
        else:
            hi = m - 1
    if best and best[0] <= rva < best[1]:
        return best
    return (rva, rva + 0x40)


class Img:
    def __init__(self, path):
        self.path = path
        self.buf = open(path, "rb").read()
        pe = struct.unpack_from("<I", self.buf, 0x3C)[0]
        opt = pe + 0x18
        self.base = struct.unpack_from("<Q", self.buf, opt + 0x18)[0]
        nsec = struct.unpack_from("<H", self.buf, pe + 6)[0]
        optsz = struct.unpack_from("<H", self.buf, pe + 0x14)[0]
        self.secs = []
        for i in range(nsec):
            o = pe + 0x18 + optsz + i * 40
            self.secs.append((self.buf[o:o + 8].rstrip(b"\0").decode("latin1"),
                              struct.unpack_from("<I", self.buf, o + 12)[0],
                              struct.unpack_from("<I", self.buf, o + 8)[0]))

    def sec(self, rva):
        for s in self.secs:
            if s[1] <= rva < s[1] + s[2]:
                return s
        return None

    def read(self, rva, n):
        return self.buf[rva:rva + n]

    def zero_page(self, rva):
        p = rva & ~0xFFF
        return self.buf[p:p + 0x1000] == b"\0" * 0x1000


MD = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)


def hexs(b):
    return " ".join("%02x" % x for x in b)


def full_disasm(img, rva, show=True, tag=""):
    b, e = extent(rva)
    if b != rva:
        b, e = rva, rva + 0x60
    n = e - b
    calls = []
    if show:
        print("   [%s] 0x%07X..0x%07X  (%d B)  zeropage=%s" % (tag, b, e, n, img.zero_page(rva)))
        print("   bytes[0:16]: %s" % hexs(img.read(rva, 16)))
    for ins in MD.disasm(img.read(b, n), b):
        if show:
            print("     %07X  %-8s %s" % (ins.address, ins.mnemonic, ins.op_str))
        if ins.mnemonic in ("call", "jmp") and ins.op_str.startswith("0x"):
            t = int(ins.op_str, 16)
            if t != COOKIE and not (b <= t < e):
                calls.append((ins.address, ins.mnemonic, t))
    return calls, (b, e)


def main():
    single = os.path.join(ROOT, "dumps", "tutorial-hero", "SUPERVIVE-Win64-Shipping.dump.exe")
    img = Img(single)
    print("IMAGE = %s   base=0x%X\n" % (single, img.base))

    print("############ STEP 2 -- THUNKS ############")
    thunks = [("ULokiBlueprintLibrary::ServerOnly", 0x52E12B0),
              ("ULokiBlueprintLibrary::ClientOnly (ICF twin)", 0x52E12B0),
              ("GOLD-EMPTY ALokiGameMode::SpawnPlayer", 0x534C070),
              ("GOLD-REAL  ALokiRoundGameMode::GoToPhase", 0x5457200)]
    impls = {}
    done = set()
    for lbl, t in thunks:
        if t in done:
            print("\n-- %s : SAME THUNK 0x%07X (ICF fold) -- see above" % (lbl, t))
            impls[lbl] = impls[[k for k in impls if True][-1]] if impls else None
            continue
        done.add(t)
        print("\n-- %s : thunk 0x%07X" % (lbl, t))
        calls, _ = full_disasm(img, t, tag="thunk")
        print("   outbound direct call/jmp (cookie excluded): %s" %
              [(hex(a), m, hex(x)) for a, m, x in calls])
        impls[lbl] = calls[-1][2] if calls else None
        print("   ==> LAST DIRECT CALL / IMPL = %s" % (impls[lbl] and hex(impls[lbl])))

    print("\n############ STEP 3 -- IMPL BODIES ############")
    bodies = [("ServerOnly IMPL", impls["ULokiBlueprintLibrary::ServerOnly"]),
              ("GOLD-EMPTY SpawnPlayer IMPL", impls["GOLD-EMPTY ALokiGameMode::SpawnPlayer"]),
              ("GOLD-REAL GoToPhase IMPL", impls["GOLD-REAL  ALokiRoundGameMode::GoToPhase"]),
              ("GOLD-REAL AddTeamDropEvent IMPL", 0x557EAE0)]
    for lbl, rva in bodies:
        print("\n-- %s = %s" % (lbl, rva and hex(rva)))
        if rva is None:
            continue
        full_disasm(img, rva, tag="impl")
        b, e = extent(rva)
        sz = (e - b) if b == rva else "?"
        g = "COVERAGE-BLOCKED" if img.zero_page(rva) else (
            "EMPTY-STUB (%s)" % FOLDS[rva] if rva in FOLDS else "REAL / CONST-BODY")
        print("   SIZE(pdata) = %s   GRADE = %s" % (sz, g))


if __name__ == "__main__":
    main()
