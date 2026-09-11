#!/usr/bin/env python
"""mdctx.py -- READ-ONLY minidump context/memory reader for the SUPERVIVE crash corpus.

Extracts the exception record, the faulting thread's full CONTEXT_AMD64, the module
list, and a byte-addressable view of every memory range the dump carries
(MemoryList / Memory64List / thread stacks).  Opens 'rb' only; never writes into
the Crashes tree.

usage:  mdctx.py <dump.dmp> [--read=0xADDR[,LEN]] ...
"""
import struct, sys, os, bisect


class MD:
    # CONTEXT_AMD64 field offsets
    GPR = [('rax', 0x78), ('rcx', 0x80), ('rdx', 0x88), ('rbx', 0x90), ('rsp', 0x98),
           ('rbp', 0xA0), ('rsi', 0xA8), ('rdi', 0xB0), ('r8', 0xB8), ('r9', 0xC0),
           ('r10', 0xC8), ('r11', 0xD0), ('r12', 0xD8), ('r13', 0xE0), ('r14', 0xE8),
           ('r15', 0xF0), ('rip', 0xF8)]

    def __init__(self, path):
        with open(path, 'rb') as f:
            self.d = f.read()
        d = self.d
        assert d[:4] == b'MDMP', "not a minidump"
        ver, nstreams, dirrva = struct.unpack_from('<III', d, 4)
        self.streams = {}
        for i in range(nstreams):
            st, ds, rva = struct.unpack_from('<III', d, dirrva + i * 12)
            self.streams.setdefault(st, []).append((ds, rva))
        self._mods()
        self._mem()
        self._exc()
        self._threads()

    def _wstr(self, rva):
        if rva <= 0 or rva + 4 > len(self.d):
            return "?"
        ln = struct.unpack_from('<I', self.d, rva)[0]
        if ln <= 0 or ln > 4096:
            return "?"
        return self.d[rva + 4:rva + 4 + ln].decode('utf-16-le', 'replace')

    def _mods(self):
        self.mods = []
        if 4 not in self.streams:
            return
        _, rva = self.streams[4][0]
        n = struct.unpack_from('<I', self.d, rva)[0]
        for i in range(n):
            m = rva + 4 + i * 108
            b, sz = struct.unpack_from('<QI', self.d, m)
            nm = self._wstr(struct.unpack_from('<I', self.d, m + 20)[0])
            nm = nm.replace(chr(92), '/').split('/')[-1]
            self.mods.append((b, sz, nm))
        self.mods.sort()

    def modof(self, a):
        for b, sz, nm in self.mods:
            if b <= a < b + sz:
                return (nm, a - b)
        return None

    def _mem(self):
        rs = []
        if 5 in self.streams:
            for _, rva in self.streams[5]:
                n = struct.unpack_from('<I', self.d, rva)[0]
                for i in range(n):
                    md = rva + 4 + i * 16
                    sa = struct.unpack_from('<Q', self.d, md)[0]
                    sz, sr = struct.unpack_from('<II', self.d, md + 8)
                    rs.append((sa, sz, sr))
        if 9 in self.streams:
            for _, rva in self.streams[9]:
                nr, basrva = struct.unpack_from('<QQ', self.d, rva)
                cur = basrva
                for i in range(nr):
                    sa, sz = struct.unpack_from('<QQ', self.d, rva + 16 + i * 16)
                    rs.append((sa, sz, cur))
                    cur += sz
        # MINIDUMP_THREAD (48 B): Tid@0 Susp@4 PriCls@8 Pri@12 Teb@16
        #                         Stack{Start@24, DataSize@32, Rva@36}
        #                         ThreadContext{DataSize@40, Rva@44}
        # NB: tools/re/parse_minidump.py has these offsets wrong (uses 16/24/28),
        # which yields multi-GB bogus ranges. Corrected here.
        if 3 in self.streams:
            for _, rva in self.streams[3]:
                n = struct.unpack_from('<I', self.d, rva)[0]
                for i in range(n):
                    t = rva + 4 + i * 48
                    sa = struct.unpack_from('<Q', self.d, t + 24)[0]
                    sz, sr = struct.unpack_from('<II', self.d, t + 32)
                    if sz:
                        rs.append((sa, sz, sr))
        seen = set()
        self.ranges = []
        for r in sorted(rs):
            if r in seen:
                continue
            seen.add(r)
            self.ranges.append(r)
        self.starts = [r[0] for r in self.ranges]

    def read(self, addr, n):
        i = bisect.bisect_right(self.starts, addr) - 1
        while i >= 0:
            sa, sz, sr = self.ranges[i]
            if sa <= addr < sa + sz:
                avail = min(n, sa + sz - addr)
                return self.d[sr + (addr - sa): sr + (addr - sa) + avail]
            i -= 1
        return b''

    def q(self, addr):
        b = self.read(addr, 8)
        return struct.unpack('<Q', b)[0] if len(b) == 8 else None

    def _exc(self):
        self.exc = None
        if 6 not in self.streams:
            return
        _, rva = self.streams[6][0]
        tid = struct.unpack_from('<I', self.d, rva)[0]
        off = rva + 8
        code, flags, rec, addr = struct.unpack_from('<IIQQ', self.d, off)
        nparm = struct.unpack_from('<I', self.d, off + 24)[0]
        parms = [struct.unpack_from('<Q', self.d, off + 32 + j * 8)[0]
                 for j in range(min(nparm, 15))]
        cds, crva = struct.unpack_from('<II', self.d, rva + 160)
        self.exc = dict(tid=tid, code=code, addr=addr, parms=parms, ctx=crva, ctxsize=cds)

    def _threads(self):
        self.threads = []
        if 3 not in self.streams:
            return
        _, rva = self.streams[3][0]
        n = struct.unpack_from('<I', self.d, rva)[0]
        for i in range(n):
            t = rva + 4 + i * 48
            tid = struct.unpack_from('<I', self.d, t)[0]
            teb = struct.unpack_from('<Q', self.d, t + 16)[0]
            sa = struct.unpack_from('<Q', self.d, t + 24)[0]
            sz, sr = struct.unpack_from('<II', self.d, t + 32)
            cds, crva = struct.unpack_from('<II', self.d, t + 40)
            self.threads.append(dict(tid=tid, teb=teb, stack=(sa, sz, sr),
                                     ctx=crva, ctxsize=cds))

    def ctx(self, crva):
        out = {}
        for nm, o in self.GPR:
            out[nm] = struct.unpack_from('<Q', self.d, crva + o)[0]
        out['eflags'] = struct.unpack_from('<I', self.d, crva + 0x44)[0]
        for i in range(8):
            lo, hi = struct.unpack_from('<QQ', self.d, crva + 0x1A0 + i * 16)
            out['xmm%d' % i] = (lo, hi)
        return out


