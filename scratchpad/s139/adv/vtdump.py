import sys
sys.path.insert(0,r"G:\git\Supervive Revival Project\scratchpad\s139\adv")
from img import *
def vt(rva, n=420):
    out=[]
    for i in range(n):
        va = u64(rva+i*8)
        r = va - IMAGEBASE
        out.append(r)
    return out
if __name__=='__main__':
    a=int(sys.argv[1],16); b=int(sys.argv[2],16) if len(sys.argv)>2 else None
    n=int(sys.argv[3]) if len(sys.argv)>3 else 420
    A=vt(a,n)
    if b:
        B=vt(b,n)
        diffs=[i for i in range(n) if A[i]!=B[i]]
        print("differing slots:",len(diffs))
        for i in diffs: print(f"  slot {i:3d} disp 0x{i*8:04X}: A=0x{A[i]:08X} B=0x{B[i]:08X}")
    else:
        for i in range(n): print(f"slot {i:3d} disp 0x{i*8:04X}: 0x{A[i]:08X}")
