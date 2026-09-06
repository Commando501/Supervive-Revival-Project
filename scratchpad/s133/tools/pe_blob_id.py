#!/usr/bin/env python3
# LANE 3 (b) -- identify the MZ-headed blobs found in PRIVATE executable memory
# (SUPERVIVE-Win64-Shipping.exec_0x*.bin). These are manually-mapped PE images.
# Prints: machine, SizeOfImage, #sections + names, timestamp, entrypoint,
#         export-directory DLL name (if the export dir is inside the captured
#         extent), and the PDB path from the debug directory when present.
#
# POSITIVE CONTROL: the parser is run on a known-good PE too (pass --control <path>)
# so a null ("no section names recovered") is distinguishable from a parse failure.
#
# Usage: python pe_blob_id.py <execbin_bins.csv> [--control <pe>]

import os, sys, struct, csv, collections


def rd(b, off, n):
    return b[off:off + n]


def u16(b, o):
    return struct.unpack_from('<H', b, o)[0]


def u32(b, o):
    return struct.unpack_from('<I', b, o)[0]


def u64(b, o):
    return struct.unpack_from('<Q', b, o)[0]


def cstr(b, o, maxn=260):
    e = b.find(b'\x00', o, o + maxn)
    if e < 0:
        e = o + maxn
    return b[o:e].decode('latin1', 'replace')


def parse_pe(b):
    r = {'ok': False}
    if len(b) < 0x40 or b[:2] != b'MZ':
        r['err'] = 'no MZ'
        return r
    e_lfanew = u32(b, 0x3C)
    if e_lfanew + 0x108 > len(b) or rd(b, e_lfanew, 4) != b'PE\x00\x00':
        r['err'] = 'no PE at e_lfanew=0x%X' % e_lfanew
        return r
    fh = e_lfanew + 4
    r['machine'] = u16(b, fh)
    nsec = u16(b, fh + 2)
    r['timestamp'] = u32(b, fh + 4)
    szopt = u16(b, fh + 16)
    r['characteristics'] = u16(b, fh + 18)
    oh = fh + 20
    magic = u16(b, oh)
    r['magic'] = magic
    pe32p = (magic == 0x20B)
    r['entry'] = u32(b, oh + 16)
    r['imagebase'] = u64(b, oh + 24) if pe32p else u32(b, oh + 28)
    r['sizeofimage'] = u32(b, oh + 56)
    ddoff = oh + (112 if pe32p else 96)
    ndd = u32(b, oh + (108 if pe32p else 92))
    dirs = []
    for i in range(min(16, ndd)):
        dirs.append((u32(b, ddoff + i * 8), u32(b, ddoff + i * 8 + 4)))
    r['dirs'] = dirs
    secoff = oh + szopt
    secs = []
    for i in range(nsec):
        so = secoff + i * 40
        if so + 40 > len(b):
            break
        nm = rd(b, so, 8).rstrip(b'\x00').decode('latin1', 'replace')
        secs.append((nm, u32(b, so + 8), u32(b, so + 12), u32(b, so + 16), u32(b, so + 20), u32(b, so + 36)))
    r['sections'] = secs
    r['nsec'] = nsec
    # export dir name (memory-mapped layout: RVA == offset)
    r['dllname'] = ''
    r['nexports'] = 0
    if dirs and dirs[0][0] and dirs[0][0] + 40 <= len(b):
        ed = dirs[0][0]
        namerva = u32(b, ed + 12)
        r['nexports'] = u32(b, ed + 24)
        if 0 < namerva < len(b):
            r['dllname'] = cstr(b, namerva, 128)
    # debug dir -> PDB
    r['pdb'] = ''
    if len(dirs) > 6 and dirs[6][0] and dirs[6][0] + 28 <= len(b):
        dd = dirs[6][0]
        n = dirs[6][1] // 28
        for i in range(n):
            o = dd + i * 28
            if o + 28 > len(b):
                break
            typ = u32(b, o + 12)
            adr = u32(b, o + 20)
            if typ == 2 and 0 < adr + 24 < len(b) and rd(b, adr, 4) == b'RSDS':
                r['pdb'] = cstr(b, adr + 24, 260)
                break
    # import dir -> imported DLL names
    r['imports'] = []
    if len(dirs) > 1 and dirs[1][0]:
        idt = dirs[1][0]
        for i in range(64):
            o = idt + i * 20
            if o + 20 > len(b):
                break
            namerva = u32(b, o + 12)
            if namerva == 0 and u32(b, o) == 0:
                break
            if 0 < namerva < len(b):
                r['imports'].append(cstr(b, namerva, 64))
    r['ok'] = True
    return r


def show(path, b, tag=''):
    r = parse_pe(b)
    if not r['ok']:
        print('  %-70s PARSE FAIL: %s' % (os.path.basename(path), r.get('err')))
        return None
    secnames = ' '.join(s[0] for s in r['sections'])
    print('  %s%s' % (tag, path))
    print('     machine=0x%X magic=0x%X SizeOfImage=0x%X ImageBase=0x%X entry=0x%X ts=0x%X nsec=%d'
          % (r['machine'], r['magic'], r['sizeofimage'], r['imagebase'], r['entry'],
             r['timestamp'], r['nsec']))
    print('     sections: %s' % secnames)
    print('     exportDLL=%r nexports=%d pdb=%r imports=%s'
          % (r['dllname'], r['nexports'], r['pdb'], ','.join(r['imports'][:8])))
    return r


def main():
    csvpath = sys.argv[1]
    control = None
    if '--control' in sys.argv:
        control = sys.argv[sys.argv.index('--control') + 1]
    rows = list(csv.DictReader(open(csvpath)))
    mz = [r for r in rows if r['mz'] == '1']
    print('=== PE identification of MZ-headed private-exec blobs ===')
    print('MZ blobs: %d of %d exec .bin files' % (len(mz), len(rows)))
    if control:
        print('')
        print('POSITIVE CONTROL (known-good on-disk PE):')
        with open(control, 'rb') as f:
            cb = f.read(4 * 1024 * 1024)
        show(control, cb, tag='[CTRL] ')
    seen = {}
    for r in mz:
        if r['sha256'] in seen:
            seen[r['sha256']].append(r['path'])
            continue
        seen[r['sha256']] = [r['path']]
    print('')
    print('distinct MZ blob contents: %d' % len(seen))
    sig = collections.Counter()
    details = {}
    for sha, paths in seen.items():
        with open(paths[0], 'rb') as f:
            b = f.read()
        pr = parse_pe(b)
        if not pr['ok']:
            sig['PARSEFAIL:' + pr.get('err', '?')] += len(paths)
            continue
        key = (pr['sizeofimage'], tuple(s[0] for s in pr['sections']), pr['timestamp'],
               pr['dllname'], pr['pdb'])
        sig[key] += len(paths)
        details.setdefault(key, (paths[0], b))
    print('')
    print('distinct PE identities (SizeOfImage, sections, timestamp, exportname, pdb):')
    for key, n in sig.most_common():
        print('  n=%-4d %s' % (n, key))
        if key in details:
            p, b = details[key]
            print('        example: %s' % p)
    print('')
    print('detail for each distinct identity:')
    for key in sig:
        if key in details:
            p, b = details[key]
            show(p, b)


if __name__ == '__main__':
    main()
