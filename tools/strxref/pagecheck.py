#!/usr/bin/env python3
"""pagecheck.py -- is a given RVA's .text page decrypted in each dump?

Tests the 're-encryption of cold pages' hypothesis: if startup-only code (the PE
entry point, CRT init, dynamic initializers) is ZERO in a dump taken minutes later,
the packer re-encrypts cold pages and coverage is NOT monotonic in wall-clock time.
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dumpcov import Img, PAGE

DUMPS = r"G:\git\Supervive Revival Project\dumps"
NAMES = ["menu", "store", "roster", "missions", "loadout",
         "accountpass", "vmbuild", "toggles", "rcb"]

PROBES = [
    (0x751EFD0, "PE AddressOfEntryPoint (ran exactly once, at process start)"),
    (0x13454A0, "ProcessInternal -- the project's keystone hook (hot every frame)"),
    (0x5794480, "CheckAccountPassChanges (S83, menu-only)"),
    (0x57CA670, "seasonal VM builder entry (S83)"),
    (0x55DB370, "ULokiGameFeatureToggles::Get (S89)"),
    (0x587BE90, "UPartyModel::SetParty (S85)"),
    (0x585A570, "progression native ingester (S83)"),
    (0x12F4230, "FPrimaryAssetId::ToString (S83)"),
    (0x536A5A0, "gameplay BP-function-library registrar"),
]


def nonzero_page(path, rva):
    with open(path, "rb") as f:
        f.seek(rva & ~(PAGE - 1))
        b = f.read(PAGE)
    return bool(b.strip(b"\0")), b


def main():
    imgs = [("merged", os.path.join(DUMPS, "merged.dump.exe"))]
    imgs += [(n, os.path.join(DUMPS, n, "SUPERVIVE-Win64-Shipping.dump.exe")) for n in NAMES]
    hdr = f"{'probe':<58}" + "".join(f"{n[:6]:>8}" for n, _ in imgs)
    print(hdr)
    for rva, desc in PROBES:
        row = f"0x{rva:07X} {desc[:47]:<47}"
        for n, p in imgs:
            ok, _ = nonzero_page(p, rva)
            row += f"{'YES' if ok else '.':>8}"
        print(row)

    # how much of the region AROUND the entry point is decrypted?
    print()
    print("decrypted-page density in 256 KB windows around the entry point:")
    p = os.path.join(DUMPS, "merged.dump.exe")
    for lo in range(0x7500000, 0x7560000, 0x10000):
        cnt = 0
        for pg in range(16):
            ok, _ = nonzero_page(p, lo + pg * PAGE)
            cnt += ok
        print(f"  0x{lo:08X}-0x{lo+0xFFFF:08X}: {cnt:2d}/16 pages decrypted")


if __name__ == "__main__":
    main()
