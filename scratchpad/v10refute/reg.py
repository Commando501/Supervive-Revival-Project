import sys, struct, re
sys.path.insert(0,r'G:/git/Supervive Revival Project/scratchpad/v10refute')
from lib import *
import capstone
md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64); md.detail=True
DATA = load_all()
TEXT_LO, TEXT_HI = 0x1000, 0x1000+0x07649000

def find_wstr(name):
    pat = name.encode('utf-16-le')+b'\x00\x00'
    res=[]
    start=0
    while True:
        i = DATA.find(pat, start)
        if i<0: break
        # must be preceded by 00 00 (string start) to be exact
        if i>=2 and DATA[i-2:i]==b'\x00\x00':
            res.append(i)
        start=i+1
    return res

def lea_xrefs(target):
    """scan .text for 48/4c 8d /5 rel32 with computed target == target"""
    hits=[]
    d=DATA
    i=TEXT_LO
    end=TEXT_HI-7
    while True:
        j = d.find(b'\x8d', i, end)
        if j<0: break
        p = j-1
        if p>=TEXT_LO and d[p] in (0x48,0x4c,0x49,0x4d):
            modrm = d[j+1]
            if (modrm & 0xC7) == 0x05:
                rel = struct.unpack_from('<i', d, j+2)[0]
                tgt = j+6+rel
                if tgt==target:
                    hits.append(p)
        i = j+1
    return hits

def decode_reg(fn_rva, span=0x140):
    """decode GetPrivateStaticClassBody args from a registration function"""
    code = rd(fn_rva, span)
    info={'fn':fn_rva,'stack':{}, 'regs':{}, 'call':None}
    r11_is_rsp=False; rsp_delta=0
    for i in md.disasm(code, fn_rva):
        s=i.op_str
        if i.mnemonic=='mov' and s=='r11, rsp': r11_is_rsp=True
        if i.mnemonic=='sub' and s.startswith('rsp,'): rsp_delta=int(s.split(',')[1].strip(),16)
        if i.mnemonic=='lea':
            for op in i.operands:
                if op.type==capstone.x86.X86_OP_MEM and op.mem.base==capstone.x86.X86_REG_RIP:
                    info['regs'][i.reg_name(i.operands[0].reg)] = i.address+i.size+op.mem.disp
        if i.mnemonic in ('mov','lea') and len(i.operands)==2 and i.operands[0].type==capstone.x86.X86_OP_MEM:
            m=i.operands[0].mem
            base=i.reg_name(m.base) if m.base else None
            src=i.operands[1]
            val=None
            if src.type==capstone.x86.X86_OP_IMM: val=('imm',src.imm)
            elif src.type==capstone.x86.X86_OP_REG:
                rn=i.reg_name(src.reg)
                val=('reg',rn,info['regs'].get(rn))
            if base in ('rsp','r11') and val:
                # normalize to rsp-relative
                if base=='r11' and r11_is_rsp: off = m.disp + rsp_delta
                elif base=='rsp': off = m.disp
                else: off=None
                if off is not None: info['stack'][off]=(val, '0x%08X'%i.address)
        if i.mnemonic=='call' and s.startswith('0x'):
            info['call']=int(s,16); break
    return info

def report(name, pkg=None):
    locs = find_wstr(name)
    for L in locs:
        if sec_of(L) != '.rdata': continue
        xs = lea_xrefs(L)
        for x in xs:
            # walk back to function start heuristically: find the containing reg fn by scanning back for 4c 8b dc (mov r11,rsp) within 0x60
            fn=None
            for back in range(0,0x80):
                if DATA[x-back:x-back+3]==b'\x4c\x8b\xdc': fn=x-back; break
            if fn is None: continue
            inf=decode_reg(fn)
            st=inf['stack']
            def g(o):
                v=st.get(o)
                if not v: return None
                vv=v[0]
                return vv[1] if vv[0]=='imm' else vv[2]
            print('== %-28s strloc=0x%08X leaat=0x%08X fn=0x%08X call->0x%08X'%(name,L,x,fn,inf['call'] or 0))
            print('   size=0x%X align=%s classflags=0x%08X castflags=%s'%(g(0x20) or 0, g(0x28), g(0x30) or 0, hex(g(0x38)) if g(0x38) is not None else None))
            for o in (0x40,0x48,0x50,0x58,0x60,0x68):
                v=g(o)
                print('     rsp+0x%02X = %s'%(o, ('0x%08X [%s]'%(v,sec_of(v))) if v else v))
            print('   rcx=0x%08X rdx=0x%08X r8=0x%08X'%(inf['regs'].get('rcx',0),inf['regs'].get('rdx',0),inf['regs'].get('r8',0)))
if __name__=='__main__':
    for n in sys.argv[1:]:
        report(n)
