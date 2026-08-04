#!/usr/bin/env python3
"""
mdpdata.py -- recover the missing .pdata (x64 unwind / RUNTIME_FUNCTION table) from a
UE crash minidump's FunctionTableStream (MINIDUMP_STREAM_TYPE 13).

Why this exists
---------------
This build's on-disk .pdata is packer-encrypted and the live in-memory .pdata is 100%
zeroed, so every function boundary in dumps/merged.dump.exe is recovered heuristically.
But SEH still has to work at runtime, which means the loader/packer must publish the
real table somewhere the OS can find it -- a DYNAMIC function table.  MiniDumpWriteDump
serializes dynamic function tables into stream 13.  86 crash minidumps exist under
%LOCALAPPDATA%\\SUPERVIVE\\Saved\\Crashes.

Layout (Windows SDK, minidumpapiset.h):
  MINIDUMP_FUNCTION_TABLE_STREAM { u32 SizeOfHeader, SizeOfDescriptor,
                                   SizeOfNativeDescriptor, SizeOfFunctionEntry,
                                   NumberOfDescriptors, SizeOfAlignPad }
  then NumberOfDescriptors x:
    MINIDUMP_FUNCTION_TABLE_DESCRIPTOR { u64 MinimumAddress, MaximumAddress,
                                         u64 BaseAddress, u32 EntryCount,
                                         u32 SizeOfAlignPad }
    + SizeOfNativeDescriptor bytes of RAW native descriptor
    + EntryCount x SizeOfFunctionEntry bytes of entries (x64 RUNTIME_FUNCTION = 12 B:
      u32 BeginAddress, u32 EndAddress, u32 UnwindInfoAddress -- all RVAs from BaseAddress)
    + SizeOfAlignPad bytes

Usage:
  python mdpdata.py info   <UEMinidump.dmp>
  python mdpdata.py verify <UEMinidump.dmp>            # cross-check vs merged.dump.exe
  python mdpdata.py export <UEMinidump.dmp> <out.bin>  # raw .pdata blob (RVA-sorted)
  python mdpdata.py csv    <UEMinidump.dmp> <out.csv>  # begin,end,size per function
  python mdpdata.py survey <crashes-dir>               # all 86 dumps: which have it
"""
import os
import sys
import struct
import glob

MERGED = r"G:\git\Supervive Revival Project\dumps\merged.dump.exe"
TEXT_RVA, TEXT_SIZE = 0x1000, 0x7649000
PDATA_RVA, PDATA_SIZE = 0xA0B7000, 0x5FE000
PAGE = 4096


def streams(path):
    with open(path, "rb") as f:
        hdr = f.read(32)
        if hdr[:4] != b"MDMP":
            raise ValueError("not a minidump: " + path)
        sig, ver, nstreams, dir_rva, chks, ts, flags = struct.unpack("<IIIIIIQ", hdr[:32])
        f.seek(dir_rva)
        dirbuf = f.read(nstreams * 12)
        out = []
        for i in range(nstreams):
            st, sz, rva = struct.unpack_from("<III", dirbuf, i * 12)
            out.append((st, sz, rva))
        return out


def read_at(path, rva, size):
    with open(path, "rb") as f:
        f.seek(rva)
        return f.read(size)


def parse_ft(path, quiet=False):
    ss = streams(path)
    ft = [s for s in ss if s[0] == 13]
    if not ft:
        return None
    st, sz, rva = ft[0]
    blob = read_at(path, rva, sz)
    (soh, sod, sond, sofe, nd, pad) = struct.unpack_from("<IIIIII", blob, 0)
    if not quiet:
        print(f"  FunctionTableStream: {sz} bytes @ 0x{rva:X}")
        print(f"    SizeOfHeader={soh} SizeOfDescriptor={sod} SizeOfNativeDescriptor={sond}")
        print(f"    SizeOfFunctionEntry={sofe} NumberOfDescriptors={nd} SizeOfAlignPad={pad}")
    off = soh
    descs = []
    for i in range(nd):
        # Tolerate truncated streams: MiniDumpWriteDump caps the stream, and some of
        # these dumps declare more descriptors than were actually written.  Parse what
        # is there and stop -- the exe descriptor is near the front.
        if off + sod > len(blob):
            if not quiet:
                print(f"    [truncated after {i} of {nd} descriptors]")
            break
        mn, mx, base, cnt, apad = struct.unpack_from("<QQQII", blob, off)
        off += sod + sond
        if off + cnt * sofe > len(blob):
            if not quiet:
                print(f"    [descriptor {i} entries truncated: want {cnt}]")
            break
        ents = blob[off:off + cnt * sofe]
        off += cnt * sofe + apad
        descs.append(dict(min=mn, max=mx, base=base, count=cnt, entries=ents, esize=sofe))
    return descs


