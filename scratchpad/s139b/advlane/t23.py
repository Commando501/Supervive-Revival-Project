import io,sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
exec(open('H.py').read())
n=0
for i in MD.disasm(D[0x035EC850:0x035EC887],0x035EC850):
    n+=1; print(n, "%08X %s %s"%(i.address,i.mnemonic,i.op_str))
