import sys
sys.path.insert(0,'scratchpad/refute-x2')
from pe import PE
p=PE('dumps/merged13.dump.exe')
t=p.sec('.text')
d=p.data
base=t['rawptr']; npg=t['vsize']//0x1000
nz=0
zeropages=[]
for i in range(npg):
    o=base+i*0x1000
    pg=d[o:o+0x1000]
    if pg.count(0)!=0x1000: nz+=1
print('.text pages=%d nonzero=%d pct=%.2f%%'%(npg,nz,100.0*nz/npg))
pd=p.sec('.pdata')
seg=d[pd['rawptr']:pd['rawptr']+pd['rawsize']]
print('.pdata bytes=%d nonzero_bytes=%d'%(len(seg),len(seg)-seg.count(0)))
# calibration byte scans
for tok,enc in [(b'KERNEL32','ascii'),(b'kernel32','ascii'),('KERNEL32'.encode('utf-16-le'),'utf16'),(b'ZZZQQQNOTPRESENT','ascii')]:
    print(repr(tok[:20]),enc,d.count(tok))
