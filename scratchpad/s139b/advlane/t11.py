import io,sys,struct
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
exec(open('H.py').read())
rs,rl = RDATA
RD = D[rs:rs+rl]
def find_ascii(name):
    pat = name.encode()+b'\x00'
    out=[]; i=0
    while True:
        i = RD.find(pat, i)
        if i<0: break
        # must be preceded by a NUL (string start)
        if i==0 or RD[i-1]==0: out.append(rs+i)
        i+=1
    return out
def recs_for(strrva):
    va = r2v(strrva); pb = struct.pack('<Q',va)
    out=[]; i=0
    while True:
        i = RD.find(pb, i)
        if i<0: break
        if (rs+i)%8==0: out.append(rs+i)
        i+=1
    return out
for name in ("GravityScale","Velocity","Acceleration","MovementMode","MaxSimulationIterations","AnalogInputModifier","JumpZVelocity"):
    ss = find_ascii(name)
    print("== %s : %d ascii sites" % (name, len(ss)))
    for s in ss:
        for rec in recs_for(s):
            # scan +0x20..+0x50 for uint16 values
            u16=[struct.unpack_from('<H',D,rec+k)[0] for k in range(0x20,0x50,2)]
            print("   str %08X rec %08X u16[+0x20..0x4E]=%s" % (s,rec,[hex(x) for x in u16]))
