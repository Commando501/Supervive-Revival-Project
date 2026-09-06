#!/usr/bin/env python3
# LANE 3 (a) -- census every crashpad/Sentry minidump on disk for bytes captured
# INSIDE the SUPERVIVE-Win64-Shipping.exe image.
#
# Parses, per file:
#   stream 4  ModuleListStream   -> module base/size/name  (find the game image)
#   stream 3  ThreadListStream   -> thread stack ranges    (POSITIVE CONTROL)
#   stream 5  MemoryListStream   -> captured 32-bit ranges
#   stream 9  Memory64ListStream -> captured 64-bit ranges (if present)
#   stream 16 MemoryInfoListStream (presence + entry count only)
#
# POSITIVE CONTROLS (a null must be a fact about the dump, not about the parser):
#   C1  parser must find a non-empty ModuleList AND the game module by name.
#   C2  parser must attribute captured bytes to thread stacks (known-present class).
#   C3  file_size - sum(captured range sizes) = residual overhead (reported).
#   C4  every range's file RVA+size must lie inside the file.
#
# Usage: python mdcensus.py <root> [--csv out.csv] [--top N]

import os, struct, sys, csv

MDMP = b'MDMP'
ST_THREAD_LIST = 3
ST_MODULE_LIST = 4
ST_MEMORY_LIST = 5
ST_MEMORY64_LIST = 9
ST_MEMORY_INFO_LIST = 16


def read_at(f, off, n):
    f.seek(off)
    return f.read(n)


def read_mdstring(f, rva):
    b = read_at(f, rva, 4)
    if len(b) < 4:
        return ''
    ln = struct.unpack('<I', b)[0]
    if ln > 4096:
        ln = 4096
    raw = read_at(f, rva + 4, ln)
    return raw.decode('utf-16-le', 'replace')


def parse(path):
    r = {'path': path, 'size': os.path.getsize(path), 'ok': False, 'err': ''}
    with open(path, 'rb') as f:
        hdr = read_at(f, 0, 32)
        if len(hdr) < 32 or hdr[:4] != MDMP:
            r['err'] = 'not a minidump sig=' + repr(hdr[:4])
            return r
        sig, ver, nstreams, dirrva, csum, ts, flags = struct.unpack('<IIIIIIQ', hdr)
        r['flags'] = flags
        r['nstreams'] = nstreams
        dirs = {}
        d = read_at(f, dirrva, nstreams * 12)
        for i in range(nstreams):
            st, dsz, drva = struct.unpack_from('<III', d, i * 12)
            dirs.setdefault(st, []).append((dsz, drva))
        r['streams'] = sorted(dirs.keys())

        # ---- ModuleList ----
        mods = []
        game = None
        for dsz, drva in dirs.get(ST_MODULE_LIST, []):
            blob = read_at(f, drva, dsz)
            if len(blob) < 4:
                continue
            nmod = struct.unpack_from('<I', blob, 0)[0]
            off = 4
            for i in range(nmod):
                if off + 108 > len(blob):
                    break
                base, ssize, chk, mts, nrva = struct.unpack_from('<QIIII', blob, off)
                name = read_mdstring(f, nrva)
                mods.append((base, ssize, name))
                off += 108
        r['nmodules'] = len(mods)
        for base, ssize, name in mods:
            if name.lower().endswith('supervive-win64-shipping.exe'):
                game = (base, ssize, name)
                break
        r['game_base'] = game[0] if game else 0
        r['game_size'] = game[1] if game else 0
        r['modnames'] = mods

        # ---- ThreadList (POSITIVE CONTROL C2) ----
        stacks = []
        for dsz, drva in dirs.get(ST_THREAD_LIST, []):
            blob = read_at(f, drva, dsz)
            if len(blob) < 4:
                continue
            nth = struct.unpack_from('<I', blob, 0)[0]
            off = 4
            for i in range(nth):
                if off + 48 > len(blob):
                    break
                tid, susp, pcl, pri, teb, sbase, ssz, srva, ctxsz, ctxrva = \
                    struct.unpack_from('<IIIIQQIIII', blob, off)
                stacks.append((sbase, ssz))
                off += 48
        r['nthreads'] = len(stacks)
        stackset = set(stacks)

        # ---- MemoryList / Memory64List ----
        ranges = []
        for dsz, drva in dirs.get(ST_MEMORY_LIST, []):
            blob = read_at(f, drva, dsz)
            if len(blob) < 4:
                continue
            nr = struct.unpack_from('<I', blob, 0)[0]
            off = 4
            for i in range(nr):
                if off + 16 > len(blob):
                    break
                start, sz, rva = struct.unpack_from('<QII', blob, off)
                ranges.append((start, sz, rva))
                off += 16
        r['n_mem'] = len(ranges)
        n64 = 0
        for dsz, drva in dirs.get(ST_MEMORY64_LIST, []):
            blob = read_at(f, drva, 16)
            if len(blob) < 16:
                continue
            nr, baserva = struct.unpack('<QQ', blob)
            body = read_at(f, drva + 16, dsz - 16)
            cur = baserva
            off = 0
            for i in range(nr):
                if off + 16 > len(body):
                    break
                start, sz = struct.unpack_from('<QQ', body, off)
                ranges.append((start, sz, cur))
                cur += sz
                off += 16
                n64 += 1
        r['n_mem64'] = n64
        r['n_ranges'] = len(ranges)

        # ---- MemoryInfoList (presence only) ----
        r['n_meminfo'] = 0
        r['meminfo_bytes'] = 0
        for dsz, drva in dirs.get(ST_MEMORY_INFO_LIST, []):
            blob = read_at(f, drva, 16)
            if len(blob) < 16:
                continue
            szhdr, szent, nent = struct.unpack('<IIQ', blob)
            r['n_meminfo'] += nent
            r['meminfo_bytes'] += dsz

        # ---- attribution ----
        total = sum(sz for _, sz, _ in ranges)
        gb, gs = r['game_base'], r['game_size']
        in_img = 0
        in_img_ranges = 0
        img_detail = []
        in_stack = 0
        maxend = 0
        for start, sz, rva in ranges:
            maxend = max(maxend, rva + sz)
            if gs and start < gb + gs and start + sz > gb:
                lo = max(start, gb)
                hi = min(start + sz, gb + gs)
                in_img += hi - lo
                in_img_ranges += 1
                img_detail.append((start, sz, rva, lo - gb, hi - gb))
            if (start, sz) in stackset:
                in_stack += sz
        r['bytes_captured'] = total
        r['bytes_in_image'] = in_img
        r['ranges_in_image'] = in_img_ranges
        r['img_detail'] = img_detail
        r['bytes_in_stacks'] = in_stack
        r['max_range_end_rva'] = maxend
        r['residual'] = r['size'] - total
        r['C1_modules_ok'] = (len(mods) > 0 and gs != 0)
        r['C2_stacks_attributed'] = (in_stack > 0)
        r['C4_ranges_in_file'] = (maxend <= r['size'])
        r['ok'] = True
    return r


