import capstone
from vimg import VImg
CS = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64); CS.detail=True
im=VImg()
# every raw-byte line the lane published, verbatim from its report
CLAIMS = [
 (0x035e9f82, "88 83 03 07 00 00",             "mov byte [rbx+0x703], al"),
 (0x035e9f44, "66 0f 2e 8b 60 03 00 00",       "ucomisd xmm1,[rbx+0x360]"),
 (0x035e9f5f, "66 0f 2e 8b 68 03 00 00",       "ucomisd xmm1,[rbx+0x368]"),
 (0x035e9f6f, "66 0f 2e 83 70 03 00 00",       "ucomisd xmm0,[rbx+0x370]"),
 (0x035ea009, "88 8b e9 02 00 00",             "mov byte [rbx+0x2e9], cl"),
 (0x035eb130, "44 89 bb dc 03 00 00",          "mov dword [rbx+0x3dc], r15d"),
 (0x035eb13a, "ff 90 20 07 00 00",             "call qword [rax+0x720]"),
 (0x035eb78d, "0f 11 83 60 03 00 00",          "movups [rbx+0x360], xmm0"),
 (0x035eb7bb, "0f 11 83 78 03 00 00",          "movups [rbx+0x378], xmm0"),
 (0x035cabe0, "80 89 e9 02 00 00 08 c3",       "or byte [rcx+0x2e9],8 ; ret"),
 (0x055b85c1, "e8 fa 18 03 fe",                "call 0x035e9ec0"),
 (0x035e9f7f, "45 33 ff",                      "xor r15d,r15d"),
 (0x035e9fad, "41 8b d7",                      "mov edx,r15d"),
 (0x03600a73, "",                              "or al,0x40 (lane by-product 2)"),
 (0x03600a75, "",                              "mov [rbx+0x2e8],al"),
]
for rva, expect, note in CLAIMS:
    n = len(expect.split()) if expect else 8
    b = im.read(rva, max(n,16))
    got = " ".join("%02x"%x for x in b[:n]) if expect else ""
    ok = (got==expect.lower()) if expect else None
    ins = list(CS.disasm(bytes(b), rva))[:2]
    dis = "; ".join("%s %s"%(i.mnemonic,i.op_str) for i in ins[:1])
    flag = "OK " if ok else ("MISMATCH" if ok is False else "   ")
    print("0x%08x %s expect[%s] got[%s]  -> %s   (%s)" % (rva, flag, expect, got, dis, note))
