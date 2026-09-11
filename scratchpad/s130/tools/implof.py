import sys, os, struct
import capstone
DUMPS = {
 "s129":  r"G:\git\Supervive Revival Project\dumps\s129-poolgate\SUPERVIVE-Win64-Shipping.dump.exe",
 "merged2": r"G:\git\Supervive Revival Project\dumps\merged2.dump.exe",
 "tuthero": r"G:\git\Supervive Revival Project\dumps\tutorial-hero\SUPERVIVE-Win64-Shipping.dump.exe",
}
BASES = {"s129":0x7FF7B86D0000}
def load(d):
    data = open(DUMPS[d],'rb').read()
    # ImageBase from optional header
    pe = struct.unpack_from('<I', data, 0x3C)[0]
    base = struct.unpack_from('<Q', data, pe+0x30)[0]
    return data, base
FOLDS = {0xF7EC20:"ret 0 (c2 00 00)", 0xF7EB50:"xor eax,eax; ret", 0xF7EB60:"xor al,al; ret", 0x0B9E1F0:"mov al,1; ret"}
def tail(rva, dump="s129", maxn=400):
    data, base = load(dump)
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
    md.detail=False
    code = data[rva:rva+maxn]
    if not any(code[:16]):
        return None, "PAGE ZERO / coverage-blocked"
    last=None; seq=[]
    for ins in md.disasm(code, rva):
        seq.append((ins.address, ins.mnemonic, ins.op_str))
        if ins.mnemonic in ('call','jmp') and ins.op_str.startswith('0x'):
            t = int(ins.op_str,16)
            if t > base: t -= base
            last = (ins.address, ins.mnemonic, t, ins.bytes.hex())
        if ins.mnemonic == 'ret':
            break
    return last, seq
def multiplicity(target_rva, dump="s129"):
    """count qword pointers in the whole image equal to base+target"""
    data, base = load(dump)
    needle = struct.pack('<Q', base+target_rva)
    n=0; i=0
    while True:
        i = data.find(needle, i)
        if i<0: break
        n+=1; i+=1
    return n
if __name__=="__main__":
    for a in sys.argv[1:]:
        rva=int(a,16)
        last, seq = tail(rva)
        print(f"--- thunk {rva:#x}")
        if last is None:
            print("   ", seq); continue
        addr,mn,t,by = last
        print(f"    last direct {mn} at {addr:#x} bytes={by} -> {t:#x}   {FOLDS.get(t,'')}")
        # show bytes at target
        data, base = load("s129")
        print(f"    target bytes: {data[t:t+8].hex()}")
        print(f"    qword-ptr multiplicity of target {t:#x} = {multiplicity(t)}")