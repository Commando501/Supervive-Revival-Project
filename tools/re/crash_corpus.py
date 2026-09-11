# crash_corpus.py -- READ-ONLY survey of the UE crash-report corpus under
#   %LOCALAPPDATA%\SUPERVIVE\Saved\Crashes
# Parses CrashContext.runtime-xml (uptime, error message, crashed thread + RVA chain)
# and UEMinidump.dmp (exception record, faulting-thread CONTEXT, memory pages).
# Opens every file 'rb' and never writes into the crash tree.
#
# S106 (2026-07-27): built for FK-7 ("the tutorial route is flaky, ~2 of 3 launches die").
# Usage:
#   python crash_corpus.py survey                  # one line per crash
#   python crash_corpus.py cluster                 # group by (thread, faulting RVA)
#   python crash_corpus.py ctx <CrashGUIDsubstr>   # registers + memory around the fault
#   python crash_corpus.py mem <GUID> <addr> <len> # hexdump from the dump's memory list
#   python crash_corpus.py cmdline                 # per-crash command line (shim launch mode)
import sys, os, re, struct, glob, datetime
from collections import defaultdict

CRASHDIR = os.path.expandvars(r"%LOCALAPPDATA%\SUPERVIVE\Saved\Crashes")


class MD(object):
    """Minimal read-only minidump reader."""

    REGS = ['Rax', 'Rcx', 'Rdx', 'Rbx', 'Rsp', 'Rbp', 'Rsi', 'Rdi',
            'R8', 'R9', 'R10', 'R11', 'R12', 'R13', 'R14', 'R15', 'Rip']

    def __init__(self, path):
        self.d = open(path, 'rb').read()          # READ-ONLY
        assert self.d[:4] == b'MDMP'
        _, nst, drva = struct.unpack_from('<III', self.d, 4)
        self.streams = {}
        for i in range(nst):
            t, sz, rva = struct.unpack_from('<III', self.d, drva + i * 12)
            self.streams.setdefault(t, (sz, rva))
        self._mem = None

    def modules(self):
        out = []
        if 4 not in self.streams:
            return out
        _, rva = self.streams[4]
        n = struct.unpack_from('<I', self.d, rva)[0]
        for i in range(n):
            m = rva + 4 + i * 108
            base, size = struct.unpack_from('<QI', self.d, m)
            nr = struct.unpack_from('<I', self.d, m + 20)[0]
            nm = '?'
            if 0 < nr < len(self.d) - 4:
                ln = struct.unpack_from('<I', self.d, nr)[0]
                if 0 < ln < 1024:
                    nm = self.d[nr + 4:nr + 4 + ln].decode('utf-16-le', 'replace')
            out.append((base, size, nm.replace('/', '\\').split('\\')[-1]))
        return out

    def game_base(self):
        for b, s, n in self.modules():
            if n.lower().startswith('supervive'):
                return b, s
        return None, None

    def modof(self, addr):
        for b, s, n in self.modules():
            if b <= addr < b + s:
                return n, addr - b
        return None, None

    def exception(self):
        if 6 not in self.streams:
            return None
        _, rva = self.streams[6]
        tid = struct.unpack_from('<I', self.d, rva)[0]
        e = rva + 8
        code, flags, nested, addr, nparm = struct.unpack_from('<IIQQI', self.d, e)
        parms = [struct.unpack_from('<Q', self.d, e + 32 + j * 8)[0]
                 for j in range(min(nparm, 15))]
        csz, crva = struct.unpack_from('<II', self.d, rva + 8 + 152)
        return dict(tid=tid, code=code, addr=addr, parms=parms, ctx=(csz, crva))

    def context(self, crva):
        r = {}
        for i, nm in enumerate(self.REGS):
            r[nm] = struct.unpack_from('<Q', self.d, crva + 0x78 + i * 8)[0]
        r['EFlags'] = struct.unpack_from('<I', self.d, crva + 0x44)[0]
        for i in range(6):
            lo, hi = struct.unpack_from('<QQ', self.d, crva + 0x1A0 + i * 16)
            r['Xmm%d' % i] = (hi << 64) | lo
        return r

    def threads(self):
        out = []
        if 3 not in self.streams:
            return out
        _, rva = self.streams[3]
        n = struct.unpack_from('<I', self.d, rva)[0]
        for i in range(n):
            t = rva + 4 + i * 48
            tid, sus, pri0, pri, teb, sst, ssz, srva, csz, crva = \
                struct.unpack_from('<IIIIQQIIII', self.d, t)
            out.append(dict(tid=tid, teb=teb, stack=(sst, ssz, srva), ctx=crva))
        return out

    def mem_index(self):
        if self._mem is not None:
            return self._mem
        rs = []
        if 9 in self.streams:                       # Memory64ListStream
            _, rva = self.streams[9]
            n, base = struct.unpack_from('<QQ', self.d, rva)
            off = base
            for i in range(n):
                sa, sz = struct.unpack_from('<QQ', self.d, rva + 16 + i * 16)
                rs.append((sa, sz, off))
                off += sz
        if 5 in self.streams:                       # MemoryListStream
            _, rva = self.streams[5]
            n = struct.unpack_from('<I', self.d, rva)[0]
            for i in range(n):
                sa, sz, dr = struct.unpack_from('<QII', self.d, rva + 4 + i * 16)
                rs.append((sa, sz, dr))
        rs.sort()
        self._mem = rs
        return rs

    def read(self, addr, n):
        for sa, sz, off in self.mem_index():
            if sa <= addr < sa + sz:
                k = min(n, sa + sz - addr)
                return self.d[off + (addr - sa): off + (addr - sa) + k]
        return b''


