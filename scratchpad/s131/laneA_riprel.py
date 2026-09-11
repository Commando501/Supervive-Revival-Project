import sys, struct
sys.path.insert(0, r"G:\git\Supervive Revival Project\scratchpad\fk27")
import fkdis
img = fkdis.Img(r"G:\git\Supervive Revival Project\dumps\merged4.dump.exe")

# (site_rva, end_rva, disp) machine-computed from the capstone listing
sites = [
    ("0x55CD598 addsd  xmm0,[rip+d]", 0x055CD598, 0x055CD5A0, 0x354FF28),
    ("0x55CD684 movups xmm0,[rip+d]", 0x055CD684, 0x055CD68B, 0x43FB12D),
    ("0x55CD693 movsd  xmm0,[rip+d]", 0x055CD693, 0x055CD69B, 0x43FB12D),
    ("0x55CD6E6 movss  xmm0,[rip+d]", 0x055CD6E6, 0x055CD6EE, 0x20D39F2),
    ("0x55CD794 cmp    byte[rip+d],2", 0x055CD794, 0x055CD79B, 0x4A69325),
    ("0x55CD79D lea    rdx,[rip+d]",  0x055CD79D, 0x055CD7A4, 0x354F84C),
    ("0x55CD7A4 lea    rcx,[rip+d]",  0x055CD7A4, 0x055CD7AB, 0x4A69315),
    ("0x55CD7B2 cmp    byte[rip+d],2",0x055CD7B2, 0x055CD7B9, 0x4A686C7),
    ("0x55CD7BB lea    rdx,[rip+d]",  0x055CD7BB, 0x055CD7C2, 0x354F746),
    ("0x55CD7C2 lea    rcx,[rip+d]",  0x055CD7C2, 0x055CD7C9, 0x4A686B7),
    ("0x55CD7CE lea    rdx,[rip+d]",  0x055CD7CE, 0x055CD7D5, 0x354F75B),
]
def wstr(rva, maxn=400):
    d = img.read(rva, maxn*2)
    if d is None: return "<unmapped>"
    out=[]
    for i in range(0, len(d), 2):
        c = d[i] | (d[i+1]<<8)
        if c==0: break
        out.append(chr(c))
    return "".join(out)

for label, site, end, disp in sites:
    tgt = end + disp
    s = img.sec_of(tgt)
    secn = s[0] if s else "?"
    raw = img.read(tgt, 16)
    print(f"{label}")
    print(f"    -> RVA 0x{tgt:08X}  sec={secn}  bytes={raw.hex() if raw else None}")
    if secn in (".rdata",):
        print(f"    W\"{wstr(tgt)[:200]}\"")
    print()
