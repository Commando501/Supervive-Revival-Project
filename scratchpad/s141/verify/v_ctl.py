import sys, struct
sys.path.insert(0,'G:/git/Supervive Revival Project/scratchpad/s141/tools')
from peimg import Img
IMG=r"G:/git/Supervive Revival Project/dumps/merged14.dump.exe"
im=Img(IMG)
print(f"IMAGE {IMG}\n ImageBase {im.imagebase:#x} FLAT={im.flat()} sections={im.nsec}")
for s in im.sections:
    print(f"   {s['name']:10s} va={s['va']:#010x} praw={s['praw']:#010x} vsz={s['vsz']:#010x} rawsz={s['rawsz']:#010x}")
print("--- DARK negative control")
print(f" 0x5A6AC40 page_nonzero = {im.page_nonzero(0x5A6AC40)}/4096  (expect 0)")
print("--- fold constants")
for rva,exp in [(0x0F7EC20,'c20000'),(0x0F7EB50,'33c0c3'),(0x0F7EB60,'32c0c3'),(0x0B9E1F0,'b001c3'),(0x0FC6CF0,'0f57c0c3')]:
    got=im.read(rva,len(exp)//2).hex()
    print(f" {rva:#09x} exp={exp:10s} got={got:10s} {'PASS' if got==exp else '*** FAIL ***'}")
print("--- LIT positive controls (lane-relevant)")
for rva,name in [(0x55AC9F0,'+0xC00 GAS helper'),(0x55ACB90,'GetMaxSpeed?'),(0x55AC910,'GetMaxAcceleration?'),
                 (0x1F62B10,'GetCurrentValue?'),(0x55266E0,'min helper?'),(0x4481AC0,'InitStats?'),
                 (0x447D240,'GetOrCreateAttributeSubobject?'),(0x44797F0,'GetAttributeSubobject?'),
                 (0x35E3AD0,'engine GetMaxAcceleration?'),(0x35E3C20,'engine GetMaxSpeed?')]:
    print(f" {rva:#09x} {name:35s} page_nonzero={im.page_nonzero(rva)}/4096")
