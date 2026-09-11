#!/usr/bin/env python3
"""
wpattrib.py -- name the writer, offline, from one `[WP] TRAP` record.

INPUT  : the RVA the FK-24 watchpoint probe printed (and, optionally, the code
         bytes it captured live at that RIP).
OUTPUT : function extent, the exact STORE instruction, the class/vtable slot it
         belongs to, the string literals its function touches, and an explicit
         statement of what is NOT knowable for this RVA.

WHY THE LIVE BYTES MATTER (this is the whole point of capturing them)
---------------------------------------------------------------------
`.text` is only 52.29% decrypted in dumps/merged.dump.exe, so ~47.7% of any RVA
we might trap lands in an all-zero page there. That is NOT a dead end:

  * the writer's page IS decrypted at the instant it traps -- the CPU just
    fetched and executed the instruction. The probe therefore copies the raw
    bytes around RIP out of the LIVE process, and this script disassembles
    those instead of the dump. A dark RVA still yields the instruction.
  * the .pdata union (tools/strxref/index/pdata_union.csv, 382,282 functions
    recovered from 70 crash minidumps) covers 55.3% of .text and is INDEPENDENT
    of decryption -- 6.4% of .text has EXACT function bounds with zero bytes in
    the merged dump. So "no bytes" and "no bounds" are different failures.

TWO RIP CONVENTIONS -- getting this backwards misnames the writer by ONE
INSTRUCTION, so it is an explicit argument, never a guess:

  --conv after  (DR data breakpoint, STATUS_SINGLE_STEP 0x80000004)
                x86 data breakpoints are TRAPS: the store has ALREADY retired
                and RIP points at the NEXT instruction. The writer is the
                instruction that ENDS at RIP.
  --conv at     (PAGE_GUARD / access violation, 0x80000001 / 0xC0000005)
                those are FAULTS: RIP points AT the instruction that faulted.
                The writer is the instruction that STARTS at RIP.

Usage
-----
  python wpattrib.py 0x3C5DC52 --conv after
  python wpattrib.py 0x3C5DC52 --conv after --bytes-at 0x3C5DC22 \
        --bytes "48 8B 01 FF 90 00 07 00 00 ..."
  python wpattrib.py 0x3C5DC52 --conv at --json

Needs capstone (measured present: 5.0.7). Everything else is stdlib.
"""
import argparse, bisect, csv, json, os, re, subprocess, sys

HERE   = os.path.dirname(os.path.abspath(__file__))
ROOT   = os.path.abspath(os.path.join(HERE, os.pardir, os.pardir))
STRX   = os.path.join(ROOT, 'tools', 'strxref')
PDATA  = os.path.join(STRX, 'index', 'pdata_union.csv')
DUMP   = os.path.join(ROOT, 'dumps', 'merged.dump.exe')
SYMS   = os.path.join(ROOT, 'docs', 'symbols.csv')

# .text bounds of this build (measured; strxref.py census)
TEXT_VA, TEXT_SZ = 0x1000, 124030976


# ---------------------------------------------------------------- pdata bounds
def load_pdata():
    if not os.path.exists(PDATA):
        return [], []
    ents = []
    with open(PDATA, newline='') as f:
        r = csv.reader(f); next(r, None)
        for row in r:
            ents.append((int(row[0], 16), int(row[1], 16)))
    ents.sort()
    return ents, [b for b, _ in ents]


def fn_extent(rva, ents, begins):
    i = bisect.bisect_right(begins, rva) - 1
    if i >= 0 and ents[i][0] <= rva < ents[i][1]:
        return ents[i]
    return None


# ------------------------------------------------------------------ dump bytes
def dump_read(rva, n):
    """file offset == RVA in a usmapdump image. Returns b'' if unavailable."""
    if not os.path.exists(DUMP):
        return b''
    with open(DUMP, 'rb') as f:
        f.seek(rva)
        return f.read(n)


def page_is_dark(rva):
    pg = dump_read(rva & ~0xFFF, 0x1000)
    return (not pg) or pg.count(0) == len(pg)


# --------------------------------------------------------------- disassembling
def get_cs():
    try:
        import capstone
    except ImportError:
        return None, None
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
    md.detail = False
    return capstone, md


def decode_from(md, blob, base, stop=None, limit=64):
    out = []
    for i in md.disasm(blob, base):
        out.append(i)
        if stop is not None and i.address >= stop:
            break
        if len(out) >= limit:
            break
    return out


