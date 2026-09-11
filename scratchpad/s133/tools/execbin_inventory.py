#!/usr/bin/env python3
# LANE 3 (b)/(c) -- inventory every SUPERVIVE-Win64-Shipping.exec_0x*.bin on disk
# (the PRIVATE executable regions dumpimage captured outside the module image),
# plus the SKIPPED MEM_IMAGE executable regions recorded in each .dump.txt manifest.
#
# For each .bin:  size, sha256, MZ/PE test, entropy, first 16 bytes, x86-64
#                 decode sanity (via a tiny length-check heuristic + optional capstone)
# For each manifest: parse the "Executable region inventory" table and flag any
#                 MEM_IMAGE exec region that contains ZERO exports from the sibling
#                 <stem>.exports.txt -> candidate MANUALLY-MAPPED / HIDDEN module
#                 (S131: the protector runtime.dll is MEM_IMAGE with no module entry).
#
# Usage: python execbin_inventory.py <dumps-root> [--out prefix]

import os, sys, re, hashlib, math, collections, csv

try:
    import capstone
    HAVE_CS = True
except Exception:
    HAVE_CS = False


def entropy(b):
    if not b:
        return 0.0
    c = collections.Counter(b)
    n = len(b)
    return -sum((v / n) * math.log2(v / n) for v in c.values())


def cs_stats(buf, limit=4096):
    """Linear-sweep decode from offset 0; returns (n_insns, bytes_covered, invalid)."""
    if not HAVE_CS:
        return (None, None, None)
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
    n = 0
    cov = 0
    for i in md.disasm(buf[:limit], 0):
        n += 1
        cov += i.size
    return (n, cov, len(buf[:limit]) - cov)


def scan_bins(root):
    rows = []
    pat = re.compile(r'\.exec_0x([0-9A-Fa-f]+)_([0-9A-Fa-f]+)\.bin$')
    for dp, dn, fn in os.walk(root):
        for n in fn:
            m = pat.search(n)
            if not m:
                continue
            p = os.path.join(dp, n)
            va = int(m.group(1), 16)
            declsz = int(m.group(2), 16)
            with open(p, 'rb') as f:
                b = f.read()
            h = hashlib.sha256(b).hexdigest()
            nz = sum(1 for x in b if x)
            ins, cov, inv = cs_stats(b)
            rows.append(dict(path=p, dir=os.path.basename(dp), va=va, declsize=declsz,
                             filesize=len(b), sha=h, mz=(b[:2] == b'MZ'),
                             pe=(b'PE\x00\x00' in b[:0x400]),
                             allzero=(nz == 0), nonzero=nz, ent=entropy(b[:65536]),
                             head=b[:16].hex(), insns=ins, cov=cov, inv=inv))
    return rows


HDR = re.compile(r'^0x([0-9A-F]+)\s+0x([0-9A-F]+)\s+0x([0-9A-F]+)\s+(\S+)\s+(.*)$')


def parse_manifest(path):
    """returns (base, sizeofimage, [ (va,size,prot,type,dumped) ... ])"""
    base = 0
    soi = 0
    regs = []
    inrows = False
    with open(path, 'r', encoding='utf-8', errors='replace') as f:
        for line in f:
            line = line.rstrip('\n')
            if line.startswith('base      :'):
                base = int(line.split(':')[1].strip(), 16)
            elif line.startswith('SizeOfImage:'):
                soi = int(line.split(':')[1].split()[0], 16)
            elif line.startswith('VA ') and 'SIZE' in line:
                inrows = True
                continue
            elif inrows:
                m = HDR.match(line.strip())
                if m:
                    regs.append((int(m.group(1), 16), int(m.group(2), 16),
                                 int(m.group(3), 16), m.group(4), m.group(5).strip()))
                elif line.strip().startswith('('):
                    inrows = False
    return base, soi, regs


def load_exports(path):
    addrs = []
    if not os.path.exists(path):
        return addrs
    with open(path, 'r', encoding='utf-8', errors='replace') as f:
        for line in f:
            parts = line.split('\t')
            if len(parts) >= 2:
                try:
                    addrs.append(int(parts[0], 16))
                except ValueError:
                    pass
    addrs.sort()
    return addrs


