# Verify the ROOT REGISTRY found by disassembly: TSet<int32> of InternalIndices at .data 0x99D3CA0.
# PREDICTION registered before reading: the registry's contents == exactly the set of HIGH-INDEX
# objects carrying bit 30 that rootset_census.py measures independently (n=32 at last sample).
# A set-identity match is the test; a mere count match is not.
import os, sys, struct
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "tools", "re"))
import item_watch as IW

RVA_ROOTREG = 0x99D3CA0
STRIDE, PERCHUNK, ITEM_FMT = IW.STRIDE, IW.PERCHUNK, IW.ITEM_FMT
ROOTBIT = 30

pid = IW.autodetect_pid(); base = IW.autodetect_base(pid)
w = IW.Watch(pid, base, lambda s: None)

# --- A. independent census: high-index bit30 objects -------------------------------------------
objectsPtr, numEl = w.header()
chunks = w.chunks(objectsPtr, numEl)
live, rooted_hi, names = {}, set(), {}
for ci, (addr, cnt) in enumerate(chunks):
    if not addr: continue
    d = w.rpm_into(addr, cnt * STRIDE)
    if d is None: continue
    for j, (o, fl, cl, se) in enumerate(struct.iter_unpack(ITEM_FMT, d.tobytes())):
        if o:
            i = ci * PERCHUNK + j
            live[i] = (o, fl & 0xFFFFFFFF)
first_free = next(i for i in range(numEl) if i not in live)
for i, (o, fl) in live.items():
    if i >= first_free and (fl & (1 << ROOTBIT)):
        rooted_hi.add(i); names[i] = (w.ocls_name(o), w.oname(o))
print("A. census: ObjFirstGCIndex(census)=%d   high-index bit%d objects = %d"
      % (first_free, ROOTBIT, len(rooted_hi)))

# --- B. the registry ----------------------------------------------------------------------------
raw = w.rpm(base + RVA_ROOTREG, 0x50)
print("\nB. raw TSet at base+0x%X:" % RVA_ROOTREG)
for i in range(0, 0x50, 8):
    q = struct.unpack_from("<Q", raw, i)[0]
    a, b = struct.unpack_from("<ii", raw, i)
    print("   +0x%02X  %016X   as int32 pair: %-12d %-12d" % (i, q, a, b))

dataPtr = struct.unpack_from("<Q", raw, 0)[0]
num, mx = struct.unpack_from("<ii", raw, 8)
print("\n   Elements.Data=0x%X  ArrayNum=%d  ArrayMax=%d" % (dataPtr, num, mx))

if not IW.looksptr(dataPtr) or not (0 < num < 100000):
    print("   !! header does not parse as TSparseArray -- ABORT, do not guess")
    sys.exit(1)

# TSetElement<int32> is {int32 Value; int32 HashNextId; int32 HashIndex} = 12 bytes, but the sparse
# array may pad to 16. Try both and let the set-identity test pick the winner -- neither is assumed.
blob = w.rpm(dataPtr, num * 16 + 64)
for stride in (8, 12, 16):
    vals = set()
    for k in range(num):
        off = k * stride
        if off + 4 > len(blob): break
        v = struct.unpack_from("<i", blob, off)[0]
        if 0 <= v < numEl: vals.add(v)
    inter = vals & rooted_hi
    print("\n   stride %2d -> %3d plausible indices, %3d of them are high-index-bit%d objects"
          % (stride, len(vals), len(inter), ROOTBIT))
    if vals and len(inter) >= max(4, len(vals) // 2):
        only_reg = sorted(vals - rooted_hi); only_cen = sorted(rooted_hi - vals)
        print("      SET IDENTITY: registry=%d census=%d  intersection=%d"
              % (len(vals), len(rooted_hi), len(inter)))
        print("      in registry but NOT high-index-rooted : %s" % (only_reg or "none"))
        print("      high-index-rooted but NOT in registry : %s" % (only_cen or "none"))
        if not only_reg and not only_cen:
            print("      *** SET-IDENTICAL ***")
        for i in sorted(vals):
            e = live.get(i)
            fl = e[1] if e else 0
            cn, nm = names.get(i, (w.ocls_name(e[0]) if e else "?", w.oname(e[0]) if e else "?"))
            print("        idx=%-8d flags=%08X  bit%d=%d  %-30s %s"
                  % (i, fl, ROOTBIT, 1 if fl & (1 << ROOTBIT) else 0, cn[:30], nm[:36]))
        break
