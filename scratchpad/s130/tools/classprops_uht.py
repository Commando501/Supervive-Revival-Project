#!/usr/bin/env python
"""Enumerate EVERY reflected UPROPERTY of one UClass from the UHT FClassParams
tables, with the CORRECT per-type record layout, and map each to its byte offset.

WHY THIS EXISTS
---------------
S130 tried to name `AActor+0x6C` with two instruments and both were wrong:

  * `boolscan.py --off 0x6c` finds bool records whose SetBitFunc displacement is
    0x6C -- but that displacement is an offset within the record's OWN outer
    class, so 11 hits across 11 unrelated classes say nothing about AActor.
  * `propscan.py --off 0x6c` reads `Offset` at record+0x32 for every record --
    but `FBoolPropertyParams` puts `ElementSize` there, so bools decode as
    garbage (`off=0x1`) and the type label is misaligned too.

The fix is to (a) pick the class first and walk ITS PropPointers array, and
(b) decode each record by its own variant layout.

LAYOUTS (measured, s129 dump; see boolscan.py / propscan.py headers)
  common      +0x00 NameUTF8  +0x08 RepNotify  +0x10 PropertyFlags(u64)
              +0x18 GenFlags(u32)  +0x1C ObjectFlags(u32)==0x45
              +0x20 SetterFunc  +0x28 GetterFunc  +0x30 u16 ArrayDim
  non-bool    +0x32 u16 Offset
  bool        +0x32 u16 ElementSize  +0x34 u32 SizeOfOuter
              +0x38 SetBitFunc -> `or/mov byte|dword [rcx+DISP], MASK` ; DISP is the offset

CALIBRATION (all [M], and it is a POSITIVE control in both directions)
  AActor::bAlwaysRelevant -> SetBitFunc 0x032F7100 `or byte ptr [rcx+0x68],8`
  AActor::bHidden         -> SetBitFunc 0x03368980 `or byte ptr [rcx+0x68],0x80`
  AActor::bEnablePooling  -> SetBitFunc 0x03368BF0 `mov byte ptr [rcx+0x2d3],1`
A run that does not reproduce all three is not to be trusted.

USAGE
  classprops_uht.py --seed <known-record-rva> [--dump s129] [--covers 0x6c]
  classprops_uht.py --seed-name bAlwaysRelevant --covers 0x6c
"""
import struct, argparse, sys
import propscan as P
import propowner
import capstone

md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
md.detail = True

BOOL_GEN = 0x0C          # empirical: boolscan.py selects Bool records with (gflags & 0x1F)==0x0C
GENMASK = 0x1F


def _setbit(img, rec):
    """bool record -> (disp, mask, kind, text) using its SetBitFunc."""
    va = struct.unpack_from('<Q', img.d, rec + 0x38)[0]
    r = img.rva(va)
    if r is None:
        return (None, None, 'badptr', '')
    blob = img.d[r:r + 24]
    if blob == b'\0' * 24:
        return (None, None, 'COVERAGE-BLOCKED', '')
    for ins in md.disasm(blob, r):
        if ins.mnemonic in ('or', 'mov', 'and') and ins.operands:
            o = ins.operands[0]
            if o.type == capstone.x86.X86_OP_MEM and o.mem.base == capstone.x86.X86_REG_RCX and o.mem.index == 0:
                imm = ins.operands[1].imm if ins.operands[1].type == capstone.x86.X86_OP_IMM else None
                return (o.mem.disp, imm, ins.mnemonic, '%s %s' % (ins.mnemonic, ins.op_str))
        break
    ins = next(md.disasm(blob, r), None)
    return (None, None, 'unrecognised', ('%s %s' % (ins.mnemonic, ins.op_str)) if ins else '?')


def decode(img, rec):
    d = img.d
    nameva = struct.unpack_from('<Q', d, rec)[0]
    nr = img.rva(nameva)
    name = '?'
    if nr is not None:
        e = d.find(b'\0', nr)
        name = d[nr:e].decode('latin1', 'replace')
    pflags = struct.unpack_from('<Q', d, rec + 0x10)[0]
    gflags = struct.unpack_from('<I', d, rec + 0x18)[0]
    oflags = struct.unpack_from('<I', d, rec + 0x1C)[0]
    dim = struct.unpack_from('<H', d, rec + 0x30)[0]
    t = gflags & GENMASK
    out = dict(rec=rec, name=name, pflags=pflags, gflags=gflags, oflags=oflags,
               dim=dim, gen=P.genstr(gflags), isbool=(t == BOOL_GEN))
    if t == BOOL_GEN:
        out['elemsize'] = struct.unpack_from('<H', d, rec + 0x32)[0]
        out['sizeofouter'] = struct.unpack_from('<I', d, rec + 0x34)[0]
        disp, mask, kind, text = _setbit(img, rec)
        out.update(off=disp, mask=mask, kind=kind, setbit=text, width=1)
    else:
        out.update(off=struct.unpack_from('<H', d, rec + 0x32)[0],
                   mask=None, kind='offset', setbit='', width=None)
    return out


