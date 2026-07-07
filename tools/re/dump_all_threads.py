# Walk EVERY thread's stack in a minidump; print module-resolved return-address chains,
# highlighting SUPERVIVE-Win64-Shipping.exe frames (the game call context at crash time).
# usage: dump_all_threads.py <dump.dmp> [exe_rva_only]
import struct, sys

p = sys.argv[1]
exe_only = len(sys.argv) > 2
d = open(p, 'rb').read()
assert d[:4] == b'MDMP'
ver, nstreams, dirrva = struct.unpack_from('<III', d, 4)
streams = {}
for i in range(nstreams):
    st, ds, rva = struct.unpack_from('<III', d, dirrva + i*12)
    streams.setdefault(st, (ds, rva))

sep = chr(92)
def rd_str(rva):
    if rva <= 0 or rva + 4 > len(d): return "?"
    ln = struct.unpack_from('<I', d, rva)[0]
    if ln <= 0 or ln > 1024 or rva + 4 + ln > len(d): return "?"
    return d[rva+4:rva+4+ln].decode('utf-16-le', 'replace')

mods = []
_, mrva = streams[4]
nmod = struct.unpack_from('<I', d, mrva)[0]
exebase = 0
for i in range(nmod):
    m = mrva + 4 + i*108
    b, s = struct.unpack_from('<QI', d, m)
    nm = rd_str(struct.unpack_from('<I', d, m+20)[0]).split(sep)[-1]
    mods.append((b, s, nm))
    if nm.lower() == 'supervive-win64-shipping.exe':
        exebase = b
mods.sort()
import bisect
_bases = [m[0] for m in mods]

def modof(a):
    if a < 0x10000: return None
    i = bisect.bisect_right(_bases, a) - 1
    if 0 <= i < len(mods):
        b, s, nm = mods[i]
        if b <= a < b + s:
            return (nm, a - b)
    return None

# thread stacks: ThreadList (3): MINIDUMP_THREAD is 48 bytes; Stack.Start@+16, Stack.Mem(loc)@+24
_, trva = streams[3]
nthr = struct.unpack_from('<I', d, trva)[0]
print("threads: %d   exeBase=0x%X" % (nthr, exebase))
for i in range(nthr):
    t = trva + 4 + i*48
    tid = struct.unpack_from('<I', d, t)[0]
    sstart = struct.unpack_from('<Q', d, t + 16)[0]
    sdsize, srva = struct.unpack_from('<II', d, t + 24)
    ctx_ds, ctx_rva = struct.unpack_from('<II', d, t + 40)
    rip = rsp = 0
    if ctx_rva and ctx_rva + 0x100 <= len(d):
        rsp = struct.unpack_from('<Q', d, ctx_rva + 0x98)[0]
        rip = struct.unpack_from('<Q', d, ctx_rva + 0xF8)[0]
    stk = d[srva:srva+sdsize]
    # collect module-resolved return addrs
    frames = []
    for off in range(0, len(stk) - 8, 8):
        v = struct.unpack_from('<Q', stk, off)[0]
        mo = modof(v)
        if mo:
            frames.append((v, mo))
    exe_frames = [f for f in frames if f[1][0].lower() == 'supervive-win64-shipping.exe']
    if exe_only and not exe_frames:
        continue
    ripmod = modof(rip)
    riptag = ("%s+0x%X" % ripmod) if ripmod else ("0x%X<no-mod>" % rip)
    print("\n--- thread %d (tid=0x%X)  RIP=%s  RSP=0x%X  exeFrames=%d ---" % (i, tid, riptag, rsp, len(exe_frames)))
    # print the exe frames (the game call context) + a few top module frames
    shown = 0
    seen = set()
    for v, mo in frames:
        key = (mo[0], mo[1])
        if key in seen: continue
        seen.add(key)
        star = "  <== EXE" if mo[0].lower() == 'supervive-win64-shipping.exe' else ""
        if mo[0].lower() == 'supervive-win64-shipping.exe' or shown < 6:
            print("   0x%X  %s+0x%X%s" % (v, mo[0], mo[1], star))
            shown += 1
        if shown > 40: break
