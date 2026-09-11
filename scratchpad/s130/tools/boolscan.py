#!/usr/bin/env python
"""Decode the offset of every UHT native/bitfield bool UPROPERTY.

FBoolPropertyParams (measured layout, s129 dump):
  +0x00 NameUTF8   +0x08 RepNotify   +0x10 PropertyFlags(u64)
  +0x18 GenFlags(u32)  +0x1C ObjectFlags(u32)=0x45
  +0x20 SetterFunc  +0x28 GetterFunc
  +0x30 u16 ArrayDim   +0x32 u16 ElementSize   +0x34 u32 SizeOfOuter
  +0x38 void(*SetBitFunc)(void* Obj)      <-- offset lives HERE
Evidence: AActor::bAlwaysRelevant -> 0x032F7100 `or byte ptr [rcx+0x68],8; ret`
          AActor::bHidden         -> 0x03368980 `or byte ptr [rcx+0x68],0x80; ret`
"""
import struct, argparse, collections
import propscan as P
import capstone

md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
md.detail = True


def setbit(img, rec_rva):
    """-> (fn_rva, disp, mask, kind, text) or (fn_rva, None, None, reason, '')"""
    va = struct.unpack_from('<Q', img.d, rec_rva + 0x38)[0]
    r = img.rva(va)
    if r is None:
        return (None, None, None, 'badptr', '')
    blob = img.d[r:r + 24]
    if blob == b'\0' * 24:
        return (r, None, None, 'COVERAGE-BLOCKED', '')
    for ins in md.disasm(blob, r):
        if ins.mnemonic in ('or', 'mov', 'and') and ins.operands:
            o = ins.operands[0]
            if o.type == capstone.x86.X86_OP_MEM and o.mem.base == capstone.x86.X86_REG_RCX \
               and o.mem.index == 0:
                imm = ins.operands[1].imm if ins.operands[1].type == capstone.x86.X86_OP_IMM else None
                return (r, o.mem.disp, imm, ins.mnemonic, '%s %s' % (ins.mnemonic, ins.op_str))
        break
    ins = next(md.disasm(blob, r), None)
    return (r, None, None, 'unrecognised', ('%s %s' % (ins.mnemonic, ins.op_str)) if ins else 'undecodable')


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--dump', default='s129')
    ap.add_argument('--off', type=lambda x: int(x, 0), default=None)
    ap.add_argument('--name', default=None)
    ap.add_argument('--stats', action='store_true')
    a = ap.parse_args()
    img = P.Img(P.DUMPS[a.dump])
    recs = [h for h in P.scan(img) if (h['gflags'] & P.GENMASK) == 0x0C]
    print('image %s base 0x%X   Bool records: %d' % (a.dump, img.base, len(recs)))
    kinds = collections.Counter()
    fncount = collections.Counter()
    out = []
    for h in recs:
        fn, disp, mask, kind, txt = setbit(img, h['rva'])
        kinds[kind] += 1
        if fn is not None:
            fncount[fn] += 1
        h.update(fn=fn, disp=disp, mask=mask, kind=kind, txt=txt)
        out.append(h)
    if a.stats:
        for k, v in kinds.most_common():
            print('   %-20s %d' % (k, v))
    sel = out
    if a.off is not None:
        sel = [h for h in sel if h['disp'] == a.off]
    if a.name is not None:
        sel = [h for h in sel if h['name'] == a.name]
    if a.off is not None or a.name is not None:
        print('selected: %d' % len(sel))
        for h in sel:
            P.show(h)
            print('     SetBitFunc=0x%08X  [%s]  disp=%s mask=%s  fold=%d' %
                  (h['fn'] or 0, h['txt'], hex(h['disp']) if h['disp'] is not None else '?',
                   hex(h['mask']) if h['mask'] is not None else '?', fncount[h['fn']]))
