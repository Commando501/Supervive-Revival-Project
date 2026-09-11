import sys, struct
sys.path.insert(0,'scratchpad/lanev5')
from pe import load, pehdr
data=load(); IB,secs=pehdr(data)
def u64(a): return struct.unpack_from('<Q',data,a)[0]
def u32(a): return struct.unpack_from('<I',data,a)[0]
def cstr(a):
    e=data.index(b'\0',a); return data[a:e].decode('latin1')
def vt_rtti(vt_rva):
    col_va=u64(vt_rva-8)
    if col_va==0: return None,"COL ptr is 0"
    col=col_va-IB
    if not (0<col<len(data)): return None,"COL out of range 0x%X"%col_va
    sig,off,cdoff,ptd,pcd,selfrva=struct.unpack_from('<IIIIII',data,col)
    # In /LARGEADDRESSAWARE 64-bit, fields are RVAs relative to module base
    td=ptd
    if not (0<td<len(data)): return None,"TypeDescriptor rva bad 0x%X"%td
    name=cstr(td+16)
    return name,dict(col_rva=hex(col),sig=sig,offset=off,td=hex(td),self=hex(selfrva))
for a in sys.argv[1:]:
    v=int(a,16)
    n,info=vt_rtti(v)
    print("vtable 0x%08X -> %s   %s"%(v,n,info))
