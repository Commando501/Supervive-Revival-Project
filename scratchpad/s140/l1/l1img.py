"""L1 INDEPENDENT instruments. Own PE reader + own recursive-descent CFG.
Deliberately does NOT import scratchpad/s140/tools/{peimg,cfg}.py."""
import struct, sys
from capstone import *
from capstone.x86 import *

IMG = r"G:/git/Supervive Revival Project/dumps/merged13.dump.exe"

class PE:
    def __init__(self, path=IMG):
        self.path = path
        with open(path,'rb') as f: self.d = f.read()
        d = self.d
        pe = struct.unpack_from('<I', d, 0x3C)[0]
        assert d[pe:pe+4] == b'PE\0\0'
        nsec = struct.unpack_from('<H', d, pe+6)[0]
        optsz = struct.unpack_from('<H', d, pe+20)[0]
        opt = pe+24
        assert struct.unpack_from('<H', d, opt)[0] == 0x20b
        self.base = struct.unpack_from('<Q', d, opt+24)[0]
        self.secs=[]
        for i in range(nsec):
            o = opt+optsz+i*40
            nm = d[o:o+8].rstrip(b'\0').decode('latin1')
            vsz,va,rawsz,praw = struct.unpack_from('<IIII', d, o+8)
            self.secs.append((nm,va,vsz,praw,rawsz))
    def flat(self): return all(va==praw for _,va,_,praw,_ in self.secs)
    def sec(self, rva):
        for s in self.secs:
            nm,va,vsz,praw,rawsz = s
            if va <= rva < va+max(vsz,rawsz): return s
        return None
    def read(self, rva, n):
        s = self.sec(rva)
        if s is None: raise ValueError("rva %#x outside sections"%rva)
        nm,va,vsz,praw,rawsz = s
        off = praw + (rva-va)
        return self.d[off:off+n]
    def page_nz(self, rva):
        p = rva & ~0xFFF
        return sum(1 for x in self.read(p,0x1000) if x)

def md():
    m = Cs(CS_ARCH_X86, CS_MODE_64); m.detail = True; return m

COND = set("""jo jno jb jae je jne jbe ja js jns jp jnp jl jge jle jg
jae jnae jnb jnbe jc jnc jz jnz jna jnae jpe jpo jcxz jecxz jrcxz
loop loope loopne""".split())

class CFG:
    """Recursive descent over INSTRUCTIONS. succ maps addr -> [addr...]."""
    def __init__(self, pe, entry, follow_tailjmp=True, max_insn=200000):
        self.pe = pe; self.entry = entry
        self.insns = {}          # addr -> (mnem, opstr, size, bytes)
        self.succ  = {}          # addr -> list of successor addrs
        self.calls = []          # (site, target|None, opstr)
        self.indirect_jumps = [] # (site, opstr)
        self.rets = []
        self.decode_fail = []
        self.terminators = []    # (addr, mnem) for int3/ud2/hlt
        self.tail_jmps = []      # (site, target) direct jmp whose target is > 0x400 away
        m = md()
        work = [entry]; seen=set()
        while work:
            a = work.pop()
            if a in seen: continue
            seen.add(a)
            try: b = self.pe.read(a, 24)
            except ValueError:
                self.decode_fail.append((a,'outside-sections')); continue
            if len(b) < 1: self.decode_fail.append((a,'short')); continue
            g = list(m.disasm(b, a, count=1))
            if not g:
                self.decode_fail.append((a, b[:8].hex())); continue
            i = g[0]
            self.insns[a] = (i.mnemonic, i.op_str, i.size, bytes(i.bytes))
            nxt = a + i.size
            s = []
            mn = i.mnemonic
            if mn == 'jmp':
                op = i.operands[0]
                if op.type == X86_OP_IMM:
                    t = op.imm; s=[t]
                    if abs(t-a) > 0x2000: self.tail_jmps.append((a,t))
                    if not follow_tailjmp and abs(t-a) > 0x2000: s=[]
                else:
                    self.indirect_jumps.append((a, i.op_str)); s=[]
            elif mn in COND or (mn.startswith('j') and mn!='jmp'):
                op = i.operands[0]
                if op.type == X86_OP_IMM: s=[op.imm, nxt]
                else:
                    self.indirect_jumps.append((a, i.op_str)); s=[nxt]
            elif mn == 'call':
                op = i.operands[0]
                if op.type == X86_OP_IMM: self.calls.append((a, op.imm, i.op_str))
                else: self.calls.append((a, None, i.op_str))
                s=[nxt]
            elif mn in ('ret','retf','iret','iretd','iretq'):
                self.rets.append(a); s=[]
            elif mn in ('int3','ud2','hlt'):
                self.terminators.append((a,mn)); s=[]
            else:
                s=[nxt]
            self.succ[a]=s
            for t in s:
                if t not in seen: work.append(t)
            if len(self.insns) > max_insn: raise RuntimeError("insn cap")
        # preds
        self.pred = {}
        for a, ss in self.succ.items():
            for t in ss:
                if t in self.insns: self.pred.setdefault(t,[]).append(a)

    def reach_backward(self, target):
        """set of insns that can reach `target` following succ edges (target itself included)."""
        R=set([target]); w=[target]
        while w:
            n=w.pop()
            for p in self.pred.get(n,[]):
                if p not in R: R.add(p); w.append(p)
        return R

    def dis(self, a):
        mn,op,sz,b = self.insns[a]
        return f"{a:#010x}  {b.hex():<20s} {mn} {op}"

if __name__=='__main__':
    pe=PE()
    print("base %#x flat=%s"%(pe.base, pe.flat()))
    for s in pe.secs: print("  %-10s va=%#010x praw=%#010x vsz=%#010x raw=%#010x %s"%(s[0],s[1],s[3],s[2],s[4],"FLAT" if s[1]==s[3] else "***NOTFLAT***"))
