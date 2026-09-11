#!/usr/bin/env python3
"""Which SECTIONS of the game image do UECC minidumps capture, and is any of it .text?"""
import struct, glob, os, collections
SECS=[('.text',0x1000,0x7649000),('.rdata',0x764A000,0x237D000),('.data',0x99C7000,0x6F0000),
      ('.pdata',0xA0B7000,0x5FE000),('.msvcjmc',0xA6B5000,0x1000),('CPADinfo',0xA6B6000,0x1000),
      ('.rodata',0xA6B7000,0x1000),('_RDATA',0xA6B8000,0x5E000),('.rsrc',0xA716000,0xF000),
      ('.reloc',0xA725000,0x2BC000)]
def streams(f):
    f.seek(0); sig,ver,n,rva = struct.unpack_from('<IIII',f.read(32),0)
    f.seek(rva); d=f.read(12*n)
    return {t:(sz,r) for t,sz,r in (struct.unpack_from('<III',d,i*12) for i in range(n))}
def modules(f,sz,rva):
    f.seek(rva); n=struct.unpack('<I',f.read(4))[0]; out=[]
    for i in range(n):
        b=f.read(108); base,size,cs,ts,nrva=struct.unpack('<QIIII',b[:24])
        cur=f.tell(); f.seek(nrva); ln=struct.unpack('<I',f.read(4))[0]
        nm=f.read(ln).decode('utf-16-le','replace'); f.seek(cur); out.append((base,size,nm))
    return out
def memlist(f,sz,rva):
    f.seek(rva); n=struct.unpack('<I',f.read(4))[0]
    return [struct.unpack('<QII',f.read(16)) for _ in range(n)]

files=[p for p in sorted(glob.glob(r'C:\Users\eastr\AppData\Local\SUPERVIVE\Saved\Crashes\UECC-*\UEMinidump.dmp')) if os.path.getsize(p)>0]
agg=collections.Counter(); agg_r=collections.Counter()
textpages=set()
per=[]
for p in files:
    with open(p,'rb') as f:
        st=streams(f); mods=modules(f,*st[4]); rs=memlist(f,*st[5])
        sup=[m for m in mods if 'SUPERVIVE-Win64' in m[2]]
        rt=[m for m in mods if m[2].lower().endswith('runtime.dll')]
        if not sup: continue
        b,sz,_=sup[0]; loc=collections.Counter()
        for sa,s,rv in rs:
            if not (b<=sa<b+sz): continue
            rva0=sa-b
            for nm,srva,svsz in SECS:
                if srva<=rva0<srva+svsz:
                    loc[nm]+=s; agg[nm]+=s
                    if nm=='.text':
                        for pgi in range((rva0-0x1000)//4096, (rva0-0x1000+s+4095)//4096):
                            textpages.add(pgi)
                    break
            else: loc['<gap>']+=s; agg['<gap>']+=s
        if rt:
            rb,rsz,_=rt[0]
            agg_r['runtime.dll bytes']+=sum(s for sa,s,_ in rs if rb<=sa<rb+rsz)
        per.append((os.path.basename(os.path.dirname(p))[13:29], dict(loc)))
print(f"dumps analysed: {len(per)}")
print("\n=== AGGREGATE bytes captured inside the game image, BY SECTION (all dumps summed) ===")
for k,v in agg.most_common(): print(f"  {k:10s} {v:12d}  ({v/1e6:8.1f} MB)")
print("\n=== first 5 dumps, per-section ===")
for cid,loc in per[:5]: print(f"  {cid}: {loc}")
print(f"\n.text PAGES touched by UECC memory ranges (union over {len(per)} dumps): {len(textpages)}")
print(f"runtime.dll bytes captured (all dumps): {dict(agg_r)}")
