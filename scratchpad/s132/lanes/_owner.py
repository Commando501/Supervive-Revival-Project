import sys, struct, re, capstone
sys.path.insert(0,r'scratchpad\s130\tools')
import propscan as P, propowner as PO
P.DUMPS['merged4']=r'dumps\merged4.dump.exe'
img=P.Img(P.DUMPS['merged4'])
md=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_64)
def wstr(rva,n=90):
    out=[]
    for i in range(0,n*2,2):
        c=img.d[rva+i]|(img.d[rva+i+1]<<8)
        if c==0: break
        if not (32<=c<127): return None
        out.append(chr(c))
    return ''.join(out)
def clsname(ctor):
    """GetPrivateStaticClass: rcx=PackageName, rdx=ClassName (wide)."""
    pkg=cls=None
    for ins in md.disasm(img.d[ctor:ctor+0x100], ctor):
        if ins.mnemonic=='lea':
            m=re.search(r'^(r[a-z0-9]+), \[rip ([+-]) (0x[0-9a-f]+)\]$', ins.op_str)
            if m:
                reg=m.group(1); d=int(m.group(3),16)*(1 if m.group(2)=='+' else -1)
                t=ins.address+ins.size+d
                s=wstr(t)
                if s:
                    if reg=='rcx' and s.startswith('/Script'): pkg=s
                    elif reg=='rdx': cls=s
        if ins.mnemonic=='call': break
    return pkg,cls
def owners(rec):
    out=[]
    for r in PO.owner(img,rec):
        pkg,cls=clsname(r['ctor']) if r['ctor'] else (None,None)
        out.append((cls,pkg,r))
    return out
def find(off=None,name=None):
    for h in P.scan(img,off,name):
        os=owners(h['rva'])
        for cls,pkg,r in os:
            print('  0x%08X %-40s off=0x%-5X idx=%-3d owner=%s (%s) nprops=%d'%(h['rva'],h['name'],h['off'],r['idx'],cls,pkg,r['nprops']))
        if not os:
            print('  0x%08X %-40s off=0x%-5X owner=UNRESOLVED'%(h['rva'],h['name'],h['off']))
