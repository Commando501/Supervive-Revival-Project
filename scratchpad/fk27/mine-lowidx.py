# One-off: characterise the 20 objects that sit INSIDE the never-freed prefix but do NOT carry bit 30.
# They are the reason the boundary test printed "boundaries DISAGREE", and they matter because they
# separate two properties that have been treated as one: "is permanent" vs "carries RootSet".
# READ-ONLY RPM.
import os, sys, struct
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "tools", "re"))
import item_watch as IW

STRIDE, PERCHUNK, ITEM_FMT = IW.STRIDE, IW.PERCHUNK, IW.ITEM_FMT
ROOTBIT, REACH = 30, 0b111

pid = IW.autodetect_pid(); base = IW.autodetect_base(pid)
w = IW.Watch(pid, base, lambda s: None)
objectsPtr, numEl = w.header()
chunks = w.chunks(objectsPtr, numEl)

rows = []
for ci, (addr, cnt) in enumerate(chunks):
    if not addr: continue
    data = w.rpm_into(addr, cnt * STRIDE)
    if data is None: continue
    for j, (o, fl, cl, se) in enumerate(struct.iter_unpack(ITEM_FMT, data.tobytes())):
        rows.append((ci * PERCHUNK + j, o, fl & 0xFFFFFFFF, cl))

live = {i: (o, fl, cl) for i, o, fl, cl in rows if o}
first_free = next(i for i in range(numEl) if i not in live)
print("numEl=%d  live=%d  first_free=%d" % (numEl, len(live), first_free))

free_total = numEl - len(live)
# If the free slots were uniformly scattered, what is P(none of them lands in the prefix)?
# Hypergeometric with all free slots drawn without replacement from numEl positions.
from math import lgamma, exp
def lC(n, k):
    if k < 0 or k > n: return float("-inf")
    return lgamma(n+1) - lgamma(k+1) - lgamma(n-k+1)
logp = lC(numEl - first_free, free_total) - lC(numEl, free_total)
print("free slots=%d ; P(zero free in prefix [0..%d) if uniform) = e^%.1f  (~10^%.1f)"
      % (free_total, first_free, logp, logp / 2.302585))

low_unrooted = [(i, v) for i, v in live.items() if i < first_free and not (v[1] & (1 << ROOTBIT))]
print("\nobjects inside the never-freed prefix WITHOUT bit%d: %d" % (ROOTBIT, len(low_unrooted)))
print("%-8s %-10s %-34s %s" % ("index", "flags", "class", "name"))
for i, (o, fl, cl) in sorted(low_unrooted):
    print("%-8d %08X   %-34s %s" % (i, fl, w.ocls_name(o)[:34], w.oname(o)[:44]))

# Do they carry a reachability value? If they are permanent-but-unflagged they should NOT.
acc = {}
for i, (o, fl, cl) in low_unrooted:
    acc[fl & REACH] = acc.get(fl & REACH, 0) + 1
print("\nlow-bit (reachability) values among those %d: %s" % (len(low_unrooted), acc))

# Control: the reachability values of bit30 objects inside the prefix, and of ordinary high-index ones.
def dist(sel):
    d = {}
    for i, (o, fl, cl) in sel:
        d[fl & REACH] = d.get(fl & REACH, 0) + 1
    return d
low_rooted = [(i, v) for i, v in live.items() if i < first_free and (v[1] & (1 << ROOTBIT))]
hi_any = [(i, v) for i, v in live.items() if i >= first_free][:5000]
print("control  bit%d objects in prefix        : %s" % (ROOTBIT, dist(low_rooted)))
print("control  high-index objects (5000)      : %s" % dist(hi_any))
