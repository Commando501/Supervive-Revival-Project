from h import *
def show(rva,n,label=""):
    print("=== 0x%08X %s"%(rva,label))
    for i in list(md.disasm(DATA[rva:rva+n*10],rva))[:n]:
        print("  0x%08X  %-8s %-22s %s"%(i.address,i.bytes.hex(),i.mnemonic,i.op_str))
show(0x055D5EB0,60,"default getter")
