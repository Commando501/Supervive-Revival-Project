import io,sys,struct
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
exec(open('H.py').read())
rs,rl=RDATA
pb=struct.pack('<Q', r2v(0x3600990))
hits=[]; i=0
RD=D[rs:rs+rl]
while True:
    i=RD.find(pb,i)
    if i<0: break
    if (rs+i)%8==0: hits.append(rs+i)
    i+=1
print("aligned .rdata qwords == VA(0x3600990):", [hex(h) for h in hits], " implied vt bases:", [hex(h-0x720) for h in hits])
pb2=struct.pack('<Q', r2v(0x55C2430))
hits2=[];i=0
while True:
    i=RD.find(pb2,i)
    if i<0: break
    if (rs+i)%8==0: hits2.append(rs+i)
    i+=1
print("aligned .rdata qwords == VA(0x55C2430):", [hex(h) for h in hits2], " implied vt bases:", [hex(h-0x720) for h in hits2])
