from h import *
from capstone.x86 import *
def rips(rva,n=0x120,label=""):
    print("=== 0x%08X %s"%(rva,label))
    for i in md.disasm(DATA[rva:rva+n],rva):
        for op in i.operands:
            if op.type==X86_OP_MEM and op.mem.base==X86_REG_RIP:
                t=i.address+i.size+op.mem.disp
                s=""
                if 0x0764A000<=t<0x099C7000:
                    b=DATA[t:t+80]
                    # try wide
                    w=b''
                    for k in range(0,80,2):
                        if b[k]==0 and b[k+1]==0: break
                        if b[k+1]!=0: w=b''; break
                        w+=bytes([b[k]])
                    a=b.split(b'\0')[0]
                    s="  W='%s'"%w.decode('latin1') if len(w)>2 else ("  A='%s'"%a.decode('latin1') if 2<len(a)<60 else "")
                print("  0x%08X %-28s -> 0x%08X%s"%(i.address,i.mnemonic+" "+i.op_str,t,s))
        if i.mnemonic=='ret': break
rips(0x052F01E0,0x100,"class getter A")
rips(0x0528FE60,0x100,"class getter B")
