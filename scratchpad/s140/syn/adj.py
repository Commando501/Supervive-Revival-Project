import struct, sys, capstone
P=r"G:/git/Supervive Revival Project/dumps/merged13.dump.exe"
D=open(P,'rb').read()
pe=struct.unpack_from('<I',D,0x3c)[0]
assert D[pe:pe+4]==b'PE\0\0'
nsec=struct.unpack_from('<H',D,pe+6)[0]
optsz=struct.unpack_from('<H',D,pe+20)[0]
IB=struct.unpack_from('<Q',D,pe+24+24)[0]
secs=[]
flat=True
for i in range(nsec):
    o=pe+24+optsz+40*i
    nm=D[o:o+8].rstrip(b'\0').decode()
    vs,va,rs,pr=struct.unpack_from('<IIII',D,o+8)
    secs.append((nm,va,vs,pr,rs))
    if va!=pr: flat=False
print("ImageBase %#x flat=%s sections=%d"%(IB,flat,nsec))
for s in secs: print("  %-8s va=%#010x vs=%#x praw=%#x rs=%#x"%s)
def rd(rva,n): return D[rva:rva+n]
def q(rva): return struct.unpack_from('<Q',D,rva)[0]
def pagenz(rva):
    b=rva & ~0xfff
    return sum(1 for c in D[b:b+0x1000] if c)
md=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_64); md.detail=True
def dis(rva,n=12):
    out=[]
    for i in md.disasm(D[rva:rva+256],rva):
        out.append((i.address,i.bytes.hex(),i.mnemonic+' '+i.op_str))
        if len(out)>=n: break
    return out

print("\n=== CONTROLS ===")
print("DARK ctrl 0x5A6AC40 page_nz =", pagenz(0x5A6AC40))
for a,n in [(0x035E9EC0,'engPM'),(0x055B8370,'lokiPM'),(0x055C2430,'lokiSNP'),(0x03600990,'engSNP'),(0x0530ABF0,'A50'),(0x0530AC10,'GetRecentVel'),(0x03C9B0A0,'IsSimPhys'),(0x035E64C0,'HasValidData')]:
    print("  %-14s %#010x page_nz=%d"%(n,a,pagenz(a)))
folds={0x00F7EC20:'c20000',0x00F7EB50:'33c0c3',0x00F7EB60:'32c0c3',0x00B9E1F0:'b001c3',0x00FC6CF0:'0f57c0c3'}
for a,h in folds.items():
    ok = rd(a,len(h)//2).hex()==h
    print("  fold %#010x expect %s got %s %s"%(a,h,rd(a,len(h)//2).hex(),"PASS" if ok else "FAIL"))

print("\n=== VTABLES ===")
LV=0x088F8570; EV=0x07FBED58
for disp,exp,nm in [(0xAA8,0x055B8370,'PerformMovement'),(0x720,0x055C2430,'StartNewPhysics'),(0x3D0,0x055C2B90,'TickComponent'),(0x890,0x055A7680,'?'),(0xA38,0x055A75B0,'?'),(0x830,0x055B89F0,'?'),(0x6B8,0x035E64C0,'HasValidData'),(0xA50,0x0530ABF0,'A50-CLEAR'),(0x00,None,'slot0')]:
    v=q(LV+disp); r=v-IB
    print("  LokiVT+%#05x -> %#018x rva %#010x  exp %s  %s  [%s]"%(disp,v,r,hex(exp) if exp else '-', "PASS" if exp and r==exp else ("" if exp is None else "FAIL"),nm))
for disp,exp,nm in [(0xAA8,0x035E9EC0,'engPM'),(0x720,0x03600990,'engSNP'),(0x890,0x035DCD10,'engCCM'),(0x6B8,0x035E64C0,'HasValidData'),(0x4E0,0x0364BA80,'ShouldSkipUpdate'),(0xA50,0x035D6790,'engA50')]:
    v=q(EV+disp); r=v-IB
    print("  EngVT +%#05x -> rva %#010x exp %#010x %s [%s]"%(disp,r,exp,"PASS" if r==exp else "FAIL",nm))
