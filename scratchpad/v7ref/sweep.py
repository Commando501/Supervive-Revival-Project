exec(open('scratchpad/v7ref/lib.py').read())
import sys
def rel32_callers(target, lo=TEXT_LO, hi=TEXT_HI):
    hits=[]
    i=lo
    dv=memoryview(D)
    import struct
    while i<hi-5:
        op=D[i]
        if op==0xE8 or op==0xE9:
            rel=struct.unpack_from("<i",D,i+1)[0]
            if i+5+rel==target:
                hits.append((i,'call' if op==0xE8 else 'jmp'))
        i+=1
    return hits
if __name__=='__main__':
    for a in sys.argv[1:]:
        t=int(a,16)
        h=rel32_callers(t)
        print(f'target {t:#x}: {len(h)} rel32 sites -> {[(hex(x),k) for x,k in h[:20]]}')
