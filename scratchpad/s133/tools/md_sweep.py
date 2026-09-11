#!/usr/bin/env python
"""md_sweep.py -- one READ-ONLY pass over the whole crashpad minidump corpus.

Emits one TSV row per DISTINCT report (deduped by crashpad report GUID, which is the
.dmp basename) with everything Q1/Q2/Q3 need:

  Q1  kill-region census   : the MemoryInfoList region + AllocationBase group covering
                             the faulting address (the manually-mapped, module-list-hidden
                             protector image)
  Q2  boot-session census  : ntdll/kernel32/KERNELBASE/user32/combase bases (ASLR is
                             per-BOOT for system DLLs on Windows, per-LAUNCH for the exe),
                             + MiscInfo ProcessCreateTime and header TimeDateStamp
  Q3  fault census         : exception code, address, ExceptionInformation[0..], RIP,
                             module attribution

usage: python md_sweep.py [--out out.tsv] [--limit N] [glob ...]
       default glob = dumps/crashpad-*/reports/*.dmp
"""
import glob as globmod
import os
import struct
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from md_streams import Dump, STATE, TYPE, protname   # noqa: E402

SYSDLLS = ['ntdll.dll', 'kernel32.dll', 'KERNELBASE.dll', 'user32.dll', 'combase.dll',
           'advapi32.dll', 'gdi32.dll']

COLS = ['guid', 'first_path', 'ndirs', 'size_bytes', 'streams',
        'pid', 'create_time', 'create_iso', 'hdr_stamp', 'hdr_iso',
        'os_build', 'ncpu',
        'nmods', 'nthreads', 'nhandles', 'nunloaded', 'nmeminfo',
        'game_base', 'preloader_base', 'runtime_in_modlist',
        'ntdll', 'kernel32', 'kernelbase', 'user32', 'combase', 'advapi32', 'gdi32',
        'exc_code', 'exc_addr', 'exc_nparm', 'exc_p0', 'exc_p1', 'rip',
        'rip_mod', 'rip_rva', 'addr_mod', 'addr_rva',
        'kill_shape',
        'killreg_base', 'killreg_size', 'killreg_state', 'killreg_type',
        'killreg_prot', 'killreg_aprot',
        'killalloc_base', 'killalloc_nregions', 'killalloc_span',
        'killalloc_exec_regions', 'killalloc_in_modlist']


def iso(t):
    if not t:
        return ""
    try:
        return time.strftime('%Y-%m-%dT%H:%M:%S', time.localtime(t))
    except Exception:                                # noqa: BLE001
        return ""


def fast_meminfo(path, streams):
    """Parse stream 16 with iter_unpack -- 44k records x 124 dumps in Python needs it."""
    if 16 not in streams:
        return []
    _ds, rva = streams[16][0]
    with open(path, 'rb') as f:
        f.seek(rva)
        szhdr, szent = struct.unpack('<II', f.read(8))
        n = struct.unpack('<Q', f.read(8))[0]
        f.seek(rva + szhdr)
        blob = f.read(n * szent)
    if szent != 48:
        # honour the declared stride rather than assuming 48
        out = []
        for i in range(n):
            m = i * szent
            base, alloc, aprot, _a1, rsz, state, prot, typ, _a2 = \
                struct.unpack_from('<QQIIQIIII', blob, m)
            out.append((base, alloc, aprot, rsz, state, prot, typ))
        return out
    return [(b, a, ap, sz, st, pr, ty)
            for (b, a, ap, _a1, sz, st, pr, ty, _a2)
            in struct.iter_unpack('<QQIIQIIII', blob)]


