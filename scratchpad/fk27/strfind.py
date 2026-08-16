# fk27: locate literal strings (ASCII and UTF-16LE) anywhere in a dump image, with section labels.
# ⚠ FK-4: almost every behavioural literal in this image is UTF-16LE. Always search BOTH.
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dumplib import load

def sec_of(im, rva):
    for (n, va, vsz, ra, rsz) in im.sections:
        if va <= rva < va + max(vsz, rsz): return n
    return "?"

def find_all(data, needle, limit=200):
    out = []; i = 0
    while len(out) < limit:
        j = data.find(needle, i)
        if j < 0: break
        out.append(j); i = j + 1
    return out

def search(im, s, case_variants=True, limit=60):
    res = {}
    forms = {"ascii": s.encode("latin1"), "utf16": s.encode("utf-16-le")}
    for k, b in forms.items():
        res[k] = find_all(im.data, b, limit)
    return res

if __name__ == "__main__":
    key = os.environ.get("FK27_IMG", "merged2")
    im = load(key)
    for s in sys.argv[1:]:
        r = search(im, s)
        tot = sum(len(v) for v in r.values())
        print(f"== {s!r}  image={key}  total={tot}")
        for k, hits in r.items():
            if not hits:
                print(f"   {k}: 0")
                continue
            print(f"   {k}: {len(hits)}")
            for h in hits[:25]:
                print(f"      +0x{h:07X} [{sec_of(im,h)}]")
