import sys,os,struct
os.chdir('G:/git/Supervive Revival Project'); sys.path.insert(0,'scratchpad/s138/laneW2')
from pe import PE
pe=PE('dumps/merged13.dump.exe'); d=pe.data; IB=pe.imagebase
VERB={0:'NoLogging',1:'Fatal',2:'Error',3:'Warning',4:'Display',5:'Log',6:'Verbose',7:'VeryVerbose'}
def wstr(r,n=400):
    out=[]
    for i in range(n):
        c=d[r+2*i]|(d[r+2*i+1]<<8)
        if c==0: break
        if c<32 or c>126: out.append('?')
        else: out.append(chr(c))
    return ''.join(out)
def astr(r,n=300):
    e=d.find(b'\0',r,r+n)
    return d[r:e].decode('latin1') if e>r else ''
def rec(r):
    fmtp,filep,line,verb = struct.unpack_from('<QQii', d, r)
    return dict(rec=r, fmt_rva=fmtp-IB, fmt=wstr(fmtp-IB), file=astr(filep-IB), line=line, verb=VERB.get(verb,verb))
if __name__=='__main__':
    for a in (0x076EC5C8,):
        x=rec(a); print(x)
