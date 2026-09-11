import sys
sys.path.insert(0,'scratchpad/s138/refute-x1')
from pg import Img
IMGS={n:Img(f'dumps/{n}.dump.exe') for n in ['merged2','merged10','merged12','merged13']}
addrs=[int(x,16) for x in sys.argv[1:]]
for a in addrs:
    row=[]
    for n in ['merged2','merged10','merged12','merged13']:
        row.append(IMGS[n].page_nonzero(a))
    e=IMGS['merged13'].bytes_at(a,32)
    enz=sum(1 for c in e if c)
    print(f"0x{a:08X} page=0x{a&~0xFFF:08X} m2={row[0]} m10={row[1]} m12={row[2]} m13={row[3]} entry32nz={enz} bytes={e[:16].hex(' ')}")
