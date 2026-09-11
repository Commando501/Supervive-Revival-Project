#!/usr/bin/env python3
"""FK-20: per-image .text decrypted-page matrix.

A page at RVA R of a dumpimage snapshot is DECRYPTED iff the 4096 bytes at file
offset R are not all zero (file offset == RVA in these dumps -- verified below by
a positive control on the PE header page).

Outputs:
  - per-image page count
  - UNIQUE pages per image (present in exactly one of the 26 images)
  - greedy incremental cover order (which images, in which order, buy the most)
"""
import os, sys, glob, struct

TEXT_RVA  = 0x1000
TEXT_VSZ  = 0x7649000
PAGE      = 4096
NPAGES    = (TEXT_VSZ + PAGE - 1)//PAGE   # 30281

def bitmap(path):
    """Return (bytearray of NPAGES 0/1, name)."""
    bm = bytearray(NPAGES)
    with open(path,'rb') as f:
        f.seek(TEXT_RVA)
        for i in range(NPAGES):
            b = f.read(PAGE)
            if not b: break
            # any nonzero byte -> decrypted
            if b.count(0) != len(b):
                bm[i] = 1
    return bm

def positive_control(path):
    """Prove file offset == RVA: the DOS header at offset 0 must be 'MZ' and the
    PE header pointed to by e_lfanew must be 'PE\0\0'. Also prove the .text
    section header says RVA 0x1000 / rawptr 0x1000."""
    with open(path,'rb') as f:
        d = f.read(0x400)
    assert d[:2]==b'MZ', 'not a PE'
    e_lfanew = struct.unpack_from('<I', d, 0x3c)[0]
    assert d[e_lfanew:e_lfanew+4]==b'PE\0\0', 'no PE sig'
    nsec = struct.unpack_from('<H', d, e_lfanew+6)[0]
    optsz= struct.unpack_from('<H', d, e_lfanew+20)[0]
    secs = e_lfanew+24+optsz
    for i in range(nsec):
        o = secs+i*40
        nm = d[o:o+8].rstrip(b'\0').decode()
        vsz,vrva,rawsz,rawptr = struct.unpack_from('<IIII', d, o+8)
        if nm=='.text':
            return nm, vsz, vrva, rawsz, rawptr
    return None

imgs = sorted(glob.glob('dumps/*/SUPERVIVE-Win64-Shipping.dump.exe'))
imgs = [q.replace(os.sep,'/') for q in imgs]
names = [q.split('/')[1] for q in imgs]

pc = positive_control(imgs[0])
print(f"[CTRL] {imgs[0]}")
print(f"[CTRL] section {pc[0]}  VSize={pc[1]:#x} VRVA={pc[2]:#x} RawSize={pc[3]:#x} RawPtr={pc[4]:#x}")
print(f"[CTRL] file offset == RVA for .text: {'PASS' if pc[2]==pc[4] else 'FAIL'}")
print(f"[CTRL] our TEXT_RVA/VSZ constants match header: "
      f"{'PASS' if (pc[2]==TEXT_RVA and pc[1]==TEXT_VSZ) else 'FAIL'}")
print(f"[CTRL] NPAGES = {NPAGES}")
print()

bms = {}
for p,n in zip(imgs,names):
    bms[n] = bitmap(p)
    print(f"{n:38s} {sum(bms[n]):6d} pages  {sum(bms[n])/NPAGES*100:6.2f}%", flush=True)

# union
union = bytearray(NPAGES)
for n in names:
    b = bms[n]
    for i in range(NPAGES):
        if b[i]: union[i]=1
print()
print(f"{'UNION of all '+str(len(names))+' images':38s} {sum(union):6d} pages  {sum(union)/NPAGES*100:6.2f}%")

# multiplicity per page
mult = [0]*NPAGES
for n in names:
    b = bms[n]
    for i in range(NPAGES):
        mult[i]+=b[i]

print()
print("UNIQUE pages (page decrypted in EXACTLY ONE image):")
uniq = {n:0 for n in names}
for i in range(NPAGES):
    if mult[i]==1:
        for n in names:
            if bms[n][i]: uniq[n]+=1; break
for n,c in sorted(uniq.items(), key=lambda kv:-kv[1]):
    if c: print(f"  {n:38s} {c:5d} unique pages")
print(f"  total pages with multiplicity 1: {sum(1 for m in mult if m==1)}")
print(f"  total pages with multiplicity 0 (DARK everywhere): {sum(1 for m in mult if m==0)}")
print(f"  pages present in ALL {len(names)} images: {sum(1 for m in mult if m==len(names))}")

print()
print("GREEDY INCREMENTAL COVER (max new pages first):")
cov = bytearray(NPAGES); left=set(names); order=[]
while left:
    best=None;bestg=-1
    for n in left:
        g=0; b=bms[n]
        for i in range(NPAGES):
            if b[i] and not cov[i]: g+=1
        if g>bestg: bestg=g; best=n
    b=bms[best]
    for i in range(NPAGES):
        if b[i]: cov[i]=1
    order.append((best,bestg,sum(cov)))
    left.discard(best)
    if bestg==0 and len(order)>1:
        # print the rest compactly
        rest=sorted(left)
        for n in rest: order.append((n,0,sum(cov)))
        break
for rank,(n,g,tot) in enumerate(order,1):
    print(f"  {rank:2d}. {n:38s} +{g:5d} new  -> {tot:6d} ({tot/NPAGES*100:6.2f}%)")
