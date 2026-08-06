#!/usr/bin/env python
"""mdexc.py -- READ-ONLY lean minidump exception extractor.

Reads ONLY the header, the stream directory, ModuleListStream(4),
ThreadListStream(3), ExceptionStream(6) and ThreadNamesStream(24).
Never reads memory ranges, so it is fast enough to sweep 100+ 43.8 MB dumps.
Opens 'rb' only.  Stdlib only.
"""
import struct, os, sys

MDMP = b'MDMP'


class Lean:
    def __init__(self, path):
        self.path = path
        self.ok = False
        self.err = ""
        self.f = open(path, 'rb')
        try:
            self._load()
            self.ok = True
        except Exception as e:                       # noqa: BLE001
            self.err = "%s: %s" % (type(e).__name__, e)
        finally:
            self.f.close()

    # --- raw helpers -----------------------------------------------------
    def _at(self, off, n):
        self.f.seek(off)
        b = self.f.read(n)
        if len(b) != n:
            raise EOFError("short read at 0x%X (%d of %d)" % (off, len(b), n))
        return b

    def _wstr(self, rva):
        if rva <= 0:
            return "?"
        ln = struct.unpack('<I', self._at(rva, 4))[0]
        if ln <= 0 or ln > 4096:
            return "?"
        return self._at(rva + 4, ln).decode('utf-16-le', 'replace')

    # --- streams ---------------------------------------------------------
    def _load(self):
        hdr = self._at(0, 32)
        if hdr[:4] != MDMP:
            raise ValueError("not a minidump (magic %r)" % hdr[:4])
        nstreams, dirrva = struct.unpack_from('<II', hdr, 8)
        self.streams = {}
        dirb = self._at(dirrva, nstreams * 12)
        for i in range(nstreams):
            st, ds, rva = struct.unpack_from('<III', dirb, i * 12)
            self.streams.setdefault(st, []).append((ds, rva))

        # modules
        self.mods = []
        if 4 in self.streams:
            _, rva = self.streams[4][0]
            n = struct.unpack('<I', self._at(rva, 4))[0]
            blob = self._at(rva + 4, n * 108)
            for i in range(n):
                m = i * 108
                b, sz = struct.unpack_from('<QI', blob, m)
                nrva = struct.unpack_from('<I', blob, m + 20)[0]
                nm = self._wstr(nrva).replace('\\', '/').split('/')[-1]
                self.mods.append((b, sz, nm))
            self.mods.sort()

        # thread names (stream 24).  Element size is derived from the stream,
        # not assumed -- see validate().
        self.tnames = {}
        self.tname_elem = 0
        if 24 in self.streams:
            ds, rva = self.streams[24][0]
            n = struct.unpack('<I', self._at(rva, 4))[0]
            if n:
                elem = (ds - 4) // n
                self.tname_elem = elem
                blob = self._at(rva + 4, n * elem)
                for i in range(n):
                    tid = struct.unpack_from('<I', blob, i * elem)[0]
                    nr = struct.unpack_from('<Q', blob, i * elem + (8 if elem >= 16 else 4))[0]
                    try:
                        self.tnames[tid] = self._wstr(nr)
                    except Exception:                # noqa: BLE001
                        pass

        # threads
        self.threads = []
        if 3 in self.streams:
            _, rva = self.streams[3][0]
            n = struct.unpack('<I', self._at(rva, 4))[0]
            blob = self._at(rva + 4, n * 48)
            for i in range(n):
                t = i * 48
                tid = struct.unpack_from('<I', blob, t)[0]
                cds, crva = struct.unpack_from('<II', blob, t + 40)
                self.threads.append((tid, crva, cds))

        # exception
        self.exc = None
        if 6 in self.streams:
            _, rva = self.streams[6][0]
            blob = self._at(rva, 168)
            tid = struct.unpack_from('<I', blob, 0)[0]
            code, flags, rec, addr = struct.unpack_from('<IIQQ', blob, 8)
            nparm = struct.unpack_from('<I', blob, 8 + 24)[0]
            parms = [struct.unpack_from('<Q', blob, 8 + 32 + j * 8)[0]
                     for j in range(min(nparm, 15))]
            cds, crva = struct.unpack_from('<II', blob, 160)
            self.exc = dict(tid=tid, code=code, flags=flags, addr=addr,
                            parms=parms, ctx=crva, ctxsize=cds)

    # --- derived ---------------------------------------------------------
    def modof(self, a):
        for b, sz, nm in self.mods:
            if b <= a < b + sz:
                return (nm, a - b)
        return None

    def rip(self):
        if not self.exc or not self.exc['ctx']:
            return None
        return struct.unpack('<Q', self._readf(self.exc['ctx'] + 0xF8, 8))[0]

    def regs(self, names=('rax', 'rcx', 'rdx', 'rbx', 'rsp', 'rbp', 'rsi', 'rdi',
                          'r8', 'r9', 'r10', 'r11', 'r12', 'r13', 'r14', 'r15', 'rip')):
        OFF = dict(rax=0x78, rcx=0x80, rdx=0x88, rbx=0x90, rsp=0x98, rbp=0xA0,
                   rsi=0xA8, rdi=0xB0, r8=0xB8, r9=0xC0, r10=0xC8, r11=0xD0,
                   r12=0xD8, r13=0xE0, r14=0xE8, r15=0xF0, rip=0xF8)
        if not self.exc or not self.exc['ctx']:
            return {}
        b = self._readf(self.exc['ctx'], 0x100)
        return {n: struct.unpack_from('<Q', b, OFF[n])[0] for n in names}

    def _readf(self, off, n):
        with open(self.path, 'rb') as f:
            f.seek(off)
            return f.read(n)


def summarize(path):
    m = Lean(path)
    out = dict(dump=path, ok=m.ok, err=m.err)
    if not m.ok:
        return out
    e = m.exc
    game = [x for x in m.mods if x[2].lower().startswith('supervive')]
    out['nmods'] = len(m.mods)
    out['nthreads'] = len(m.threads)
    out['game_base'] = game[0][0] if game else 0
    out['streams'] = sorted(m.streams)
    out['tname_elem'] = m.tname_elem
    out['ntnames'] = len(m.tnames)
    if e:
        out['exc_code'] = e['code']
        out['exc_addr'] = e['addr']
        out['exc_parms'] = e['parms']
        out['exc_tid'] = e['tid']
        mo = m.modof(e['addr'])
        out['exc_addr_mod'] = mo[0] if mo else ""
        out['exc_addr_rva'] = mo[1] if mo else None
        r = m.regs()
        out['rip'] = r.get('rip')
        mo = m.modof(r.get('rip', 0))
        out['rip_mod'] = mo[0] if mo else ""
        out['rip_rva'] = mo[1] if mo else None
        out['crashed_thread_name'] = m.tnames.get(e['tid'], "")
        out['regs'] = r
    out['thread_names'] = m.tnames
    return out


if __name__ == '__main__':
    import pprint
    for p in sys.argv[1:]:
        pprint.pprint(summarize(p))
