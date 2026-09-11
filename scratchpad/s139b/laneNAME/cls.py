import sys,struct,re
sys.path.insert(0,r'scratchpad/s139b/laneNAME')
from hh import *
def wstr(rva,n=200):
    b=rd(rva,n*2); s=''
    for i in range(0,len(b),2):
        c=b[i]|(b[i+1]<<8)
        if c==0: break
        if c<32 or c>126: return None
        s+=chr(c)
    return s
def clsname(fn,span=0x140):
    out=[]
    for ins in dis(fn,span):
        if ins.mnemonic=='lea' and 'rip' in ins.op_str:
            try: disp=int(ins.op_str.split('rip + ')[1].rstrip(']'),16)
            except:
                try: disp=-int(ins.op_str.split('rip - ')[1].rstrip(']'),16)
                except: continue
            t=ins.address+ins.size+disp
            if sec_of(t)=='.rdata':
                s=wstr(t)
                if s and len(s)>2: out.append((hex(t),s))
    return out
if __name__=='__main__':
    for a in sys.argv[1:]:
        fn=int(a,16)
        print(hex(fn), clsname(fn))
