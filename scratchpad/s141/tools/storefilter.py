"""Validate storehits against pdata function boundaries; keep real STORE mnemonics."""
import sys, json, csv, bisect
sys.path.insert(0,'.')
from peimg import Img
import capstone as cs
from collections import Counter

IMG = r"G:/git/Supervive Revival Project/dumps/merged14.dump.exe"
im = Img(IMG)
TX = [s for s in im.sections if s['name']=='.text'][0]
tlo = TX['va']; praw = TX['praw']
data = im.data

hits = json.load(open('storehits.json'))

STORE_MNEM = {'mov','movups','movaps','movupd','movapd','movsd','movss','movdqu','movdqa',
              'movq','movd','vmovups','vmovaps','vmovsd','vmovss','vmovdqu','vmovdqa',
              'vmovlpd','vmovhpd','vmovlps','vmovhps'}
RMW = {'add','sub','adc','sbb','or','and','xor','inc','dec','xchg','cmpxchg','lock inc','lock add','not','neg'}

pure = [h for h in hits if h['mnem'] in STORE_MNEM]
print(f"[FILTER-1] mnemonic is a pure STORE: {len(pure)} of {len(hits)}")
print("           dropped mnemonics:", Counter(h['mnem'] for h in hits if h['mnem'] not in STORE_MNEM).most_common())

# --- pdata function map
begins=[]; ends=[]
with open(r"G:/git/Supervive Revival Project/tools/strxref/index/pdata_union.csv") as f:
    r = csv.DictReader(f)
    for row in r:
        b = int(row['begin_rva'],16); e = int(row['end_rva'],16)
        begins.append(b); ends.append(e)
order = sorted(range(len(begins)), key=lambda i: begins[i])
B = [begins[i] for i in order]; E = [ends[i] for i in order]
print(f"[PDATA] {len(B)} rows (size>1 only; BLIND on dark pages BY CONSTRUCTION)")

def containing(rva):
    i = bisect.bisect_right(B, rva)-1
    while i>=0 and B[i] <= rva:
        if rva < E[i]: return B[i], E[i]
        i -= 1
        if i>=0 and B[i] < rva-0x20000: break
    return None, None

md = cs.Cs(cs.CS_ARCH_X86, cs.CS_MODE_64); md.detail=True
_bcache = {}
def boundaries(fb, fe):
    k=(fb,fe)
    if k in _bcache: return _bcache[k]
    b = data[praw+(fb-tlo): praw+(fe-tlo)]
    s = set()
    for ins in md.disasm(b, fb):
        s.add(ins.address)
    _bcache[k]=s
    return s

valid=[]; nofn=0; badbound=0
for h in pure:
    fb, fe = containing(h['rva'])
    if fb is None:
        nofn += 1
        h['fn']=None; h['boundary']='NO-PDATA-ROW'
        valid.append(h)   # keep, flagged
        continue
    if h['rva'] in boundaries(fb,fe):
        h['fn']=fb; h['fnend']=fe; h['boundary']='OK'
        valid.append(h)
    else:
        badbound += 1
print(f"[FILTER-2] on a real instruction boundary: {len(valid)-nofn}   no pdata row (kept, flagged): {nofn}   REJECTED misaligned: {badbound}")
json.dump(valid, open('storehits_valid.json','w'))
print("  by disp:", Counter(hex(h['disp']) for h in valid))
print("  by mnemonic:", Counter(h['mnem'] for h in valid).most_common())
print("  distinct containing functions:", len({h.get('fn') for h in valid if h.get('fn')}))
