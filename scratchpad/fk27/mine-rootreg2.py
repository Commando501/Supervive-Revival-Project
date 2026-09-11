# What IS the 49,307-element array at base+0x99D3CA0 live? Characterise it instead of assuming.
# Controls: a real root registry should be SMALL and its members should be high-index bit30 objects.
import os, sys, struct
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "tools", "re"))
import item_watch as IW
STRIDE, PERCHUNK, ITEM_FMT = IW.STRIDE, IW.PERCHUNK, IW.ITEM_FMT
ROOTBIT = 30
KEEPMASK = 0x4E100000

pid = IW.autodetect_pid(); base = IW.autodetect_base(pid)
w = IW.Watch(pid, base, lambda s: None)
objectsPtr, numEl = w.header()
chunks = w.chunks(objectsPtr, numEl)
live = {}
for ci, (addr, cnt) in enumerate(chunks):
    if not addr: continue
    d = w.rpm_into(addr, cnt * STRIDE)
    if d is None: continue
    for j, (o, fl, cl, se) in enumerate(struct.iter_unpack(ITEM_FMT, d.tobytes())):
        if o: live[ci * PERCHUNK + j] = (o, fl & 0xFFFFFFFF)
first_free = next(i for i in range(numEl) if i not in live)
hi_rooted = {i for i, (o, fl) in live.items() if i >= first_free and (fl & (1 << ROOTBIT))}
keepmask_n = sum(1 for i, (o, fl) in live.items() if fl & KEEPMASK)
print("live=%d  ObjFirstGCIndex=%d  high-index bit30=%d" % (len(live), first_free, len(hi_rooted)))
print("live objects matching keep mask 0x%08X: %d   <-- compare to ArrayNum below" % (KEEPMASK, keepmask_n))

raw = w.rpm(base + 0x99D3CA0, 0x10)
dataPtr, num, mx = struct.unpack("<Qii", raw)
print("\narray: Data=0x%X Num=%d Max=%d" % (dataPtr, num, mx))
blob = w.rpm(dataPtr, min(num, 60000) * 12 + 64)
vals = [struct.unpack_from("<i", blob, k * 12)[0] for k in range(min(num, 60000))]
valid = [v for v in vals if 0 <= v < numEl and v in live]
print("stride-12 dword0: %d slots, %d are LIVE indices (%.1f%%)"
      % (len(vals), len(valid), 100.0 * len(valid) / max(1, len(vals))))
print("  sorted ascending? %s" % (valid == sorted(valid)))
print("  min=%s max=%s" % (min(valid) if valid else None, max(valid) if valid else None))
below = sum(1 for v in valid if v < first_free)
print("  below ObjFirstGCIndex: %d   above: %d" % (below, len(valid) - below))
rb = sum(1 for v in valid if live[v][1] & (1 << ROOTBIT))
km = sum(1 for v in valid if live[v][1] & KEEPMASK)
print("  carrying bit%d: %d (%.1f%%)   carrying keep mask: %d (%.1f%%)"
      % (ROOTBIT, rb, 100.0*rb/max(1,len(valid)), km, 100.0*km/max(1,len(valid))))
print("  contains all 32 high-index rooted? %s (missing %s)"
      % (hi_rooted <= set(valid), sorted(hi_rooted - set(valid))[:8]))
# Is it just a dense run? A dense 0..N-1 array would trivially "contain" low indices.
dense = sum(1 for k, v in enumerate(vals[:5000]) if v == k)
print("  dword0 == slot index for %d of the first 5000 slots (dense-run check)" % dense)
print("\n  first 24 raw 12-byte records:")
for k in range(24):
    a, b, c = struct.unpack_from("<iii", blob, k * 12)
    print("    [%3d] %-10d %-12d %-12d" % (k, a, b, c))
