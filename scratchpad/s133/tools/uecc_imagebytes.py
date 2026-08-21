#!/usr/bin/env python3
"""Do the UE crash minidumps (UECC-*/UEMinidump.dmp) contain SUPERVIVE image .text bytes?
POSITIVE CONTROL built in: the parser must (a) find the SUPERVIVE module in ModuleList and
(b) account for ~all captured memory bytes, and (c) demonstrate it CAN attribute bytes to a
known-present region (thread stacks / other module images)."""
import struct, glob, os, sys, collections

def streams(f):
    f.seek(0); hdr=f.read(32)
    sig,ver,n,rva = struct.unpack_from('<IIII',hdr,0)
    assert sig==0x504d444d, 'not a minidump'
    f.seek(rva); d=f.read(12*n)
    return {t:(sz,r) for t,sz,r in (struct.unpack_from('<III',d,i*12) for i in range(n))}

def modules(f, sz, rva):
    f.seek(rva); n=struct.unpack('<I',f.read(4))[0]
    out=[]
    for i in range(n):
        b=f.read(108)
        base,size,cs,ts,nrva=struct.unpack('<QIIII',b[:24])
        cur=f.tell(); f.seek(nrva); ln=struct.unpack('<I',f.read(4))[0]
        nm=f.read(ln).decode('utf-16-le','replace'); f.seek(cur)
        out.append((base,size,nm))
    return out

def memlist(f, sz, rva):
    f.seek(rva); n=struct.unpack('<I',f.read(4))[0]
    return [struct.unpack('<QII', f.read(16)) for _ in range(n)]

def mem64(f, sz, rva):
    f.seek(rva); n,base = struct.unpack('<QQ', f.read(16))
    out=[]; off=base
    for _ in range(n):
        sa,s = struct.unpack('<QQ', f.read(16))
        out.append((sa,s,off)); off+=s
    return out

files=sorted(glob.glob(r'C:\Users\eastr\AppData\Local\SUPERVIVE\Saved\Crashes\UECC-*\UEMinidump.dmp'))
print(f"UECC minidumps found: {len(files)}")
tot_in=0; nonzero=0; parsed=0; empty=0
rows=[]
for p in files:
    if os.path.getsize(p)==0: empty+=1; continue
    try:
        with open(p,'rb') as f:
            st=streams(f)
            mods = modules(f,*st[4]) if 4 in st else []
            sup=[m for m in mods if 'SUPERVIVE-Win64' in m[2]]
            ranges=[]
            if 5 in st: ranges += [(sa,s) for sa,s,_ in memlist(f,*st[5])]
            has64 = 9 in st
            if has64: ranges += [(sa,s) for sa,s,_ in mem64(f,*st[9])]
            allb=sum(s for _,s in ranges)
            if not sup:
                rows.append((os.path.basename(os.path.dirname(p))[13:29],'NO-SUP-MODULE',len(mods),allb,0,has64,sorted(st)))
                continue
            b,sz,_=sup[0]
            ins=sum(s for sa,s in ranges if b<=sa<b+sz)
            tot_in+=ins
            if ins: nonzero+=1
            parsed+=1
            rows.append((os.path.basename(os.path.dirname(p))[13:29], hex(b), len(mods), allb, ins, has64, sorted(st)))
    except Exception as e:
        rows.append((os.path.basename(os.path.dirname(p))[13:29],'ERR '+str(e)[:40],0,0,0,False,[]))

print(f"parsed OK: {parsed}   zero-byte files skipped: {empty}")
print()
print(f"{'crashid':18s} {'sup base':>16s} {'#mod':>5s} {'mem bytes':>12s} {'IN IMAGE':>12s} m64 streams")
for r in rows[:12]:
    print(f"{r[0]:18s} {str(r[1]):>16s} {r[2]:5d} {r[3]:12d} {r[4]:12d} {str(r[5]):>5s} {r[6]}")
print(f"... ({len(rows)} rows total)")
print()
print(f"TOTAL bytes of captured memory inside the SUPERVIVE image, across all UECC dumps: {tot_in}")
print(f"dumps with ANY image bytes: {nonzero} / {parsed}")
print()
# POSITIVE CONTROL: can the parser attribute bytes to *some* module image?
if rows:
    p=[q for q in files if os.path.getsize(q)>0][0]
    with open(p,'rb') as f:
        st=streams(f); mods=modules(f,*st[4]); ranges=[(sa,s) for sa,s,_ in memlist(f,*st[5])]
        if 9 in st: ranges += [(sa,s) for sa,s,_ in mem64(f,*st[9])]
        hit=collections.Counter()
        for sa,s in ranges:
            for mb,ms,mn in mods:
                if mb<=sa<mb+ms: hit[os.path.basename(mn)]+=s; break
            else: hit['<not in any module>']+=s
    print("[CTRL] byte attribution for", os.path.basename(os.path.dirname(p)))
    for k,v in hit.most_common(8): print(f"   {v:12d}  {k}")
    print("[CTRL] parser CAN attribute bytes to module images:",
          'PASS' if any(k!='<not in any module>' for k in hit) else 'FAIL (uninterpretable null)')
