#!/usr/bin/env python3
"""Grade a set of RVAs REAL / FOLD / PAGE-DARK across several images."""
import sys
sys.path.insert(0,r"G:\git\Supervive Revival Project\scratchpad\s132")
from xr import load
FOLD={0xF7EC20:'FOLD ret0(c2 00 00)',0xF7EB50:'FOLD xor eax,eax;ret',0xF7EB60:'FOLD xor al,al;ret',0xB9E1F0:'FOLD mov al,1;ret'}
IMGS=['merged4','merged2','tuthero','s129']
_c={}
def img(n):
    if n not in _c: _c[n]=load(n)
    return _c[n]
def grade(rva):
    if rva in FOLD: return 'FOLD', FOLD[rva], ''
    cov=[]
    for n in IMGS:
        i=img(n); pg=rva & ~0xFFF
        d=i.read(pg,0x1000)
        if d and any(d): cov.append(n)
    if not cov: return 'PAGE-DARK','impl page all-zero in %s'%('/'.join(IMGS)),''
    i=img(cov[0]); by=i.read(rva,12).hex()
    # is it a jump-to-fold or a tiny stub?
    tag='REAL'
    if by.startswith('c20000') or by.startswith('33c0c3') or by.startswith('32c0c3') or by.startswith('b001c3'):
        tag='INLINE-FOLD-BODY'
    return tag, by, 'cov='+','.join(cov)
if __name__=='__main__':
    for a in sys.argv[1:]:
        r=int(a,0)
        t,b,c=grade(r)
        print(f"0x{r:08X}  {t:<18} {b:<28} {c}")
