import sys, struct
sys.path.insert(0, r"G:\git\Supervive Revival Project\scratchpad\fk27")
import fkdis
img = fkdis.Img(r"G:\git\Supervive Revival Project\dumps\merged4.dump.exe")
IB = img.imagebase
def rva(va): return va - IB
def wstr(r, maxn=600):
    d = img.read(r, maxn*2)
    if d is None: return "<unmapped>"
    out=[]
    for i in range(0, len(d), 2):
        c = d[i] | (d[i+1]<<8)
        if c==0: break
        out.append(chr(c))
    return "".join(out)
def astr(r, maxn=600):
    d = img.read(r, maxn)
    if d is None: return "<unmapped>"
    out=[]
    for c in d:
        if c==0: break
        if c<32 or c>126: return None
        out.append(chr(c))
    return "".join(out)

def dumprec(r, n=6, label=""):
    print(f"== record @0x{r:08X} {label}")
    d = img.read(r, n*8)
    for i in range(n):
        q = struct.unpack_from("<Q", d, i*8)[0]
        note=""
        if IB <= q < IB+0x0B000000:
            t = rva(q)
            s = img.sec_of(t)
            w = wstr(t, 200)
            a = astr(t, 200)
            note = f"-> rva 0x{t:08X} [{s[0] if s else '?'}]"
            if w and all(32<=ord(c)<0x3000 for c in w[:60]) and len(w)>2:
                note += f'  W"{w[:180]}"'
            elif a and len(a)>2:
                note += f'  A"{a[:180]}"'
        print(f"   +0x{i*8:02X} = 0x{q:016X}  {note}")
    print()

for r,l in [(0x08B1CFF0,"bail@0x55CD794 (rdx)"),(0x08B1CF08,"bail@0x55CD7B2 (rdx)"),(0x08B1CF30,"str@0x55CD7CE (rdx)")]:
    dumprec(r, 6, l)

# log category objects
for r,l in [(0x0A036AC0,"cat @0x55CD794"),(0x0A035E80,"cat @0x55CD7B2")]:
    d = img.read(r,16)
    print(f"category @0x{r:08X} {l}: {d.hex()}")
    # FLogCategoryBase: Verbosity@0, DebugBreak@1, DefaultVerbosity@2, CompileTime@3, FName@4
    ver,dbg,dv,ct = d[0],d[1],d[2],d[3]
    fn = struct.unpack_from("<I", d, 4)[0]
    print(f"   Verbosity={ver} Default={dv} CompileTime={ct} FNameIdx={fn}")
print()
