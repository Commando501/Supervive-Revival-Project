import sys, struct
sys.path.insert(0, r"G:/git/Supervive Revival Project/scratchpad/s140/tools")
from peimg import Img
import capstone
CS=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_64); CS.detail=True
im=Img(); d=im.data; IB=im.imagebase
def dis(rva,n,label=''):
    print(f"--- {label} {rva:#x} ---")
    for i in CS.disasm(im.read(rva,n),rva):
        print(f"  {i.address:#010x} {i.bytes.hex():22s} {i.mnemonic} {i.op_str}")
dis(0x0530ABF0, 0x40, 'LF-13 disp 0xA50 impl')
print()
dis(0x035EB550, 0x40, 'engine PerformMovement around 0x035EB569')
print()
# stored-pointer occurrences of 0x0530ABF0
p=struct.pack('<Q', IB+0x0530ABF0)
occ=[];i=d.find(p)
while i!=-1: occ.append(i); i=d.find(p,i+1)
print("stored qword pointers to 0x0530ABF0:", [hex(x) for x in occ])
# All writers of [reg+0x16c8] byte in .text? scan for c8 16 00 00
sec=[s for s in im.sections if s['name']=='.text'][0]
base=sec['va']; data=d[sec['praw']:sec['praw']+max(sec['vsz'],sec['rawsz'])]
PAT=bytes([0xc8,0x16,0x00,0x00]); hits=[];i=data.find(PAT)
while i!=-1: hits.append(base+i); i=data.find(PAT,i+1)
print("dword-pattern c8 16 00 00 hits in .text:", len(hits))
