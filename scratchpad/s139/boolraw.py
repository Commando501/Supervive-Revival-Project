import struct,sys,importlib.util
spec=importlib.util.spec_from_file_location("uht",r"G:\git\Supervive Revival Project\scratchpad\s139\uht.py")
m=importlib.util.module_from_spec(spec); sys.argv=['x','__none__']; spec.loader.exec_module(m)
im=m.im
lo=0x07FB1BB0
names={}
for k in range(164):
    rr=im.rva(im.q(lo+k*8)); dd=m.decode_prop(rr); names[dd['name']]=rr
for n in ('bCheatFlying','bRunPhysicsWithNoController','bJustTeleported','bDeferUpdateMoveComponent'):
    r=names[n]
    print(n, "rec=0x%08X"%r)
    for o in range(0,0x60,8):
        print("   +0x%02X %s"%(o, im.d[r+o:r+o+8].hex()))
