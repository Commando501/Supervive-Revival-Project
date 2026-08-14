# offline_xref.py -- OFFLINE rip-relative / call xref scanner over a cold PE image dump.
#
# Why this exists (S102, FK-2 input-pipeline probe):
#   usmapdump's `xrefstr` / `callxref` need a LIVE process. This round of work was
#   explicitly offline (no launching the game), so we needed the same capability
#   against dumps/merged.dump.exe (file-offset == RVA, ImageBase = 0x7FF6AF000000).
#
# Modes:
#   xref  <hexRVA>            rip-relative references (any instruction whose disp32
#                             lands exactly on the target). Reports the referencing
#                             instruction decoded with capstone + the enclosing
#                             function start (int3/CC-padding heuristic).
#   call  <hexRVA>            E8/E9 rel32 references to the target.
#   ptr   <hexRVA>            ABSOLUTE qword == ImageBase+RVA, anywhere in the image.
#                             *** THIS is the mode that works on UE reflection. ***
#   fn    <hexRVA>            find the start of the function containing RVA.
#   str   <regex> [max]       ANSI+UTF16 string search returning RVAs.
#
# S102 lesson (cost an hour): UE5's generated reflection (FPropertyParamsBase,
# FClassFunctionLinkInfo, FClassParams, FFunctionParams) stores names as ABSOLUTE
# `const char*` pointers inside static structs -- NOT as `lea reg,[rip+..]` from
# .text. `xref` returns 0 for every reflection name; `ptr` finds them instantly and
# lands you directly in the class's property/function tables. Reach for `ptr` first
# when chasing a UCLASS/UPROPERTY/UFUNCTION name; `xref` only for code literals.
#
# Coverage caveat: the dump demand-decrypts .text, so ~48% of .text is present
# (and dumps/merged.dump.exe is effectively ONE menu-state dump -- its four extra
# inputs contributed ~1.2 KB total; see dumps/merged.dump.exe.txt). A "0 xrefs"
# result therefore NEVER proves absence -- it proves the referencing page was not
# decrypted in the captured state. Gameplay-only code (input binding, MoveForward)
# reads as all-zero pages. Say so in any finding.
import sys, re, numpy as np, capstone

  # 2026-08-14 (S121, FK-18/FK-19): merged2 is the canonical cold image -- same ImageBase
  # 0x7FF6AF000000, byte-identical .rdata/.data, and a STRICT .text superset (16,625 vs
  # 15,833 decrypted pages). docs/fk18-fk19-multistate-merge-settled.md
DUMP = r"G:\git\Supervive Revival Project\dumps\merged2.dump.exe"
IMAGEBASE = 0x7FF6AF000000
TEXT_RVA, TEXT_SIZE = 0x1000, 0x7649000

_data = None
def data():
    global _data
    if _data is None:
        _data = open(DUMP, "rb").read()
    return _data

def fnstart(rva, back=0x4000):
    """Walk back to the nearest 0xCC/0x00 padding run followed by a plausible prologue."""
    d = data()
    lo = max(TEXT_RVA, rva - back)
    for i in range(rva, lo, -1):
        # padding run of >=2 int3 immediately before a 16-byte-ish aligned start
        if d[i-1] == 0xCC and d[i-2] == 0xCC:
            return i
    return None

md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
md.detail = True

def decode_at(rva, n=1, back=24):
    """Decode the instruction that most plausibly *ends* at rva+4 (disp32 is last field)."""
    d = data()
    best = None
    for s in range(back, 0, -1):
        start = rva - s
        if start < TEXT_RVA:
            continue
        try:
            ins = next(md.disasm(d[start:start+16], IMAGEBASE + start))
        except StopIteration:
            continue
        if start + ins.size == rva + 4:
            best = (start, ins)
    return best

def xref(target, kind="rip", limit=200):
    d = np.frombuffer(data(), dtype=np.uint8)
    seg = d[TEXT_RVA:TEXT_RVA+TEXT_SIZE]
    disp = seg[:len(seg)-3].view(np.uint8)
    # build int32 view over every byte offset
    a = np.frombuffer(data()[TEXT_RVA:TEXT_RVA+TEXT_SIZE], dtype=np.uint8).astype(np.int64)
    n = len(a) - 4
    v = (a[0:n] | (a[1:n+1] << 8) | (a[2:n+2] << 16) | (a[3:n+3] << 24)).astype(np.int64)
    v = np.where(v >= 0x80000000, v - 0x100000000, v)
    idx = np.arange(n, dtype=np.int64) + TEXT_RVA
    if kind == "rip":
        hits = np.nonzero(idx + 4 + v == target)[0]
    else:  # call/jmp rel32: opcode E8/E9 at idx-1
        hits = np.nonzero(idx + 4 + v == target)[0]
    out = []
    for h in hits[:limit*8]:
        rva = int(idx[h])
        if kind == "call":
            op = data()[rva-1]
            if op not in (0xE8, 0xE9):
                continue
            out.append((rva-1, None))
        else:
            r = decode_at(rva)
            if r is None:
                continue
            out.append(r)
        if len(out) >= limit:
            break
    return out

if __name__ == "__main__":
    mode = sys.argv[1]
    if mode == "str":
        pat = re.compile(sys.argv[2].encode("latin1"), re.I)
        mx = int(sys.argv[3]) if len(sys.argv) > 3 else 100
        d = data(); n = 0; seen = set()
        for m in re.finditer(rb"[\x20-\x7e]{4,200}", d):
            if pat.search(m.group()) and m.group() not in seen:
                seen.add(m.group()); print(f"A 0x{m.start():X}  {m.group().decode('latin1')}"); n += 1
                if n >= mx: break
        for m in re.finditer(rb"(?:[\x20-\x7e]\x00){4,200}", d):
            s = m.group()[::2]
            if pat.search(s) and s not in seen:
                seen.add(s); print(f"W 0x{m.start():X}  {s.decode('latin1')}"); n += 1
                if n >= mx: break
    elif mode == "ptr":
        t = int(sys.argv[2], 16)
        d = data()
        q = np.frombuffer(d[:len(d) // 8 * 8], dtype='<u8')
        for h in np.nonzero(q == (IMAGEBASE + t))[0]:
            r = int(h) * 8
            sec = ".text" if r < 0x764A000 else (".rdata" if r < 0x99C7000 else ".data+")
            print(f"0x{r:X} [{sec}]")
    elif mode == "fn":
        print(hex(fnstart(int(sys.argv[2], 16))))
    else:
        t = int(sys.argv[2], 16)
        lim = int(sys.argv[3]) if len(sys.argv) > 3 else 200
        for rva, ins in xref(t, "call" if mode == "call" else "rip", lim):
            fs = fnstart(rva)
            if ins is None:
                print(f"+0x{rva:X}  call/jmp -> 0x{t:X}   [fn +0x{fs:X}]" if fs else f"+0x{rva:X} call")
            else:
                print(f"+0x{rva:X}  {ins.mnemonic:6s} {ins.op_str:44s} [fn +0x{fs:X}]" if fs
                      else f"+0x{rva:X}  {ins.mnemonic:6s} {ins.op_str}")
