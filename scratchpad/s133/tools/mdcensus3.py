#!/usr/bin/env python3
# LANE 3 (a) supplement 2 -- aggregate over EVERY minidump: how many bytes of
# captured memory fall inside ANY loaded module, broken down by module.
# This is the discriminating positive control for the "0 bytes in the game
# image" result: it proves the in-module attribution path is exercised and
# produces non-zero answers for other modules in the same parse.
#
# Usage: python mdcensus3.py <root>

import os, struct, sys
from mdcensus import parse, read_at, ST_MEMORY_LIST


def ranges_of(p):
    out = []
    with open(p, 'rb') as f:
        hdr = read_at(f, 0, 32)
        if hdr[:4] != b'MDMP':
            return out
        sig, ver, nstreams, dirrva, csum, ts, flags = struct.unpack('<IIIIIIQ', hdr)
        d = read_at(f, dirrva, nstreams * 12)
        for i in range(nstreams):
            st, dsz, drva = struct.unpack_from('<III', d, i * 12)
            if st == ST_MEMORY_LIST:
                blob = read_at(f, drva, dsz)
                nr = struct.unpack_from('<I', blob, 0)[0]
                for k in range(nr):
                    start, sz, rva = struct.unpack_from('<QII', blob, 4 + k * 16)
                    out.append((start, sz))
    return out


def main():
    root = sys.argv[1]
    files = []
    for dp, dn, fn in os.walk(root):
        for n in fn:
            if n.lower().endswith('.dmp'):
                files.append(os.path.join(dp, n))
    files.sort()
    permod = {}
    permod_files = {}
    tot_inmod = 0
    tot_nomod = 0
    nfiles = 0
    files_with_inmod = 0
    files_with_game = 0
    for p in files:
        r = parse(p)
        if not r['ok']:
            continue
        nfiles += 1
        mods = r['modnames']
        rs = ranges_of(p)
        seen = set()
        f_inmod = 0
        for start, sz in rs:
            hit = None
            for base, ssize, name in mods:
                if start < base + ssize and start + sz > base:
                    hit = os.path.basename(name)
                    break
            if hit:
                permod[hit] = permod.get(hit, 0) + sz
                seen.add(hit)
                f_inmod += sz
                tot_inmod += sz
                if hit.lower() == 'supervive-win64-shipping.exe':
                    files_with_game += 1
            else:
                tot_nomod += sz
        if f_inmod:
            files_with_inmod += 1
        for h in seen:
            permod_files[h] = permod_files.get(h, 0) + 1
    print('=== bytes of captured minidump memory INSIDE a loaded module ===')
    print('files parsed                 : %d' % nfiles)
    print('files with >0 in-module bytes: %d' % files_with_inmod)
    print('ranges inside game image     : %d' % files_with_game)
    print('total in-module bytes        : %d' % tot_inmod)
    print('total NOT-in-any-module bytes: %d' % tot_nomod)
    print('%-40s %14s %8s' % ('MODULE', 'BYTES', 'FILES'))
    for name, b in sorted(permod.items(), key=lambda kv: -kv[1]):
        print('%-40s %14d %8d' % (name, b, permod_files.get(name, 0)))


if __name__ == '__main__':
    main()
