#!/usr/bin/env python3
# Felix-free RE: locate UActorChannel::ReadContentBlockHeader in the deobf dump by finding the LEA(s) that
# reference the committed UTF-16LE log string "sub-object class", then find each referencing function's start.
import sys
DUMP = r"G:\git\Supervive Revival Project\dumps\toggles\SUPERVIVE-deobf.exe"
DATA = open(DUMP, "rb").read()
# ImageBase: read from PE optional header for correctness.
import struct
pe_off = struct.unpack_from("<I", DATA, 0x3C)[0]
assert DATA[pe_off:pe_off+4] == b"PE\0\0"
opt = pe_off + 24
magic = struct.unpack_from("<H", DATA, opt)[0]
IMAGEBASE = struct.unpack_from("<Q", DATA, opt+24)[0] if magic == 0x20b else struct.unpack_from("<I", DATA, opt+28)[0]
print(f"ImageBase = {IMAGEBASE:#x}  file size = {len(DATA):#x}")

def find_utf16(s):
    pat = s.encode("utf-16-le")
    hits = []
    i = DATA.find(pat)
    while i != -1 and len(hits) < 40:
        hits.append(i)
        i = DATA.find(pat, i+2)
    return hits

for needle in ["sub-object class", "stably named", "Instantiating sub-object"]:
    hits = find_utf16(needle)
    print(f"\n=== UTF-16LE '{needle}': {len(hits)} hit(s) ===")
    for rva in hits[:6]:
        va = IMAGEBASE + rva
        # show a little context (the full wide string)
        end = DATA.find(b"\0\0", rva)
        raw = DATA[rva:end if 0<end-rva<200 else rva+120]
        try: txt = raw.decode("utf-16-le", "replace")
        except: txt = "?"
        txt = "".join(c if 32 <= ord(c) < 127 else "." for c in txt)
        print(f"  @ rva {rva:#x} va {va:#x}  \"{txt}\"")

# Now scan for LEA rip-rel referencing the FIRST 'sub-object class' hit's VA.
targets = find_utf16("sub-object class")
if not targets:
    print("\nNO 'sub-object class' string — may be encrypted. Trying 'stably named'/'Instantiating'.")
lea_modrm = {0x05,0x0D,0x15,0x1D,0x25,0x2D,0x35,0x3D}
def find_lea_refs(string_rva):
    tgt_va = IMAGEBASE + string_rva
    refs = []
    # scan for (48|4C) 8D <modrm rip> <disp32>
    i = 0
    n = len(DATA)
    while i < n-7:
        b0 = DATA[i]
        if (b0 == 0x48 or b0 == 0x4C) and DATA[i+1] == 0x8D and DATA[i+2] in lea_modrm:
            disp = struct.unpack_from("<i", DATA, i+3)[0]
            instr_end = i + 7
            if IMAGEBASE + instr_end + disp == tgt_va:
                refs.append(i)
        i += 1
    return refs

for string_rva in targets[:4]:
    refs = find_lea_refs(string_rva)
    print(f"\n=== LEA refs to string @ va {IMAGEBASE+string_rva:#x}: {len(refs)} ===")
    for r in refs:
        print(f"  lea @ rva {r:#x} va {IMAGEBASE+r:#x}")
