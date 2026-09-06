import sys,struct
sys.path.insert(0,'scratchpad/s137-w3')
from img import Img
im=Img('dumps/merged13.dump.exe'); b=im.b
tx=[s for s in im.sections if s[0]=='.text'][0]
lo,hi=tx[1],tx[1]+tx[4]
def callers(target):
    out=[]
    for pos in range(lo,hi-5):
        op=b[pos]
        if op!=0xE8 and op!=0xE9: continue
        d=struct.unpack_from('<i',b,pos+1)[0]
        if pos+5+d==target: out.append((pos,'call' if op==0xE8 else 'jmp'))
    return out
if __name__=='__main__':
    for t in [int(x,16) for x in sys.argv[1:]]:
        c=callers(t)
        print(hex(t),'rel32 sites (FLOOR):',len(c), [(hex(p),k) for p,k in c[:20]])
