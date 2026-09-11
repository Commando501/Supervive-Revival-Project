import struct,sys
d=open("dumps/merged13.dump.exe",'rb').read()
LO,HI=0x1000,0x1000+0x07649000
def callers(t):
    out=[]
    i=LO
    while i<HI-5:
        b=d[i]
        if b==0xE8 or b==0xE9:
            rel=struct.unpack_from("<i",d,i+1)[0]
            if i+5+rel==t: out.append((i,'call' if b==0xE8 else 'jmp'))
        i+=1
    return out
for a in sys.argv[1:]:
    t=int(a,16)
    c=callers(t)
    print("target 0x%08X : %d rel32 sites"%(t,len(c)))
    for x,k in c[:30]: print("   0x%08X %s"%(x,k))
