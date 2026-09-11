import sys, struct
sys.path.insert(0,'scratchpad/s137-w3')
from img import Img
import capstone

def lea_xrefs(im, target_rva, secname='.text'):
    """Find rip-relative LEA/MOV instructions whose computed target == target_rva.
    Brute: scan for any 4-byte little-endian d such that (pos+4+d) == target within .text,
    then disassemble backwards a few bytes to confirm an instruction boundary yielding it."""
    b = im.b
    sec = [s for s in im.sections if s[0]==secname][0]
    lo, hi = sec[1], sec[1]+sec[4]
    hits=[]
    # scan every offset; d = target - (pos+4)
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
    md.detail = True
    for pos in range(lo, hi-4):
        d = struct.unpack_from('<i', b, pos)[0]
        if pos+4+d == target_rva:
            # try to decode an instruction starting 2..8 bytes before pos whose length ends at pos+4
            for back in range(2, 11):
                start = pos-back
                if start < lo: continue
                if b[start] == 0 and b[start+1]==0: continue
                try:
                    ins = next(md.disasm(b[start:start+16], im.rva2va(start)))
                except StopIteration:
                    continue
                if ins.size == back+4:
                    hits.append((start, ins.mnemonic, ins.op_str, back))
                    break
    return hits
