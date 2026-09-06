# Independent PE reader + recursive-descent CFG. Written for the V5 adversarial pass.
# Imports nothing from tools/ or scratchpad/s140*/.
import struct, sys
from capstone import *
from capstone.x86 import *

PATH = r"G:\git\Supervive Revival Project\dumps\merged13.dump.exe"
_buf = open(PATH,'rb').read()

def u8(o):  return _buf[o]
def u16(o): return struct.unpack_from('<H',_buf,o)[0]
def u32(o): return struct.unpack_from('<I',_buf,o)[0]
def u64(o): return struct.unpack_from('<Q',_buf,o)[0]
def i32(o): return struct.unpack_from('<i',_buf,o)[0]
def f32(o): return struct.unpack_from('<f',_buf,o)[0]
def f64(o): return struct.unpack_from('<d',_buf,o)[0]

e_lfanew = u32(0x3C)
assert _buf[e_lfanew:e_lfanew+4]==b'PE\0\0', "no PE sig"
nsec = u16(e_lfanew+6)
szopt = u16(e_lfanew+20)
opt = e_lfanew+24
magic = u16(opt)
assert magic==0x20b, hex(magic)
IMAGEBASE = u64(opt+24)
SEC = opt+szopt
sections=[]
for i in range(nsec):
    o = SEC+i*40
    name=_buf[o:o+8].rstrip(b'\0').decode('latin1')
    vsz=u32(o+8); va=u32(o+12); rsz=u32(o+16); ptr=u32(o+20); ch=u32(o+36)
    sections.append(dict(name=name,vsz=vsz,va=va,rsz=rsz,ptr=ptr,ch=ch))

def sec_of(rva):
    for s in sections:
        if s['va']<=rva< s['va']+max(s['vsz'],s['rsz']): return s
    return None

FLAT = all(s['va']==s['ptr'] for s in sections)

def page_nonzero(rva):
    p=rva & ~0xFFF
    return sum(1 for b in _buf[p:p+4096] if b)

md = Cs(CS_ARCH_X86, CS_MODE_64)
md.detail = True

COND = set()
for m in ['jo','jno','js','jns','je','jz','jne','jnz','jb','jnae','jc','jnb','jae','jnc',
          'jbe','jna','ja','jnbe','jl','jnge','jge','jnl','jle','jng','jg','jnle','jp','jpe','jnp','jpo',
          'jcxz','jecxz','jrcxz','loop','loope','loopne']:
    COND.add(m)
TERM = set(['ret','retf','iret','iretq','ud2','hlt'])

def cfg(entry, limit=200000):
    """Sound recursive descent. Returns dict."""
    seen={}
    work=[entry]
    calls=[]           # (addr, target or None)
    indirect_jmp=[]
    rets=[]
    decode_fail=[]
    edges={}           # addr -> list of successor addrs
    while work:
        a=work.pop()
        if a in seen: continue
        s=sec_of(a)
        if s is None or s['name']!='.text':
            decode_fail.append((a,'outside .text')); continue
        try:
            ins=next(md.disasm(_buf[a:a+16], a, 1))
        except StopIteration:
            decode_fail.append((a,'undecodable')); continue
        seen[a]=ins
        if len(seen)>limit: raise RuntimeError('limit')
        m=ins.mnemonic; succ=[]
        if m in TERM:
            rets.append(a)
        elif m=='jmp':
            op=ins.operands[0]
            if op.type==X86_OP_IMM:
                succ=[op.imm]
            else:
                indirect_jmp.append((a,ins.op_str))
        elif m in COND:
            op=ins.operands[0]
            if op.type==X86_OP_IMM: succ=[op.imm, a+ins.size]
            else: indirect_jmp.append((a,ins.op_str)); succ=[a+ins.size]
        elif m=='call':
            op=ins.operands[0]
            calls.append((a, op.imm if op.type==X86_OP_IMM else None, ins.op_str))
            succ=[a+ins.size]
        elif m in ('int3','nop'):
            succ=[a+ins.size]
        else:
            succ=[a+ins.size]
        edges[a]=succ
        for t in succ: work.append(t)
    lo=min(seen); hi=max(seen); hiend=hi+seen[hi].size
    covered=sum(i.size for i in seen.values())
    span=hiend-lo
    return dict(seen=seen,edges=edges,calls=calls,indirect_jmp=indirect_jmp,rets=rets,
                decode_fail=decode_fail,lo=lo,hi=hiend,span=span,covered=covered,gaps=span-covered)

def preds(edges):
    p={}
    for a,ss in edges.items():
        for s in ss: p.setdefault(s,[]).append(a)
    return p

def reach_backward(edges, target):
    p=preds(edges); R=set([target]); w=[target]
    while w:
        n=w.pop()
        for q in p.get(n,[]):
            if q not in R: R.add(q); w.append(q)
    return R

def exit_edges(edges, R, target):
    """edges leaving R (from a node in R to a node not in R), excluding target's own out-edges"""
    out=[]
    for a in R:
        if a==target: continue
        for s in edges.get(a,[]):
            if s not in R: out.append((a,s))
    return out

FOLDS = {
 0x0F7EC20: bytes.fromhex('c20000'),
 0x0F7EB50: bytes.fromhex('33c0c3'),
 0x0F7EB60: bytes.fromhex('32c0c3'),
 0x0B9E1F0: bytes.fromhex('b001c3'),
 0x0FC6CF0: bytes.fromhex('0f57c0c3'),
}
def grade(rva):
    nz=page_nonzero(rva)
    if nz==0: return 'DARK(0/4096)'
    for f,b in FOLDS.items():
        if rva==f: return 'FOLD@%X'%f
    # is it one of the fold BODIES by bytes?
    for f,b in FOLDS.items():
        if _buf[rva:rva+len(b)]==b: return 'FOLDSHAPE(=%X)'%f
    return 'REAL(page %d/4096)'%nz

def dis(rva,n=40,verbose=True):
    out=[]
    for ins in md.disasm(_buf[rva:rva+n*16], rva, n):
        out.append('0x%08X  %-24s %s %s'%(ins.address,ins.bytes.hex(),ins.mnemonic,ins.op_str))
    return '\n'.join(out)

def vt_slot(vt_rva, disp):
    """read absolute VA from a dumped-image vtable and convert to RVA"""
    va=u64(vt_rva+disp)
    return va - IMAGEBASE, va

if __name__=='__main__':
    print('IMAGEBASE 0x%X  FLAT=%s  sections=%d'%(IMAGEBASE,FLAT,len(sections)))
    for s in sections: print('  %-8s va=%08X vsz=%08X ptr=%08X rsz=%08X'%(s['name'],s['va'],s['vsz'],s['ptr'],s['rsz']))
