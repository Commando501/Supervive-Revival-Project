# Live confirmation of the offline claim: state->KeepFlags == 0 (=> GC mark body B is dead, and the
# root TSet is the ENTIRE seed, making an insert SUFFICIENT and not merely necessary).
# PREDICTION registered before the read: [base+0x9E25348] == 0.
# Control: read the neighbouring bPerformFullPurge and the GC state object base too, so a wholesale
# "this region is all zero / unmapped" failure is distinguishable from a real measured zero.
import os, sys, struct
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "tools", "re"))
import item_watch as IW
pid = IW.autodetect_pid(); base = IW.autodetect_base(pid)
w = IW.Watch(pid, base, lambda s: None)
blk = w.rpm(base + 0x9E252C0, 0xA0)
if blk is None:
    print("GC state object at base+0x9E252C0 is UNREADABLE -- result is VOID, not zero"); sys.exit(1)
kf = struct.unpack_from("<i", blk, 0x88)[0]
fp = blk[0x8C]
nz = sum(1 for b in blk if b)
print("GC state object base+0x9E252C0 .. +0x9E25360")
print("  +0x88  KeepFlags          = %d   (predicted 0)  -> %s" % (kf, "CONFIRMED" if kf == 0 else "REFUTED"))
print("  +0x8C  bPerformFullPurge  = %d" % fp)
print("  CONTROL: %d of %d bytes in the block are non-zero -> %s"
      % (nz, len(blk), "region is live, so the zero above is a real read"
         if nz else "WHOLE BLOCK IS ZERO -- uninterpretable, treat as VOID"))
print("\n  cross-check, root registry live count (ArrayNum - NumFreeIndices):")
r = w.rpm(base + 0x99D3CA0, 0x40)
num = struct.unpack_from("<i", r, 8)[0]; free = struct.unpack_from("<i", r, 0x34)[0]
print("    %d - %d = %d" % (num, free, num - free))
