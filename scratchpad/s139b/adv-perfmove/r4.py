from advh import *
def show(a,b,label=""):
    print("=== 0x%08X..0x%08X %s"%(a,b,label))
    for i in md.disasm(DATA[a:b],a):
        print("  0x%08X %-16s %s"%(i.address,i.bytes.hex(),i.mnemonic+" "+i.op_str))
show(0x055A7460,0x055A7530,"around the 3rd +0x12B0 writer")
print()
show(0x055A56D0,0x055A5710,"around the +0x12B0 reader")
