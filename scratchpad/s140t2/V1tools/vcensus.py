# V1 independent displacement census. Different method from L1: for each 4-byte LE occurrence of
# the displacement in .text, try decoding at every start 1..15 bytes back; accept a decode iff it
# has a MEM operand with exactly that disp AND the disp field's file position lies inside the insn.
import sys, struct
sys.path.insert(0,'G:/git/Supervive Revival Project/scratchpad/s140t2/V1tools')
from vpe import Img
from capstone import *
from capstone.x86 import *

def census(im, lo_disp, hi_disp):
    md = Cs(CS_ARCH_X86, CS_MODE_64); md.detail=True
    _,va,vsz,_,rsz = im.sec('.text')
    end = va+max(vsz,rsz)
    data = im.raw
    found = {}   # addr -> (insn, disp)
    for d in range(lo_disp, hi_disp+1):
        pat = struct.pack('<i', d)
        pos = data.find(pat, va, end)
        while pos != -1:
            for back in range(1,16):
                a = pos-back
                if a < va: continue
                if data[a] == 0: continue
                try:
                    ins = next(md.disasm(data[a:a+16], a), None)
                except Exception:
                    ins = None
                if ins is None: continue
                if a+ins.size < pos+4: continue     # disp must be inside the insn
                ok=False
                for op in ins.operands:
                    if op.type==X86_OP_MEM and op.mem.disp==d and op.mem.base!=0:
                        ok=True; break
                if ok:
                    prev = found.get(a)
                    if prev is None or ins.size > prev[0].size:
                        found[a]=(ins,d)
            pos = data.find(pat, pos+1, end)
    return found

def is_write(ins):
    if ins.mnemonic in ('cmp','test'): return False
    if not ins.operands: return False
    return ins.operands[0].type == X86_OP_MEM

def vote(im, addr, nstarts=64):
    """Self-synchronising linear-sweep vote: how many of nstarts backward starts land exactly on addr."""
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    data = im.raw
    hits = 0
    for back in range(1, nstarts+1):
        a = addr - back
        if a < 0x1000: continue
        cur = a
        ok = False
        for ins in md.disasm(data[a:addr+16], a):
            if ins.address == addr: ok = True; break
            if ins.address > addr: break
        if ok: hits += 1
    return hits
