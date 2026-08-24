# Disambiguate overlapping candidate decodes by linear-sweep voting:
# for several back-offsets N, linear-disassemble from (a-N) and see which candidate
# address the sweep actually lands on. The real instruction boundary wins the vote.
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from pe import load
import capstone as CS
from capstone import x86 as X86
pe = load()
md = CS.Cs(CS.CS_ARCH_X86, CS.CS_MODE_64); md.detail=True

BACKOFFS = [8,12,16,20,24,32,40,48,64,80,96,128,160,192,256]

def sweep_boundaries(start, end):
    """linear sweep, return set of instruction start addresses reached"""
    out=set(); a=start
    while a < end:
        g=list(md.disasm(pe.buf[a:a+16], a, count=1))
        if not g: return out, False
        out.add(a); a += g[0].size
    return out, True

def vote(cands):
    """cands: sorted list of candidate addresses forming one overlap cluster.
       returns dict addr->votes"""
    lo = min(cands); hi = max(cands)
    votes = {c:0 for c in cands}
    for N in BACKOFFS:
        s = lo - N
        b,_ = sweep_boundaries(s, hi+1)
        for c in cands:
            if c in b: votes[c]+=1
    return votes

def cluster(addrs, gap=16):
    """group addresses that overlap (within gap bytes)"""
    addrs=sorted(addrs); out=[]; cur=[addrs[0]]
    for a in addrs[1:]:
        if a - cur[-1] <= gap: cur.append(a)
        else: out.append(cur); cur=[a]
    out.append(cur); return out
