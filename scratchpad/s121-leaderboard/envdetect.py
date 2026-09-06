"""ENVELOPE DETECTOR + POSITIVE CONTROL.

For every FJsonObjectConverter::JsonObjectToUStruct(0x1f99e20) site, look at the
window between the LAST FJsonSerializer::Deserialize / GetContentAsString and the
converter call, and report any rip-relative lea to a .rdata wide string (a JSON
key would appear exactly there, because FJsonObject::GetObjectField(TEXT("data"))
must materialise its key literal).

Also reports whether rcx at the call is fed straight from the Deserialize output.
"""
import sys, os, struct, pickle, bisect
sys.path.insert(0, os.path.dirname(__file__))
from img import Img, TEXT_LO, TEXT_HI, RDATA_LO, RDATA_HI, ripdest
import capstone

img = Img(); b = img.b
CONV = 0x1f99e20
DESER = 0x11695b0
READER = 0x1185580
rows = pickle.load(open(os.path.join(os.path.dirname(__file__), "jconv.pkl"), "rb"))


def printable_w(rva, maxn=80):
    w = img.wstr(rva, maxn)
    if len(w) >= 2 and all(32 <= ord(c) < 127 for c in w):
        return w
    return None


def analyse(fn, site, name):
    ins = list(img.md.disasm(b[fn:site + 8], fn))
    # index of the converter call
    ci = len(ins) - 1
    # find last reader/deser/GetContentAsString before it
    anchor = 0
    for k, i in enumerate(ins[:ci]):
        if i.mnemonic == "call":
            if i.operands and i.operands[0].type == capstone.x86.X86_OP_IMM and \
               i.operands[0].imm in (DESER, READER):
                anchor = k
            elif i.op_str.startswith("qword ptr [rax + 0x60]"):
                anchor = k
    win = ins[anchor:ci]
    keys = []
    for i in win:
        d = ripdest(i)
        if i.mnemonic == "lea" and d is not None and RDATA_LO <= d < RDATA_HI:
            s = printable_w(d)
            if s: keys.append((i.address, d, s))
    # indirect calls in the window (GetObjectField is non-virtual, but TryGetField etc.)
    ncall = sum(1 for i in win if i.mnemonic == "call")
    return len(win), ncall, keys


if __name__ == "__main__":
    flagged = []
    for fn, site, ss, name, hr, hd, n in rows:
        w, nc, keys = analyse(fn, site, name)
        if keys or nc > 3:
            flagged.append((fn, site, name, w, nc, keys))
    print("sites analysed:", len(rows))
    print("sites with a string literal or >3 calls in the pre-convert window:", len(flagged))
    for fn, site, name, w, nc, keys in flagged:
        print("  %-46s fn=%08x site=%08x win=%d calls=%d" % (name, fn, site, w, nc))
        for a, d, s in keys[:8]:
            print("        key-literal @%08x -> %08x  W\"%s\"" % (a, d, s))
    # explicit report for the three targets
    print("\n--- TARGETS ---")
    for want in ("LokiPlayerStatsLeaderboard", "Leaderboard", "PlayerStats", "PlayerProgression"):
        for fn, site, ss, name, hr, hd, n in rows:
            if name == want:
                w, nc, keys = analyse(fn, site, name)
                print("  %-28s fn=%08x site=%08x  window_insns=%d calls_in_window=%d  key_literals=%d"
                      % (name, fn, site, w, nc, len(keys)))
