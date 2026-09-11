#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""
asdump_report.py -- derived reports over PrecompiledScript.Cache.

Emits into out/:
    const_pool.txt      section-D constant pool as (ptr, constant, owning type)
    gameplay_tags.txt   FGameplayTag constants  (entries typed "GameplayTags")
    typed_consts.txt    all typed constants grouped by owning type (FVector, EKeys, ...)
    module_index.txt    per-module ordered string skeleton (class / props / funcs /
                        param names / default-arg source text)
    cvars.txt           console-command / CVar strings

Read-only, stdlib only.
"""
import struct, os, re, collections, importlib.util

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location('asd', os.path.join(HERE, 'asdump_strings.py'))
asd = importlib.util.module_from_spec(spec); spec.loader.exec_module(asd)

OUT = os.path.join(HERE, 'out')
PTR_HI = asd.PTR_HI


def parse_const_pool(data, rows):
    """Section D entry = ptr64 , FString constantName [, FString owningType].
    Built off the validated string list: a string whose preceding 8 bytes are a
    live pointer starts an entry; an immediately-adjacent following string that
    is NOT itself pointer-prefixed is that entry's owning type."""
    def ptr_at(off):
        if off < 8:
            return None
        v = struct.unpack_from('<Q', data, off - 8)[0]
        return v if ((v >> 32) == PTR_HI and (v & 7) == 0) else None

    sd = [r for r in rows if asd.section(r[0]) == 'D_constpool']
    out = []
    i = 0
    while i < len(sd):
        off, s, f, tb = sd[i]
        v = ptr_at(off)
        if v is None:
            out.append((0, s, '', off))          # trailing plain-string run
            i += 1
            continue
        owner = ''
        if i + 1 < len(sd):
            noff, ns, nf, ntb = sd[i + 1]
            # __StaticType_* entries put the module name flush after the name;
            # typed value-constants (FGameplayTag / FVector / FColor / EKeys ...)
            # have a 4-byte field in between.
            if noff in (off + tb, off + tb + 4) and ptr_at(noff) is None:
                owner = ns
                i += 1
        out.append((v, s, owner, off))
        i += 1
    return out


def main():
    data = open(asd.CACHE, 'rb').read()
    rows = asd.scan_all(data)
    os.makedirs(OUT, exist_ok=True)

    # ---------------- constant pool -------------------------------------
    cp = parse_const_pool(data, rows)
    with open(os.path.join(OUT, 'const_pool.txt'), 'w', encoding='utf-8') as fh:
        fh.write('# section D constant pool: ptr -> (constant, owning type)\n')
        fh.write('# %d entries\n\n' % len(cp))
        for v, name, owner, off in cp:
            fh.write('0x%011x  0x%06x  %-60s %s\n' % (v, off, name, owner))
    print('const pool entries: %d' % len(cp))

    bytype = collections.defaultdict(list)
    for v, name, owner, off in cp:
        bytype[owner].append(name)
    with open(os.path.join(OUT, 'typed_consts.txt'), 'w', encoding='utf-8') as fh:
        for owner in sorted(bytype, key=lambda k: -len(bytype[k])):
            fh.write('== %s (%d) ==\n' % (owner or '<untyped / plain string or FName>',
                                          len(bytype[owner])))
            for nm in bytype[owner]:
                fh.write('    %s\n' % nm)
            fh.write('\n')
    print('constant owning-types:', {k or '<none>': len(v)
                                     for k, v in sorted(bytype.items(),
                                                        key=lambda kv: -len(kv[1]))[:8]})

    tags = bytype.get('GameplayTags', [])
    with open(os.path.join(OUT, 'gameplay_tags.txt'), 'w', encoding='utf-8') as fh:
        for t in tags:
            fh.write(t + '\n')
    print('gameplay tags: %d' % len(tags))

    # ---------------- cvars / console commands ---------------------------
    CV = re.compile(r'^(p\.|r\.|net\.|a\.|s\.|Log |ShowDebug|God|Server|Request|Debug|'
                    r'[A-Za-z]+\.[A-Za-z]+\.[A-Za-z]+)')
    cv = sorted(set(s for off, s, f, tb in rows
                    if asd.section(off) == 'D_constpool' and CV.match(s) and len(s) > 4))
    with open(os.path.join(OUT, 'cvars.txt'), 'w', encoding='utf-8') as fh:
        for s in cv:
            fh.write(s + '\n')
    print('cvar/console-command-like constants: %d' % len(cv))

    # ---------------- per-module skeleton --------------------------------
    aspaths = [(off, s, tb) for off, s, f, tb in rows if s.endswith('.as')]
    prev = asd.SEC_A
    modrows = []
    for off, s, tb in aspaths:
        modrows.append((prev, off + tb, s))
        prev = off + tb
    with open(os.path.join(OUT, 'module_index.txt'), 'w', encoding='utf-8') as fh:
        fh.write('# per-module ordered string skeleton.\n'
                 '# gap = bytes of binary (signature blocks + bytecode) between strings.\n\n')
        for a, b, name in modrows:
            fh.write('=== %s   [0x%06x..0x%06x, %d bytes] ===\n' % (name, a, b, b - a))
            pe = a
            for off, s, f, tb in rows:
                if a <= off < b:
                    fh.write('  0x%06x gap=%-6d %s\n' % (off, off - pe, s))
                    pe = off + tb
            fh.write('\n')
    print('modules indexed: %d' % len(modrows))
    print('module record sizes: min=%d max=%d total=%d'
          % (min(b - a for a, b, _ in modrows), max(b - a for a, b, _ in modrows),
             sum(b - a for a, b, _ in modrows)))


if __name__ == '__main__':
    main()
