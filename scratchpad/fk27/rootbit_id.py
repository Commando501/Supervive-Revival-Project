# rootbit_id.py -- OFFLINE. Is bit 30 of FUObjectItem.Flags actually EInternalObjectFlags::RootSet?
#
# The claimant's control C3 ("100% of sampled UClasses carry bit 30") CANNOT DISCRIMINATE: every UClass
# is also in the permanent pool, so C3 passes identically whether bit30 means "RootSet" or "permanent".
# The identification currently rests on class NAMES looking like textbook AddToRoot() callers, which is
# engine knowledge, not measurement.
#
# A discriminating test exists and is purely static. UE's ONLY writer of EInternalObjectFlags onto a
# live FUObjectItem from outside the GC is:
#     UObject::AddToRoot()  ->  FUObjectItem::SetRootSet()  ->  ThisThreadAtomicallySetFlag(RootSet)
# and ThisThreadAtomicallySetFlag is a CAS retry loop:
#     do { Old = Flags; } while (InterlockedCompareExchange(&Flags, Old | int32(Flag), Old) != Old);
# which compiles to  `or <reg>, imm32` followed closely by `lock cmpxchg dword ptr [mem], <reg>`.
#
# FUObjectItem is {UObject* Object; int32 Flags; int32 ClusterRootIndex; int32 SerialNumber; pad}, so
# Flags sits at +0x08 of the item. A RootSet setter is therefore
#     lock cmpxchg dword ptr [rX+8], rY     with a nearby   or rY, 40000000h
#
# CONTROLS (each can fail, and the run is void for negatives if they do):
#   P1  the same scan must FIND the analogous sites for OTHER known EInternalObjectFlags bits --
#       specifically the low reachability bits 0/1/2, which THIS PROJECT HAS ALREADY MEASURED live
#       (FK-28). If the scan cannot see a bit we know is written, its silence about bit30 is worthless.
#   P2  a negative control immediate that should NOT appear in this idiom.
#   N   report how much of .text is decrypted, because an absence in an encrypted region is nothing.
import os, struct, sys
from collections import Counter

DUMP = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "dumps", "merged2.dump.exe")


def sections(buf):
    e_lfanew = struct.unpack_from("<I", buf, 0x3C)[0]
    nsec = struct.unpack_from("<H", buf, e_lfanew + 6)[0]
    optsz = struct.unpack_from("<H", buf, e_lfanew + 20)[0]
    base = struct.unpack_from("<Q", buf, e_lfanew + 24 + 24)[0]
    off = e_lfanew + 24 + optsz
    out = []
    for i in range(nsec):
        r = buf[off + i * 40: off + (i + 1) * 40]
        name = r[:8].rstrip(b"\0").decode("latin1")
        vsz, va, rsz, ro = struct.unpack_from("<IIII", r, 8)
        out.append((name, va, vsz, ro, rsz))
    return base, out


def main():
    buf = open(DUMP, "rb").read()
    imgbase, secs = sections(buf)
    text = next(s for s in secs if s[0] == ".text")
    _, va, vsz, ro, rsz = text
    body = buf[ro:ro + rsz]
    nz_pages = sum(1 for p in range(0, len(body), 0x1000) if any(body[p:p + 0x1000]))
    tot_pages = (len(body) + 0xFFF) // 0x1000
    print("image=%s  base=0x%X  .text va=0x%X size=%d  decrypted pages %d/%d (%.2f%%)"
          % (os.path.basename(DUMP), imgbase, va, rsz, nz_pages, tot_pages, 100.0 * nz_pages / tot_pages))

    # every `lock cmpxchg dword ptr [mem], reg`  == F0 0F B1 /r   (no REX.W -> 32-bit operand)
    # We accept an optional REX prefix between F0 and 0F.
    sites = []
    i = 0
    n = len(body)
    while True:
        i = body.find(b"\x0f\xb1", i)
        if i < 0 or i >= n - 4:
            break
        # walk back over an optional REX and require the LOCK prefix
        j = i - 1
        rex = None
        if j >= 0 and 0x40 <= body[j] <= 0x4F:
            rex = body[j]
            j -= 1
        if j >= 0 and body[j] == 0xF0:
            modrm = body[i + 2]
            mod, reg, rm = modrm >> 6, (modrm >> 3) & 7, modrm & 7
            disp = None
            if mod == 1:
                disp = body[i + 3] if body[i + 3] < 0x80 else body[i + 3] - 0x100
            elif mod == 0 and rm != 5:
                disp = 0
            elif mod == 2:
                disp = struct.unpack_from("<i", body, i + 3)[0]
            sites.append((j, i, rex, mod, reg, rm, disp))
        i += 2
    print("lock cmpxchg (32-bit) sites in decrypted .text: %d" % len(sites))
    bydisp = Counter(s[6] for s in sites)
    print("  by displacement: %s" % dict(sorted((k, v) for k, v in bydisp.items()
                                                if v >= 3 and k is not None)))

    # For each site, look BACK up to 64 bytes for `or r32, imm32` / `or r/m32, imm32` and record imm.
    WINDOW = 64
    found = Counter()
    detail = {}
    for (start, ci, rex, mod, reg, rm, disp) in sites:
        lo = max(0, start - WINDOW)
        win = body[lo:start + 8]
        for k in range(len(win) - 6):
            if win[k] == 0x81 and 0xC8 <= win[k + 1] <= 0xCF:      # or r32, imm32
                imm = struct.unpack_from("<I", win, k + 2)[0]
            elif win[k] == 0x0D:                                    # or eax, imm32
                imm = struct.unpack_from("<I", win, k + 1)[0]
            elif win[k] == 0x09:                                    # or r/m32, r32 -> no imm
                continue
            else:
                continue
            if imm == 0:
                continue
            found[(imm, disp)] += 1
            detail.setdefault((imm, disp), []).append(va + start)

    print("")
    print("  `or <reg>, imm32` within %d bytes BEFORE a `lock cmpxchg [reg+disp]`:" % WINDOW)
    print("  %-12s %-8s %-6s  first few RVAs" % ("imm32", "disp", "count"))
    for (imm, disp), c in sorted(found.items(), key=lambda kv: -kv[1])[:30]:
        bits = [b for b in range(32) if imm & (1 << b)]
        print("  0x%08X  %-8s %-6d  %s   bits=%s"
              % (imm, disp, c, " ".join("0x%X" % r for r in detail[(imm, disp)][:4]), bits))

    print("")
    print("  --- the question -------------------------------------------------------------")
    at8 = {(imm, d): c for (imm, d), c in found.items() if d == 8}
    print("  sites with disp == +0x08 (i.e. FUObjectItem.Flags):")
    if not at8:
        print("    NONE. Scan found no atomic flag-set at +8 at all => the scan is BLIND here and")
        print("    says NOTHING about bit 30. Treat as VOID, not as a negative.")
    for (imm, d), c in sorted(at8.items(), key=lambda kv: -kv[1]):
        bits = [b for b in range(32) if imm & (1 << b)]
        tag = ""
        if imm == 0x40000000:
            tag = "   <== bit30, the claimed RootSet"
        if imm & 0b111 and imm < 8:
            tag = "   <== a LOW reachability bit (FK-28 control P1)"
        print("    imm=0x%08X bits=%-10s count=%-4d %s" % (imm, bits, c, tag))


if __name__ == "__main__":
    main()
