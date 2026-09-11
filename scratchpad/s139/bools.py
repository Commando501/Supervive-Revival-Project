import struct,sys
sys.path.insert(0,r"G:\git\Supervive Revival Project\scratchpad\s139")
import importlib.util
spec=importlib.util.spec_from_file_location("uht",r"G:\git\Supervive Revival Project\scratchpad\s139\uht.py")
m=importlib.util.module_from_spec(spec)
sys.argv=['x','__none__']
spec.loader.exec_module(m)
im=m.im
def decode_setbit(rva):
    b=im.d[rva:rva+16]
    # forms: 80 89 OFF32 MASK  (or byte [rcx+off],imm8)  ; 83 89 OFF32 imm8 (or dword)
    #        81 89 OFF32 imm32 ; 0c/... ; c6 81 OFF32 imm8 (mov byte)
    if b[0:2]==b'\x80\x89': return ('or byte',struct.unpack_from('<I',b,2)[0], b[6])
    if b[0:2]==b'\x83\x89': return ('or dword',struct.unpack_from('<I',b,2)[0], b[6])
    if b[0:2]==b'\x81\x89': return ('or dword32',struct.unpack_from('<I',b,2)[0], struct.unpack_from('<I',b,6)[0])
    if b[0:2]==b'\x80\x49': return ('or byte8',b[2], b[3])
    if b[0:2]==b'\x83\x49': return ('or dword8',b[2], b[3])
    if b[0:2]==b'\x0d\x00': return None
    return ('RAW', b[:10].hex(), 0)
def run(anchor,want):
    strs=m.find_ascii(anchor)
    for s in strs:
        for pr in m.find_qword_refs(s):
            d=m.decode_prop(pr)
            if not d: continue
            for slot in m.find_qword_refs(pr):
                lo,hi=m.walk_array(slot)
                n=(hi-lo)//8+1
                if n<3: continue
                print("== array 0x%08X (%d entries) via %s"%(lo,n,anchor))
                for k in range(n):
                    rr=im.rva(im.q(lo+k*8)); dd=m.decode_prop(rr)
                    if dd['ty'].startswith('Bool') and (not want or dd['name'] in want):
                        sbf=im.q(dd['rec']+0x20); r=im.rva(sbf)
                        info=decode_setbit(r) if r else None
                        print("   %-46s setbit=0x%08X %s"%(dd['name'],r or 0,info))
                    elif want and dd['name'] in want:
                        print("   %-46s off=0x%04X %s"%(dd['name'],dd['off'],dd['ty']))
                return
run('bRunPhysicsWithNoController',{'bCheatFlying','bRunPhysicsWithNoController','bMovementInProgress','bJustTeleported','bDeferUpdateMoveComponent','bEnableScopedMovementUpdates'})
run('bAutoRegisterUpdatedComponent',{'bUpdateOnlyIfRendered','bAutoUpdateTickRegistration','bTickBeforeOwner','bConstrainToPlane'})