def main():
    root = sys.argv[1]
    prefix = 'execbin'
    if '--out' in sys.argv:
        prefix = sys.argv[sys.argv.index('--out') + 1]

    print('capstone available: %s' % HAVE_CS)
    rows = scan_bins(root)
    print('')
    print('=== (b) PRIVATE EXEC REGION .bin FILES ===')
    print('files: %d   total bytes: %d' % (len(rows), sum(r['filesize'] for r in rows)))
    bysha = collections.defaultdict(list)
    for r in rows:
        bysha[r['sha']].append(r)
    print('distinct contents (sha256): %d' % len(bysha))
    print('MZ-headed: %d   contains PE sig in first 0x400: %d   all-zero: %d'
          % (sum(1 for r in rows if r['mz']), sum(1 for r in rows if r['pe']),
             sum(1 for r in rows if r['allzero'])))
    print('')
    print('%-66s %6s %8s %6s %5s %6s %s' % ('SHA256[:16] (n copies)', 'SIZE', 'NONZERO', 'ENT', 'MZ', 'INSNS', 'HEAD16'))
    for sha, lst in sorted(bysha.items(), key=lambda kv: -kv[1][0]['filesize']):
        r = lst[0]
        print('%-16s x%-3d %-44s %6d %8d %6.2f %5s %6s %s'
              % (sha[:16], len(lst), '', r['filesize'], r['nonzero'], r['ent'],
                 r['mz'], r['insns'], r['head']))
    with open(prefix + '_bins.csv', 'w', newline='') as fh:
        w = csv.writer(fh)
        w.writerow(['path', 'dir', 'va', 'declsize', 'filesize', 'sha256', 'mz', 'pe',
                    'allzero', 'nonzero', 'entropy', 'head16', 'insns', 'cov', 'invalid'])
        for r in rows:
            w.writerow([r['path'], r['dir'], hex(r['va']), hex(r['declsize']), r['filesize'],
                        r['sha'], int(r['mz']), int(r['pe']), int(r['allzero']), r['nonzero'],
                        '%.4f' % r['ent'], r['head'], r['insns'], r['cov'], r['inv']])
    print('csv -> %s_bins.csv' % prefix)

    # ---- (b2) skipped MEM_IMAGE exec regions ----
    print('')
    print('=== (b2) SKIPPED MEM_IMAGE EXEC REGIONS (never dumped by dumpimage) ===')
    mrows = []
    for dp, dn, fn in os.walk(root):
        for n in fn:
            if not n.endswith('.dump.txt'):
                continue
            p = os.path.join(dp, n)
            base, soi, regs = parse_manifest(p)
            exp = load_exports(p.replace('.dump.txt', '.exports.txt'))
            himg = 0
            himgbytes = 0
            hidden = []
            for va, sz, prot, typ, dumped in regs:
                if typ != 'Image':
                    continue
                himg += 1
                himgbytes += sz
                lo = 0
                hi = len(exp)
                # any export inside [va, va+sz)?
                import bisect
                i = bisect.bisect_left(exp, va)
                has = (i < len(exp) and exp[i] < va + sz)
                if not has:
                    hidden.append((va, sz, prot))
            mrows.append((p, base, len(regs), himg, himgbytes, hidden, len(exp)))
    tot_hidden = sum(len(m[5]) for m in mrows)
    print('manifests parsed: %d' % len(mrows))
    print('total MEM_IMAGE exec regions listed: %d (%d bytes)'
          % (sum(m[3] for m in mrows), sum(m[4] for m in mrows)))
    print('MEM_IMAGE exec regions containing ZERO known exports: %d' % tot_hidden)
    for p, base, nreg, himg, himgb, hidden, nexp in mrows:
        if not hidden:
            continue
        print('  %s  (exports=%d, image-exec-regions=%d)' % (p, nexp, himg))
        for va, sz, prot in sorted(hidden, key=lambda t: -t[1])[:25]:
            print('     va=0x%-14X size=0x%-9X prot=0x%X' % (va, sz, prot))
    with open(prefix + '_imageregions.csv', 'w', newline='') as fh:
        w = csv.writer(fh)
        w.writerow(['manifest', 'game_base', 'n_exec_rows', 'n_image_exec', 'image_exec_bytes',
                    'n_exports', 'hidden_va', 'hidden_size', 'hidden_prot'])
        for p, base, nreg, himg, himgb, hidden, nexp in mrows:
            if hidden:
                for va, sz, prot in hidden:
                    w.writerow([p, hex(base), nreg, himg, himgb, nexp, hex(va), hex(sz), hex(prot)])
            else:
                w.writerow([p, hex(base), nreg, himg, himgb, nexp, '', '', ''])
    print('csv -> %s_imageregions.csv' % prefix)


if __name__ == '__main__':
    main()
