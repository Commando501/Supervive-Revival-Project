"""Find direct call/jmp rel32 xrefs to an RVA, and lea-xrefs to an RVA."""
import sys, os, struct
sys.path.insert(0, os.path.dirname(__file__))
from img import Img, TEXT_LO, TEXT_HI

img = Img()
b = img.b


def rel32_xrefs(target):
    out = []
    for opc in (0xE8, 0xE9):
        i = TEXT_LO
        needle = bytes([opc])
        while True:
            i = b.find(needle, i, TEXT_HI - 5)
            if i < 0: break
            d = struct.unpack_from("<i", b, i + 1)[0]
            if i + 5 + d == target:
                out.append((i, "call" if opc == 0xE8 else "jmp"))
            i += 1
    return out


def lea_xrefs(target, lo=TEXT_LO, hi=TEXT_HI):
    """48 8D /r with rip-rel disp32 -> target. Scan all 48 8D and 4C 8D."""
    out = []
    for pre in (b"\x48\x8d", b"\x4c\x8d"):
        i = lo
        while True:
            i = b.find(pre, i, hi - 8)
            if i < 0: break
            modrm = b[i + 2]
            if (modrm & 0xC7) == 0x05:  # rip-relative
                d = struct.unpack_from("<i", b, i + 3)[0]
                if i + 7 + d == target:
                    out.append(i)
            i += 1
    return out


def mov_rip_xrefs(target):
    """48 8B /r rip-rel (mov reg, [rip+d]) and 48 89 (mov [rip+d], reg)."""
    out = []
    for pre in (b"\x48\x8b", b"\x4c\x8b", b"\x48\x89", b"\x4c\x89"):
        i = TEXT_LO
        while True:
            i = b.find(pre, i, TEXT_HI - 8)
            if i < 0: break
            modrm = b[i + 2]
            if (modrm & 0xC7) == 0x05:
                d = struct.unpack_from("<i", b, i + 3)[0]
                if i + 7 + d == target:
                    out.append((i, pre.hex()))
            i += 1
    return out


if __name__ == "__main__":
    mode = sys.argv[1]
    for a in sys.argv[2:]:
        t = int(a, 16)
        print("=== target %08x" % t)
        if mode in ("call", "all"):
            for r, k in rel32_xrefs(t):
                print("   %s @ %08x  (page_dec=%s)" % (k, r, img.page_decrypted(r)))
        if mode in ("lea", "all"):
            for r in lea_xrefs(t):
                print("   lea  @ %08x  (page_dec=%s)" % (r, img.page_decrypted(r)))
        if mode in ("mov", "all"):
            for r, p in mov_rip_xrefs(t):
                print("   mov(%s) @ %08x" % (p, r))
