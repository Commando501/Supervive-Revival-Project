# Watch a pawn's movement-input vectors + its CMC accel/velocity over a few seconds, to see if WASD input reaches
# the pawn. Hold movement keys while this runs. Read-only RPM.
#   usage: input_watch.py <PID> <PAWN-hex> <CMC-hex> [seconds]
# Offsets (this build): Pawn ControlInputVector@+0x418, LastControlInputVector@+0x430 (FVector dbl);
#   CMC Acceleration@+0x328 (FVector dbl), Velocity@+0xE8 (FVector dbl), MovementMode@+0x231.
import ctypes, sys, struct, time
from ctypes import wintypes
PID=int(sys.argv[1],0); PAWN=int(sys.argv[2],16); CMC=int(sys.argv[3],16); SECS=float(sys.argv[4]) if len(sys.argv)>4 else 8.0
k32=ctypes.WinDLL("kernel32",use_last_error=True); k32.OpenProcess.restype=wintypes.HANDLE
h=k32.OpenProcess(0x1F0FFF,False,PID)
def rpm(a,n):
    b=(ctypes.c_ubyte*n)(); r=ctypes.c_size_t(0)
    if not k32.ReadProcessMemory(h,ctypes.c_void_p(a),b,n,ctypes.byref(r)) or r.value!=n: return None
    return bytes(b)
def vec(a):
    b=rpm(a,24)
    if not b: return (0.0,0.0,0.0)
    return struct.unpack("<ddd",b)
def mag(v): return (v[0]*v[0]+v[1]*v[1]+v[2]*v[2])**0.5
def u8(a): b=rpm(a,1); return b[0] if b else -1
MODES={0:"None",1:"Walk",2:"NavWalk",3:"Fall",4:"Swim",5:"Fly",6:"Custom"}
print("Hold WASD now. Sampling ControlInputVector / LastControlInputVector / Acceleration / Velocity ...")
print(f"{'t':>5} {'mode':>5} {'|Ctrl|':>8} {'|LastCtrl|':>10} {'|Accel|':>10} {'|Vel|':>8}")
t0=time.time(); maxc=maxl=maxa=maxv=0.0
while time.time()-t0<SECS:
    ci=vec(PAWN+0x418); li=vec(PAWN+0x430); ac=vec(CMC+0x328); ve=vec(CMC+0xE8); mm=u8(CMC+0x231)
    mc,ml,ma,mv=mag(ci),mag(li),mag(ac),mag(ve)
    maxc=max(maxc,mc); maxl=max(maxl,ml); maxa=max(maxa,ma); maxv=max(maxv,mv)
    print(f"{time.time()-t0:5.1f} {MODES.get(mm,str(mm)):>5} {mc:8.3f} {ml:10.3f} {ma:10.1f} {mv:8.1f}")
    time.sleep(0.25)
print(f"\nMAX over window: |Ctrl|={maxc:.3f} |LastCtrl|={maxl:.3f} |Accel|={maxa:.1f} |Vel|={maxv:.1f}")
print("Interpretation: |Ctrl|/|LastCtrl|>0 => WASD reaches the pawn (AddMovementInput fires). ==0 => input not routed to the pawn.")
