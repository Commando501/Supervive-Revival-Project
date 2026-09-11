# LANE 5 independent PE + CFG harness. Imports nothing from other lanes.
import struct, sys
from capstone import *
from capstone.x86 import *

PATH = r"G:\git\Supervive Revival Project\dumps\merged13.dump.exe"

class Img:
    def __init__(self, path=PATH):
        self.buf = open(path,'rb').read()
        b = self.buf
        e_lfanew = struct.unpack_from('<I', b, 0x3C)[0]
        assert b[e_lfanew:e_lfanew+4] == b'PE\0\0'
        coff = e_lfanew+4
        self.nsec = struct.unpack_from('<H', b, coff+2)[0]
        szopt = struct.unpack_from('<H', b, coff+16)[0]
        opt = coff+20
        self.magic = struct.unpack_from('<H', b, opt)[0]
        assert self.magic == 0x20b, hex(self.magic)
        self.imagebase = struct.unpack_from('<Q', b, opt+24)[0]
        self.sections = []
        so = opt+szopt
        for i in range(self.nsec):
            off = so + i*40
            name = b[off:off+8].rstrip(b'\0').decode('latin1')
            vsz, va, rsz, rp = struct.unpack_from('<IIII', b, off+8)
            self.sections.append(dict(name=name, vsz=vsz, va=va, rsz=rsz, rp=rp))
        self.flat = all(s['va']==s['rp'] for s in self.sections)
    def sec(self, rva):
        for s in self.sections:
            if s['va'] <= rva < s['va']+max(s['vsz'], s['rsz']):
                return s
        return None
    def read(self, rva, n):
        return self.buf[rva:rva+n]
    def u64(self, rva): return struct.unpack_from('<Q', self.buf, rva)[0]
    def u32(self, rva): return struct.unpack_from('<I', self.buf, rva)[0]
    def i32(self, rva): return struct.unpack_from('<i', self.buf, rva)[0]
    def ptr2rva(self, rva):
        v = self.u64(rva)
        if v == 0: return 0
        return v - self.imagebase
    def pagecount(self, rva):
        p = rva & ~0xFFF
        return sum(1 for c in self.buf[p:p+4096] if c)

md = Cs(CS_ARCH_X86, CS_MODE_64)
md.detail = True

FOLDS = {
 0x0F7EC20: ("VOID ret imm16 0", b'\xc2\x00\x00'),
 0x0F7EB50: ("nullptr xor eax,eax", b'\x33\xc0\xc3'),
 0x0F7EB60: ("false xor al,al", b'\x32\xc0\xc3'),
 0x0B9E1F0: ("true mov al,1", b'\xb0\x01\xc3'),
 0x0FC6CF0: ("0.0f xorps xmm0", b'\x0f\x57\xc0\xc3'),
}

def disasm(img, rva, n=0x400):
    return list(md.disasm(img.read(rva,n), rva))

def cfg(img, entry, maxbytes=0x4000):
    """recursive descent; returns dict rva->insn, plus succ edges"""
    insns = {}
    succ = {}
    work = [entry]
    seen = set()
    fails = []
    while work:
        a = work.pop()
        while True:
            if a in insns: break
            if a < entry or a >= entry+maxbytes:
                break
            code = img.read(a, 16)
            g = list(md.disasm(code, a, count=1))
            if not g:
                fails.append(a); break
            i = g[0]
            insns[a] = i
            nxt = a + i.size
            s = []
            grp = set(i.groups)
            m = i.mnemonic
            if m == 'ret' or m.startswith('ret'):
                s = []
            elif m == 'jmp':
                op = i.operands[0]
                if op.type == X86_OP_IMM:
                    s = [op.imm]
                else:
                    s = []  # indirect jmp
                    succ.setdefault(a, [])
                    succ[a] = []
                    insns[a] = i
                    break
            elif m.startswith('j'):   # conditional
                op = i.operands[0]
                if op.type == X86_OP_IMM:
                    s = [op.imm, nxt]
                else:
                    s = [nxt]
            elif m == 'int3' or m=='ud2':
                s = []
            else:
                s = [nxt]
            succ[a] = s
            if not s: break
            for t in s[1:]:
                work.append(t)
            a = s[0]
    return insns, succ, fails

def extent(insns):
    if not insns: return (0,0)
    lo = min(insns); hi = max(a+insns[a].size for a in insns)
    return lo,hi

def calltargets(insns):
    direct = {}
    indirect = []
    for a,i in sorted(insns.items()):
        if i.mnemonic == 'call':
            op = i.operands[0]
            if op.type == X86_OP_IMM:
                direct.setdefault(op.imm, []).append(a)
            else:
                indirect.append((a, i.op_str))
    return direct, indirect

def grade(img, rva):
    """fold / DARK / REAL, three-state, plus stub-shape detection"""
    if rva in FOLDS:
        return "FOLD(%s)" % FOLDS[rva][0]
    for f,(nm,by) in FOLDS.items():
        if img.read(rva, len(by)) == by:
            return "FOLD-BYTES(%s)@%#x" % (nm, rva)
    pc = img.pagecount(rva)
    if pc == 0:
        return "DARK(page 0/4096)"
    ins = disasm(img, rva, 0x40)
    if not ins:
        return "UNDECODABLE"
    return "REAL(page %d/4096)" % pc
