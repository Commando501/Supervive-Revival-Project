import sys, os, pickle, bisect
sys.path.insert(0, os.path.dirname(__file__))
from img import Img

with open(os.path.join(os.path.dirname(__file__), "calltargets.pkl"), "rb") as f:
    T = pickle.load(f)
KEYS = sorted(T)

def prev_starts(rva, n=6):
    i = bisect.bisect_left(KEYS, rva)
    return [(k, T[k]) for k in KEYS[max(0, i - n):i]]

def next_starts(rva, n=4):
    i = bisect.bisect_right(KEYS, rva)
    return [(k, T[k]) for k in KEYS[i:i + n]]

if __name__ == "__main__":
    img = Img()
    for a in sys.argv[1:]:
        rva = int(a, 16)
        print("=== %08x  page_decrypted=%s" % (rva, img.page_decrypted(rva)))
        for k, c in prev_starts(rva):
            print("   prev start %08x refs=%-3d  delta=-%#x   %s" % (k, c, rva - k, img.r(k, 12).hex()))
        for k, c in next_starts(rva):
            print("   next start %08x refs=%-3d  delta=+%#x" % (k, c, k - rva))
