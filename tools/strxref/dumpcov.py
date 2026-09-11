#!/usr/bin/env python3
"""
dumpcov.py -- page-level coverage auditor for usmapdump dumpimage / mergedumps output.

Companion to strxref.py.  Answers: which dumps exist, what .text page coverage each
has, whether merged.dump.exe is actually a merge, and what a CORRECT merge would give.

A "covered" page here = a 4 KiB page that is not entirely zero.  In a flat dumpimage
image an unreadable (never-demand-decrypted) page is written as zeros, so for the
read-only .text section zero-page == not-decrypted is an exact proxy (a real all-zero
4 KiB code page does not occur).  For .data/.rdata the proxy is NOT valid -- see FK-3.

Usage:
  python dumpcov.py audit  <dumps-dir>          # per-dump coverage + union + novelty
  python dumpcov.py reloc  <image>              # base relocations per section
  python dumpcov.py cmptext <a> <b>             # .text byte-equality on shared pages
  python dumpcov.py union  <out.txt> <img...>   # union coverage of an explicit list
"""
import os
import sys
import struct

PAGE = 4096
ZERO = bytes(PAGE)


class Img:
    def __init__(self, path):
        self.path = path
        with open(path, "rb") as f:
            head = f.read(0x1000)
        if head[:2] != b"MZ":
            raise ValueError("not MZ: " + path)
        pe_off = struct.unpack_from("<I", head, 0x3C)[0]
        if head[pe_off:pe_off + 4] != b"PE\0\0":
            raise ValueError("not PE: " + path)
        coff = pe_off + 4
        machine, nsec = struct.unpack_from("<HH", head, coff)
        opt_size = struct.unpack_from("<H", head, coff + 16)[0]
        opt = coff + 20
        magic = struct.unpack_from("<H", head, opt)[0]
        if magic != 0x20B:
            raise ValueError("not PE32+")
        self.image_base = struct.unpack_from("<Q", head, opt + 24)[0]
        self.size_of_image = struct.unpack_from("<I", head, opt + 56)[0]
        self.secs = []
        st = opt + opt_size
        for i in range(nsec):
            o = st + i * 40
            name = head[o:o + 8].rstrip(b"\0").decode("ascii", "replace")
            vsize, vaddr, rawsize, rawptr = struct.unpack_from("<IIII", head, o + 8)
            self.secs.append((name, vaddr, vsize, rawsize, rawptr))
        self.size = os.path.getsize(path)

    def sec(self, name):
        for s in self.secs:
            if s[0] == name:
                return s
        return None


def page_bits(path, vaddr, vsize):
    """Return (bytearray of 1/0 per page, npages).  File offset == RVA (flat dump)."""
    n = (vsize + PAGE - 1) // PAGE
    bits = bytearray(n)
    with open(path, "rb") as f:
        f.seek(vaddr)
        CH = 1 << 24  # 16 MiB
        got = 0
        pi = 0
        while got < vsize:
            want = min(CH, vsize - got)
            buf = f.read(want)
            if not buf:
                break
            mv = memoryview(buf)
            for off in range(0, len(buf), PAGE):
                chunk = mv[off:off + PAGE]
                if len(chunk) == PAGE:
                    if chunk != ZERO:
                        bits[pi] = 1
                else:
                    if bytes(chunk).strip(b"\0"):
                        bits[pi] = 1
                pi += 1
            got += len(buf)
            if len(buf) < want:
                break
    return bits, n


def popcount(bits):
    return sum(bits)


def cmd_audit(dumps_dir):
    entries = []
    merged = os.path.join(dumps_dir, "merged.dump.exe")
    for root, dirs, files in os.walk(dumps_dir):
        for fn in files:
            if fn.endswith(".dump.exe"):
                p = os.path.join(root, fn)
                label = os.path.relpath(p, dumps_dir).replace("\\", "/")
                entries.append((label, p))
    entries.sort()

    print("=" * 96)
    print("PER-IMAGE .text PAGE COVERAGE  (page = 4096 B; covered = not all-zero)")
    print("=" * 96)
    print(f"{'image':<46} {'base':>14} {'pages':>7} {'covered':>8} {'pct':>7}")
    cov = {}
    meta = {}
    for label, p in entries:
        im = Img(p)
        t = im.sec(".text")
        bits, n = page_bits(p, t[1], t[2])
        cov[label] = bits
        meta[label] = im
        c = popcount(bits)
        print(f"{label:<46} 0x{im.image_base:012X} {n:7d} {c:8d} {100.0*c/n:6.2f}%")
    return cov, meta, entries


def cmd_reloc(path):
    im = Img(path)
    r = im.sec(".reloc")
    with open(path, "rb") as f:
        f.seek(r[1])
        data = f.read(r[2])
    # count relocs per target section
    counts = {}
    total = 0
    off = 0
    blocks = 0
    while off + 8 <= len(data):
        page_rva, blk = struct.unpack_from("<II", data, off)
        if blk == 0:
            break
        blocks += 1
        n = (blk - 8) // 2
        for i in range(n):
            e = struct.unpack_from("<H", data, off + 8 + i * 2)[0]
            typ = e >> 12
            if typ == 0:
                continue
            rva = page_rva + (e & 0xFFF)
            total += 1
            sec = "??"
            for nm, va, vs, rs, rp in im.secs:
                if va <= rva < va + vs:
                    sec = nm
                    break
            counts[sec] = counts.get(sec, 0) + 1
        off += blk
    print(f"reloc blocks: {blocks}   entries(type!=ABS): {total}")
    for k in sorted(counts, key=lambda k: -counts[k]):
        print(f"  {k:<10} {counts[k]:>10,}")
    return counts


def cmd_cmptext(a, b):
    ia, ib = Img(a), Img(b)
    ta, tb = ia.sec(".text"), ib.sec(".text")
    assert ta[1] == tb[1] and ta[2] == tb[2]
    ba, n = page_bits(a, ta[1], ta[2])
    bb, _ = page_bits(b, tb[1], tb[2])
    both = same = diff = 0
    fa = open(a, "rb")
    fb = open(b, "rb")
    difflist = []
    for i in range(n):
        if ba[i] and bb[i]:
            both += 1
            fa.seek(ta[1] + i * PAGE)
            fb.seek(tb[1] + i * PAGE)
            pa = fa.read(PAGE)
            pb = fb.read(PAGE)
            if pa == pb:
                same += 1
            else:
                diff += 1
                if len(difflist) < 10:
                    nd = sum(1 for x, y in zip(pa, pb) if x != y)
                    difflist.append((ta[1] + i * PAGE, nd))
    fa.close()
    fb.close()
    print(f"{os.path.basename(os.path.dirname(a))} vs {os.path.basename(os.path.dirname(b))}")
    print(f"  pages covered in BOTH : {both}")
    print(f"  byte-identical        : {same}  ({100.0*same/both if both else 0:.4f}%)")
    print(f"  differing             : {diff}")
    for rva, nd in difflist:
        print(f"     rva 0x{rva:08X}  {nd} differing bytes")
    print(f"  A-only pages: {sum(1 for i in range(n) if ba[i] and not bb[i])}")
    print(f"  B-only pages: {sum(1 for i in range(n) if bb[i] and not ba[i])}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "audit"
    if cmd == "audit":
        cmd_audit(sys.argv[2])
    elif cmd == "reloc":
        cmd_reloc(sys.argv[2])
    elif cmd == "cmptext":
        cmd_cmptext(sys.argv[2], sys.argv[3])
