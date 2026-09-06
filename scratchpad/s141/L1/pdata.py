import sys, struct
sys.path.insert(0, r"G:/git/Supervive Revival Project/scratchpad/s141/tools")
from peimg import Img
im = Img(r"G:/git/Supervive Revival Project/dumps/merged14.dump.exe")
s = [x for x in im.sections if x['name']=='.pdata'][0]
d = im.data[s['praw']: s['praw']+s['rawsz']]
print(f".pdata {len(d)//12} rows")
rows=[]
for o in range(0, len(d)-11, 12):
    b,e,u = struct.unpack_from('<III', d, o)
    if b==0 and e==0: continue
    rows.append((b,e,u))
rows.sort()
print("rows with Begin in [0x35EC000,0x35EF000):")
for b,e,u in rows:
    if 0x35EC000 <= b < 0x35EF000:
        print(f"  {b:#010x} .. {e:#010x}  size {e-b:#x} ({e-b})  unwind {u:#x}")