def main():
    root = sys.argv[1]
    outcsv = None
    if '--csv' in sys.argv:
        outcsv = sys.argv[sys.argv.index('--csv') + 1]
    files = []
    for dp, dn, fn in os.walk(root):
        for n in fn:
            if n.lower().endswith('.dmp'):
                files.append(os.path.join(dp, n))
    files.sort()
    rows = []
    tot_size = tot_cap = tot_img = tot_stk = 0
    nc1 = nc2 = nc4 = 0
    hits = []
    nmeminfo_present = 0
    n64present = 0
    for p in files:
        try:
            r = parse(p)
        except Exception as e:
            print('ERR ' + p + ': ' + str(e))
            continue
        if not r['ok']:
            print('SKIP ' + p + ': ' + r['err'])
            continue
        rows.append(r)
        tot_size += r['size']
        tot_cap += r['bytes_captured']
        tot_img += r['bytes_in_image']
        tot_stk += r['bytes_in_stacks']
        nc1 += 1 if r['C1_modules_ok'] else 0
        nc2 += 1 if r['C2_stacks_attributed'] else 0
        nc4 += 1 if r['C4_ranges_in_file'] else 0
        if r['n_meminfo'] > 0:
            nmeminfo_present += 1
        if r['n_mem64'] > 0:
            n64present += 1
        if r['bytes_in_image'] > 0:
            hits.append(r)
    print('=== LANE 3 (a) MINIDUMP IMAGE-BYTE CENSUS ===')
    print('files parsed               : %d' % len(rows))
    print('total file bytes           : %d (%.3f GiB)' % (tot_size, tot_size / 2 ** 30))
    print('total CAPTURED memory bytes: %d (%.3f GiB)' % (tot_cap, tot_cap / 2 ** 30))
    print('  of which THREAD STACKS   : %d (%.3f GiB)  <- POSITIVE CONTROL C2' % (tot_stk, tot_stk / 2 ** 30))
    print('  of which INSIDE GAME IMG : %d bytes' % tot_img)
    print('files with Memory64List    : %d' % n64present)
    print('files with MemoryInfoList  : %d' % nmeminfo_present)
    print('CONTROLS: C1 game module found %d/%d | C2 stack bytes attributed %d/%d | C4 range RVAs inside file %d/%d'
          % (nc1, len(rows), nc2, len(rows), nc4, len(rows)))
    print('')
    print('files WITH image bytes     : %d' % len(hits))
    for r in hits[:80]:
        print('  HIT %s  in_image=%d ranges=%d' % (r['path'], r['bytes_in_image'], r['ranges_in_image']))
        for st, sz, rva, r0, r1 in r['img_detail'][:40]:
            print('      va=0x%X size=0x%X filerva=0x%X  imgRVA 0x%X..0x%X' % (st, sz, rva, r0, r1))
    if outcsv:
        with open(outcsv, 'w', newline='') as fh:
            w = csv.writer(fh)
            w.writerow(['path', 'file_size', 'streams', 'nmodules', 'game_base', 'game_size',
                        'nthreads', 'n_mem', 'n_mem64', 'n_ranges', 'bytes_captured',
                        'bytes_in_stacks', 'bytes_in_image', 'ranges_in_image',
                        'n_meminfo', 'meminfo_bytes', 'residual', 'max_range_end_rva',
                        'C1', 'C2', 'C4'])
            for r in rows:
                w.writerow([r['path'], r['size'], ' '.join(map(str, r['streams'])), r['nmodules'],
                            hex(r['game_base']), hex(r['game_size']), r['nthreads'],
                            r['n_mem'], r['n_mem64'], r['n_ranges'], r['bytes_captured'],
                            r['bytes_in_stacks'], r['bytes_in_image'], r['ranges_in_image'],
                            r['n_meminfo'], r['meminfo_bytes'], r['residual'],
                            r['max_range_end_rva'], int(r['C1_modules_ok']),
                            int(r['C2_stacks_attributed']), int(r['C4_ranges_in_file'])])
        print('')
        print('csv -> ' + outcsv)


if __name__ == '__main__':
    main()
