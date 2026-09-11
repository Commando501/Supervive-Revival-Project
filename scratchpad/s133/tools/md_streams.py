#!/usr/bin/env python
"""md_streams.py -- READ-ONLY full-stream minidump reader for the SUPERVIVE crashpad corpus.

Reads streams NOTHING in tools/crashtri/ has ever read:
    7  SystemInfoStream
   12  HandleDataStream        (count only)
   14  UnloadedModuleListStream
   15  MiscInfoStream          (ProcessCreateTime / ProcessId / times)
   16  MemoryInfoListStream    (the complete VirtualQueryEx region map at death)

plus the ones mdexc.py already reads (3 threads, 4 modules, 6 exception) so a single
pass can answer Q1/Q2/Q3 together.

STRUCT REFERENCES (minidumpapiset.h):
  MINIDUMP_MEMORY_INFO_LIST { ULONG SizeOfHeader; ULONG SizeOfEntry; ULONG64 NumberOfEntries; }
  MINIDUMP_MEMORY_INFO      { ULONG64 BaseAddress; ULONG64 AllocationBase;
                              ULONG32 AllocationProtect; ULONG32 __alignment1;
                              ULONG64 RegionSize; ULONG32 State; ULONG32 Protect;
                              ULONG32 Type; ULONG32 __alignment2; }   -- 48 bytes
  MINIDUMP_MISC_INFO_N      { ULONG SizeOfInfo; ULONG Flags1; ULONG ProcessId;
                              ULONG ProcessCreateTime; ULONG ProcessUserTime;
                              ULONG ProcessKernelTime; ... }

SizeOfEntry / SizeOfInfo / SizeOfHeader are READ FROM THE STREAM, never assumed, so a
different dump writer cannot silently mis-stride.  Opens 'rb' only.  Stdlib only.
"""
import struct
import sys

STATE = {0x1000: "COMMIT", 0x2000: "RESERVE", 0x10000: "FREE"}
TYPE = {0x20000: "PRIVATE", 0x40000: "MAPPED", 0x1000000: "IMAGE", 0: "-"}
PROT = {0x00: "-", 0x01: "NOACCESS", 0x02: "READONLY", 0x04: "READWRITE",
        0x08: "WRITECOPY", 0x10: "EXECUTE", 0x20: "EXECUTE_READ",
        0x40: "EXECUTE_READWRITE", 0x80: "EXECUTE_WRITECOPY"}


def protname(p):
    base = PROT.get(p & 0xFF, "0x%X" % (p & 0xFF))
    extra = ""
    if p & 0x100:
        extra += "|GUARD"
    if p & 0x200:
        extra += "|NOCACHE"
    if p & 0x400:
        extra += "|WRITECOMBINE"
    return base + extra