def class_props(img, seed_rec):
    """seed record rva -> (FClassParams, array base, NumProperties, [decoded props])"""
    owns = propowner.owner(img, seed_rec)
    if not owns:
        return None
    o = owns[0]
    arr, n = o['arr'], o['nprops']
    props = []
    for k in range(n):
        va = struct.unpack_from('<Q', img.d, arr + k * 8)[0]
        r = img.rva(va)
        if r is None:
            props.append(dict(rec=None, name='<unresolvable slot %d>' % k, off=None, isbool=False))
            continue
        props.append(decode(img, r))
    return o, arr, n, props


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--dump', default='s129')
    ap.add_argument('--seed', type=lambda x: int(x, 0), default=None)
    ap.add_argument('--seed-name', default=None)
    ap.add_argument('--covers', type=lambda x: int(x, 0), default=None)
    ap.add_argument('--near', type=lambda x: int(x, 0), default=None)
    ap.add_argument('--all', action='store_true')
    a = ap.parse_args()
    img = P.Img(P.DUMPS[a.dump])

    seed = a.seed
    if seed is None:
        assert a.seed_name, 'need --seed or --seed-name'
        hits = P.scan(img, want_name=a.seed_name)
        assert len(hits) == 1, 'seed name %r matched %d records (need exactly 1)' % (a.seed_name, len(hits))
        seed = hits[0]['rva']
        print('seed %r -> record 0x%08X' % (a.seed_name, seed))

    r = class_props(img, seed)
    assert r, 'could not resolve owner of record 0x%X' % seed
    o, arr, n, props = r
    print('FClassParams 0x%08X  PropPointers 0x%08X  NumProperties=%d  ClassFlags=0x%08X'
          % (o['clsparams'], arr, n, o['classflags']))
    resolved = [p for p in props if p.get('off') is not None]
    print('decoded %d/%d records (%d bool, %d other)'
          % (len(resolved), n, sum(1 for p in resolved if p['isbool']),
             sum(1 for p in resolved if not p['isbool'])))

    # ---- POSITIVE CONTROLS: three known AActor offsets must reproduce ----
    ctl = {'bAlwaysRelevant': 0x68, 'bHidden': 0x68, 'bEnablePooling': 0x2D3}
    seen = {p['name']: p.get('off') for p in props}
    ok = 0
    for k, v in ctl.items():
        if k in seen:
            good = (seen[k] == v)
            ok += good
            print('  [CTRL] %-18s expected 0x%X  got %s  %s'
                  % (k, v, ('0x%X' % seen[k]) if seen[k] is not None else 'None',
                     'PASS' if good else '*** FAIL ***'))
    if ok == 0:
        print('  [CTRL] none of the three AActor controls is in this class -- controls NOT exercised')

    if a.covers is not None:
        t = a.covers
        print('\n--- records whose offset == 0x%X ---' % t)
        hit = [p for p in props if p.get('off') == t]
        for p in hit:
            print('  %-40s off=0x%-5X %-28s pflags=0x%016X %s'
                  % (p['name'], p['off'], p['gen'], p['pflags'], p.get('setbit', '')))
        if not hit:
            print('  NONE. 0x%X is not the declared offset of any reflected property of this class.' % t)
            near = sorted([p for p in props if p.get('off') is not None], key=lambda p: p['off'])
            below = [p for p in near if p['off'] <= t][-4:]
            above = [p for p in near if p['off'] > t][:4]
            print('  nearest below:')
            for p in below:
                print('    0x%-5X %-38s %s' % (p['off'], p['name'], p['gen']))
            print('  nearest above:')
            for p in above:
                print('    0x%-5X %-38s %s' % (p['off'], p['name'], p['gen']))

    if a.near is not None:
        lo, hi = a.near - 0x18, a.near + 0x18
        print('\n--- offsets in [0x%X, 0x%X] ---' % (lo, hi))
        for p in sorted([p for p in props if p.get('off') is not None], key=lambda p: p['off']):
            if lo <= p['off'] <= hi:
                print('  0x%-5X %-38s %-24s %s' % (p['off'], p['name'], p['gen'], p.get('setbit', '')))

    if a.all:
        print('\n--- all properties, by offset ---')
        for p in sorted([p for p in props if p.get('off') is not None], key=lambda p: p['off']):
            print('  0x%-5X %-42s %-26s %s' % (p['off'], p['name'], p['gen'], p.get('setbit', '')))