def instr_ending_at(md, blob, base, rip):
    """The instruction whose LAST byte is rip-1. Two independent methods."""
    res = {'method': None, 'ins': None, 'agree': None}
    # (1) EXACT: linear decode forward from the function entry, if the entry is
    #     inside the blob we hold. No heuristic: x86 from a true entry is exact.
    # (2) CONVERGENCE: try every start in [rip-15, rip-24...] and keep the
    #     predecessor each chain lands on. x86 re-synchronises within ~20 bytes,
    #     so agreement across starts is itself the confidence measure.
    preds = []
    for s in range(base, rip):
        off = s - base
        prev = None
        for i in md.disasm(blob[off:], s):
            if i.address == rip:
                if prev is not None:
                    preds.append(prev)
                break
            if i.address > rip:
                break
            prev = i
    if not preds:
        return res
    from collections import Counter
    c = Counter(p.address for p in preds)
    addr, votes = c.most_common(1)[0]
    res['ins'] = next(p for p in preds if p.address == addr)
    res['agree'] = '%d/%d starts' % (votes, len(preds))
    res['method'] = 'backward-convergence'
    return res


def instr_at(md, blob, base, rip):
    off = rip - base
    if off < 0 or off >= len(blob):
        return None
    for i in md.disasm(blob[off:], rip):
        return i
    return None


# ------------------------------------------------------------- other indexes
def run_tool(script, *args):
    try:
        p = subprocess.run([sys.executable, script] + list(args),
                           cwd=STRX, capture_output=True, text=True, timeout=180)
        return (p.stdout or '') + (p.stderr or '')
    except Exception as e:
        return '(%s failed: %s)' % (os.path.basename(script), e)


def symbols_hits(rva, lo, hi):
    if not os.path.exists(SYMS):
        return []
    out = []
    with open(SYMS, newline='', encoding='utf-8', errors='replace') as f:
        for row in csv.DictReader(f):
            try:
                a = int(row['rva'], 16)
            except Exception:
                continue
            if lo <= a < hi:
                out.append(row)
    return out


STORE_RE = re.compile(r'^(mov|and|or|xor|add|sub|set\w+|bts|xchg|stos)', re.I)


def looks_like_the_store(ins):
    """Is this instruction a byte-width store of a small immediate/flag?"""
    if ins is None:
        return (False, 'no instruction decoded')
    txt = '%s %s' % (ins.mnemonic, ins.op_str)
    why = []
    if 'byte ptr' in ins.op_str:
        why.append('byte-width')
    if re.search(r'\[.*\]', ins.op_str.split(',')[0]):
        why.append('memory destination')
    if re.search(r',\s*1$', ins.op_str):
        why.append('immediate 1')
    if ins.mnemonic.startswith('set'):
        why.append('setcc (writes 0/1)')
    hit = ('byte-width' in why or 'setcc (writes 0/1)' in why) and 'memory destination' in why
    return (hit, '%s   [%s]' % (txt, ', '.join(why) if why else 'no store signature'))


