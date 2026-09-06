import struct,sys
d=open("dumps/merged13.dump.exe",'rb').read()
LO,HI=0x1000,0x1000+0x07649000
def leas(t):
    out=[];i=LO
    while i<HI-7:
        if d[i]==0x48 and d[i+1]==0x8d:
            modrm=d[i+2]
            if (modrm & 0xC7)==0x05:  # rip-relative
                rel=struct.unpack_from("<i",d,i+3)[0]
                if i+7+rel==t: out.append(i)
        i+=1
    return out
for a in sys.argv[1:]:
    t=int(a,16); c=leas(t)
    print("lea rip-> 0x%08X : %d sites"%(t,len(c)))
    for x in c[:20]: print("   0x%08X"%x)