def hexdump(b, base=0):
    out = []
    for i in range(0, len(b), 16):
        row = b[i:i + 16]
        txt = ''.join(chr(x) if 32 <= x < 127 else '.' for x in row)
        out.append("  +0x%03X  %-47s  %s" % (base + i, row.hex(' '), txt))
    return chr(10).join(out)


def main():
    p = sys.argv[1]
    md = MD(p)
    game = [m for m in md.mods if m[2].lower().startswith('supervive')]
    gb = game[0][0] if game else 0
    print("dump: %s  (%d bytes)" % (os.path.basename(p), len(md.d)))
    print("streams present: %s" % sorted(md.streams))
    print("memory ranges: %d  total %.2f MB" % (len(md.ranges), sum(r[1] for r in md.ranges) / 1e6))
    print("SUPERVIVE base: 0x%X   modules: %d" % (gb, len(md.mods)))
    e = md.exc
    if e:
        print("")
        print("EXCEPTION code=0x%08X addr=0x%X parms=%s tid=%d"
              % (e['code'], e['addr'], [hex(x) for x in e['parms']], e['tid']))
        mo = md.modof(e['addr'])
        if mo:
            print("  fault PC = %s+0x%X" % mo)
        c = md.ctx(e['ctx'])
        for nm, _ in MD.GPR:
            v = c[nm]
            mo = md.modof(v)
            extra = ("  %s+0x%X" % mo) if mo else ""
            got = md.read(v, 32)
            mapped = ("  [in-dump %d B: %s]" % (len(got), got[:16].hex(' '))) if got else ""
            print("  %-4s = 0x%016X%s%s" % (nm, v, extra, mapped))
        import struct as _s
        f1 = _s.unpack('<f', _s.pack('<Q', c['xmm1'][0])[:4])[0]
        f6 = _s.unpack('<f', _s.pack('<Q', c['xmm6'][0])[:4])[0]
        print("  xmm1.f32 = %r   xmm6.f32 = %r" % (f1, f6))
    for a in sys.argv[2:]:
        if a.startswith('--read='):
            spec = a.split('=', 1)[1]
            addr, _, ln = spec.partition(',')
            addr = int(addr, 16)
            ln = int(ln, 0) if ln else 128
            b = md.read(addr, ln)
            print("")
            print("read 0x%X (%d of %d bytes present)" % (addr, len(b), ln))
            if b:
                print(hexdump(b))


if __name__ == '__main__':
    main()
