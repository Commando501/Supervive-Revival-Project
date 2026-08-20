#!/usr/bin/env python3
"""
Count rel32 CALL/JMP sites to the known folds inside a byte range of a cold image. Uncapped.

Every target is machine-computed (no hand arithmetic). Prints each site so a count can be audited
rather than trusted, and prints the range it actually scanned so an extent disagreement is visible.

usage: foldcalls.py <image> <startRVA-hex> <endRVA-hex> [more ranges...]
"""
import struct, sys, os

FOLDS = {
    0x0F7EC20: "ret 0            (c2 00 00)",
    0x0F7EB50: "xor eax,eax; ret (33 c0 c3)",
    0x0F7EB60: "xor al,al; ret   (32 c0 c3)",
    0x0B9E1F0: "mov al,1; ret    (b0 01 c3)",
    0x0FC6CF0: "xorps xmm0,xmm0; ret (0f 57 c0 c3)   <- the FIFTH fold, S131 lane D",
}


def load(path):
    d = open(path, 'rb').read()
    pe = struct.unpack_from('<I', d, 0x3C)[0]
    nsec = struct.unpack_from('<H', d, pe + 6)[0]
    optsz = struct.unpack_from('<H', d, pe + 20)[0]
    sh = pe + 24 + optsz
    for i in range(nsec):
        o = sh + i * 40
        if d[o:o + 8].rstrip(b'\0') == b'.text':
            vsz, va, rsz, ra = struct.unpack_from('<IIII', d, o + 8)
            return d, va, ra, rsz
    raise SystemExit("no .text")


def main():
    if len(sys.argv) < 4:
        print(__doc__); return 2
    img = sys.argv[1]
    d, tva, tra, trs = load(img)
    print("image %s   .text vaddr 0x%X rawptr 0x%X size 0x%X   (off==rva: %s)"
          % (os.path.basename(img), tva, tra, trs, tva == tra))
    args = sys.argv[2:]
    for k in range(0, len(args) - 1, 2):
        lo, hi = int(args[k], 16), int(args[k + 1], 16)
        print("\n=== range 0x%X .. 0x%X  (%d bytes) ===" % (lo, hi, hi - lo))
        hits = {}
        i = lo
        while i < hi - 4:
            op = d[i]
            if op in (0xE8, 0xE9):
                disp = struct.unpack_from('<i', d, i + 1)[0]
                tgt = (i + 5 + disp) & 0xFFFFFFFF
                if tgt in FOLDS:
                    hits.setdefault(tgt, []).append((i, 'call' if op == 0xE8 else 'jmp'))
            i += 1
        if not hits:
            print("  no fold calls (scanned every byte offset -- this is an UPPER bound scan, so a")
            print("  hit inside another instruction's bytes would show up; zero here means zero)")
        for t in sorted(hits):
            print("  -> 0x%07X  %-45s  %d site(s)" % (t, FOLDS[t], len(hits[t])))
            for a, kind in hits[t]:
                print("       %s at 0x%07X" % (kind, a))
    return 0


if __name__ == "__main__":
    sys.exit(main())
