# PRE-REGISTERED PREDICTION (written before reading pawn#2's Number):
#   Known creation order (from flight-3 marker + flight-2 marker timestamps):
#     PlayerController < player hero < botpawn#1 < AIC#1 < botpawn#2 < AIC#2
#   If FName.Number is a DECREASING global spawn counter, then Number must be
#   STRICTLY DECREASING along that sequence. Specifically:
#     2147470886 (AIC#2) < N(botpawn#2) < 2147470967 (AIC#1)
import ctypes
from ctypes import wintypes
PID=43456; BASE=0x7FF608F40000; NAMEPOOL=BASE+0x9D81450
k32=ctypes.WinDLL("kernel32",use_last_error=True); k32.OpenProcess.restype=wintypes.HANDLE
h=k32.OpenProcess(0x1F0FFF,False,PID)
def rpm(a,n):
    b=(ctypes.c_ubyte*n)(); r=ctypes.c_size_t(0)
    if not k32.ReadProcessMemory(h,ctypes.c_void_p(a),b,n,ctypes.byref(r)) or r.value!=n: return None
    return bytes(b)
def u32(b,o): return int.from_bytes(b[o:o+4],"little")
def ptr(v): return 0x10000<=v<0x0001000000000000 and (v&7)==0
def fname(i):
    blk=i>>16; off=(i&0xFFFF)<<1; bp=rpm(NAMEPOOL+blk*8,8)
    bp=int.from_bytes(bp,"little"); hd=int.from_bytes(rpm(bp+off,2),"little")
    ln=hd>>6; w=hd&1; s=rpm(bp+off+2,ln*(2 if w else 1))
    return "".join(chr(s[k*2]|(s[k*2+1]<<8)) for k in range(ln)) if w else s.decode("latin1","replace")
seq=[("PlayerController      ",0x1B3234713C0),("player hero (sp shim) ",0x1B399FF5580),
     ("botpawn#1 (flight2)   ",0x1B3E6922AE0),("AIC#1     (flight2)   ",0x1B3F58BC5E0),
     ("botpawn#2 (flight3)   ",0x1B302F7D560),("AIC#2     (flight3)   ",0x1B3F75EAEA0)]
print("object (in KNOWN creation order)        InternalIndex   FName.Number")
prev=None; ok_num=True; ok_idx=True
for lbl,o in seq:
    b=rpm(o,0x28); idx=u32(b,0x10); num=u32(b,0x24)
    mark=""
    if prev is not None:
        if num>=prev[1]: ok_num=False; mark+=" <-- Number NOT decreasing"
        if idx>=prev[0]: pass
        else: ok_idx=False
    print(f"  {lbl} {fname(u32(b,0x20)):22s} {idx:<9} {num}{mark}")
    prev=(idx,num)
print(f"\nFName.Number strictly DECREASING along known creation order? {'YES' if ok_num else 'NO'}")
print(f"InternalIndex monotone along known creation order?           {'YES' if ok_idx else 'NO  <-- USELESS as creation-order signal'}")
