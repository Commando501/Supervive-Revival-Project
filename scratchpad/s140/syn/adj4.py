exec(open(r"scratchpad/s140/syn/adj3.py").read().split("for E,name in")[0])
insns,succ,calls,ijmp,rets,fails=cfg(0x035E9EC0)
SNP=0x035EB13A; A50=0x035EB569; RET=0x035EB1CA
print("ret reachable from 0x35EB1CB avoiding A50:", RET in reach(succ,0x035EB1CB,ban=A50))
print("A50 dominates ret from 0x35EB1CB:", RET not in reach(succ,0x035EB1CB,ban=A50))
# rbx writers in engine PM
import capstone as cs
w=[]
for a in sorted(insns):
    i=insns[a]
    for r in i.regs_access()[1]:
        if i.reg_name(r) in ('rbx','ebx','bx','bl'): w.append((a,i.bytes.hex(),i.mnemonic+' '+i.op_str)); break
print("\nRBX writers in engine PM:", [(hex(a),t) for a,b,t in w])
# rcx writers between 0x35E9F2E and 0x35E9FB5, and any call in between
seg=[a for a in sorted(insns) if 0x035E9F2E < a < 0x035E9FB5]
callsin=[hex(a) for a in seg if insns[a].mnemonic=='call']
rcxw=[]
for a in seg:
    i=insns[a]
    for r in i.regs_access()[1]:
        if i.reg_name(r) in ('rcx','ecx','cx','cl'): rcxw.append(hex(a)); break
print("calls in (0x35E9F2E,0x35E9FB5):",callsin," rcx writers:",rcxw)
# r8 writers between xor and call
seg=[a for a in sorted(insns) if 0x035EB129 <= a < SNP]
r8w=[]
for a in seg:
    i=insns[a]
    if a==0x035EB129: continue
    for r in i.regs_access()[1]:
        if i.reg_name(r).startswith('r8'): r8w.append(hex(a)); break
print("r8 writers after xor r8d,r8d before SNP call:",r8w, " calls:",[hex(a) for a in seg if insns[a].mnemonic=='call'])
