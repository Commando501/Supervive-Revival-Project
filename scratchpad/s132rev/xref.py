#!/usr/bin/env python3
"""Independent xref scanner: rel32 call/jmp targets, rip-rel lea/mov targets, qword pointers.
   UNCAPPED. Prints total count + all rows (or --head N)."""
import sys, os, struct
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rev import load, dis

def rel32_refs(img, target_rva, sec=".text"):
    s = img.secrange(sec)
    name,vaddr,vsize,rawptr,rawsize = s
    data = img.buf[rawptr:rawptr+rawsize]
    a = np.frombuffer(data, dtype=np.uint8)
    hits=[]
    # E8 rel32 (call), E9 rel32 (jmp)
    for opc,kind in ((0xE8,'call'),(0xE9,'jmp')):
        idx = np.nonzero(a[:-5]==opc)[0]
        if len(idx)==0: continue
        rel = np.frombuffer(data, dtype='<i4', count=(len(data)-4)//4*1, offset=0)
        # do it directly
        for i in idx:
            r = struct.unpack_from('<i', data, i+1)[0]
            tgt = vaddr + i + 5 + r
            if tgt == target_rva:
                hits.append((vaddr+i, kind))
    return hits

def riprel_refs(img, target_rva, sec=".text"):
    """Find any instruction whose rip-relative disp lands on target_rva.
       Brute force: for each 4-byte little-endian value v at offset i, check if
       vaddr+i+4+v == target for some instruction end == i+4. We approximate by
       testing every alignment (superset), then verifying by disassembling backwards."""
    s = img.secrange(sec)
    name,vaddr,vsize,rawptr,rawsize = s
    data = img.buf[rawptr:rawptr+rawsize]
    a = np.frombuffer(data, dtype=np.uint8)
    n = len(data)-4
    disp = np.frombuffer(data[:n+4], dtype=np.uint8)
    # vectorized: v[i] = int32 at i
    v = (disp[0:n].astype(np.int64) | (disp[1:n+1].astype(np.int64)<<8) |
         (disp[2:n+2].astype(np.int64)<<16) | (disp[3:n+3].astype(np.int64)<<24))
    v = np.where(v >= 0x80000000, v - 0x100000000, v)
    i = np.arange(n, dtype=np.int64)
    want = target_rva - vaddr - 4  # v == want - i
    hit = np.nonzero(v == (want - i))[0]
    return [vaddr+int(k) for k in hit]   # k = offset of disp field; instr ends at k+4

def qword_refs(img, target_va, sections=None):
    hits=[]
    for (name,vaddr,vsize,rawptr,rawsize) in img.sections:
        if sections and name not in sections: continue
        data = img.buf[rawptr:rawptr+rawsize]
        n=len(data)//8*8
        arr=np.frombuffer(data[:n], dtype='<u8')
        idx=np.nonzero(arr==np.uint64(target_va))[0]
        for k in idx: hits.append((name, vaddr+int(k)*8))
    return hits

if __name__=="__main__":
    mode=sys.argv[1]; rva=int(sys.argv[2],0)
    dumpname = sys.argv[sys.argv.index("--dump")+1] if "--dump" in sys.argv else "merged4"
    head = int(sys.argv[sys.argv.index("--head")+1]) if "--head" in sys.argv else 100000
    img=load(dumpname)
    if mode=="rel32":
        h=rel32_refs(img,rva)
        print("TOTAL rel32 refs to 0x%08X in .text of %s: %d (unit: instructions)"%(rva,dumpname,len(h)))
        for a,k in h[:head]: print("  0x%08X %s"%(a,k))
    elif mode=="rip":
        h=riprel_refs(img,rva)
        print("TOTAL rip-rel disp candidates to 0x%08X in .text of %s: %d (unit: 4-byte disp fields; superset)"%(rva,dumpname,len(h)))
        for a in h[:head]: print("  disp@0x%08X (instr ends 0x%08X)"%(a,a+4))
    elif mode=="qword":
        va=img.imagebase+rva if rva < img.imagebase else rva
        h=qword_refs(img,va)
        print("TOTAL qword refs to VA 0x%X: %d (unit: 8-byte slots)"%(va,len(h)))
        for s,a in h[:head]: print("  %s 0x%08X"%(s,a))