class Dump:
    def __init__(self, path):
        self.path = path
        self.ok = False
        self.err = ""
        self.streams = {}
        self.mods = []
        self.unloaded = []
        self.threads = []
        self.exc = None
        self.rip = None
        self.regs = {}
        self.sysinfo = None
        self.misc = None
        self.nhandles = 0
        self._meminfo_cache = None
        try:
            self.f = open(path, 'rb')
            self._load()
            self.ok = True
        except Exception as e:                       # noqa: BLE001
            self.err = "%s: %s" % (type(e).__name__, e)
        finally:
            try:
                self.f.close()
            except Exception:                        # noqa: BLE001
                pass

    # ---- raw ------------------------------------------------------------
    def _at(self, off, n):
        with open(self.path, 'rb') as f:
            f.seek(off)
            b = f.read(n)
        if len(b) != n:
            raise EOFError("short read at 0x%X (%d of %d)" % (off, len(b), n))
        return b

    def _wstr(self, rva):
        if rva <= 0:
            return ""
        ln = struct.unpack('<I', self._at(rva, 4))[0]
        if ln <= 0 or ln > 8192:
            return ""
        return self._at(rva + 4, ln).decode('utf-16-le', 'replace')

    def _load(self):
        hdr = self._at(0, 32)
        if hdr[:4] != b'MDMP':
            raise ValueError("not a minidump (magic %r)" % hdr[:4])
        nstreams, dirrva = struct.unpack_from('<II', hdr, 8)
        self.stamp = struct.unpack_from('<I', hdr, 20)[0]
        self.hflags = struct.unpack_from('<Q', hdr, 24)[0]
        dirb = self._at(dirrva, nstreams * 12)
        for i in range(nstreams):
            st, ds, rva = struct.unpack_from('<III', dirb, i * 12)
            self.streams.setdefault(st, []).append((ds, rva))
        self._modules()
        self._unloaded()
        self._exception()
        self._sysinfo()
        self._miscinfo()
        self._handles()
        self._threads()

    # ---- stream 4 -------------------------------------------------------
    def _modules(self):
        if 4 not in self.streams:
            return
        _, rva = self.streams[4][0]
        n = struct.unpack('<I', self._at(rva, 4))[0]
        blob = self._at(rva + 4, n * 108)
        for i in range(n):
            m = i * 108
            b, sz, ts, ck = struct.unpack_from('<QIII', blob, m)
            nrva = struct.unpack_from('<I', blob, m + 20)[0]
            full = self._wstr(nrva)
            nm = full.replace(chr(92), '/').split('/')[-1]
            self.mods.append(dict(base=b, size=sz, name=nm, path=full, ts=ts, csum=ck))
        self.mods.sort(key=lambda x: x['base'])

    def modbase(self, name):
        n = name.lower()
        for m in self.mods:
            if m['name'].lower() == n:
                return m['base']
        return None

    def modof(self, a):
        for m in self.mods:
            if m['base'] <= a < m['base'] + m['size']:
                return (m['name'], a - m['base'])
        return None

    # ---- stream 14 ------------------------------------------------------
    def _unloaded(self):
        if 14 not in self.streams:
            return
        _ds, rva = self.streams[14][0]
        szhdr, szent, n = struct.unpack('<III', self._at(rva, 12))
        if n == 0 or szent == 0:
            return
        blob = self._at(rva + szhdr, n * szent)
        # MINIDUMP_UNLOADED_MODULE = { U64 BaseOfImage; U32 SizeOfImage; U32 CheckSum;
        #                              U32 TimeDateStamp; RVA ModuleNameRva; } == 24 B.
        # NOTE: reading only 4 fields puts TimeDateStamp where ModuleNameRva belongs and
        # blows up on a garbage RVA -- that is exactly how this parser failed first pass.
        for i in range(n):
            m = i * szent
            b, sz, _ck, ts, nrva = struct.unpack_from('<QIIII', blob, m)
            self.unloaded.append(dict(base=b, size=sz, ts=ts,
                                      name=self._wstr(nrva).replace(chr(92), '/').split('/')[-1]))

    # ---- stream 6 -------------------------------------------------------
    def _exception(self):
        if 6 not in self.streams:
            return
        _, rva = self.streams[6][0]
        blob = self._at(rva, 168)
        tid = struct.unpack_from('<I', blob, 0)[0]
        code, flags, _rec, addr = struct.unpack_from('<IIQQ', blob, 8)
        nparm = struct.unpack_from('<I', blob, 8 + 24)[0]
        parms = [struct.unpack_from('<Q', blob, 8 + 32 + j * 8)[0] for j in range(min(nparm, 15))]
        cds, crva = struct.unpack_from('<II', blob, 160)
        self.exc = dict(tid=tid, code=code, flags=flags, addr=addr, nparm=nparm,
                        parms=parms, ctxrva=crva, ctxsize=cds)
        # RIP from the EXCEPTION stream's own context -- NOT MINIDUMP_THREAD's, which
        # gives the dump writer's state (fk8_classify.py's recorded parser trap).
        if crva:
            OFF = dict(rax=0x78, rcx=0x80, rdx=0x88, rbx=0x90, rsp=0x98, rbp=0xA0,
                       rsi=0xA8, rdi=0xB0, r8=0xB8, r9=0xC0, r10=0xC8, r11=0xD0,
                       r12=0xD8, r13=0xE0, r14=0xE8, r15=0xF0, rip=0xF8)
            b = self._at(crva, 0x100)
            self.regs = {k: struct.unpack_from('<Q', b, v)[0] for k, v in OFF.items()}
            self.rip = self.regs['rip']

    # ---- stream 7 -------------------------------------------------------
    def _sysinfo(self):
        if 7 not in self.streams:
            return
        _, rva = self.streams[7][0]
        b = self._at(rva, 56)
        arch, plev, prev = struct.unpack_from('<HHH', b, 0)
        ncpu, ptype = struct.unpack_from('<BB', b, 6)
        maj, mnr, bld, plat = struct.unpack_from('<IIII', b, 8)
        csdrva = struct.unpack_from('<I', b, 24)[0]
        self.sysinfo = dict(arch=arch, proclevel=plev, procrev=prev, ncpu=ncpu,
                            producttype=ptype, major=maj, minor=mnr, build=bld,
                            platform=plat, csd=self._wstr(csdrva))

    # ---- stream 15 ------------------------------------------------------
    def _miscinfo(self):
        if 15 not in self.streams:
            return
        ds, rva = self.streams[15][0]
        sz = struct.unpack('<I', self._at(rva, 4))[0]
        sz = min(sz, ds)
        b = self._at(rva, sz)
        d = dict(size=sz, flags1=struct.unpack_from('<I', b, 4)[0])
        if sz >= 24:
            d['pid'], d['create_time'], d['user_time'], d['kernel_time'] = \
                struct.unpack_from('<IIII', b, 8)
        d['has_pid_time'] = bool(d['flags1'] & 0x1)
        d['has_proc_times'] = bool(d['flags1'] & 0x2)
        self.misc = d

    # ---- stream 12 ------------------------------------------------------
    def _handles(self):
        if 12 not in self.streams:
            return
        _ds, rva = self.streams[12][0]
        _szhdr, szdesc, n, _res = struct.unpack('<IIII', self._at(rva, 16))
        self.nhandles = n
        self.handle_desc_size = szdesc

    # ---- stream 3 -------------------------------------------------------
    def _threads(self):
        if 3 not in self.streams:
            return
        _, rva = self.streams[3][0]
        n = struct.unpack('<I', self._at(rva, 4))[0]
        blob = self._at(rva + 4, n * 48)
        for i in range(n):
            t = i * 48
            tid = struct.unpack_from('<I', blob, t)[0]
            teb = struct.unpack_from('<Q', blob, t + 16)[0]
            sa = struct.unpack_from('<Q', blob, t + 24)[0]
            ssz, _srva = struct.unpack_from('<II', blob, t + 32)
            self.threads.append(dict(tid=tid, teb=teb, stack=sa, stacksize=ssz))

    # ---- stream 16 (lazy: ~2.1 MB / 45k records per dump) ----------------
    def meminfo(self):
        if self._meminfo_cache is not None:
            return self._meminfo_cache
        out = []
        if 16 in self.streams:
            _ds, rva = self.streams[16][0]
            szhdr, szent = struct.unpack('<II', self._at(rva, 8))
            n = struct.unpack('<Q', self._at(rva + 8, 8))[0]
            blob = self._at(rva + szhdr, n * szent)
            for i in range(n):
                m = i * szent
                base, alloc = struct.unpack_from('<QQ', blob, m)
                aprot = struct.unpack_from('<I', blob, m + 16)[0]
                rsz = struct.unpack_from('<Q', blob, m + 24)[0]
                state, prot, typ = struct.unpack_from('<III', blob, m + 32)
                out.append(dict(base=base, alloc=alloc, aprot=aprot, size=rsz,
                                state=state, prot=prot, type=typ))
        self._meminfo_cache = out
        return out

    def region_of(self, addr):
        for r in self.meminfo():
            if r['base'] <= addr < r['base'] + r['size']:
                return r
        return None

    def regions_of_alloc(self, allocbase):
        return [r for r in self.meminfo() if r['alloc'] == allocbase]


