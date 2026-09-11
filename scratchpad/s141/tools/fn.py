import sys, collections
sys.path.insert(0,'.')
from peimg import Img
from cfg import CFG, X86
IMG = r"G:/git/Supervive Revival Project/dumps/merged14.dump.exe"

def load(entry, img=None):
    im = img or Img(IMG)
    return im, CFG(im, entry)

def show(entry, grep=None, calls_only=False, img=None):
    im, c = load(entry, img)
    print(f"### {entry:#x}: {len(c.insns)} insns, {len(c.calls)} calls, "
          f"{len(c.indirect_jumps)} indirect jumps, {len(c.decode_failures)} decode fails")
    for rva in sorted(c.insns):
        i = c.insns[rva]
        line = f"{rva:#010x}  {i.mnemonic} {i.op_str}"
        if calls_only and i.mnemonic != 'call': continue
        if grep and grep not in line: continue
        print("  "+line)
    return im, c

if __name__ == '__main__':
    entry = int(sys.argv[1],16)
    grep = sys.argv[2] if len(sys.argv)>2 else None
    show(entry, grep)
