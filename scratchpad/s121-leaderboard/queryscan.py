"""Enumerate every Loki Query<T>::OnResponse by its Query.h:212 static log record,
then, for each, find the JsonObjectStringToUStruct<T> it calls and the struct type.
"""
import sys, os, struct, pickle, bisect
sys.path.insert(0, os.path.dirname(__file__))
from img import Img, TEXT_LO, TEXT_HI, RDATA_LO, RDATA_HI
import capstone

img = Img(); b = img.b; BASE = 0x7FF6AF000000
T = pickle.load(open(os.path.join(os.path.dirname(__file__), "calltargets.pkl"), "rb"))
KEYS = sorted(T)


def fstart(rva):
    i = bisect.bisect_left(KEYS, rva)
    return KEYS[i - 1] if i else None


def records_for(fmt_rva):
    needle = struct.pack("<Q", fmt_rva)
    out = []
    i = RDATA_LO
    while True:
        i = b.find(needle, i, RDATA_HI)
        if i < 0: break
        out.append(i); i += 1
    return set(out)


def lea_sites(targets):
    """single pass over .text collecting rip-rel lea sites whose dest is in targets"""
    out = {}
    for pre in (b"\x48\x8d", b"\x4c\x8d"):
        i = TEXT_LO
        while True:
            i = b.find(pre, i, TEXT_HI - 8)
            if i < 0: break
            if (b[i + 2] & 0xC7) == 0x05:
                d = struct.unpack_from("<i", b, i + 3)[0]
                t = i + 7 + d
                if t in targets:
                    out.setdefault(t, []).append(i)
            i += 1
    return out


if __name__ == "__main__":
    fmt = img.u64(0x8b52988)          # "Deserialization failure on Query: %s: %s."
    recs = records_for(fmt)
    print("# static log records (Query.h:212):", len(recs))
    sites = lea_sites(recs)
    print("# with a .text lea site:", len(sites))
    funcs = sorted({fstart(s) for lst in sites.values() for s in lst})
    print("# distinct enclosing functions:", len(funcs))
    pickle.dump({"recs": sorted(recs), "sites": sites, "funcs": funcs},
                open(os.path.join(os.path.dirname(__file__), "queries.pkl"), "wb"))
    for f in funcs:
        print("  %08x" % f)
