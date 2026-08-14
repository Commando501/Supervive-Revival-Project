# S118 FINAL -- full 8-byte-stride delegate enumeration + full-length case bodies.
# BLIND SPOT CLOSED: the previous enumerations stepped 0x10 and so could not see a
# slot at an offset == 8 (mod 16).  +0x228 is exactly such a slot.
import ctypes,sys,json
from ctypes import wintypes
PID=int(sys.argv[1],0);BASE=int(sys.argv[2],16);LOBBY=int(sys.argv[3],16);MODHI=BASE+0xA9E1000
k32=ctypes.WinDLL("kernel32",use_last_error=True);k32.OpenProcess.restype=wintypes.HANDLE
h=k32.OpenProcess(0x1F0FFF,False,PID)
def rpm(a,n):
    b=(ctypes.c_ubyte*n)();r=ctypes.c_size_t(0)
    if not k32.ReadProcessMemory(h,ctypes.c_void_p(a),b,n,ctypes.byref(r)) or r.value!=n: return None
    return bytes(b)
def u64(b,o): return int.from_bytes(b[o:o+8],"little")
def u32(b,o): return int.from_bytes(b[o:o+4],"little")
def i32(b,o): return int.from_bytes(b[o:o+4],"little",signed=True)
NAMEPOOL=BASE+0x9D81450; OBJOBJECTS=BASE+0x9E38930; PERCHUNK=65536; STRIDE=0x18
hdr=rpm(OBJOBJECTS,0x18); objectsPtr=u64(hdr,0); numEl=u32(hdr,0x14)
chunkPtrs=rpm(objectsPtr,((numEl+PERCHUNK-1)//PERCHUNK)*8)
def looksptr(v): return 0x10000<=v<0x0001000000000000 and (v&7)==0
_nc={}
def fname(idx):
    if idx in _nc: return _nc[idx]
    blk=idx>>16;off=(idx&0xFFFF)<<1;bp=rpm(NAMEPOOL+blk*8,8);r="?"
    if bp:
        bp=int.from_bytes(bp,"little")
        if looksptr(bp):
            hd=rpm(bp+off,2)
            if hd:
                hd=int.from_bytes(hd,"little");ln=hd>>6;wide=hd&1
                if 0<ln<200:
                    s=rpm(bp+off+2,ln*(2 if wide else 1))
                    if s: r=("".join(chr(s[i*2]|(s[i*2+1]<<8)) for i in range(ln)) if wide else s.decode("latin1","replace"))
    _nc[idx]=r;return r
def obj_at(idx):
    if idx<0 or idx>=numEl: return None
    ci,j=divmod(idx,PERCHUNK); ch=int.from_bytes(chunkPtrs[ci*8:ci*8+8],"little")
    if not looksptr(ch): return None
    it=rpm(ch+j*STRIDE,STRIDE)
    return (u64(it,0),i32(it,0x10)) if it else None
def objinfo(o):
    cb=rpm(o+0x18,8);nb=rpm(o+0x20,4)
    if not cb or not nb: return("?","?")
    c=int.from_bytes(cb,"little");cn="?"
    if looksptr(c):
        x=rpm(c+0x20,4)
        if x: cn=fname(u32(x,0))
    return (cn,fname(u32(nb,0)))
found=[]
for off in range(0,0x2000,8):
    b=rpm(LOBBY+off,16)
    if not b: continue
    p,s=u64(b,0),i32(b,8)
    if not looksptr(p) or not (1<=s<=8): continue
    inst=rpm(p,0x30)
    if not inst: continue
    vt=u64(inst,0)
    if not (BASE<=vt<MODHI): continue
    handle=u64(inst,0x10); idx,ser=i32(inst,0x18),i32(inst,0x1C); m=u64(inst,0x20)
    it=obj_at(idx); cls=nm="?"; live=None; ok=False
    if it and looksptr(it[0]): cls,nm=objinfo(it[0]); live=it[1]; ok=(live==ser)
    found.append(dict(off=hex(off),ptr=hex(p),size=s,vt=hex(vt-BASE),handle=handle,
        objIndex=idx,serial=ser,liveSerial=live,serialMatch=ok,obj=hex(it[0]) if it else None,
        objClass=cls,objName=nm,method=hex(m-BASE) if BASE<=m<MODHI else hex(m)))
print(f"BOUND delegate slots at 8-byte stride: {len(found)}  (16-byte-aligned only: "
      f"{sum(1 for f in found if int(f['off'],16)%16==0)})")
print(f"{'off':>8} {'size':>4} {'vt':>10} {'handle':>7} {'idx':>7} {'ser':>6} {'ok':>5} {'class':22} {'method':>11}")
for f in found:
    print(f"{f['off']:>8} {f['size']:4d} {f['vt']:>10} {f['handle']:7d} {f['objIndex']:7d} "
          f"{f['serial']:6d} {str(f['serialMatch']):>5} {f['objClass']:22} {f['method']:>11}")
json.dump(found,open("scratchpad/s118/bound_delegates_full.json","w"),indent=1)
print(f"\ndistinct subscriber objects: {sorted(set((f['objClass'],f['obj']) for f in found))}")
print(f"distinct DelegateSize values: {sorted(set(f['size'] for f in found))}")
print(f"distinct instance vtables: {sorted(set(f['vt'] for f in found))}")
