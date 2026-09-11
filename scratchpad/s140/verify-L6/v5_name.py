import struct
P=r"G:\git\Supervive Revival Project\dumps\merged13.dump.exe"
D=open(P,'rb').read(); IB=0x7FF608F40000
def q(r): return struct.unpack_from('<Q',D,r)[0]
def cstr(r,n=64):
    e=D.find(b'\0',r); return D[r:e].decode('ascii','replace')
for lbl,rec in [("GetRecentVelocity?",0x09BC9AD0),("GetLokiCharacterMovement? (CONTROL)",0x09BC4B60)]:
    a,b,c=q(rec),q(rec+8),q(rec+16)
    print(f"{lbl:38} rec={rec:#x}")
    print(f"   +0x00 name_ptr={a:#x} rva={a-IB:#x} -> {cstr(a-IB)!r}")
    print(f"   +0x08 thunk   ={b:#x} rva={b-IB:#x}")
    print(f"   +0x10 impl    ={c:#x} rva={c-IB:#x}")
# search .rdata for the literal
for s in (b"GetRecentVelocity\0", b"GetLokiCharacterMovement\0", b"OnMovementUpdated\0",
          b"StartNewPhysics\0", b"PerformMovement\0"):
    o=0; hits=[]
    while True:
        i=D.find(s,o)
        if i<0: break
        hits.append(i); o=i+1
    print(f"ASCII {s[:-1].decode():26} hits={len(hits)} {[hex(h) for h in hits[:4]]}")
