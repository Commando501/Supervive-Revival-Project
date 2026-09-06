# Read the bytes AROUND GUObjectArray.ObjObjects looking for the disregard-for-GC fields.
# Stock UE5 FUObjectArray:
#   int32 ObjFirstGCIndex @0x00 ; int32 ObjLastNonGCIndex @0x04 ;
#   int32 MaxObjectsNotConsideredByGC @0x08 ; bool OpenForDisregardForGC @0x0C ;
#   FChunkedFixedUObjectArray ObjObjects @0x10   { Objects@0x00, PreAlloc@0x08, Max@0x10, Num@0x14, MaxChunks@0x18, NumChunks@0x1C }
# The project constant RVA_OBJOBJECTS=0x9E38930 has NumElements at +0x14, so it is &ObjObjects,
# and FUObjectArray should begin at 0x9E38930-0x10 = 0x9E38920.
# PREDICTION registered before reading: ObjFirstGCIndex == 39295 (or ObjLastNonGCIndex == 39294).
import os, sys, struct
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "tools", "re"))
import item_watch as IW

pid = IW.autodetect_pid(); base = IW.autodetect_base(pid)
w = IW.Watch(pid, base, lambda s: None)
OBJ = IW.RVA_OBJOBJECTS
lo = OBJ - 0x40
raw = w.rpm(base + lo, 0x90)
print("window base+0x%X .. +0x%X   (ObjObjects at +0x%X)\n" % (lo, lo + 0x90, OBJ))
print("%-14s %-10s %-12s %s" % ("rva", "off(FUOA)", "int32", "note"))
for i in range(0, 0x90, 4):
    v = struct.unpack_from("<i", raw, i)[0]
    rva = lo + i
    off = rva - (OBJ - 0x10)
    note = ""
    if v == 39295: note = "  <<<<<< == first_free (predicted ObjFirstGCIndex)"
    elif v == 39294: note = "  <<<<<< == first_free-1 (predicted ObjLastNonGCIndex)"
    elif v == 207719: note = "  (NumElements)"
    print("base+0x%08X  %+5d      %-12d%s" % (rva, off, v, note))
