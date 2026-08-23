import struct,sys,importlib.util
_SAVED=list(sys.argv)
spec=importlib.util.spec_from_file_location("uht",r"G:\git\Supervive Revival Project\scratchpad\s139\uht.py")
m=importlib.util.module_from_spec(spec); sys.argv=['x','__none__']; spec.loader.exec_module(m)
sys.argv=_SAVED
im=m.im
def dec(r):
    b=im.d[r:r+16]
    # or byte  [rcx+disp32], imm8  = 80 89 dd dd dd dd ii
    if b[0:2]==b'\x80\x89': return "or byte [rcx+0x%X],0x%02X"%(struct.unpack_from('<I',b,2)[0],b[6])
    if b[0:2]==b'\x83\x89': return "or dword [rcx+0x%X],0x%02X"%(struct.unpack_from('<I',b,2)[0],b[6])
    if b[0:2]==b'\x81\x89': return "or dword [rcx+0x%X],0x%X"%(struct.unpack_from('<I',b,2)[0],struct.unpack_from('<I',b,6)[0])
    if b[0:2]==b'\x80\x49': return "or byte [rcx+0x%X],0x%02X"%(b[2],b[3])
    if b[0:2]==b'\x83\x49': return "or dword [rcx+0x%X],0x%02X"%(b[2],b[3])
    if b[0:2]==b'\x80\x09': return "or byte [rcx],0x%02X"%(b[2])
    if b[0:2]==b'\x83\x09': return "or dword [rcx],0x%02X"%(b[2])
    return "RAW "+b[:10].hex()
def run(anchor,arr=None):
    strs=m.find_ascii(anchor)
    for s in strs:
        for pr in m.find_qword_refs(s):
            d=m.decode_prop(pr)
            if not d: continue
            for slot in m.find_qword_refs(pr):
                lo,hi=m.walk_array(slot); n=(hi-lo)//8+1
                if n<3: continue
                print("== %s array 0x%08X (%d)"%(anchor,lo,n))
                for k in range(n):
                    rr=im.rva(im.q(lo+k*8)); dd=m.decode_prop(rr)
                    gen=dd['gen']&0x3F
                    if gen==0x0C:
                        sz=struct.unpack_from('<I',im.d,rr+0x34)[0]
                        sb=im.q(rr+0x38); sr=im.rva(sb)
                        print("   %-48s sizeofouter=0x%-6X setbit@0x%08X : %s"%(dd['name'],sz,sr or 0,dec(sr) if sr else '?'))
                return
for a in sys.argv[1:]:
    run(a)
