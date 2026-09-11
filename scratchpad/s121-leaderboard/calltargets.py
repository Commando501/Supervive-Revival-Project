"""Build a set of rel32 CALL targets in .text -> candidate function starts.
Positive control: known function starts from CLAUDE.md must appear.
"""
import sys, os, struct, pickle
sys.path.insert(0, os.path.dirname(__file__))
from img import Img, TEXT_LO, TEXT_HI

OUT = os.path.join(os.path.dirname(__file__), "calltargets.pkl")


def build(img):
    b = img.b
    tgts = {}
    i = TEXT_LO
    end = TEXT_HI - 5
    find = b.find
    while True:
        i = find(b"\xe8", i, end)
        if i < 0: break
        d = struct.unpack_from("<i", b, i + 1)[0]
        t = i + 5 + d
        if TEXT_LO <= t < TEXT_HI and (t & 0xFFF or True):
            tgts[t] = tgts.get(t, 0) + 1
        i += 1
    return tgts


if __name__ == "__main__":
    img = Img()
    t = build(img)
    with open(OUT, "wb") as f:
        pickle.dump(t, f)
    print("targets:", len(t))
    # positive controls: known function starts
    for name, rva in [("ProcessInternal", 0x13454A0), ("UEngine::Exec", 0x3ED66C0),
                      ("ExecuteConsoleCommand thunk", 0x395D790),
                      ("JsonObjectStringToUStruct?", 0), ("FindVM", 0x57AB180),
                      ("CheckAccountPassChanges", 0x5794480),
                      ("ingester", 0x585A570), ("MakeMissionModel", 0x56F16F0)]:
        if rva:
            print("  CTRL %-28s %08x  refs=%s" % (name, rva, t.get(rva, "MISS")))
