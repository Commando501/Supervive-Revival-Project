# Minimal minidump parser: extract faulting exception address + resolve its module.
# usage: parse_minidump.py <dump.dmp>
import struct, sys, os

p = sys.argv[1]
d = open(p, 'rb').read()
assert d[:4] == b'MDMP', d[:4]
ver, nstreams, dirrva = struct.unpack_from('<III', d, 4)
streams = {}
for i in range(nstreams):
    stype, dsize, rva = struct.unpack_from('<III', d, dirrva + i*12)
    streams[stype] = (dsize, rva)

exc_code = exc_addr = None
if 6 in streams:  # ExceptionStream
    _, rva = streams[6]
    off = rva + 8  # skip ThreadId(4) + align(4)
    exc_code = struct.unpack_from('<I', d, off)[0]
    exc_addr = struct.unpack_from('<Q', d, off + 16)[0]
    nparm = struct.unpack_from('<I', d, off + 24)[0]
    params = [struct.unpack_from('<Q', d, off + 32 + j*8)[0] for j in range(min(nparm, 15))]
    print("ExceptionCode=0x%08X  ExceptionAddress=0x%X  nparm=%d params=%s" %
          (exc_code, exc_addr, nparm, [hex(x) for x in params]))

def rd_str(rva):
    if rva <= 0 or rva + 4 > len(d):
        return "?"
    ln = struct.unpack_from('<I', d, rva)[0]
    if ln <= 0 or ln > 1024 or rva + 4 + ln > len(d):
        return "?"
    return d[rva+4:rva+4+ln].decode('utf-16-le', 'replace')

sep = chr(92)  # backslash
mods = []
if 4 in streams:  # ModuleListStream
    _, rva = streams[4]
    nmod = struct.unpack_from('<I', d, rva)[0]
    base = rva + 4
    for i in range(nmod):
        m = base + i*108
        baseimg, sizeimg = struct.unpack_from('<QI', d, m)
        namerva = struct.unpack_from('<I', d, m + 20)[0]  # ModuleNameRva is at +20
        nm = rd_str(namerva).split(sep)[-1]
        mods.append((baseimg, sizeimg, nm))
    print("total modules: %d" % nmod)
    # modules bracketing the fault address
    smods = sorted(mods)
    print("\nmodules nearest fault 0x%X:" % exc_addr)
    for baseimg, sizeimg, nm in smods:
        if abs(baseimg - exc_addr) < 0x8000000 or (baseimg <= exc_addr < baseimg+sizeimg):
            mark = "  <== CONTAINS FAULT" if baseimg <= exc_addr < baseimg+sizeimg else ""
            print("  %-30s base=0x%X end=0x%X%s" % (nm, baseimg, baseimg+sizeimg, mark))
    def modof(addr):
        for baseimg, sizeimg, nm in mods:
            if baseimg <= addr < baseimg + sizeimg:
                return (nm, addr - baseimg)
        return None
    # --- faulting thread context: RSP/RIP, then walk the stack for return addresses ---
    if 6 in streams:
        _, erva = streams[6]
        ctx_ds, ctx_rva = struct.unpack_from('<II', d, erva + 160)  # ThreadContext MINIDUMP_LOCATION_DESCRIPTOR
        # CONTEXT_AMD64: Rsp @ +0x98, Rip @ +0xF8
        rsp = struct.unpack_from('<Q', d, ctx_rva + 0x98)[0]
        rip = struct.unpack_from('<Q', d, ctx_rva + 0xF8)[0]
        print("\nfaulting thread: RIP=0x%X RSP=0x%X" % (rip, rsp))
        # NB: RIP may be a poisoned/unmapped addr while RSP is a VALID stack (S77: anti-tamper
        # deliberate-crash jumps to a poisoned addr but leaves a real stack). For the CALL CHAIN
        # across ALL threads (the faulting frame is often wiped), use tools/re/dump_threads.py.
        # locate stack memory: try ThreadList (3), MemoryList (5), Memory64List (9)
        stackbytes = stackbase = None
        # --- ThreadList type 3: MINIDUMP_THREAD is 48 bytes; Stack.StartOfMemoryRange@+16, Stack.Memory(loc)@+24
        if not stackbytes and 3 in streams:
            _, trva = streams[3]
            nthr = struct.unpack_from('<I', d, trva)[0]
            for i in range(nthr):
                t = trva + 4 + i*48
                sstart = struct.unpack_from('<Q', d, t + 16)[0]
                sdsize, srva = struct.unpack_from('<II', d, t + 24)
                if sstart <= rsp < sstart + sdsize:
                    stackbase, stackbytes = sstart, d[srva:srva+sdsize]; break
        # --- MemoryList type 5: MINIDUMP_MEMORY_DESCRIPTOR is 16 bytes {StartOfMemoryRange(8), Memory:loc(8)}
        if not stackbytes and 5 in streams:
            _, mrva = streams[5]
            nmem = struct.unpack_from('<I', d, mrva)[0]
            for i in range(nmem):
                md = mrva + 4 + i*16
                sa = struct.unpack_from('<Q', d, md)[0]
                sz, sr = struct.unpack_from('<II', d, md + 8)
                if sa <= rsp < sa + sz:
                    stackbase, stackbytes = sa, d[sr:sr+sz]; break
        if not stackbytes and 9 in streams:
            _, mrva = streams[9]
            nranges, basrva = struct.unpack_from('<QQ', d, mrva)
            cur = basrva
            for i in range(nranges):
                sa, sz = struct.unpack_from('<QQ', d, mrva + 16 + i*16)
                if sa <= rsp < sa + sz:
                    stackbase, stackbytes = sa, d[cur:cur+sz]; break
                cur += sz
        if stackbytes:
            print("\n  stack return-address chain (callers):")
            shown = 0
            for off in range(rsp - stackbase, len(stackbytes) - 8, 8):
                v = struct.unpack_from('<Q', stackbytes, off)[0]
                mo = modof(v)
                if mo:
                    print("    [rsp+0x%04X] 0x%X  %s+0x%X" % (off - (rsp - stackbase), v, mo[0], mo[1]))
                    shown += 1
                    if shown >= 12: break
        else:
            print("  (stack memory for RSP not in dump)")
    hit = None
    for baseimg, sizeimg, nm in mods:
        if baseimg <= exc_addr < baseimg + sizeimg:
            hit = (baseimg, sizeimg, nm); break
    if hit:
        print("\n>>> FAULTING MODULE: %s  base=0x%X size=0x%X" % (hit[2], hit[0], hit[1]))
        print(">>> module-relative RVA: +0x%X" % (exc_addr - hit[0]))
        low = hit[2].lower()
        if 'supervive' in low:
            print(">>> => GAME-LOGIC / SUPERVIVE exe (compare +0x29xxxxx = under-replication TArray crash)")
        elif 'd3d12' in low or 'nvwgf' in low or 'nvd3d' in low:
            print(">>> => D3D12 / GPU RENDER WALL")
        else:
            print(">>> => other module: " + hit[2])
    else:
        print("\nexc_addr 0x%X not in any listed module" % exc_addr)
    print("\nkey modules:")
    for baseimg, sizeimg, nm in mods:
        if any(k in nm.lower() for k in ('supervive', 'd3d12', 'nvwgf', 'nvd3d', 'dxgi', 'nvcuda')):
            print("  %-34s base=0x%X size=0x%X" % (nm, baseimg, sizeimg))