def tag(x, t):
    m = re.search('<' + t + '>(.*?)</' + t + '>', x, re.S)
    return m.group(1).strip() if m else None


def parse_ctx(path):
    x = open(path, 'rb').read().decode('utf-8', 'replace')
    r = dict(guid=tag(x, 'CrashGUID'), secs=tag(x, 'SecondsSinceStart'),
             err=tag(x, 'ErrorMessage'), ctype=tag(x, 'CrashType'),
             ensure=tag(x, 'IsEnsure'), assert_=tag(x, 'IsAssert'),
             stall=tag(x, 'IsStall'), pid=tag(x, 'ProcessId'),
             hash=tag(x, 'PCallStackHash'), cmdline=tag(x, 'CommandLine'),
             gamestate=tag(x, 'GameStateName'))
    r['thread'] = None
    r['tid'] = None
    r['frames'] = []
    r['raw'] = ''
    r['nthreads'] = len(re.findall(r'<Thread>', x))
    for m in re.finditer(r'<Thread>(.*?)</Thread>', x, re.S):
        b = m.group(1)
        if '<IsCrashed>true' in b:
            r['thread'] = tag(b, 'ThreadName')
            r['tid'] = tag(b, 'ThreadID')
            cs = tag(b, 'CallStack') or ''
            r['raw'] = cs
            fr = []
            for mm in re.finditer(r'(\S+)\s+0x([0-9a-fA-F]+)\s*\+\s*([0-9a-fA-F]+)', cs):
                fr.append((mm.group(1), int(mm.group(3), 16)))
            r['frames'] = fr
            break
    return r


# frames the crash reporter always prepends: UE ReportCrash + the packer's VEH stub
HANDLER = set([0x1153803, 0x755524E, 0x7555F4E])


def fault_frames(fr):
    """SUPERVIVE frames with the crash-handler prologue stripped."""
    g = []
    for m, o in fr:
        if not m.lower().startswith('supervive'):
            continue
        if o in HANDLER:
            continue
        g.append(o)
    return g


def dirs():
    return sorted(glob.glob(os.path.join(CRASHDIR, 'UECC-*')))


def _row(d):
    cx = os.path.join(d, 'CrashContext.runtime-xml')
    dp = os.path.join(d, 'UEMinidump.dmp')
    if not os.path.exists(cx):
        return None
    c = parse_ctx(cx)
    rv = code = av = avkind = None
    base = None
    if os.path.exists(dp):
        try:
            md = MD(dp)
            e = md.exception()
            base, _ = md.game_base()
            if e:
                code = e['code']
                ctx = md.context(e['ctx'][1])
                if base and base <= ctx['Rip'] < base + 0x8000000:
                    rv = ctx['Rip'] - base
                if len(e['parms']) >= 2:
                    avkind = e['parms'][0]
                    av = e['parms'][1]
        except Exception:
            pass
    ff = fault_frames(c['frames'])
    if rv is None and ff:
        rv = ff[0]
    c['rv'] = rv
    c['code'] = code
    c['av'] = av
    c['avkind'] = avkind
    c['ff'] = ff
    c['dir'] = os.path.basename(d)
    c['mtime'] = os.path.getmtime(d)
    return c


def survey(args):
    print("%-40s %-5s %-24s %-9s %-9s %-14s %s" %
          ("crashdir", "secs", "thread", "faultPC", "excCode", "AVaddr", "mtime"))
    for d in dirs():
        c = _row(d)
        if not c:
            continue
        av = ''
        if c['av'] is not None:
            av = '%s@%x' % ({0: 'R', 1: 'W', 8: 'X'}.get(c['avkind'], '?'), c['av'])
        mt = datetime.datetime.fromtimestamp(c['mtime']).strftime('%m-%d %H:%M')
        print("%-40s %-5s %-24s %-9s %-9s %-14s %s" %
              (c['dir'][:40], c['secs'], (c['thread'] or '-')[:24],
               ('%x' % c['rv']) if c['rv'] is not None else '-',
               ('%08X' % c['code']) if c['code'] else '-', av, mt))


