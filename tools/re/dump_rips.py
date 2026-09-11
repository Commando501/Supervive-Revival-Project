# Compact per-thread RIP summary from a minidump: tid + RIP(module+off) + top exe return-addr.
# Finds which threads are BUSY (not in an ntdll wait) = candidate lock holders.
# usage: dump_rips.py <dump.dmp> [gameTidHex]
import struct, sys
p = sys.argv[1]
gtid = int(sys.argv[2], 16) if len(sys.argv) > 2 else 0
d = open(p, 'rb').read()
assert d[:4] == b'MDMP'
_, nstreams, dirrva = struct.unpack_from('<III', d, 4)
streams = {}
for i in range(nstreams):
    st, ds, rva = struct.unpack_from('<III', d, dirrva + i*12); streams.setdefault(st, (ds, rva))
sep = chr(92)
def rd_str(rva):
    if rva <= 0 or rva + 4 > len(d): return "?"
    ln = struct.unpack_from('<I', d, rva)[0]
    if ln <= 0 or ln > 1024 or rva + 4 + ln > len(d): return "?"
    return d[rva+4:rva+4+ln].decode('utf-16-le', 'replace')
mods = []
_, mrva = streams[4]
for i in range(struct.unpack_from('<I', d, mrva)[0]):
    m = mrva + 4 + i*108
    b, s = struct.unpack_from('<QI', d, m)
    mods.append((b, s, rd_str(struct.unpack_from('<I', d, m+20)[0]).split(sep)[-1]))
mods.sort()
def modof(a):
    for b, s, nm in mods:
        if b <= a < b+s: return (nm, a-b)
    return None
exe = next((m for m in mods if 'supervive' in m[2].lower()), None)
exebase = exe[0] if exe else 0
# memory regions for stack walk
regions = []
if 9 in streams:
    _, mr = streams[9]; nr, bas = struct.unpack_from('<QQ', d, mr); cur = bas
    for i in range(nr):
        sa, sz = struct.unpack_from('<QQ', d, mr+16+i*16); regions.append((sa, sz, cur)); cur += sz
if 5 in streams:
    _, mr = streams[5]
    for i in range(struct.unpack_from('<I', d, mr)[0]):
        md = mr+4+i*16; sa = struct.unpack_from('<Q', d, md)[0]; sz, sr = struct.unpack_from('<II', d, md+8)
        regions.append((sa, sz, sr))
def readmem(a, n):
    for sa, sz, fr in regions:
        if sa <= a < sa+sz:
            o = fr+(a-sa); return d[o:o+min(n, sz-(a-sa))]
    return None
def top_exe(rsp, limit=120):
    mem = readmem(rsp, limit*8)
    if not mem: return []
    out = []
    for off in range(0, len(mem)-8, 8):
        v = struct.unpack_from('<Q', mem, off)[0]
        if exebase and exebase <= v < exebase + (exe[1]):
            out.append(v-exebase)
            if len(out) >= 6: break
    return out
_, trva = streams[3]; nthr = struct.unpack_from('<I', d, trva)[0]
print("threads=%d exeBase=0x%X gameTid=0x%X" % (nthr, exebase, gtid))
busy = []
for i in range(nthr):
    t = trva+4+i*48; tid = struct.unpack_from('<I', d, t)[0]
    _, crva = struct.unpack_from('<II', d, t+40)
    rip = struct.unpack_from('<Q', d, crva+0xF8)[0]; rsp = struct.unpack_from('<Q', d, crva+0x98)[0]
    mo = modof(rip); rm = ("%s+0x%X" % mo) if mo else "0x%X" % rip
    modname = mo[0].lower() if mo else "?"
    waiting = ('ntdll' in modname or 'win32u' in modname or 'kernelbase' in modname)
    tag = "  <== GAME" if tid == gtid else ("" if waiting else "  <== BUSY")
    tx = top_exe(rsp)
    line = "tid=0x%-6X %-28s%s  exe:[%s]" % (tid, rm, tag, " ".join("+0x%X" % x for x in tx))
    if tid == gtid or not waiting:
        print(line)
    if not waiting and tid != gtid:
        busy.append((tid, rm))
print("\n%d BUSY (non-wait) threads besides the game thread" % len(busy))
