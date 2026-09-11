# disasm_live.py — capstone disassembly of a live-process function (read-only RPM).
# usage: disasm_live.py <PID> <BASE-hex> <RVA-hex> [nbytes]
import ctypes, sys
from ctypes import wintypes
from capstone import *

PID=int(sys.argv[1],0); BASE=int(sys.argv[2],16); RVA=int(sys.argv[3],16)
N=int(sys.argv[4],0) if len(sys.argv)>4 else 0x400

k32=ctypes.WinDLL("kernel32",use_last_error=True); k32.OpenProcess.restype=wintypes.HANDLE
h=k32.OpenProcess(0x1F0FFF,False,PID)
if not h: print("OpenProcess failed",ctypes.get_last_error()); sys.exit(1)
def rpm(a,n):
    b=(ctypes.c_ubyte*n)(); r=ctypes.c_size_t(0)
    if not k32.ReadProcessMemory(h,ctypes.c_void_p(a),b,n,ctypes.byref(r)): return None
    return bytes(b)[:r.value]

addr=BASE+RVA
code=rpm(addr,N)
if not code: print("RPM failed"); sys.exit(1)
md=Cs(CS_ARCH_X86,CS_MODE_64); md.detail=True
print("func @0x%X (base+0x%X)  %d bytes"%(addr,RVA,len(code)))
depth=0
for i in md.disasm(code,addr):
    rva=i.address-BASE
    tgt=""
    # annotate rip-relative and direct call/jmp targets
    if i.mnemonic in ("call","jmp") and i.op_str.startswith("0x"):
        t=int(i.op_str,16); tgt="   -> base+0x%X"%(t-BASE) if BASE<t<BASE+0xA9E1000 else "   -> 0x%X"%t
    mark=""
    if i.mnemonic=="ret": mark="   <<<<<< RET"
    if i.mnemonic.startswith("j") and i.mnemonic!="jmp": mark="   <-- branch"
    print("  +0x%-8X %-22s %s%s%s"%(rva," ".join("%02x"%b for b in i.bytes)[:21],
          "%s %s"%(i.mnemonic,i.op_str), tgt, mark))
