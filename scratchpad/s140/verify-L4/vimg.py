# Independent PE reader + recursive-descent CFG. Written from scratch for L4 verification.
import struct, capstone
PATH = r"G:\git\Supervive Revival Project\dumps\merged13.dump.exe"
IMAGEBASE = 0x7FF608F40000

class Img:
    def __init__(self, path=PATH):
        self.buf = open(path,'rb').read()
        pe = struct.unpack_from('<I', self.buf, 0x3C)[0]
        assert self.buf[pe:pe+4] == b'PE\0\0'
        nsec = struct.unpack_from('<H', self.buf, pe+6)[0]
        optsz = struct.unpack_from('<H', self.buf, pe+20)[0]
        self.imagebase = struct.unpack_from('<Q', self.buf, pe+24+24)[0]
        so = pe+24+optsz
        self.secs=[]
        for i in range(nsec):
            o=so+40*i
            name=self.buf[o:o+8].rstrip(b'\0').decode('latin1')
            vsz,va,rsz,praw = struct.unpack_from('<IIII', self.buf, o+8)
            self.secs.append((name,va,vsz,praw,rsz))
    def flat(self):
        return all(va==praw for (_,va,_,praw,_) in self.secs)
    def read(self, rva, n):
        return self.buf[rva:rva+n]
    def page_nonzero(self, rva):
        p = rva & ~0xFFF
        return sum(1 for b in self.buf[p:p+0x1000] if b)
    def secof(self, rva):
        for (nm,va,vsz,praw,rsz) in self.secs:
            if va <= rva < va+max(vsz,rsz): return nm
        return None

md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
md.detail = True

UNCOND = {'jmp'}
COND = set('''jo jno js jns je jz jne jnz jb jnae jc jnb jae jnc jbe jna ja jnbe jl jnge jge jnl jle jng jg jnle jp jpe jnp jpo jcxz jecxz jrcxz loop loope loopne'''.split())

class CFG:
    def __init__(self, img, entry, maxi=400000):
        self.img=img; self.entry=entry
        self.insns={}       # rva -> insn
        self.succ={}        # rva -> set
        self.pred={}
        self.calls=[]
        self.indirect_jumps=[]
        self.decode_failures=[]
        self.rets=[]
        work=[entry]; seen=set()
        while work:
            a=work.pop()
            if a in seen: continue
            seen.add(a)
            data=img.read(a, 24)
            try:
                ins=next(md.disasm(data, a))
            except StopIteration:
                self.decode_failures.append(a); continue
            self.insns[a]=ins
            self.succ.setdefault(a,set())
            m=ins.mnemonic; nxt=a+ins.size
            if m=='ret' or m.startswith('ret'):
                self.rets.append(a); continue
            if m=='int3' or m=='ud2':
                continue
            if m=='call':
                self.calls.append(a)
                op=ins.operands[0]
                if op.type==capstone.x86.X86_OP_IMM:
                    pass  # do not follow calls
                self.succ[a].add(nxt); work.append(nxt); continue
            if m in UNCOND:
                op=ins.operands[0]
                if op.type==capstone.x86.X86_OP_IMM:
                    t=op.imm; self.succ[a].add(t); work.append(t)
                else:
                    self.indirect_jumps.append(a)
                continue
            if m in COND:
                op=ins.operands[0]
                if op.type==capstone.x86.X86_OP_IMM:
                    t=op.imm; self.succ[a].add(t); work.append(t)
                else:
                    self.indirect_jumps.append(a)
                self.succ[a].add(nxt); work.append(nxt); continue
            self.succ[a].add(nxt); work.append(nxt)
        for a,ss in self.succ.items():
            for s in ss:
                self.pred.setdefault(s,set()).add(a)
        for a in self.insns:
            self.pred.setdefault(a,set())
    def reach_backward(self, target):
        R=set([target]); work=[target]
        while work:
            n=work.pop()
            for p in self.pred.get(n,()):
                if p not in R: R.add(p); work.append(p)
        return R
    def reach_forward(self, start, avoid=()):
        F=set(); work=[start]
        while work:
            n=work.pop()
            if n in F or n in avoid: continue
            F.add(n)
            for s in self.succ.get(n,()): work.append(s)
        return F
    def exits_from(self, target):
        R=self.reach_backward(target)
        out=[]
        for a in R:
            for s in self.succ.get(a,()):
                if s not in R: out.append((a,s))
        return sorted(out)
