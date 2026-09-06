import sys,os,struct
os.chdir('G:/git/Supervive Revival Project'); sys.path.insert(0,'scratchpad/s138/laneW2')
from pe import PE
pe=PE('dumps/merged13.dump.exe'); d=pe.data
TEXT=[s for s in pe.sections if s['name']=='.text'][0]
lo,hi=TEXT['rawptr'],TEXT['rawptr']+TEXT['rawsz']
def refs_to(target, maxhits=200):
    """all p in .text where dword at p is a rip-disp landing on target (instr end = p+4)."""
    out=[]
    # brute: scan every 4-byte window
    import array
    for p in range(lo, hi-4):
        # cheap filter on last byte of disp
        disp = target - (p+4)
        if -0x80000000 <= disp < 0x80000000:
            pass
        else:
            continue
        break
    # do it the other way: compute needed dword per position -> too slow. Use direct search on candidate disp bytes.
    # Instead: for each position, read dword and test. Vectorize with numpy.
    import numpy as np
    arr = np.frombuffer(d[lo:hi-4+4], dtype=np.uint8)
    n = hi-lo-4
    dw = np.frombuffer(d[lo:lo+n+4], dtype=np.uint8)
    # build int32 view over unaligned offsets: use 4 shifted arrays
    b0=arr[0:n].astype(np.int64); b1=arr[1:n+1].astype(np.int64)
    b2=arr[2:n+2].astype(np.int64); b3=arr[3:n+3].astype(np.int64)
    val = b0 | (b1<<8) | (b2<<16) | (b3<<24)
    val = np.where(val >= 0x80000000, val - 0x100000000, val)
    pos = np.arange(lo, lo+n, dtype=np.int64)
    tgt = pos + 4 + val
    idx = np.nonzero(tgt == target)[0]
    return [int(lo+i) for i in idx[:maxhits]]
if __name__=='__main__':
    for t in [int(x,0) for x in sys.argv[1:]]:
        r=refs_to(t)
        print('target 0x%08X : %d disp-sites'%(t,len(r)), [hex(x) for x in r[:40]])
