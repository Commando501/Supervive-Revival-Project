#!/usr/bin/env python3
"""
S118 — recover the AccelByte lobby notif TMap<FString,uint8> from the LIVE process.

Container: .data RVA 0x9FFE2D0 = stock UE TMap<FString,uint8>
  +0x00 Elements.Data ptr      +0x08 ArrayNum   +0x0C ArrayMax
  +0x10 AllocationFlags inline  +0x40 Hash ptr  +0x48 HashSize
Element stride 32 (confirmed from Find fn RVA 0xFE6520: shl rbx,5):
  +0x00 FString{Data,Num,Max}   +0x10 uint8 value   +0x18 HashNextId  +0x1C HashIndex

HARNESS SELF-TEST is mandatory (method-rules 10 & 13) and runs first.
"""
import re
import subprocess
import sys

EXE = r"G:\git\Supervive Revival Project\tools\usmapdump\usmapdump.exe"
PROC = "SUPERVIVE-Win64-Shipping.exe"


def run(*args):
    p = subprocess.run([EXE, *args], capture_output=True, text=True)
    if p.returncode != 0:
        sys.exit("ABORT: usmapdump failed: %s %s" % (args, p.stderr[:400]))
    return p.stdout


HEX = re.compile(r"^\s+([0-9A-F]+)\s+((?:[0-9A-F]{2} )+)")


def peek(addr, n):
    """Return raw bytes read from ADDR."""
    out = run("peek", PROC, addr if isinstance(addr, str) else hex(addr), str(n))
    blob = bytearray()
    for line in out.splitlines():
        m = HEX.match(line)
        if not m:
            continue
        blob += bytes.fromhex(m.group(2).replace(" ", ""))
    if len(blob) < n:
        sys.exit("ABORT: short read at %s: got %d of %d bytes" % (addr, len(blob), n))
    return bytes(blob[:n])


def u64(b, o):
    return int.from_bytes(b[o:o + 8], "little")


def u32(b, o):
    return int.from_bytes(b[o:o + 4], "little")


# ---------------------------------------------------------------- self-test
print("=== HARNESS SELF-TEST ===")
# positive control: FString "LbS" global at RVA 0x9FFEBD0 (known-good, S117)
ctrl = peek("+0x9FFEBD0", 16)
cdata, cnum, cmax = u64(ctrl, 0), u32(ctrl, 8), u32(ctrl, 12)
cbuf = peek(hex(cdata), cnum * 2)
ctext = cbuf.decode("utf-16-le").rstrip("\x00")
assert ctext == "LbS", "POSITIVE CONTROL FAILED: got %r" % ctext
assert cnum == 4 and cmax == 8, "POSITIVE CONTROL FAILED: Num/Max %d/%d" % (cnum, cmax)
print("  [PASS] positive control: FString@0x9FFEBD0 -> %r (Num=%d Max=%d)" % (ctext, cnum, cmax))

# negative control: an address that is NOT an FString must not decode to a known name
neg = run("wstrings", PROC, "qqxxNotif", "500")
assert "found 0 hit(s)" in neg, "NEGATIVE CONTROL FAILED: qqxxNotif was found"
print("  [PASS] negative control: wstrings qqxxNotif -> 0 hits")
print()

# ---------------------------------------------------------------- container
print("=== CONTAINER: TMap @ .data RVA 0x9FFE2D0 ===")
hdr = peek("+0x9FFE2D0", 0x50)
elem_base = u64(hdr, 0x00)
num = u32(hdr, 0x08)
mx = u32(hdr, 0x0C)
alloc = [u32(hdr, 0x10 + 4 * i) for i in range(4)]
numbits = u32(hdr, 0x28)
maxbits = u32(hdr, 0x2C)
firstfree = u32(hdr, 0x30)
numfree = u32(hdr, 0x34)
hashptr = u64(hdr, 0x40)
hashsize = u32(hdr, 0x48)
print("  Elements.Data = 0x%X" % elem_base)
print("  ArrayNum      = %d   ArrayMax = %d" % (num, mx))
print("  AllocFlags    = %s  (popcount=%d)" % (
    [hex(a) for a in alloc], sum(bin(a).count("1") for a in alloc)))
print("  NumBits=%d MaxBits=%d FirstFreeIndex=%d NumFreeIndices=%d" % (
    numbits, maxbits, firstfree if firstfree != 0xFFFFFFFF else -1, numfree))
print("  Hash=0x%X HashSize=%d" % (hashptr, hashsize))
if num != 33:
    print("  !! WARNING: ArrayNum is %d, not 33" % num)
print()

# ---------------------------------------------------------------- elements
raw = peek(hex(elem_base), num * 32)
rows = []
for i in range(num):
    o = i * 32
    d, n, m = u64(raw, o), u32(raw, o + 8), u32(raw, o + 12)
    val = raw[o + 0x10]
    nxt = u32(raw, o + 0x18)
    hidx = u32(raw, o + 0x1C)
    allocated = bool(alloc[i // 32] >> (i % 32) & 1)
    if not allocated:
        rows.append((i, None, val, "SLOT NOT ALLOCATED"))
        continue
    if n <= 0 or n > 200 or d == 0:
        rows.append((i, None, val, "bad FString Data=0x%X Num=%d" % (d, n)))
        continue
    s = peek(hex(d), n * 2).decode("utf-16-le").rstrip("\x00")
    rows.append((i, s, val, "Data=0x%X Num=%d Max=%d next=%d hidx=%d" % (
        d, n, m, nxt if nxt != 0xFFFFFFFF else -1, hidx)))

print("=== ELEMENTS (map slot order) ===")
print("%-5s %-6s %-26s %s" % ("slot", "enum", "type name", "evidence"))
for i, s, val, ev in rows:
    print("%-5d %-6s %-26s %s" % (i, val, s if s else "<UNREADABLE>", ev))
print()

# ---------------------------------------------------------------- enum table
print("=== BY ENUM VALUE  (jump index = enum-1) ===")
byval = {}
for i, s, val, ev in rows:
    byval.setdefault(val, []).append((i, s))
dupes = {k: v for k, v in byval.items() if len(v) > 1}
if dupes:
    print("  !! DUPLICATE enum values: %s" % dupes)
missing = [v for v in range(1, 34) if v not in byval]
if missing:
    print("  !! enum values with NO entry: %s" % missing)
print("%-6s %-6s %-26s %s" % ("enum", "jmpidx", "type name", "map slot"))
for v in sorted(byval):
    for i, s in byval[v]:
        print("%-6d %-6d %-26s %d" % (v, v - 1, s, i))