def selftest(path):
    """POSITIVE CONTROL: print fields verifiable against an independent instrument."""
    d = Dump(path)
    print("dump      :", path)
    print("ok        :", d.ok, d.err)
    if not d.ok:
        return
    print("streams   :", sorted(d.streams))
    print("nmods     :", len(d.mods))
    g = [m for m in d.mods if m['name'].lower().startswith('supervive')]
    if g:
        print("GAME base : 0x%X  size 0x%X  %s" % (g[0]['base'], g[0]['size'], g[0]['path']))
    for nm in ('ntdll.dll', 'kernel32.dll', 'KERNELBASE.dll', 'user32.dll',
               'combase.dll', 'preloader.dll', 'runtime.dll'):
        b = d.modbase(nm)
        print("  %-16s %s" % (nm, ("0x%X" % b) if b else "ABSENT"))
    print("sysinfo   :", d.sysinfo)
    print("misc      :", d.misc)
    print("nhandles  :", d.nhandles)
    print("nthreads  :", len(d.threads))
    print("nunloaded :", len(d.unloaded))
    if d.exc:
        print("exc code  : 0x%08X addr 0x%X nparm %d parms %s" %
              (d.exc['code'], d.exc['addr'], d.exc['nparm'],
               [hex(x) for x in d.exc['parms']]))
        print("rip       : 0x%X" % (d.rip or 0))
    mi = d.meminfo()
    print("meminfo   : %d regions" % len(mi))
    st = {}
    for r in mi:
        k = STATE.get(r['state'], hex(r['state']))
        st[k] = st.get(k, 0) + 1
    print("            by state:", st)
    ty = {}
    for r in mi:
        k = TYPE.get(r['type'], hex(r['type']))
        ty[k] = ty.get(k, 0) + 1
    print("            by type :", ty)


if __name__ == '__main__':
    for p in sys.argv[1:]:
        selftest(p)
        print()