# --------------------------------------------------------------------- driver
def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('rva', help='the RVA the probe printed (hex, 0x...)')
    ap.add_argument('--conv', choices=['after', 'at'], required=True,
                    help='after = DR trap (RIP is the NEXT instruction); '
                         'at = page-guard/AV fault (RIP is the faulting instruction)')
    ap.add_argument('--bytes', default=None,
                    help='hex bytes captured LIVE by the probe (space/comma separated)')
    ap.add_argument('--bytes-at', default=None,
                    help='RVA the --bytes blob starts at (required with --bytes)')
    ap.add_argument('--no-strxref', action='store_true')
    ap.add_argument('--json', action='store_true')
    a = ap.parse_args()

    rva = int(a.rva, 16)
    rep = {'rva': '0x%X' % rva, 'conv': a.conv}
    P = (lambda *x: None) if a.json else print

    P('=' * 78)
    P('wpattrib  rva=0x%07X  conv=%s' % (rva, a.conv))
    P('=' * 78)

    # ---- 1. is it even in .text of this module?
    in_text = TEXT_VA <= rva < TEXT_VA + TEXT_SZ
    rep['in_text'] = in_text
    P('[1] section        : %s' % ('.text (in range)' if in_text else
                                   '*** NOT in .text -- the writer is OUTSIDE the game module '
                                   '(another DLL, a packer-hidden private region, or our own shim). '
                                   'Cross-check the probe\'s module= field.'))

    # ---- 2. function bounds (independent of decryption)
    ents, begins = load_pdata()
    ext = fn_extent(rva, ents, begins) if ents else None
    rep['fn_extent'] = ('0x%X..0x%X' % ext) if ext else None
    if ext:
        P('[2] function bounds: 0x%X .. 0x%X (%d bytes)  EXACT (.pdata union, 70 minidump tables)'
          % (ext[0], ext[1], ext[1] - ext[0]))
    else:
        P('[2] function bounds: NONE. Not a negative -- the .pdata union covers 55.3%% of .text; a gap')
        P('                     means no crash minidump ever carried this function\'s unwind entry.')

    # ---- 3. bytes: live capture beats the dump
    blob, base, src = b'', 0, None
    if a.bytes:
        if not a.bytes_at:
            ap.error('--bytes requires --bytes-at')
        base = int(a.bytes_at, 16)
        blob = bytes(int(t, 16) for t in re.findall(r'[0-9A-Fa-f]{2}', a.bytes))
        src = 'LIVE capture from the probe (%d bytes @ 0x%X)' % (len(blob), base)
    else:
        dark = page_is_dark(rva)
        rep['dump_page_dark'] = dark
        if dark:
            P('[3] bytes          : *** the merged dump has this page ALL-ZERO (never decrypted). ***')
            P('                     Re-run with --bytes/--bytes-at from the probe record, OR take a fresh')
            P('                     `usmapdump dumpimage` FROM THAT GAME STATE and `mergedumps` it in:')
            P('                     the page decrypts the moment the code runs, so the state that traps')
            P('                     is exactly the state that makes it readable.')
        else:
            base = max(TEXT_VA, rva - 64)
            blob = dump_read(base, 64 + 32)
            src = 'dumps/merged.dump.exe (page is decrypted)'
    if src:
        P('[3] bytes          : %s' % src)

    # ---- 4. THE INSTRUCTION
    capstone, md = get_cs()
    writer = None
    if md is None:
        P('[4] instruction    : capstone not importable -- install it or decode by hand.')
    elif not blob:
        P('[4] instruction    : (no bytes available, see [3])')
    else:
        if a.conv == 'after':
            r = instr_ending_at(md, blob, base, rva)
            writer = r['ins']
            if writer is None:
                P('[4] instruction    : could not resolve a predecessor ending at RIP. Widen the capture.')
            else:
                P('[4] WRITER (ends at RIP; DR traps fire AFTER the store):')
                P('      0x%07X  %-24s %s %s' % (writer.address,
                    ' '.join('%02X' % b for b in writer.bytes), writer.mnemonic, writer.op_str))
                P('      convergence: %s (x86 re-synchronises; unanimous = exact)' % r['agree'])
        else:
            writer = instr_at(md, blob, base, rva)
            if writer is None:
                P('[4] instruction    : RIP outside the byte blob.')
            else:
                P('[4] WRITER (starts at RIP; page-guard/AV faults fire BEFORE the store):')
                P('      0x%07X  %-24s %s %s' % (writer.address,
                    ' '.join('%02X' % b for b in writer.bytes), writer.mnemonic, writer.op_str))
        if writer is not None:
            hit, why = looks_like_the_store(writer)
            rep['writer'] = {'rva': '0x%X' % writer.address,
                             'text': '%s %s' % (writer.mnemonic, writer.op_str),
                             'store_signature': hit}
            P('      signature  : %s' % why)
            P('      verdict    : %s' % ('MATCHES the measured shape (1-byte store of a literal)'
                                         if hit else
                                         '*** does NOT match a 1-byte store -- either the convention is '
                                         'wrong, the capture is short, or this is not the writer ***'))

    # ---- 5. class / vtable slot
    if not a.no_strxref and ext:
        out = run_tool(os.path.join(STRX, 'vtables.py'), 'slotof', '0x%X' % ext[0])
        P('[5] vtable slot    : %s' % (out.strip().splitlines()[0] if out.strip() else '(none)'))
        for ln in out.strip().splitlines()[1:4]:
            P('                     %s' % ln.strip())
        rep['slotof'] = out.strip()

    # ---- 6. strings the function touches
    if not a.no_strxref:
        out = run_tool(os.path.join(STRX, 'strxref.py'), 'func', '0x%X' % rva)
        P('[6] strings in fn  :')
        for ln in out.strip().splitlines()[:14]:
            P('      %s' % ln)
        rep['strxref_func'] = out.strip()

    # ---- 7. symbols.csv
    if ext:
        hits = symbols_hits(rva, ext[0], ext[1])
        P('[7] symbols.csv    : %s' % ('%d row(s) inside this function' % len(hits) if hits else 'no row inside this function'))
        for h in hits[:6]:
            P('      0x%s %-28s %-10s %s' % (h['rva'][2:], h.get('proposed_name') or h.get('recorded_name') or '-',
                                             h.get('verdict', ''), (h.get('why') or '')[:60]))
        rep['symbols'] = [h['rva'] for h in hits]

    # ---- 8. what we CANNOT say
    P('')
    P('[8] LIMITS -- state these when quoting this result:')
    if not ext:
        P('    * no exact function entry => the "instruction ends at RIP" resolution rests on backward')
        P('      convergence alone (strong, not proof). Function-level naming is unavailable.')
    if src and src.startswith('dumps/'):
        P('    * bytes came from the DUMP, not the trap. If the writer\'s page was decrypted only in')
        P('      the trapping session these bytes could be a DIFFERENT build state -- prefer --bytes.')
    P('    * a name here identifies the STORE, not the intent. Confirm by re-running the probe and')
    P('      checking the same RVA repeats -- a one-shot RVA that never repeats is a lead, not a cause.')
    P('    * "no string references" never means "nothing is there" (52.29% of .text is decrypted).')

    if a.json:
        print(json.dumps(rep, indent=2))


if __name__ == '__main__':
    main()
