# All-threads minidump walker (S77). Complements parse_minidump.py:
#   parse_minidump.py = exception addr + faulting module.
#   dump_threads.py   = EVERY thread's RIP + stack return-addresses into any module (esp. SUPERVIVE.exe),
#                       plus the faulting thread's EXCEPTION-context registers + its exc-RSP call chain.
# Why: an anti-tamper / obfuscated-dispatch deliberate-crash (S77 finding) leaves RIP at a FIXED poisoned
#   addr in the system-DLL gap with a WIPED caller frame — parse_minidump's single-frame walk shows nothing.
#   The spawning/other threads (all captured in the dump) carry the real game-code context.
# usage: dump_threads.py <dump.dmp> [--all]   (--all prints every thread, else only game-touching threads)
import struct, sys

p = sys.argv[1]
show_all = '--all' in sys.argv[2:]
d = open(p, 'rb').read()
assert d[:4] == b'MDMP', d[:4]
_, nstreams, dirrva = struct.unpack_from('<III', d, 4)
streams = {}
for i in range(nstreams):
    stype, dsize, rva = struct.unpack_from('<III', d, dirrva + i*12)
    streams.setdefault(stype, (dsize, rva))

# ---- exception ----
exc_addr = faultTid = ctx_rva = None
if 6 in streams:
    _, rva = streams[6]
    faultTid = struct.unpack_from('<I', d, rva)[0]
    exc_addr = struct.unpack_from('<Q', d, rva + 8 + 16)[0]
    _, ctx_rva = struct.unpack_from('<II', d, rva + 160)
    print("Exception: addr=0x%X faultTid=%d" % (exc_addr, faultTid))

# ---- modules ----
sep = chr(92)
def rd_str(rva):
    if rva <= 0 or rva + 4 > len(d): return "?"
    ln = struct.unpack_from('<I', d, rva)[0]
    if ln <= 0 or ln > 1024 or rva + 4 + ln > len(d): return "?"
    return d[rva+4:rva+4+ln].decode('utf-16-le', 'replace')
mods = []
if 4 in streams:
    _, mrva = streams[4]
    for i in range(struct.unpack_from('<I', d, mrva)[0]):
        m = mrva + 4 + i*108
        b, s = struct.unpack_from('<QI', d, m)
        mods.append((b, s, rd_str(struct.unpack_from('<I', d, m + 20)[0]).split(sep)[-1]))
def modof(a):
    for b, s, nm in mods:
        if b <= a < b + s: return (nm, a - b)
    return None
game = next((m for m in mods if 'supervive' in m[2].lower()), None)
if game: print("SUPERVIVE base=0x%X size=0x%X" % (game[0], game[1]))

# ---- memory regions ----
regions = []
if 9 in streams:
    _, mr = streams[9]
    nranges, basrva = struct.unpack_from('<QQ', d, mr); cur = basrva
    for i in range(nranges):
        sa, sz = struct.unpack_from('<QQ', d, mr + 16 + i*16); regions.append((sa, sz, cur)); cur += sz
if 5 in streams:
    _, mr = streams[5]
    for i in range(struct.unpack_from('<I', d, mr)[0]):
        md = mr + 4 + i*16; sa = struct.unpack_from('<Q', d, md)[0]; sz, sr = struct.unpack_from('<II', d, md + 8)
        regions.append((sa, sz, sr))
def readmem(a, n):
    for sa, sz, fr in regions:
        if sa <= a < sa + sz:
            o = fr + (a - sa); return d[o:o + min(n, sz - (a - sa))]
    return None

def walk(rsp, limit=90, maxhits=16):
    hits = []; mem = readmem(rsp, limit*8)
    if not mem: return hits
    for off in range(0, len(mem) - 8, 8):
        v = struct.unpack_from('<Q', mem, off)[0]; mo = modof(v)
        if mo:
            hits.append((off, v, mo))
            if len(hits) >= maxhits: break
    return hits

# ---- faulting thread's EXCEPTION context (regs + exc-RSP chain) ----
if ctx_rva:
    names = ['Rax','Rcx','Rdx','Rbx','Rsp','Rbp','Rsi','Rdi','R8','R9','R10','R11','R12','R13','R14','R15']
    offs  = [0x78,0x80,0x88,0x90,0x98,0xA0,0xA8,0xB0,0xB8,0xC0,0xC8,0xD0,0xD8,0xE0,0xE8,0xF0]
    rip = struct.unpack_from('<Q', d, ctx_rva + 0xF8)[0]; rsp = struct.unpack_from('<Q', d, ctx_rva + 0x98)[0]
    print("\n== FAULTING EXC context ==\nRIP=0x%X RSP=0x%X" % (rip, rsp))
    print("regs:", ", ".join("%s=0x%X" % (n, struct.unpack_from('<Q', d, ctx_rva + o)[0]) for n, o in zip(names, offs)))
    ch = [h for h in walk(rsp) if 'supervive' in h[2][0].lower()]
    print("exc-RSP game-code chain:", ("EMPTY (caller frame wiped — anti-tamper/obfuscated dispatch signature)" if not ch else ""))
    for off, v, mo in ch: print("  [rsp+0x%04X] SUPERVIVE.exe+0x%X" % (off, mo[1]))

# ---- all threads ----
if 3 in streams:
    _, trva = streams[3]; nthr = struct.unpack_from('<I', d, trva)[0]
    print("\n== %d threads ==" % nthr)
    for i in range(nthr):
        t = trva + 4 + i*48; tid = struct.unpack_from('<I', d, t)[0]
        _, crva = struct.unpack_from('<II', d, t + 40)
        rip = struct.unpack_from('<Q', d, crva + 0xF8)[0]; rsp = struct.unpack_from('<Q', d, crva + 0x98)[0]
        rmo = modof(rip); hits = walk(rsp)
        ghits = [h for h in hits if 'supervive' in h[2][0].lower()]
        if not (show_all or tid == faultTid or ghits): continue
        print("\n-- tid=%d RIP=%s RSP=0x%X%s" % (tid, ("%s+0x%X" % rmo) if rmo else "0x%X(UNMAPPED)" % rip,
              rsp, "  <== FAULTING" if tid == faultTid else ""))
        for off, v, mo in hits:
            print("    [rsp+0x%04X] 0x%X  %s+0x%X%s" % (off, v, mo[0], mo[1], " <<<GAME" if 'supervive' in mo[0].lower() else ""))
