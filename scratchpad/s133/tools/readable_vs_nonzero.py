#!/usr/bin/env python3
# LANE 3 (d) -- does a ZERO .text page in a dumpimage .dump.exe mean "never decrypted"?
#
# dumpimage records TWO different things:
#   * the .dump.exe itself: img := make([]byte, SizeOfImage) zero-filled, then only
#     RPM-readable ranges overwritten (dumpimage.go:126-201). A page that was read
#     and is legitimately all zeros is INDISTINGUISHABLE from a page never read.
#   * the .dump.txt manifest: per-section `readable` = the sum of bytes RPM actually
#     returned. That DOES distinguish -- but only in aggregate, never per page.
#
# This script compares, per dump: manifest .text readable bytes (-> pages, since the
# value is always a multiple of 0x1000 on this build) against the .dump.exe's non-zero
# .text page count. Any positive difference is the size of the blind spot.
#
# Usage: python readable_vs_nonzero.py <dumps-root>

import os, re, sys

TEXT_RVA = 0x1000
TEXT_SIZE = 0x7649000
PAGE = 0x1000
NP = TEXT_SIZE // PAGE


def nonzero_pages(path):
    with open(path, 'rb') as f:
        f.seek(TEXT_RVA)
        blob = f.read(TEXT_SIZE)
    return sum(1 for pg in range(NP) if any(blob[pg * PAGE:(pg + 1) * PAGE]))


def manifest_text_readable(path):
    with open(path, 'r', encoding='utf-8', errors='replace') as f:
        for line in f:
            if line.startswith('.text '):
                m = re.search(r'(\d+) \(', line)
                if m:
                    return int(m.group(1))
    return None


def main():
    root = sys.argv[1]
    print('%-48s %10s %8s %10s %8s %8s' %
          ('DUMP DIR', 'READ_BYTES', 'READ_PG', 'MULT4K', 'NONZERO', 'DELTA'))
    tot_delta = 0
    n = 0
    for d in sorted(os.listdir(root)):
        dd = os.path.join(root, d)
        if not os.path.isdir(dd):
            continue
        ex = os.path.join(dd, 'SUPERVIVE-Win64-Shipping.dump.exe')
        mf = os.path.join(dd, 'SUPERVIVE-Win64-Shipping.dump.txt')
        if not (os.path.exists(ex) and os.path.exists(mf)):
            continue
        rb = manifest_text_readable(mf)
        if rb is None:
            continue
        nz = nonzero_pages(ex)
        rp = rb // PAGE
        n += 1
        tot_delta += rp - nz
        print('%-48s %10d %8d %10s %8d %8d' %
              (d, rb, rp, 'yes' if rb % PAGE == 0 else 'NO', nz, rp - nz))
    print('')
    print('dumps compared: %d   total (readable_pages - nonzero_pages): %d' % (n, tot_delta))
    print('A positive DELTA = pages RPM read successfully whose content is all zeros')
    print('  => that many pages are "decrypted but blank" and a zero page in the')
    print('     .dump.exe is NOT by itself proof the page was never decrypted.')


if __name__ == '__main__':
    main()