def cmd_info(path):
    print(os.path.basename(os.path.dirname(path)))
    ss = streams(path)
    names = {3: "ThreadList", 4: "ModuleList", 5: "MemoryList", 6: "Exception",
             7: "SystemInfo", 9: "Memory64List", 12: "HandleData", 13: "FunctionTable",
             14: "UnloadedModuleList", 15: "MiscInfo", 16: "MemoryInfoList",
             17: "ThreadInfoList", 21: "SystemMemoryInfo", 22: "ProcessVmCounters"}
    print("  streams: " + ", ".join(f"{names.get(t, t)}({sz})" for t, sz, r in ss if sz))
    descs = parse_ft(path)
    if not descs:
        print("  NO FunctionTableStream")
        return
    for i, d in enumerate(descs):
        span = d["max"] - d["min"]
        print(f"    [{i}] base=0x{d['base']:012X} min=0x{d['min']:012X} max=0x{d['max']:012X}"
              f" span={span/1048576:8.2f} MB  entries={d['count']:,}")
        if d["count"] and d["esize"] == 12:
            e = d["entries"]
            b0, e0, u0 = struct.unpack_from("<III", e, 0)
            bl, el, ul = struct.unpack_from("<III", e, (d["count"] - 1) * 12)
            print(f"         first RVA 0x{b0:X}..0x{e0:X}   last RVA 0x{bl:X}..0x{el:X}")


def sane(descs, esize=12):
    """Return the descriptor whose entries look like the exe's .text RUNTIME_FUNCTIONs."""
    best = None
    for d in descs:
        if d["esize"] != 12 or d["count"] < 1000:
            continue
        e = d["entries"]
        b0, e0, u0 = struct.unpack_from("<III", e, 0)
        if TEXT_RVA <= b0 < TEXT_RVA + TEXT_SIZE:
            if best is None or d["count"] > best["count"]:
                best = d
    return best


