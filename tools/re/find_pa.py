# Find PrimaryAssetId fields (PrimaryAssetType.Name == "Hero" id 0x1A568) inside a UObject,
# to locate SelectedHeroAsset etc. Read-only RPM.  usage: find_pa.py <PID> <obj-hex> <size-dec>
import ctypes, sys
from ctypes import wintypes
PID=int(sys.argv[1],0); OBJ=int(sys.argv[2],16); SIZE=int(sys.argv[3])
BASE=0x7FF682A80000; NAMEPOOL=BASE+0x9D81450; HERO=0x1A568
k32=ctypes.WinDLL("kernel32",use_last_error=True); k32.OpenProcess.restype=wintypes.HANDLE
h=k32.OpenProcess(0x1F0FFF,False,PID)
def rpm(a,n):
    b=(ctypes.c_ubyte*n)(); r=ctypes.c_size_t(0)
    if not k32.ReadProcessMemory(h,ctypes.c_void_p(a),b,n,ctypes.byref(r)) or r.value!=n: return None
    return bytes(b)
def looksptr(v): return 0x10000<=v<0x0001000000000000 and (v&7)==0
def fname(idx):
    blk=idx>>16; off=(idx&0xFFFF)<<1
    bp=rpm(NAMEPOOL+blk*8,8)
    if not bp: return "?"
    bp=int.from_bytes(bp,"little")
    if not looksptr(bp): return "?"
    hd=rpm(bp+off,2)
    if not hd: return "?"
    hd=int.from_bytes(hd,"little"); ln=hd>>6; wide=hd&1
    if ln<=0 or ln>200: return "?"
    s=rpm(bp+off+2,ln*(2 if wide else 1))
    if not s: return "?"
    return "".join(chr(s[i*2]|(s[i*2+1]<<8)) for i in range(ln)) if wide else s.decode("latin1","replace")
b=rpm(OBJ,SIZE)
if not b: print("read failed"); sys.exit(1)
for o in range(0,SIZE-16,8):
    if int.from_bytes(b[o:o+4],"little")==HERO and int.from_bytes(b[o+4:o+8],"little")==0:
        nameId=int.from_bytes(b[o+8:o+12],"little")
        print(f"  +0x{o:03X}: PrimaryAssetId Hero:{fname(nameId)}  (nameFName=0x{nameId:X})")
