from h import *
start=0x055B8370; end=0x055B88DE
insns=list(md.disasm(DATA[start:end],start))
for i in insns:
    if i.mnemonic=='call':
        print("0x%08X call %s"%(i.address,i.op_str))
print("---- bytes at 055B85B4..055B85C6")
print(DATA[0x055B85B4:0x055B85C6].hex(' '))
print("---- next function at 0x055B88DE")
for i in list(md.disasm(DATA[0x055B88DE:0x055B88DE+40],0x055B88DE))[:6]:
    print("0x%08X %s %s"%(i.address,i.mnemonic,i.op_str))
