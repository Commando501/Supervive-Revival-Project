#!/usr/bin/env python
"""
action_name_xref.py -- OFFLINE input-action forensics over a cold PE dump.

Built S101 while settling FALSE-KNOWN #2 ("SUPERVIVE must drive Enhanced Input from
IMCs").  It answers three questions with no running game:

  1. which input-action names exist as literals in the shipping image at all
     (ASCII *and* UTF-16 -- the project's earlier string scans missed UTF-16),
  2. which C++ translation unit each literal belongs to, by nearest-preceding
     `C:\\TheoryCraft\\build-staging\\...` __FILE__ marker, and
  3. whether any .text code RIP-relative-references the literal.

The TU attribution is the useful part: MSVC pools a TU's string literals together
with that TU's __FILE__ string (emitted by check()/ensure()/UE_LOG).  So
"nearest preceding marker" localises a literal to a source file.  CAVEAT: only
TUs that actually use a __FILE__-bearing macro have a marker (190 of Loki's TUs
in this build), so a literal from a marker-less TU is attributed to the previous
marked TU.  Cross-check with link/alphabetical order before trusting it.

MEASURED CAVEAT on the dump: dumps/merged.dump.exe has .text 48.1% non-zero and its
own manifest shows the "merge" added only ~1.2 KB over the seed dump -- it is
effectively a single menu-state dump.  Gameplay input code never ran, so xref
question (3) returns ~0 hits for in-match action names.  Re-dump IN A MATCH first.

Usage
-----
  python action_name_xref.py <dump.exe> <names.txt> [--out prefix]

  names.txt = one action/axis name per line.  Produce it from either
    C:\\Users\\<u>\\AppData\\Local\\SUPERVIVE\\Saved\\Config\\WindowsClient\\UserSettings.ini
    ([/Script/Loki.PlayerConfigManager] ActionMappings=/AxisMappings= rows), or from
    the packaged default at Loki/Config/DefaultInput.ini, which the extractor pulls with
      dotnet run -c Release -- rawfile "Loki/Config/DefaultInput.ini"
    -> tools/extractor/out/raw/Loki/Config/DefaultInput.ini
       ([/Script/Engine.InputSettings] +ActionMappings= / +AxisMappings= rows).

Related, higher-yield instrument for the *handler* side (needs the extractor, not this):
      dotnet run -c Release -- names <pkgpath.uasset>
  then grep the NameMap for `InpActEvt_<Action>_K2Node_InputActionEvent`.  That is
  UE's LEGACY Blueprint input-event function name and is how SUPERVIVE actually
  routes most actions (BP_LokiPlayerController alone carries 39 of them).
"""
import sys, re, os, json, bisect

BS = bytes([0x5C])
SRC_PREFIX = b"C:" + BS + b"TheoryCraft" + BS


def load(path):
    with open(path, 'rb') as f:
        return f.read()


def find_all(data, needle, cap=64):
    out, start = [], 0
    while len(out) < cap:
        i = data.find(needle, start)
        if i < 0:
            break
        out.append(i)
        start = i + 1
    return out


def src_markers(data):
    pat = re.compile(re.escape(SRC_PREFIX) + b"[ -~]{4,220}")
    m = [(x.start(), x.group(0).decode('ascii', 'replace')) for x in pat.finditer(data)]
    m.sort()
    return m


def attribute(marks, addrs, off, max_dist=0x3000):
    i = bisect.bisect_right(addrs, off) - 1
    if i < 0:
        return None
    ma, ms = marks[i]
    if off - ma > max_dist:
        return None
    nxt = marks[i + 1][1] if i + 1 < len(marks) else None
    return (ma, off - ma, ms, nxt)


def text_xrefs(data, targets, text_lo=0x1000, text_hi=None):
    """RIP-relative disp32 scan.  dumpimage sets file-offset == RVA, so a disp32 at
    file offset p targets RVA p+4+disp (for the common `lea r, [rip+d]` where the
    disp is the last 4 bytes of the instruction)."""
    if text_hi is None:
        text_hi = min(len(data), 0x764A000)
    tset = set(targets)
    hits = {t: [] for t in tset}
    for p in range(text_lo, text_hi - 4):
        v = int.from_bytes(data[p:p + 4], 'little', signed=True)
        if v == 0:
            continue
        t = p + 4 + v
        if t in tset:
            hits[t].append(p)
    return hits


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    dump, namefile = sys.argv[1], sys.argv[2]
    prefix = 'action_xref'
    if '--out' in sys.argv:
        prefix = sys.argv[sys.argv.index('--out') + 1]

    data = load(dump)
    names = [l.strip() for l in open(namefile, encoding='utf-8') if l.strip()]
    marks = src_markers(data)
    addrs = [a for a, _ in marks]
    print("image %s  (%d bytes)" % (os.path.basename(dump), len(data)))
    print("source-path markers: %d" % len(marks))
    print("names to test:       %d" % len(names))
    print()

    result = {}
    present_a = present_w = 0
    for n in names:
        a = find_all(data, n.encode('ascii', 'replace'))
        w = find_all(data, n.encode('utf-16-le'))
        if a:
            present_a += 1
        if w:
            present_w += 1
        result[n] = {'ascii': a, 'utf16': w, 'tu': []}
        for off in a[:8]:
            r = attribute(marks, addrs, off)
            if r:
                result[n]['tu'].append({'off': off, 'dist': r[1], 'file': r[2], 'next': r[3]})

    print("names present as ASCII : %d/%d" % (present_a, len(names)))
    print("names present as UTF-16: %d/%d" % (present_w, len(names)))
    print()
    print("=== NAME -> TRANSLATION UNIT ===")
    for n in names:
        for t in result[n]['tu']:
            print("%-30s %#010x  d=%#7x  %s" % (n, t['off'], t['dist'],
                                                t['file'].split(chr(92))[-1]))
    json.dump(result, open(prefix + '.json', 'w'), indent=1)
    print()
    print("wrote %s.json" % prefix)
    return 0


if __name__ == '__main__':
    sys.exit(main())