def cmd_verify(path):
    descs = parse_ft(path)
    d = sane(descs)
    if not d:
        print("no .text-shaped descriptor")
        return
    e = d["entries"]
    n = d["count"]
    print(f"\ndescriptor: base=0x{d['base']:012X}  {n:,} entries")

    # --- structural sanity ---
    bad_order = bad_range = zero = 0
    prev_end = 0
    sizes = []
    begins = []
    for i in range(n):
        b, en, u = struct.unpack_from("<III", e, i * 12)
        begins.append(b)
        if not (TEXT_RVA <= b < TEXT_RVA + TEXT_SIZE):
            bad_range += 1
        if en <= b:
            zero += 1
        else:
            sizes.append(en - b)
        if b < prev_end:
            bad_order += 1
        prev_end = en
    print(f"  entries outside .text        : {bad_range}")
    print(f"  end<=begin                   : {zero}")
    print(f"  out-of-order / overlapping   : {bad_order}")
    if sizes:
        sizes_s = sorted(sizes)
        print(f"  function size: min {min(sizes)}  median {sizes_s[len(sizes_s)//2]}"
              f"  mean {sum(sizes)/len(sizes):.0f}  max {max(sizes):,}")
        print(f"  total bytes covered          : {sum(sizes):,} "
              f"({100.0*sum(sizes)/TEXT_SIZE:.2f}% of .text VSize)")

    # --- cross-check against the merged image ---
    with open(MERGED, "rb") as f:
        img = f.read()

    def page_ok(rva):
        p = rva & ~(PAGE - 1)
        return img[p:p + PAGE].strip(b"\0") != b""

    # 1) do entry points land on decrypted pages, and do they look like prologues?
    import collections
    firstbytes = collections.Counter()
    checked = dec = 0
    step = max(1, n // 20000)
    for i in range(0, n, step):
        b, en, u = struct.unpack_from("<III", e, i * 12)
        if not page_ok(b):
            continue
        dec += 1
        firstbytes[img[b:b + 4].hex()] += 1
        checked += 1
    print(f"\n  sampled {n//step:,} entries; {dec:,} on decrypted pages")
    print("  most common first-4-bytes at entry (prologue signature):")
    for k, v in firstbytes.most_common(12):
        print(f"    {k}  {v:5d}  ({100.0*v/checked:5.1f}%)")

    # 2) alignment
    al = collections.Counter()
    for i in range(0, n, max(1, n // 50000)):
        b, en, u = struct.unpack_from("<III", e, i * 12)
        al[b & 15] += 1
    tot = sum(al.values())
    print(f"\n  entry alignment: 16-aligned {100.0*al[0]/tot:.1f}%,"
          f" 8-aligned-only {100.0*al[8]/tot:.1f}%, other {100.0*(tot-al[0]-al[8])/tot:.1f}%")

    # 3) agreement with the project's ground-truth entries
    gt = [0x13454A0, 0x5794480, 0x57CA670, 0x55DB370, 0x587BE90, 0x585A570,
          0x12F4230, 0x536A5A0, 0x57C8130, 0x57AB180, 0x57DF4B0, 0x57BB560,
          0x5794480, 0x587C699, 0x751EFD0]
    bs = begins
    import bisect
    print("\n  ground-truth check (project-recorded addresses vs table):")
    for g in sorted(set(gt)):
        i = bisect.bisect_right(bs, g) - 1
        if i < 0:
            print(f"    0x{g:07X}  -> no entry")
            continue
        b, en, u = struct.unpack_from("<III", e, i * 12)
        tag = "EXACT ENTRY" if b == g else f"inside {b:#x}..{en:#x} (+{g-b})"
        if not (b <= g < en):
            tag = f"NOT COVERED (prev {b:#x}..{en:#x})"
        print(f"    0x{g:07X}  {tag}   size={en-b}")


def cmd_export(path, out):
    descs = parse_ft(path, quiet=True)
    d = sane(descs)
    with open(out, "wb") as f:
        f.write(d["entries"])
    print(f"wrote {len(d['entries']):,} bytes ({d['count']:,} RUNTIME_FUNCTIONs) to {out}")


def cmd_csv(path, out):
    descs = parse_ft(path, quiet=True)
    d = sane(descs)
    e = d["entries"]
    with open(out, "w") as f:
        f.write("begin_rva,end_rva,size,unwind_rva\n")
        for i in range(d["count"]):
            b, en, u = struct.unpack_from("<III", e, i * 12)
            f.write(f"0x{b:X},0x{en:X},{en-b},0x{u:X}\n")
    print(f"wrote {d['count']:,} rows to {out}")


def cmd_survey(root):
    dirs = sorted(glob.glob(os.path.join(root, "UECC-*")))
    print(f"{len(dirs)} crash dirs")
    have = 0
    counts = {}
    for dd in dirs:
        p = os.path.join(dd, "UEMinidump.dmp")
        if not os.path.exists(p):
            print(f"  {os.path.basename(dd)[:46]:<46} NO UEMinidump.dmp")
            continue
        try:
            descs = parse_ft(p, quiet=True)
        except Exception as ex:
            print(f"  {os.path.basename(dd)[:46]:<46} ERR {ex}")
            continue
        if not descs:
            print(f"  {os.path.basename(dd)[:46]:<46} no stream 13")
            continue
        d = sane(descs)
        if not d:
            print(f"  {os.path.basename(dd)[:46]:<46} stream 13 but no .text descriptor")
            continue
        have += 1
        counts[os.path.basename(dd)] = (d["count"], d["base"], os.path.getsize(p))
    print(f"\n{have}/{len(dirs)} minidumps carry a .text RUNTIME_FUNCTION table")
    vals = sorted(set(c for c, b, s in counts.values()))
    print(f"distinct entry counts across all of them: {vals}")
    for k in sorted(counts)[:6]:
        c, b, s = counts[k]
        print(f"  {k[:46]:<46} {c:,} entries  base 0x{b:012X}  ({s/1048576:.1f} MB)")


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "info":
        cmd_info(sys.argv[2])
    elif cmd == "verify":
        cmd_verify(sys.argv[2])
    elif cmd == "export":
        cmd_export(sys.argv[2], sys.argv[3])
    elif cmd == "csv":
        cmd_csv(sys.argv[2], sys.argv[3])
    elif cmd == "survey":
        cmd_survey(sys.argv[2])
