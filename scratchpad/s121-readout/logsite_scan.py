#!/usr/bin/env python3
r"""logsite_scan.py -- map every `call UE::Logging::Private::BasicLog` site in .text
back to (a) its FStaticBasicLogRecord (format/file/line/verbosity) and (b) the
function that contains it (from tools/strxref/index/pdata_union.csv).

BasicLog identified at .text 0x0106B650 by its signature:
  mov [rsp+10],rdx / [rsp+18],r8 / [rsp+20],r9   <- varargs home save
  mov rax,[rdx+0x18]                              <- Log->DynamicData  (record +0x18)
  movzx r8d, byte [rax]                           <- DynamicData init flag
matching CORE_API void BasicLog(const FLogCategoryBase&, const FStaticBasicLogRecord*, ...)
(H:\Unreal Engine\UE_5.4\...\Logging\LogMacros.h:141)

Emitted call shape (MSVC):
    cmp byte ptr [rip+CAT], <verb>   ; FLogCategoryBase::Verbosity is byte 0
    jb  skip
    lea rdx, [rip+REC]               ; FStaticBasicLogRecord*
    lea rcx, [rip+CAT]
    call BasicLog

⚠ COVERAGE: .text in merged2 is 54.95% decrypted by page.  An all-zero page is
"never executed", NOT "absent".  Any per-function NEGATIVE must therefore also
report whether that function's bytes are non-zero -- this script does.
"""
import csv
import os
import struct
import sys

import capstone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from logrec_scan import Image, DUMP, VERB

BASICLOG = 0x0106B650
PDATA = r"G:\git\Supervive Revival Project\tools\strxref\index\pdata_union.csv"


def load_funcs():
    fns = []
    with open(PDATA, newline='') as f:
        rd = csv.reader(f)
        next(rd)
        for r in rd:
            fns.append((int(r[0], 16), int(r[1], 16)))
    fns.sort()
    return fns


def containing(fns, rva):
    import bisect
    i = bisect.bisect_right(fns, (rva, 1 << 62)) - 1
    if i >= 0 and fns[i][0] <= rva < fns[i][1]:
        return fns[i]
    return None


def main():
    img = Image(DUMP)
    recs, _ = __import__('logrec_scan').scan(img)
    byrva = {r['rec_rva']: r for r in recs}
    fns = load_funcs()

    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
    md.detail = False

    # --- find every direct call to BASICLOG in .text ---
    text = None
    for (n, va, vs, rp, rs) in img.sections:
        if n == '.text':
            text = (va, min(vs, rs), rp)
    tva, tlen, trp = text
    buf = img.buf
    sites = []
    for off in range(trp, trp + tlen - 5):
        if buf[off] != 0xE8:
            continue
        rel = struct.unpack_from('<i', buf, off + 1)[0]
        nxt = tva + (off - trp) + 5
        if nxt + rel != BASICLOG:
            continue
        call_rva = tva + (off - trp)
        # walk back up to 40 bytes disassembling to catch the two LEAs
        rec_rva = cat_rva = None
        start = max(trp, off - 40)
        for s in range(start, off):
            try:
                ins = list(md.disasm(buf[s:off + 5], tva + (s - trp)))
            except Exception:
                continue
            if not ins:
                continue
            if sum(i.size for i in ins) != (off + 5 - s):
                continue
            for i in ins:
                if i.mnemonic == 'lea' and 'rip' in i.op_str:
                    tgt = i.address + i.size + int(i.op_str.split('rip +')[-1].split(']')[0].strip(), 16) \
                        if 'rip +' in i.op_str else None
                    if tgt is None:
                        continue
                    if i.op_str.startswith('rdx'):
                        rec_rva = tgt
                    elif i.op_str.startswith('rcx'):
                        cat_rva = tgt
            break
        sites.append((call_rva, rec_rva, cat_rva))

    sys.stderr.write("BasicLog call sites in .text: %d  (record resolved: %d)\n" %
                     (len(sites), sum(1 for s in sites if s[1] in byrva)))

    # --- index by containing function ---
    byfunc = {}
    for (c, rec, cat) in sites:
        fn = containing(fns, c)
        byfunc.setdefault(fn, []).append((c, rec, cat))

    if len(sys.argv) > 1 and sys.argv[1] == '--func':
        for arg in sys.argv[2:]:
            rva = int(arg, 16)
            fn = containing(fns, rva)
            print("\n=== function containing 0x%08X: %s" %
                  (rva, ("0x%08X..0x%08X (%d B)" % (fn[0], fn[1], fn[1] - fn[0])) if fn else "NOT IN PDATA"))
            if fn:
                o = img.off(fn[0])
                body = img.buf[o:o + (fn[1] - fn[0])]
                nz = sum(1 for b in body if b)
                print("    bytes non-zero: %d/%d  (0 would mean never-executed page => negative is void)"
                      % (nz, len(body)))
            hits = byfunc.get(fn, [])
            print("    BasicLog call sites: %d" % len(hits))
            for (c, rec, cat) in hits:
                r = byrva.get(rec)
                print("      call@0x%08X rec=0x%08X cat=0x%08X %s" %
                      (c, rec or 0, cat or 0,
                       ("%s %s:%d %r" % (VERB.get(r['verb']), os.path.basename(r['file']),
                                         r['line'], r['fmt'])) if r else "<unresolved>"))
        return

    if len(sys.argv) > 1 and sys.argv[1] == '--file':
        want = sys.argv[2].lower()
        print("BasicLog sites whose record File contains %r:" % want)
        for (c, rec, cat) in sites:
            r = byrva.get(rec)
            if r and want in r['file'].lower():
                fn = containing(fns, c)
                print("  call@0x%08X in fn %s  cat=0x%08X  %s %s:%d %r" %
                      (c, ("0x%08X..0x%08X" % fn) if fn else "?", cat or 0,
                       VERB.get(r['verb']), os.path.basename(r['file']), r['line'], r['fmt']))
        return


if __name__ == '__main__':
    main()
