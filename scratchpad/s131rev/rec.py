# Independent record-table lookup: name(ascii in .rdata) -> .data qword ptr -> {+8 thunk, +0x10 impl}
import sys, struct, io
sys.stdout=io.TextIOWrapper(sys.stdout.buffer,encoding='utf-8',errors='backslashreplace')
sys.path.insert(0,r"G:\git\Supervive Revival Project\scratchpad\s131rev")
from av import img
FOLD={0xF7EC20:'FOLD ret0',0xF7EB50:'FOLD xor eax;ret',0xF7EB60:'FOLD xor al;ret',0xB9E1F0:'FOLD mov al,1;ret'}
def lookup(key,name,verbose=True):
    I=img(key); B=I.base; d=I.d
    # section ranges
    rng={nm:(va,vs) for nm,va,vs,ro,rs in I.secs}
    rv,rs_=rng['.rdata']; dv,ds=rng['.data']; tv,ts=rng['.text']
    pat=name.encode()+b'\x00'
    hits=[]
    off=rv
    end=rv+rs_
    while True:
        i=d.find(pat,off,end)
        if i<0: break
        # require preceding byte to be 0 (start of string)
        if i==0 or d[i-1]==0: hits.append(i)
        off=i+1
    out=[]
    for h in hits:
        tgt=(B+h).to_bytes(8,'little')
        o=dv
        while True:
            j=d.find(tgt,o,dv+ds)
            if j<0: break
            if j%8==0:
                th=int.from_bytes(d[j+8:j+16],'little'); im=int.from_bytes(d[j+16:j+24],'little')
                ok = B<=th<B+len(d) and B<=im<B+len(d)
                trv=th-B if ok else -1; irv=im-B if ok else -1
                if ok and tv<=trv<tv+ts and tv<=irv<tv+ts:
                    out.append((h,j,trv,irv))
            o=j+1
    if verbose:
        if not out: print("  %-60s : NO RECORD (name hits in .rdata: %d)"%(name,len(hits)))
        for h,j,trv,irv in out:
            b=I.read(irv,8).hex()
            print("  %-58s rec@.data 0x%08X name@0x%08X thunk 0x%08X impl 0x%08X  %-18s bytes %s"%(
                name,j-8,h,trv,irv,FOLD.get(irv,''),b))
    return out
if __name__=="__main__":
    key=sys.argv[1]
    for n in sys.argv[2:]: lookup(key,n)