def row_for(guid, paths):
    # Prefer the LARGEST copy: the archiver can catch crashpad mid-write, and one GUID
    # in this corpus (f053db6e) exists as a 6,460,608 B truncated copy AND a complete
    # 41,131,872 B copy.  Taking paths[0] silently analysed the truncated one.
    p = max(paths, key=os.path.getsize)
    d = Dump(p)
    r = {c: '' for c in COLS}
    r['guid'] = guid
    r['first_path'] = p.replace('\\', '/')
    r['ndirs'] = len(paths)
    r['size_bytes'] = os.path.getsize(p)
    if not d.ok:
        r['streams'] = 'PARSE_FAIL:' + d.err
        return r
    r['streams'] = ','.join(str(s) for s in sorted(d.streams))
    if d.misc:
        r['pid'] = d.misc.get('pid', '')
        r['create_time'] = d.misc.get('create_time', '')
        r['create_iso'] = iso(d.misc.get('create_time', 0))
    r['hdr_stamp'] = d.stamp
    r['hdr_iso'] = iso(d.stamp)
    if d.sysinfo:
        r['os_build'] = '%d.%d.%d' % (d.sysinfo['major'], d.sysinfo['minor'], d.sysinfo['build'])
        r['ncpu'] = d.sysinfo['ncpu']
    r['nmods'] = len(d.mods)
    r['nthreads'] = len(d.threads)
    r['nhandles'] = d.nhandles
    r['nunloaded'] = len(d.unloaded)
    g = [m for m in d.mods if m['name'].lower().startswith('supervive')]
    r['game_base'] = '0x%X' % g[0]['base'] if g else ''
    pb = d.modbase('preloader.dll')
    r['preloader_base'] = '0x%X' % pb if pb else ''
    r['runtime_in_modlist'] = '1' if d.modbase('runtime.dll') else '0'
    for key, nm in zip(['ntdll', 'kernel32', 'kernelbase', 'user32', 'combase',
                        'advapi32', 'gdi32'], SYSDLLS):
        b = d.modbase(nm)
        r[key] = '0x%X' % b if b else ''
    if d.exc:
        r['exc_code'] = '0x%08X' % d.exc['code']
        r['exc_addr'] = '0x%X' % d.exc['addr']
        r['exc_nparm'] = d.exc['nparm']
        pl = d.exc['parms']
        r['exc_p0'] = '0x%X' % pl[0] if len(pl) > 0 else ''
        r['exc_p1'] = '0x%X' % pl[1] if len(pl) > 1 else ''
        if d.rip is not None:
            r['rip'] = '0x%X' % d.rip
            mo = d.modof(d.rip)
            r['rip_mod'] = mo[0] if mo else ''
            r['rip_rva'] = '0x%X' % mo[1] if mo else ''
        mo = d.modof(d.exc['addr'])
        r['addr_mod'] = mo[0] if mo else ''
        r['addr_rva'] = '0x%X' % mo[1] if mo else ''

    mi = fast_meminfo(p, d.streams)
    r['nmeminfo'] = len(mi)

    # ---- Q1: the region covering the faulting address ----
    if d.exc and mi:
        addr = d.exc['addr']
        # shape flags used by fk8_classify: EXECUTE fault + addr&0xFFF==1
        shape = []
        if d.exc['code'] == 0xC0000005:
            shape.append('AV')
        if d.exc['parms'] and d.exc['parms'][0] == 8:
            shape.append('EXEC')
        elif d.exc['parms'] and d.exc['parms'][0] == 0:
            shape.append('READ')
        elif d.exc['parms'] and d.exc['parms'][0] == 1:
            shape.append('WRITE')
        if addr & 0xFFF == 1:
            shape.append('PLUS1')
        r['kill_shape'] = '+'.join(shape)
        hit = None
        for (b, a, ap, sz, st, pr, ty) in mi:
            if b <= addr < b + sz:
                hit = (b, a, ap, sz, st, pr, ty)
                break
        if hit:
            b, a, ap, sz, st, pr, ty = hit
            r['killreg_base'] = '0x%X' % b
            r['killreg_size'] = '0x%X' % sz
            r['killreg_state'] = STATE.get(st, hex(st))
            r['killreg_type'] = TYPE.get(ty, hex(ty))
            r['killreg_prot'] = protname(pr)
            r['killreg_aprot'] = protname(ap)
            grp = [x for x in mi if x[1] == a]
            span = sum(x[3] for x in grp)
            nexe = sum(1 for x in grp if (x[5] & 0xF0))
            r['killalloc_base'] = '0x%X' % a
            r['killalloc_nregions'] = len(grp)
            r['killalloc_span'] = '0x%X' % span
            r['killalloc_exec_regions'] = nexe
            r['killalloc_in_modlist'] = '1' if d.modof(a) else '0'
    return r


def main(argv):
    out = 'scratchpad/s133/evidence/md_sweep.tsv'
    pats = []
    limit = 0
    i = 0
    while i < len(argv):
        if argv[i] == '--out':
            i += 1
            out = argv[i]
        elif argv[i] == '--limit':
            i += 1
            limit = int(argv[i])
        else:
            pats.append(argv[i])
        i += 1
    if not pats:
        pats = ['dumps/crashpad-*/reports/*.dmp']
    files = []
    for p in pats:
        files.extend(globmod.glob(p))
    # dedupe by crashpad report GUID (the basename); keep every path for the ndirs count
    by = {}
    for f in sorted(files):
        by.setdefault(os.path.basename(f), []).append(f)
    keys = sorted(by)
    if limit:
        keys = keys[:limit]
    sys.stderr.write("files=%d distinct_guids=%d processing=%d\n"
                     % (len(files), len(by), len(keys)))
    rows = []
    t0 = time.time()
    for k, guid in enumerate(keys):
        rows.append(row_for(guid, by[guid]))
        if (k + 1) % 10 == 0:
            sys.stderr.write("  %d/%d  %.1fs\n" % (k + 1, len(keys), time.time() - t0))
    with open(out, 'w', encoding='utf-8') as fh:
        fh.write('\t'.join(COLS) + '\n')
        for r in rows:
            fh.write('\t'.join(str(r[c]) for c in COLS) + '\n')
    sys.stderr.write("wrote %s  rows=%d  %.1fs\n" % (out, len(rows), time.time() - t0))


if __name__ == '__main__':
    main(sys.argv[1:])
