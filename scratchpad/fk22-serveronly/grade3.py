#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""FK-22 LINE 1 part 3: fold multiplicity, multi-image presence, enum values."""
import os, struct, glob, sys
import capstone
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from grade2 import Img, PD, extent, hexs, ROOT

MD = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
SINGLE = os.path.join(ROOT, "dumps", "tutorial-hero", "SUPERVIVE-Win64-Shipping.dump.exe")


def qrefs(img, rva):
    pat = struct.pack("<Q", img.base + rva)
    out, i = [], 0
    while True:
        i = img.buf.find(pat, i)
        if i < 0:
            break
        if i % 8 == 0 and img.sec(i):
            out.append(i)
        i += 1
    return out


def rel32_sites(img, rva):
    """byte-level e8/e9 rel32 landing exactly on rva, within .text"""
    buf = img.buf
    tb, te = 0x1000, 0x1000 + 0x7649000
    hits = []
    i = tb
    while i < te - 5:
        j = buf.find(b"\xe8", i, te - 5)
        k = buf.find(b"\xe9", i, te - 5)
        cands = [x for x in (j, k) if x >= 0]
        if not cands:
            break
        c = min(cands)
        d = struct.unpack_from("<i", buf, c + 1)[0]
        if c + 5 + d == rva:
            hits.append(c)
        i = c + 1
    return hits


def main():
    img = Img(SINGLE)

    print("=== pdata rows around the ServerOnly impl ===")
    for b, e in PD:
        if 0x1311700 <= b <= 0x1311A00:
            print("   0x%07X..0x%07X  (%d B)" % (b, e, e - b))

    print("\n=== body bytes, exact ===")
    for lbl, rva, n in [("ServerOnly IMPL", 0x1311870, 8),
                        ("fold 0xF7EC20", 0x0F7EC20, 8),
                        ("fold 0xF7EB50", 0x0F7EB50, 8),
                        ("fold 0xF7EB60", 0x0F7EB60, 8)]:
        print("   %-18s 0x%07X : %s" % (lbl, rva, hexs(img.read(rva, n))))

    print("\n=== FOLD MULTIPLICITY (image-wide, 8-aligned qword pointers) ===")
    for lbl, rva in [("ServerOnly/ClientOnly THUNK 0x52E12B0", 0x52E12B0),
                     ("ServerOnly IMPL          0x1311870", 0x1311870),
                     ("GoToPhase THUNK          0x5457200", 0x5457200),
                     ("GoToPhase IMPL           0x5601020", 0x5601020),
                     ("known 91-way execFoo     0x5254180", 0x5254180),
                     ("fold ret0                0x0F7EC20", 0x0F7EC20)]:
        r = qrefs(img, rva)
        bysec = {}
        for x in r:
            bysec[img.sec(x)[0]] = bysec.get(img.sec(x)[0], 0) + 1
        print("   %-40s qwords=%-5d %s" % (lbl, len(r), bysec))

    print("\n=== rel32 direct call/jmp sites (decrypted .text only) ===")
    for lbl, rva in [("ServerOnly IMPL 0x1311870", 0x1311870),
                     ("GoToPhase IMPL  0x5601020", 0x5601020),
                     ("fold ret0       0x0F7EC20", 0x0F7EC20)]:
        h = rel32_sites(img, rva)
        print("   %-28s sites=%-6d first: %s" % (lbl, len(h), [hex(x) for x in h[:8]]))

    print("\n=== MULTI-IMAGE PRESENCE ===")
    paths = sorted(glob.glob(os.path.join(ROOT, "dumps", "*.dump.exe")) +
                   glob.glob(os.path.join(ROOT, "dumps", "*", "*.dump.exe")))
    print("   %d images" % len(paths))
    for lbl, rva, n in [("ServerOnly IMPL 0x1311870", 0x1311870, 4),
                        ("ServerOnly THUNK 0x52E12B0 (first 16)", 0x52E12B0, 16),
                        ("GOLD-EMPTY 0x0F7EB50", 0x0F7EB50, 4)]:
        agg = {}
        for p in paths:
            i = Img(p)
            agg.setdefault(hexs(i.read(rva, n)), []).append(
                os.path.basename(os.path.dirname(p)) if os.path.basename(os.path.dirname(p)) != "dumps"
                else os.path.basename(p))
        print("   -- %s" % lbl)
        for k, v in agg.items():
            print("      %-50s x%2d  %s" % (k, len(v), ",".join(sorted(v))))

    print("\n=== .data registration records for ServerOnly / ClientOnly, across SINGLE-STATE images ===")
    for p in paths:
        if "merged" in os.path.basename(p):
            continue
        i = Img(p)
        rec = struct.unpack_from("<QQQ", i.buf, 0x9BBAFB8)
        rec2 = struct.unpack_from("<QQQ", i.buf, 0x9BB8A08)
        nm = i.buf[rec[0] - i.base: rec[0] - i.base + 16].split(b"\0")[0].decode("latin1", "replace") if rec[0] > i.base else "?"
        nm2 = i.buf[rec2[0] - i.base: rec2[0] - i.base + 16].split(b"\0")[0].decode("latin1", "replace") if rec2[0] > i.base else "?"
        print("   %-22s %-11s thunk=0x%07X impl=0x%07X | %-11s thunk=0x%07X impl=0x%07X" % (
            os.path.basename(os.path.dirname(p)), nm, rec[1] - i.base, rec[2] - i.base,
            nm2, rec2[1] - i.base, rec2[2] - i.base))


if __name__ == "__main__":
    main()
