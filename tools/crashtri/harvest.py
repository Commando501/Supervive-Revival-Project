#!/usr/bin/env python
"""harvest.py -- READ-ONLY census of %LOCALAPPDATA%\SUPERVIVE\Saved\Crashes.

Parses every CrashContext.runtime-xml into one CSV + prints a classification of
the crash population by (faulting-module RVA chain).  Opens files 'rb' only.
Stdlib only.  Never writes into the Crashes tree.
"""
import os, re, sys, csv, io

CRASHDIR = r"C:\Users\eastr\AppData\Local\SUPERVIVE\Saved\Crashes"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "crash_census.csv")

def tag(d, t):
    m = re.search(r"<%s>(.*?)</%s>" % (t, t), d, re.S)
    return m.group(1).strip() if m else ""

def parse_pcallstack(s, exename="SUPERVIVE-Win64-Shipping"):
    """'MOD 0xBASE + RVA MOD 0xBASE + RVA ...' -> [(mod, base, rva)]"""
    out = []
    for m in re.finditer(r"(\S+)\s+0x([0-9a-fA-F]+)\s*\+\s*([0-9a-fA-F]+)", s):
        out.append((m.group(1), int(m.group(2), 16), int(m.group(3), 16)))
    return out

rows = []
for name in sorted(os.listdir(CRASHDIR)):
    p = os.path.join(CRASHDIR, name)
    xml = os.path.join(p, "CrashContext.runtime-xml")
    if not os.path.isfile(xml):
        rows.append(dict(guid=name, note="NO-XML")); continue
    with open(xml, "rb") as f:
        d = f.read().decode("utf-8", "replace")
    frames = parse_pcallstack(tag(d, "PCallStack"))
    game = [f for f in frames if f[0].lower().startswith("supervive")]
    base = game[0][1] if game else 0
    chain = " ".join("%x" % f[2] for f in game)
    rows.append(dict(
        guid=name,
        mtime=os.path.getmtime(xml),
        secs=tag(d, "SecondsSinceStart"),
        crashtype=tag(d, "CrashType"),
        err=tag(d, "ErrorMessage"),
        pid=tag(d, "ProcessId"),
        base="0x%X" % base,
        nframes=len(frames),
        frame0mod=frames[0][0] if frames else "",
        frame0=("0x%X" % (frames[0][1] + frames[0][2])) if frames else "",
        chain=chain,
        engine=tag(d, "EngineVersion"),
    ))

cols = ["guid","mtime","secs","crashtype","pid","base","frame0mod","frame0","nframes","chain","err","engine","note"]
with open(OUT, "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
    w.writeheader()
    for r in rows: w.writerow(r)

print("wrote %s  (%d crashes)" % (OUT, len(rows)))
# --- classification by chain prefix (first 3 game frames) ---
from collections import Counter, defaultdict
fam = defaultdict(list)
for r in rows:
    c = r.get("chain","")
    key = " ".join(c.split()[:3]) if c else "(no game frames)"
    fam[key].append(r)
print("\n%-3s %-58s %s" % ("n", "first-3 game RVAs", "SecondsSinceStart values"))
for k, v in sorted(fam.items(), key=lambda kv: -len(kv[1])):
    secs = sorted(int(x["secs"]) for x in v if str(x.get("secs","")).isdigit())
    print("%-3d %-58s %s" % (len(v), k, secs if len(secs) < 26 else "%d values %d..%d" % (len(secs), secs[0], secs[-1])))
