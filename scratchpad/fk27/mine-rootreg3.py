# Decisive SET-IDENTITY test, done properly this time: walk the TSparseArray's ALLOCATION BITMAP and
# take only ALLOCATED elements. My previous pass read all ArrayNum slots incl. free ones -- that was
# the error. PREDICTION registered before running: the allocated set == exactly the high-index bit30
# objects the census finds, and Num() == ArrayNum - NumFreeIndices.
import os, sys, struct
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "tools", "re"))
import item_watch as IW
STRIDE, PERCHUNK, ITEM_FMT = IW.STRIDE, IW.PERCHUNK, IW.ITEM_FMT
ROOTBIT = 30

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
census = {i for i, (o, fl) in live.items() if i >= first_free and (fl & (1 << ROOTBIT))}

raw = w.rpm(base + 0x99D3CA0, 0x40)
dataPtr, num, mx = struct.unpack_from("<Qii", raw, 0)
bitPtr = struct.unpack_from("<Q", raw, 0x20)[0]
numBits, maxBits = struct.unpack_from("<ii", raw, 0x28)
firstFree, numFree = struct.unpack_from("<ii", raw, 0x30)
liveN = num - numFree
print("TSparseArray: ArrayNum=%d ArrayMax=%d FirstFreeIndex=%d NumFreeIndices=%d" % (num, mx, firstFree, numFree))
print("  => Num() = %d - %d = %d" % (num, numFree, liveN))
print("  agent's free receipt  *(base+0x99D3CA8) - *(base+0x99D3CD4) = %d - %d = %d"
      % (num, numFree, liveN))
print("  census high-index bit%d objects                              = %d" % (ROOTBIT, len(census)))

bits = w.rpm(bitPtr, (numBits + 7) // 8 + 8) if numBits > 128 else raw[0x10:0x20]
blob = w.rpm(dataPtr, num * 12 + 16)
alloc = []
for k in range(num):
    if (bits[k >> 3] >> (k & 7)) & 1:
        alloc.append(struct.unpack_from("<i", blob, k * 12)[0])
print("\nallocated elements per bitmap: %d   (must equal Num()=%d) -> %s"
      % (len(alloc), liveN, "PASS" if len(alloc) == liveN else "FAIL"))
regset = set(alloc)
print("\nSET IDENTITY   registry=%d  census=%d  intersection=%d" % (len(regset), len(census), len(regset & census)))
print("  in registry but not census : %s" % (sorted(regset - census) or "none"))
print("  in census but not registry : %s" % (sorted(census - regset) or "none"))
print("  *** %s ***" % ("SET-IDENTICAL" if regset == census else "NOT IDENTICAL"))
print("\n%-8s %-10s %-32s %s" % ("index", "flags", "class", "name"))
for i in sorted(regset):
    o, fl = live.get(i, (0, 0))
    print("%-8d %08X   %-32s %s" % (i, fl, w.ocls_name(o)[:32] if o else "<dead>", w.oname(o)[:36] if o else ""))
