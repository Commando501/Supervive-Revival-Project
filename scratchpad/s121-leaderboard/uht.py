"""Decode UE5.4 UECodeGen_Private::FStructParams / FPropertyParams for this build.

The params tables live in .data (0x9c4xxxx), NOT .rdata.

FStructParams layout DERIVED FROM THIS IMAGE (see calibration at bottom):
  +0x00 OuterFunc(.text)  +0x08 SuperFunc(.text|0)  +0x10 StructOpsFunc(.text)
  +0x18 NameUTF8          +0x20 PropertyArray
  +0x28 u16 NumProperties  +0x2a u16 SizeOf  +0x2c u16 AlignOf  +0x2e u16 pad
  +0x30 u32 StructFlags    +0x34 u32 (=1)

FPropertyParamsBaseWithOffset (stock UE5.4):
  +0x00 NameUTF8 +0x08 RepNotifyFuncUTF8 +0x10 PropertyFlags(u64)
  +0x18 Flags(u32) +0x1c ObjectFlags(u32) +0x20 SetterFunc +0x28 GetterFunc
  +0x30 ArrayDim(u16) +0x32 Offset(u16)
"""
import sys, os, struct
sys.path.insert(0, os.path.dirname(__file__))
from img import Img, RDATA_LO, RDATA_HI, TEXT_LO, TEXT_HI, DATA_LO

img = Img(); b = img.b; BASE = 0x7FF6AF000000

GENFLAG = {0x00: "Byte", 0x01: "Int8", 0x02: "Int16", 0x03: "Int", 0x04: "Int64",
           0x05: "UInt16", 0x06: "UInt32", 0x07: "UInt64", 0x08: "UnsizedInt",
           0x09: "UnsizedUInt", 0x0A: "Float", 0x0B: "Double", 0x0C: "Bool",
           0x0D: "SoftClass", 0x0E: "WeakObject", 0x0F: "LazyObject",
           0x10: "SoftObject", 0x11: "Class", 0x12: "Object", 0x13: "Interface",
           0x14: "Name", 0x15: "Str", 0x16: "Array", 0x17: "Map", 0x18: "Set",
           0x19: "Struct", 0x1A: "Delegate", 0x1B: "InlineMulticastDelegate",
           0x1C: "SparseMulticastDelegate", 0x1D: "Text", 0x1E: "Enum",
           0x1F: "FieldPath", 0x20: "LWCReal", 0x21: "Optional"}


def find_ascii_all(s):
    n = s.encode() + b"\x00"
    out, i = [], 0
    while True:
        i = b.find(n, i)
        if i < 0: break
        if i > 0 and b[i - 1] == 0:
            out.append(i)
        i += 1
    return out


def ptr_hits_all(rva):
    n = struct.pack("<Q", rva + BASE)
    out, i = [], 0
    while True:
        i = b.find(n, i)
        if i < 0: break
        out.append(i); i += 1
    return out


def find_structparams(name):
    res = []
    for na in find_ascii_all(name):
        for p in ptr_hits_all(na):
            sp = p - 0x18
            if sp < 0x1000 or sp + 0x40 > len(b): continue
            try:
                outerf = img.u64(sp) - BASE
                opsf = img.u64(sp + 0x10) - BASE
                parr = img.u64(sp + 0x20) - BASE
            except Exception:
                continue
            nprop = img.u16(sp + 0x28); size = img.u16(sp + 0x2a); align = img.u16(sp + 0x2c)
            if not (TEXT_LO <= outerf < TEXT_HI and TEXT_LO <= opsf < TEXT_HI): continue
            if not (RDATA_LO <= parr < len(b)): continue
            if not (0 < nprop < 300 and 0 < size <= 0xFFFF and align in (1, 2, 4, 8, 16)): continue
            res.append((sp, na, parr, nprop, size, align, img.u32(sp + 0x30)))
    return res


def props(parr, n):
    out = []
    for k in range(n):
        pp = img.u64(parr + 8 * k) - BASE
        nm = img.cstr(img.u64(pp) - BASE, 80)
        out.append((pp, nm, img.u64(pp + 0x10), img.u32(pp + 0x18),
                    img.u16(pp + 0x30), img.u16(pp + 0x32)))
    return out


def report(name, expect=None):
    hits = find_structparams(name)
    print("=== %s   (%d FStructParams candidates)" % (name, len(hits)))
    if not hits:
        return False
    allpass = None
    for sp, na, parr, n, size, align, sflags in hits:
        print("   params@%08x  name@%08x  NumProperties=%d  SizeOf=0x%x  AlignOf=%d  StructFlags=0x%x"
              % (sp, na, n, size, align, sflags))
        rows = props(parr, n)
        for pp, nm, fl, gen, ad, off in rows:
            g = gen & 0xFF
            print("      +0x%03x  %-26s %-12s dim=%d flags=0x%016x gen=0x%08x @%08x"
                  % (off, nm, GENFLAG.get(g, hex(g)), ad, fl, gen, pp))
        if expect is not None:
            # UHT emits container INNER params (PropertyFlags==0) BEFORE the real
            # property; the inner's Offset field is meaningless. Keep real props only.
            got = {}
            for _, nm, fl, _, _, off in rows:
                if fl != 0:
                    got[nm] = off
            bad = [(k, hex(v), hex(got[k]) if k in got else "MISSING")
                   for k, v in expect.items() if got.get(k) != v]
            ok = not bad
            allpass = ok if allpass is None else (allpass or ok)
            print("   >>> CALIBRATION %s%s" % ("PASS" if ok else "FAIL", "" if ok else "  %s" % bad))
    return allpass


if __name__ == "__main__":
    print("########## CALIBRATION (known-measured offsets) ##########")
    c1 = report("PlayerProgression", {"ID": 0x0, "Version": 0x10, "Matches": 0x18,
                                      "MissionInfo": 0x68, "AccountPass": 0xe8,
                                      "HeroMastery": 0x148, "LoginReward": 0x158,
                                      "EventProgression": 0x168})
    c2 = report("HeroMasteryProgress", {"HeroId": 0x60})
    c3 = report("ProgressionTrackLevel", {"Level": 0x04, "XP": 0x08, "Cleared": 0x0C,
                                          "UnclaimedRewards": 0x10})
    print("\n########## TARGETS ##########")
    for n in ("LokiPlayerStatsLeaderboard", "LokiPlayerStatsLeaderboardEntry",
              "Leaderboard", "LeaderboardEntry", "PlayerStats"):
        report(n)
    print("\nCALIBRATION SUMMARY: PlayerProgression=%s  HeroMasteryProgress=%s" % (c1, c2))