def cluster(args):
    rows = [c for c in (_row(d) for d in dirs()) if c]
    g = defaultdict(list)
    for r in rows:
        g[(r['thread'], r['rv'])].append(r)
    print("== %d crashes, %d (thread, faultRVA) clusters ==" % (len(rows), len(g)))
    for k, v in sorted(g.items(), key=lambda kv: -len(kv[1])):
        secs = sorted(int(x['secs']) for x in v if x['secs'] and x['secs'].isdigit())
        avs = sorted(set(('%x' % x['av']) if x['av'] is not None else '-' for x in v))
        cods = sorted(set(('%08X' % x['code']) if x['code'] else '-' for x in v))
        print("\n[%2d] thread=%-24s faultRVA=%s code=%s" %
              (len(v), k[0], ('%x' % k[1]) if k[1] is not None else '-', ','.join(cods)))
        print("     AV addrs : %s" % ', '.join(avs[:10]))
        print("     uptime s : %s" % (secs if secs else '-'))
        chains = sorted(set(tuple(x['ff'][:8]) for x in v))
        for ch in chains[:3]:
            print("     chain    : %s" % ' '.join('%x' % a for a in ch))
        for x in sorted(v, key=lambda z: z['mtime'])[:8]:
            print("       %-42s %ss  %s" % (x['dir'][:42], x['secs'],
                  datetime.datetime.fromtimestamp(x['mtime']).strftime('%m-%d %H:%M')))


def cmdline(args):
    for d in dirs():
        c = _row(d)
        if not c:
            continue
        print("%-42s %-5ss %-22s %s" % (c['dir'][:42], c['secs'],
              (c['thread'] or '-')[:22], (c['cmdline'] or '')[:120]))


def ctxcmd(args):
    pat = args[0]
    for d in dirs():
        if pat.lower() not in os.path.basename(d).lower():
            continue
        dp = os.path.join(d, 'UEMinidump.dmp')
        c = parse_ctx(os.path.join(d, 'CrashContext.runtime-xml'))
        md = MD(dp)
        e = md.exception()
        base, _ = md.game_base()
        ctx = md.context(e['ctx'][1])
        print("== %s  uptime=%ss thread=%s tid=%s" %
              (os.path.basename(d), c['secs'], c['thread'], c['tid']))
        print("   %s" % c['err'])
        print("   exc=0x%08X addr=0x%X parms=%s   gamebase=0x%X" %
              (e['code'], e['addr'], [hex(p) for p in e['parms']], base))
        print("   RIP=0x%X  (RVA 0x%X)" % (ctx['Rip'], ctx['Rip'] - base if base else 0))
        for i in range(0, 16, 4):
            print("   " + "  ".join("%-4s=%016X" % (MD.REGS[j], ctx[MD.REGS[j]])
                                    for j in range(i, min(i + 4, 16))))
        for nm in ('Rax', 'Rcx', 'Rbx', 'Rdx', 'Rsi', 'Rdi', 'R8', 'R9',
                   'R12', 'R13', 'R14', 'R15'):
            v = ctx[nm]
            if v and v > 0x10000:
                mn, off = md.modof(v)
                lbl = ('  [%s+%x]' % (mn, off)) if mn else ''
                b = md.read(v, 32)
                if b:
                    print("   [%s=%016X]%s -> %s" % (nm, v, lbl, b.hex(' ')))
                else:
                    print("   [%s=%016X]%s -> <not in dump>" % (nm, v, lbl))
        return


def memcmd(args):
    pat, addr, n = args[0], int(args[1], 16), int(args[2], 0)
    for d in dirs():
        if pat.lower() not in os.path.basename(d).lower():
            continue
        md = MD(os.path.join(d, 'UEMinidump.dmp'))
        b = md.read(addr, n)
        if not b:
            print("not in dump")
            return
        for i in range(0, len(b), 16):
            print("%016X  %-47s %s" % (addr + i, b[i:i + 16].hex(' '),
                  ''.join(chr(x) if 32 <= x < 127 else '.' for x in b[i:i + 16])))
        return


if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'survey'
    {'survey': survey, 'cluster': cluster, 'ctx': ctxcmd,
     'mem': memcmd, 'cmdline': cmdline}[cmd](sys.argv[2:])
