from h import *
def show(rva,n=60,label=""):
    print("=== 0x%08X %s"%(rva,label))
    for i in list(md.disasm(DATA[rva:rva+n*8],rva))[:n]:
        print("  0x%08X  %-22s %s"%(i.address,i.mnemonic,i.op_str))
show(0x056E7C10,45,"ULokiGameFeatureToggles::Get?")
