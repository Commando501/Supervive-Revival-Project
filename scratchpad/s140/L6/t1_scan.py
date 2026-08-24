"""L6 step 1: SUPERSET candidate generator for disp/imm == 0x16C8 in .text.

KEY PROPERTY: 0x16C8 > 0x7F, so it can NEVER be encoded as disp8. Any x86 instruction
whose memory operand displacement is 0x16C8 encodes it as disp32 = bytes c8 16 00 00.
Same for a 32-bit immediate 0x16C8. Therefore a byte search for `c8 16 00 00` returns a
strict SUPERSET of the byte positions of all such encodings in the bytes we hold.
It is NOT the answer -- it is a candidate generator. Adjudication happens in step 2.
"""
import sys, struct, collections
sys.path.insert(0, r"G:/git/Supervive Revival Project/scratchpad/s140/tools")
from peimg import Img
im = Img()
tx = [s for s in im.sections if s['name']=='.text'][0]
base, size = tx['va'], tx['rawsz']
buf = im.data[tx['praw']: tx['praw']+size]
pat = bytes.fromhex('c8160000')
cands = []
off = buf.find(pat)
while off != -1:
    cands.append(base+off)
    off = buf.find(pat, off+1)
print(f".text {base:#x} size {size:#x};  candidate byte positions of 'c8 16 00 00': {len(cands)}")

# ---- POSITIVE CONTROL on the generator itself ----
# 0x055C2438 = 44 38 81 c8 16 00 00  -> disp bytes at 0x055C243B
# 0x055C2441 = 44 88 81 c8 16 00 00  -> disp bytes at 0x055C2444
# 0x055C2469 = c6 81 c8 16 00 00 01  -> disp bytes at 0x055C246B
ctrl = [0x055C243B, 0x055C2444, 0x055C246B]
cs = set(cands)
for c in ctrl:
    print(f"  GENERATOR CTRL  disp-bytes @ {c:#x}: {'FOUND' if c in cs else '*** MISSING ***'}   bytes={im.read(c-3,10).hex(' ')}")

# save
with open('L6/cands.txt','w') as f:
    for c in cands: f.write(f"{c:#x}\n")

# distribution by page for a feel
pages = collections.Counter(c>>12 for c in cands)
print(f"  spread over {len(pages)} distinct 4K pages")
