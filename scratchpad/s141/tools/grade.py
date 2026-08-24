import sys, binascii
sys.path.insert(0, r"G:/git/Supervive Revival Project/scratchpad/s141/tools")
from peimg import Img
import capstone
IMG = r"G:/git/Supervive Revival Project/dumps/merged14.dump.exe"
im = Img(IMG)
FOLDS = {0x0F7EC20:'VOID ret 0 (c20000)', 0x0F7EB50:'nullptr/false (33c0c3)',
         0x0F7EB60:'false (32c0c3)', 0x0B9E1F0:'true (b001c3)', 0x0FC6CF0:'0.0f (0f57c0c3)'}
FOLDBYTES = {0x0F7EC20:b'\xc2\x00\x00',0x0F7EB50:b'\x33\xc0\xc3',0x0F7EB60:b'\x32\xc0\xc3',
             0x0B9E1F0:b'\xb0\x01\xc3',0x0FC6CF0:b'\x0f\x57\xc0\xc3'}
md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
md.detail = False
def grade(rva, n=48, label=""):
    if rva in FOLDS: print(f"{rva:#011x} {label:38s} FOLD  == {FOLDS[rva]}"); return 'FOLD'
    pn = im.page_nonzero(rva)
    if pn == 0: print(f"{rva:#011x} {label:38s} DARK  page 0/4096"); return 'DARK'
    b = im.read(rva, n)
    for fr, fb in FOLDBYTES.items():
        if b.startswith(fb): print(f"{rva:#011x} {label:38s} FOLD-BYTES {FOLDS[fr]}"); return 'FOLD'
    print(f"{rva:#011x} {label:38s} REAL  page {pn}/4096  first16={binascii.hexlify(b[:16]).decode()}")
    return 'REAL'
def dis(rva, n=0x120, label=""):
    print(f"--- disasm {rva:#x} {label} ---")
    b = im.read(rva, n)
    for i in md.disasm(b, rva):
        print(f"  {i.address:#011x}  {i.bytes.hex():<20s} {i.mnemonic} {i.op_str}")
if __name__ == '__main__':
    for a in sys.argv[1:]:
        if a.startswith('d:'): dis(int(a[2:],16))
        else: grade(int(a,16))
