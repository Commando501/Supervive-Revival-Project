# verify_dll.py -- artifact verification for injected shims (S106c, 2026-07-27).
#
# The build must satisfy three HARD rules from CLAUDE.md before a DLL is allowed near the game:
#   1. NO C++ exception machinery. The packer's vectored handler kills the process on any C++
#      throw/unwind. Three canary variants were tested historically; all died.
#   2. The import set must stay tiny and CRT-free -- these shims run inside a packed, anti-tampered
#      process and must not drag in a C runtime that expects its own initialisation.
#   3. Entry/export shape must match the other working shims (a bare DllMain, no exported functions
#      required by the manual mapper in tools/inject).
#
# Pure stdlib PE parsing, read-only. Usage:
#   python verify_dll.py <dll> [<dll> ...]
#   python verify_dll.py --diff <a.dll> <b.dll>     # which marker strings differ (A/B sanity)
import struct, sys, os

def rva2off(secs, rva):
    for name, va, vsz, raw, rsz in secs:
        if va <= rva < va + max(vsz, rsz):
            return raw + (rva - va)
    return None

def parse(path):
    d = open(path, 'rb').read()          # read-only, always binary
    pe = struct.unpack_from('<I', d, 0x3C)[0]
    assert d[pe:pe+4] == b'PE\0\0', 'not a PE'
    nsec, = struct.unpack_from('<H', d, pe+6)
    optsz, = struct.unpack_from('<H', d, pe+20)
    chars, = struct.unpack_from('<H', d, pe+22)
    magic, = struct.unpack_from('<H', d, pe+24)
    plus = (magic == 0x20b)
    ep,  = struct.unpack_from('<I', d, pe+40)
    ddoff = pe + 24 + (112 if plus else 96)
    imp_rva, imp_sz = struct.unpack_from('<II', d, ddoff + 8)
    exp_rva, exp_sz = struct.unpack_from('<II', d, ddoff + 0)
    so = pe + 24 + optsz
    secs = []
    for i in range(nsec):
        b = so + i*40
        nm = d[b:b+8].rstrip(b'\0').decode('latin1')
        vsz, va, rsz, raw = struct.unpack_from('<IIII', d, b+8)
        secs.append((nm, va, vsz, raw, rsz))

    imports = {}
    if imp_rva:
        o = rva2off(secs, imp_rva)
        while True:
            oft, tds, fwd, nrva, fta = struct.unpack_from('<IIIII', d, o)
            if nrva == 0:
                break
            no = rva2off(secs, nrva)
            dll = d[no:d.index(b'\0', no)].decode('latin1')
            fns, t = [], rva2off(secs, oft or fta)
            while True:
                v, = struct.unpack_from('<Q' if plus else '<I', d, t)
                if v == 0:
                    break
                if not (v >> (63 if plus else 31)):          # not import-by-ordinal
                    ho = rva2off(secs, v & 0x7FFFFFFF)
                    fns.append(d[ho+2:d.index(b'\0', ho+2)].decode('latin1'))
                else:
                    fns.append('#%d' % (v & 0xFFFF))
                t += 8 if plus else 4
            imports[dll] = fns
            o += 20

    nexp = 0
    if exp_rva:
        eo = rva2off(secs, exp_rva)
        nexp, = struct.unpack_from('<I', d, eo+24)
    return dict(data=d, secs=secs, ep=ep, dll=bool(chars & 0x2000),
                imports=imports, nexp=nexp, size=len(d))

BAD = ['__CxxFrameHandler3', '__CxxFrameHandler4', '_CxxThrowException',
       '__std_terminate', '_Unwind_Resume']
CRT = ['msvcr', 'vcruntime', 'ucrtbase', 'api-ms-win-crt']

def check(path):
    p = parse(path)
    print('=== %s  (%d bytes) ===' % (os.path.basename(path), p['size']))
    print('  IMAGE_FILE_DLL      : %s' % p['dll'])
    print('  AddressOfEntryPoint : 0x%X  (DllMain thunk)' % p['ep'])
    print('  exported functions  : %d' % p['nexp'])
    for dll, fns in sorted(p['imports'].items()):
        print('  imports %-16s %d: %s' % (dll, len(fns),
              ', '.join(fns[:8]) + (' ...' if len(fns) > 8 else '')))
    blob = p['data']
    hits = [s for s in BAD if s.encode() in blob]
    crt  = [m for m in CRT if any(m in d.lower() for d in p['imports'])]
    ok = True
    if hits:
        print('  ** FAIL: C++ exception machinery present: %s' % ', '.join(hits)); ok = False
    else:
        print('  OK: no C++ exception machinery (checked %s)' % ', '.join(BAD))
    if crt:
        print('  ** FAIL: links a C runtime: %s' % ', '.join(crt)); ok = False
    else:
        print('  OK: no CRT import')
    if not p['dll']:
        print('  ** FAIL: not marked as a DLL'); ok = False
    print('  VERDICT: %s' % ('PASS' if ok else 'FAIL'))
    return ok

def markers(path, tag):
    d = open(path, 'rb').read()
    n, i = 0, 0
    t = tag.encode()
    while True:
        i = d.find(t, i)
        if i < 0:
            break
        n += 1; i += 1
    return n

if __name__ == '__main__':
    args = sys.argv[1:]
    if args and args[0] == '--diff':
        a, b = args[1], args[2]
        # S106d: '[XF]' is present in BOTH KXFORMFIX arms (the line prints the flag's value at
        # runtime), so it is NOT a discriminator for that pair -- see BUILD.md's artifact matrix for
        # the two proofs that arm is distinct. 'test-body-actor' IS the KTESTACTOR discriminator.
        for tag in ('[VTG]', '[GC]', '[GCW]', '[PIM]', '[XF]', 'test-body-actor'):
            print('%-7s %-42s %3d   %-42s %3d' % (
                tag, os.path.basename(a), markers(a, tag), os.path.basename(b), markers(b, tag)))
        sys.exit(0)
    allok = True
    for f in args:
        allok &= check(f)
        print()
    sys.exit(0 if allok else 1)
