import sys, struct
sys.path.insert(0,'G:/git/Supervive Revival Project/scratchpad/s141/tools')
from peimg import Img
import capstone
im=Img(r"G:/git/Supervive Revival Project/dumps/merged14.dump.exe")
IB=im.imagebase; D=im.data
md=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_64)
def rva_of(off):
    for s in im.sections:
        if s['praw']<=off<s['praw']+s['rawsz']: return s['va']+(off-s['praw'])
def find_str(tok):
    b=b'\x00'+tok.encode()+b'\x00'; out=[]; o=0
    while True:
        o=D.find(b,o)
        if o<0: break
        out.append(rva_of(o+1)); o+=1
    return out
def ptrs_to(rva):
    t=(rva+IB).to_bytes(8,'little'); out=[]
    for s in im.sections:
        o=s['praw']; end=s['praw']+s['rawsz']
        while True:
            o=D.find(t,o)
            if o<0 or o>=end: break
            out.append((s['name'], s['va']+(o-s['praw']))); o+=8
    return out
for tok in ('bCharacterMovementEnabled',):
    ss=find_str(tok); print(f"'{tok}' strings: {[hex(x) for x in ss]}")
    for s in ss:
        for sec,r in ptrs_to(s):
            print(f"  ptr in {sec} @{r:#x}")
            blob=im.read(r,0x48); print("   "+' '.join(f'{b:02x}' for b in blob))
            # look for a code pointer inside (SetBitFunc)
            for i in range(0,0x48,8):
                v=struct.unpack_from('<Q',blob,i)[0]
                if v>IB and 0x1000<=(v-IB)<0x764a000:
                    fr=v-IB
                    code=im.read(fr,12)
                    print(f"      +{i:#04x} code {fr:#x} bytes={code.hex()}")
                    for ins in md.disasm(code, fr):
                        print(f"          {ins.address:#x} {ins.mnemonic} {ins.op_str}")
print()
print("=== 0x52AC690 region (wide LEA check)")
code=im.read(0x52AC690,40)
for ins in md.disasm(code,0x52AC690):
    e=''
    print(f"  {ins.address:#x} {ins.bytes.hex():<20s} {ins.mnemonic} {ins.op_str}")
# manual rip resolve for the two leas
for at,ln in ((0x52AC696,7),(0x52AC6A5,7)):
    b=im.read(at,ln); disp=struct.unpack_from('<i',b,3)[0]; t=at+ln+disp
    try: s=im.read(t,60).decode('utf-16-le',errors='replace').split('\x00')[0]
    except Exception: s='?'
    print(f"  lea at {at:#x} -> {t:#x}  wide='{s}'")
