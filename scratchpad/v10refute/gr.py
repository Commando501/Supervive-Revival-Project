import sys, struct
sys.path.insert(0,r'G:/git/Supervive Revival Project/scratchpad/v10refute')
from lib import *
import capstone
md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64); md.detail=True
def walk(rva, cap=0x800):
    """linear disasm to first ret at depth0; return (end, callees[list of (site,tgt)], indirect_count)"""
    code=rd(rva,cap); callees=[]; ind=0; end=None
    for i in md.disasm(code,rva):
        if i.mnemonic=='call':
            if i.op_str.startswith('0x'): callees.append((i.address,int(i.op_str,16)))
            else: ind+=1
        if i.mnemonic=='ret':
            end=i.address; break
    return end, callees, ind
def report(rva,name='',cap=0x800):
    end,cs,ind=walk(rva,cap)
    sz = (end-rva+1) if end else None
    print('FN 0x%08X %-28s  end=%s size=%s  grade=%s  indirect_calls=%d'%(rva,name,hex(end) if end else 'NO-RET',sz,grade(rva),ind))
    seen={}
    for site,t in cs:
        g=grade(t)
        mark='   <<< FOLD' if 'FOLD' in g else ('   <<< DARK' if 'DARK' in g else '')
        print('    call@0x%08X -> 0x%08X  %s%s'%(site,t,g,mark))
        seen[t]=seen.get(t,0)+1
    return seen
if __name__=='__main__':
    for a in sys.argv[1:]:
        report(int(a,16))
