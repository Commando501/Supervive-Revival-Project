import sys, json, re; sys.path.insert(0,r"G:\git\Supervive Revival Project\scratchpad\s139\lane2")
from img2 import DATA
import capstone
md=capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
d=json.load(open(r"G:\git\Supervive Revival Project\tools\strxref\index\uesymbols.json"))['symbols']
CLS=('UCharacterMovementComponent','ULokiCharacterMovementComponent','UMovementComponent','UPawnMovementComponent','UNavMovementComponent','UActorComponent','USceneComponent')
rows=[]
for k,v in d.items():
    if v.get('kind')!='exec_thunk': continue
    if v.get('class') not in CLS: continue
    rva=int(k,16)
    disps=set(); directs=set()
    code=DATA[rva:rva+0x300]
    for ins in md.disasm(code, rva):
        if ins.mnemonic=='call':
            m=re.match(r'qword ptr \[\w+ \+ (0x[0-9a-f]+)\]$', ins.op_str)
            if m: disps.add(int(m.group(1),16))
            elif re.match(r'^0x[0-9a-f]+$', ins.op_str): directs.add(int(ins.op_str,16))
        if ins.mnemonic=='ret': break
    rows.append((v['class'], ','.join(v['names']), rva, sorted(disps), sorted(directs)))
for c,n,r,ds,dr in sorted(rows):
    print("%-32s %-40s thunk=0x%07X vdisp=%s direct=%s"%(c,n,r,[hex(x) for x in ds],[hex(x) for x in dr]))
