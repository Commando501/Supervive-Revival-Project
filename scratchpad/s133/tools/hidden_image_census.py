#!/usr/bin/env python3
# LANE 3 (c) -- mine the MemoryInfoListStream (stream 16) of every crashpad minidump.
# That stream is the FULL VirtualQueryEx region map at death (~44k entries, ~2.1 MB).
# Nobody has ever parsed it in this project.
#
# GOAL: find MEM_IMAGE allocations whose AllocationBase is NOT in the dump's
# ModuleList => MANUALLY MAPPED, HIDDEN images. S131 measured the protector's
# runtime.dll as exactly that (MEM_COMMIT/READONLY/MEM_IMAGE, AllocationBase ==
# the FK-31 kill address & ~0xFFF, absent from (Get-Process).Modules).
#
# POSITIVE CONTROLS:
#   P1 every dump must report MANY MEM_IMAGE allocations that ARE in the ModuleList
#      (if not, the AllocationBase<->module join is broken, not the data).
#   P2 the game module itself must be found as a MEM_IMAGE allocation.
#   P3 report per-dump counts so a zero is separable from a parse failure.
#
# Usage: python hidden_image_census.py <root> [--csv out.csv] [--detail N]

import os, struct, sys, csv, collections
from mdcensus import parse, read_at

ST_MEMORY_INFO_LIST = 16
MEM_IMAGE = 0x1000000
MEM_MAPPED = 0x40000
MEM_PRIVATE = 0x20000
MEM_COMMIT = 0x1000

PROTNAME = {0x01: 'NOACCESS', 0x02: 'READONLY', 0x04: 'READWRITE', 0x08: 'WRITECOPY',
            0x10: 'EXECUTE', 0x20: 'EXECUTE_READ', 0x40: 'EXECUTE_READWRITE',
            0x80: 'EXECUTE_WRITECOPY'}


def meminfo(path):
    out = []
    with open(path, 'rb') as f:
        hdr = read_at(f, 0, 32)
        if hdr[:4] != b'MDMP':
            return out
        sig, ver, nstreams, dirrva, csum, ts, flags = struct.unpack('<IIIIIIQ', hdr)
        d = read_at(f, dirrva, nstreams * 12)
        for i in range(nstreams):
            st, dsz, drva = struct.unpack_from('<III', d, i * 12)
            if st != ST_MEMORY_INFO_LIST:
                continue
            h = read_at(f, drva, 16)
            szhdr, szent, nent = struct.unpack('<IIQ', h)
            body = read_at(f, drva + szhdr, int(nent) * szent)
            for k in range(int(nent)):
                o = k * szent
                if o + 48 > len(body):
                    break
                (baseaddr, allocbase, allocprot, _a1, regsize, state,
                 prot, typ, _a2) = struct.unpack_from('<QQIIQIIII', body, o)
                out.append((baseaddr, allocbase, allocprot, regsize, state, prot, typ))
    return out


def main():
    root = sys.argv[1]
    outcsv = None
    if '--csv' in sys.argv:
        outcsv = sys.argv[sys.argv.index('--csv') + 1]
    detail = 0
    if '--detail' in sys.argv:
        detail = int(sys.argv[sys.argv.index('--detail') + 1])

    files = []
    for dp, dn, fn in os.walk(root):
        for n in fn:
            if n.lower().endswith('.dmp'):
                files.append(os.path.join(dp, n))
    files.sort()
    rows = []
    nP1 = nP2 = 0
    hidden_bases = collections.Counter()
    hidden_size = {}
    nparsed = 0
    for p in files:
        r = parse(p)
        if not r['ok']:
            continue
        mi = meminfo(p)
        if not mi:
            continue
        nparsed += 1
        modbases = set(b for b, s, n in r['modnames'])
        # group MEM_IMAGE regions by AllocationBase
        img = collections.defaultdict(int)
        imgprot = collections.defaultdict(set)
        for baseaddr, allocbase, allocprot, regsize, state, prot, typ in mi:
            if typ == MEM_IMAGE:
                img[allocbase] += regsize
                imgprot[allocbase].add(prot)
        known = [b for b in img if b in modbases]
        unknown = [b for b in img if b not in modbases]
        if len(known) > 0:
            nP1 += 1
        if r['game_base'] in img:
            nP2 += 1
        for b in unknown:
            hidden_bases[b] += 1
            hidden_size[b] = max(hidden_size.get(b, 0), img[b])
        rows.append(dict(path=p, nmi=len(mi), n_img_alloc=len(img),
                         n_known=len(known), n_unknown=len(unknown),
                         unknown=sorted(unknown, key=lambda b: -img[b]),
                         sizes={b: img[b] for b in unknown},
                         prots={b: imgprot[b] for b in unknown},
                         gamebase=r['game_base'], nmod=r['nmodules']))
    print('=== MemoryInfoList census: HIDDEN (manually mapped) MEM_IMAGE allocations ===')
    print('dumps with a MemoryInfoList : %d' % nparsed)
    print('P1 dumps where >0 MEM_IMAGE allocs join to the ModuleList : %d/%d' % (nP1, nparsed))
    print('P2 dumps where the GAME module is a MEM_IMAGE alloc       : %d/%d' % (nP2, nparsed))
    tot_unknown = sum(r['n_unknown'] for r in rows)
    print('total MEM_IMAGE allocations not in the ModuleList : %d (across all dumps)' % tot_unknown)
    print('distinct such AllocationBases : %d' % len(hidden_bases))
    print('')
    print('%-18s %6s %14s' % ('ALLOCBASE', 'DUMPS', 'MAX BYTES'))
    for b, n in hidden_bases.most_common(40):
        print('0x%-16X %6d %14d' % (b, n, hidden_size[b]))
    if detail:
        print('')
        print('per-dump detail (first %d):' % detail)
        for r in rows[:detail]:
            print('  %s  meminfo=%d imgAllocs=%d known=%d unknown=%d modules=%d'
                  % (r['path'], r['nmi'], r['n_img_alloc'], r['n_known'], r['n_unknown'], r['nmod']))
            for b in r['unknown'][:10]:
                pr = ','.join(PROTNAME.get(x, hex(x)) for x in sorted(r['prots'][b]))
                print('      0x%-14X %10d bytes  prot={%s}' % (b, r['sizes'][b], pr))
    if outcsv:
        with open(outcsv, 'w', newline='') as fh:
            w = csv.writer(fh)
            w.writerow(['path', 'n_meminfo', 'n_image_allocs', 'n_known', 'n_unknown',
                        'game_base', 'n_modules', 'unknown_base', 'unknown_bytes', 'unknown_prots'])
            for r in rows:
                if r['unknown']:
                    for b in r['unknown']:
                        pr = ','.join(PROTNAME.get(x, hex(x)) for x in sorted(r['prots'][b]))
                        w.writerow([r['path'], r['nmi'], r['n_img_alloc'], r['n_known'],
                                    r['n_unknown'], hex(r['gamebase']), r['nmod'],
                                    hex(b), r['sizes'][b], pr])
                else:
                    w.writerow([r['path'], r['nmi'], r['n_img_alloc'], r['n_known'],
                                r['n_unknown'], hex(r['gamebase']), r['nmod'], '', '', ''])
        print('')
        print('csv -> ' + outcsv)


if __name__ == '__main__':
    main()
