import sys
data=open(r"dumps/merged13.dump.exe",'rb').read()
for a in sys.argv[1:]:
    rva=int(a,16); p=rva & ~0xFFF
    nz=sum(1 for b in data[p:p+0x1000] if b)
    print("%08X page %08X nonzero=%d/4096 %s" % (rva,p,nz,"DARK" if nz==0 else "LIT"))
