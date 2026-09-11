import sys; sys.path.insert(0,'scratchpad/s139')
from img import q, IMAGEBASE, sec_of
def slots(vt,n):
    return [q(vt+8*i)-IMAGEBASE for i in range(n)]
if __name__=="__main__":
    vts=[int(x,16) for x in sys.argv[1:-1]]
    n=int(sys.argv[-1])
    tabs=[slots(v,n) for v in vts]
    for i in range(n):
        row=[t[i] for t in tabs]
        mark = "" if len(set(row))==1 else "  <-- DIFF"
        print("slot %3d disp 0x%04X  "%(i,8*i)+"  ".join("0x%08X"%v for v in row)+mark)
