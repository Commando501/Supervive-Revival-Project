import sys
sys.path.insert(0,'.')
from peimg import Img
from cfg import CFG
IMG = r"G:/git/Supervive Revival Project/dumps/merged14.dump.exe"
im=Img(IMG)
entry=int(sys.argv[1],16); node=int(sys.argv[2],16)
c=CFG(im, entry)
print(f"fn {entry:#x}: {len(c.insns)} insns, {len(c.calls)} calls, {len(c.indirect_jumps)} indirect jmps, {len(c.decode_failures)} decode fails")
R = c.reach_backward(node)
print(f"|R(can reach {node:#x})| = {len(R)}")
print(f"entry in R: {entry in R}")
# exits
ex,_ = c.exits_from(node)
print(f"exit edges leaving R: {len(ex)}")
for s,d in ex:
    print(f"   {c.txt(s)}   -> {d if d is None else hex(d)}")
# forward: what does node dominate? check other nodes
for extra in sys.argv[3:]:
    e=int(extra,16)
    Re = c.reach_backward(e)
    print(f"  {node:#x} can reach {e:#x}: {node in Re}   |R({e:#x})|={len(Re)}")
