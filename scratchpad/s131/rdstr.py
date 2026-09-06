import sys
sys.path.insert(0, r"G:\git\Supervive Revival Project\scratchpad\fk27")
import fkdis, struct
img = fkdis.Img(r"G:\git\Supervive Revival Project\dumps\merged4.dump.exe")
def wstr(rva, n=400):
    b = img.read(rva, n)
    out=[]
    for i in range(0,len(b)-1,2):
        c = struct.unpack_from("<H", b, i)[0]
        if c==0: break
        out.append(chr(c))
    return "".join(out)
for r in (0x08B1CFF0, 0x08B1CF08, 0x08B1CF30, 0x08B1D4C8):
    print("0x%08X : %r" % (r, wstr(r)))
print("--- FLogCategoryBase records (Verbosity@0,DebugBreak@1,Default@2,CompileTime@3,FName@4) ---")
for r in (0x0A036AC0, 0x0A035E80):
    b = img.read(r, 16)
    print("0x%08X : %s" % (r, b.hex(' ')))
print("--- rdata float @0x8B1D4C8 ---")
print(struct.unpack("<d", img.read(0x08B1D4C8,8))[0])
print("--- .data vector @0x99C87B8 (24B) ---")
print(struct.unpack("<3d", img.read(0x099C87B8,24)))
print("--- rdata float32 @0x76A10E0 ---")
print(struct.unpack("<f", img.read(0x076A10E0,4))[0])
