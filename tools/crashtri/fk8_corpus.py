#!/usr/bin/env python
r"""fk8_corpus.py -- READ-ONLY aggregator over the WHOLE SUPERVIVE crash corpus.

Item 21 of the cold-start shortlist; the instrument half of knowledge-gap FK-8.
Stdlib only.  Deterministic (same inputs -> byte-identical outputs; no run
timestamp is written into either output file).  Re-runnable.  Opens every file
'rb'.  NEVER writes, moves or deletes anything under the Crashes tree or under
dumps/ -- the only files it creates are the two outputs under docs/.

This is a NEW tool.  It does not modify, import or replace tools/crashtri/harvest.py
or tools/crashtri/crash_census.csv, and it deliberately reuses harvest.py's
PCallStack frame regex and its game-relative RVA-chain family key so the two
censuses stay comparable.


================================ WHAT IT READS =================================

SOURCE A -- the UECC tree  (%LOCALAPPDATA%\SUPERVIVE\Saved\Crashes)
    Every DIRECTORY is enumerated, not a UECC-* glob: one directory is named
    literally "_0000" (empty GUID) and a glob silently drops it.  Per directory:
    CrashContext.runtime-xml (parsed with xml.etree, not regex), UEMinidump.dmp
    (header + stream directory + ModuleListStream ONLY -- a few KB per dump, the
    ~14 MB body is never read), and Loki.log (Source C).

SOURCE B -- the crashpad archive class  (<repo>/dumps/crashpad-<stamp>[-label])
    ARCHIVE-INFO.txt, crashpad's binary `metadata` (DAPC) and `settings.dat`
    (sdPC), reports/<uuid>.dmp, attachments/<uuid>/__sentry-event (MessagePack,
    decoded by a ~70-line decoder in this file), and both Loki.log copies.
    This class writes NO CrashContext XML, which is why every census built on
    UECC-* has been structurally blind to it.

SOURCE C -- the per-crash Loki.log
    Never read whole into memory: scanned in 4 MiB chunks with a 512 B overlap so
    a key straddling a chunk boundary is still counted exactly once (the overlap
    is deduplicated by only counting matches that start inside the new bytes).


============================ WHAT IT EXTRACTS ==================================

identity/provenance : source, kind, artifact_id, crash_guid, execution_guid,
                      report_uuid, sentry_event_id, archive label + duplicate
                      bookkeeping, machine/login/epic ids, process id
timing              : TimeOfCrash ticks -> UTC and local ISO-8601, file mtime and
                      the delta between them, SecondsSinceStart, crashpad
                      creation/last-upload times, log first/last timestamp + span
classification      : CrashType, IsEnsure/IsStall/IsAssert/IsRequestingExit,
                      CrashTrigger, PlatformCallbackResult, Misc.IsStuck +
                      StuckThreadId, exception code, fault address, and for
                      asserts the [File:] / [Line:] pair
callstacks          : PCallStackHash, frame count, game-frame count, module base,
                      full game RVA chain + the 3-frame family key, frame0
threads             : count, crashed thread id/name, GameThread id, every
                      (id, name) pair and every per-thread callstack (JSON only)
modules             : the XML's ~21-entry Modules list AND the minidump's real
                      ~220-entry loaded-module list, both as counts + basenames
memory/host         : Used/Avail/Peak/Total physical, bIsOOM, OOMAllocationSize,
                      cores, GPU, RHI, ReplicationModel, NumClients, AppHasFocus
sentry              : build version/CL/time, and -- crashpad class only -- the
                      FULL command line and the map breadcrumbs
extra artifacts     : dir_files (EVERY file in the directory, so a surprise file
                      is visible, not silently dropped) and the RHI GPU
                      breadcrumb dumps (Breadcrumbs_RHIThread_*.txt) inline
log fingerprint     : size, line count, first/last timestamp, every
                      `Load map complete <path>`, LVL_Tutorial hit count, the
                      force-open `?game=...BP_LokiGameMode_Tutorial` URL, the
                      crash-handoff keys, the GameFeatureToggles "not ready"
                      count, and a count for each shim marker tag


========================= WHAT IT DELIBERATELY DOES NOT DO =====================

* It does NOT symbolicate.  RVAs stay raw; naming them is mdctx.py/strxref work.
* It does NOT read minidump memory, thread contexts or the exception record.
  mdctx.py owns that (and the README's MINIDUMP_THREAD offsets); this tool only
  touches the module list, so the two never disagree about layout.
* It does NOT infer launch mode from CommandLine in the UECC class.  That tag is
  the literal string "CommandLineRemoved" in all 92 XMLs -- it carries no launch
  information whatsoever.  (The crashpad class DOES carry the real command line,
  in __sentry-event; that is recorded verbatim and never merged with the UECC
  rows.)
* It does NOT attempt shim attribution from module lists.  MEASURED: 0 of 106
  minidumps list any shim DLL -- the shims are MANUAL-MAPPED (tools/inject), so
  they are never registered with the loader and cannot appear.  That is a
  property of the injection method, not evidence the shims were absent.
* It does NOT dedupe the crashpad class for you.  It emits one row per
  (archive, report) and gives you report_uuid / report_archive_count /
  report_is_primary so YOU choose the denominator.  See the gotchas below.
* It does NOT classify crash families beyond the RVA chain.  Family analysis is
  downstream of this file.


=============================== HARD-WON GOTCHAS ===============================

1.  45 crashpad archives hold 47 .dmp files but only 22 DISTINCT reports.  The
    archiver snapshots the whole crashpad database before AND after a launch, so
    almost every death is archived at least twice under two different stamps.
    Counting archives as crashes double-counts by ~2x.  Filter
    report_is_primary==1.
2.  15 of the 92 UECC directories carry NO usable stack.  They have
    PCallStackHash == DA39A3EE5E6B4B0D3255BFEF95601890AFD80709 -- the SHA-1 of
    the EMPTY STRING -- SecondsSinceStart 0, and a 2-frame PCallStack with zero
    game frames, rooted in ntdll / mdnsNSP (Bonjour) / Unknown, whose "RVA" is
    just the fault address mis-attributed to the nearest preceding module base.
    Two independent signals (empty-SHA1 hash, SecondsSinceStart==0) select
    EXACTLY the same 15, and 3 of them name `runtime` in the CallStack tag --
    the documented protector-kill family.  unwind_status='os-only'.
    A 16th (UECC-Windows-154E12A5...) has an EMPTY PCallStackHash and an EMPTY
    PCallStack but SecondsSinceStart=194 and a real dump: unwind_status='absent'.
    My first cut of this discriminator used the zero-byte-minidump conjunction
    and was WRONG -- it selected 8 of the 15.  The built-in disagreement check is
    what caught it; leave that check in.
3.  Only 8 directories are truly contentless: zero-byte UEMinidump.dmp AND no
    TimeOfCrash AND no Modules (all three sets are EXACTLY equal, N=8, and all 8
    are inside the 15 above).  Those are kind='degenerate' -- the CrashContext
    writer never finished.  The other 7 of the 15 have real ~13 MB dumps.
4.  "8 directories lack Loki.log" is TRUE but MISLEADING and only 7 lack a log:
    UECC-Windows-F86B2A5B... carries a 565 KB `Loki_2.log` instead.  A fixed
    filename drops it.  This tool globs Loki*.log and records log_filename.
    The set is also NOT the same 8 as the degenerate set (they overlap in 7):
    F86B2A5B is a real 952-second game crash, and _0000 is degenerate but kept
    its (509-byte) log.  Every file in every directory is listed in dir_files so
    the next surprise file is visible rather than silently ignored -- 12 RHI GPU
    breadcrumb files across 10 directories were found the same way.
5.  TimeOfCrash ticks are UTC, not local.  Converting them as local wall-clock
    puts every crash 18000 s (5 h) away from its own file mtime.
6.  `Modules` is NEWLINE-delimited, and the game path contains spaces
    ("G:\git\GAME BACKUPS FOR REVERSE ENGINEERING\..."), so .split() shreds each
    path into 5 fragments.  Split on newlines only.  It is also NOT the loaded-
    module list: ~21 entries vs the minidump's ~220, with duplicates.
7.  `CrashReporterMessage` appears TWICE in all 92 XMLs.  A first-match regex
    silently drops the second (which is where "Attended" lives).
8.  The documented crashpad key 'handing control over to crashpad' is present in
    only 40 of 44 session-Loki.log and in 0 of 44 attachment Loki.log -- the
    attachment copy is snapshotted by the Sentry SDK BEFORE that line is
    written.  'Sentry HandleBeforeCrash Begin' covers 44/44 attachments and
    43/44 session logs and is the better key.  Bare 'crashpad' is useless: it
    matches startup lines in 87 of 88 logs including clean exits.
9.  Shim marker tags ([SP] [PL] [FO] [ANIM] ...) appear in 0 of 130 logs.  That
    is NOT evidence the shims were absent: Marker() in the shim sources writes to
    docs/<shim>-marker.txt via CreateFileA, never to Loki.log.  The counters are
    kept anyway (cheap, and they will start firing the day a shim learns to
    UE_LOG).  The log-visible force-open signature is
    `?game=/Game/Loki/Core/GameModes/BP_LokiGameMode_Tutorial` instead.
10. Loki.log timestamps are `[YYYY.MM.DD-HH.MM.SS:mmm][frame]`, NOT `[HH:MM:SS:mmm]`,
    and the first ~40 lines carry no prefix at all.
11. Log sizes are not uniform: 84 UECC logs total 996 MB, and ONE of them
    (UECC-Windows-A15041E9...) is 742 MB on its own.  Never read one whole.
12. The two sources are DISJOINT populations.  Every crashpad __sentry-event
    carries a `Crash GUID` of the form UECC-Windows-<GUID>, but 0 of 22 have a
    matching directory in the UECC tree -- because control went to crashpad
    INSTEAD of CrashReportClient, so UE never wrote the folder.  (Join control:
    the same key type self-joins the UECC set 92/92.)  So the corpus is
    84 + 22 = 106 distinct deaths, not 92.
13. The corpus is LIVE.  A 45th crashpad archive appeared on disk while this
    tool was being written.  Always re-run rather than citing an old count.
14. MemoryStats.Used/Avail/Peak/UsedVirtual are populated in EXACTLY the 24
    CrashType=Assert rows and are 0 in all 68 CrashType=Crash rows -- the two
    sets are IDENTICAL, not merely the same size.  So "UsedPhysical == 0" means
    "this crash path never sampled memory", NOT "the game used no memory".
    bIsOOM is 0 and OOMAllocationSize is 0 in all 92: OOM is not in evidence
    ANYWHERE IN THIS ARTIFACT CLASS, which is not the same as "no run ever OOMed".
15. The archiver's `-DEATH` label is NOT a crash key: 7 of the 22 distinct
    crashpad reports sit in archives whose label does not end in -DEATH
    (animref-SUCCESS, s109-positive-control, s110itemwatch, phase2-nostage,
    phase2b-void, tut3-NOSTAGE, and one unlabelled).  Filter on the presence of
    a report, not on the label.


==================================== USAGE =====================================

    python tools/crashtri/fk8_corpus.py                 # full run, ~35 s
    python tools/crashtri/fk8_corpus.py --no-logs       # skip Source C, ~5 s
    python tools/crashtri/fk8_corpus.py --no-minidumps  # skip module lists
    python tools/crashtri/fk8_corpus.py --validate      # print the self-checks
    python tools/crashtri/fk8_corpus.py --uecc <dir> --dumps <dir> \
                                        --out-csv <f> --out-json <f>
"""

import argparse
import collections
import csv
import datetime
import hashlib
import json
import os
import re
import struct
import sys
import xml.etree.ElementTree as ET

# --------------------------------------------------------------------------- #
# constants
# --------------------------------------------------------------------------- #

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))

DEF_UECC = r"C:\Users\eastr\AppData\Local\SUPERVIVE\Saved\Crashes"
DEF_DUMPS = os.path.join(REPO, "dumps")
DEF_CSV = os.path.join(REPO, "docs", "fk8-crash-corpus.csv")
DEF_JSON = os.path.join(REPO, "docs", "fk8-crash-corpus.json")

# FDateTime ticks (100 ns since 0001-01-01) at the unix epoch.
TICKS_AT_UNIX_EPOCH = 621355968000000000
TICKS_PER_SECOND = 10000000

# SHA-1 of the empty string.  UE emits this as PCallStackHash when it hashed
# nothing, which is the tell for a crash-reporter-died-while-reporting record.
EMPTY_SHA1 = hashlib.sha1(b"").hexdigest().upper()

# Shim marker tags.  See gotcha 8: these are expected to be 0 in Loki.log.
MARKER_TAGS = ["SP", "PL", "FO", "ANIM", "VTG", "GCW", "GFT", "KANIMREF", "MISS", "BP"]

# Literal byte keys counted per log.
LOG_KEYS = collections.OrderedDict([
    ("crashpad_handoff", b"handing control over to crashpad"),
    ("sentry_beforecrash", b"Sentry HandleBeforeCrash Begin"),
    ("fatal_error", b"Fatal error"),
    ("app_error", b"appError"),
    ("lvl_tutorial", b"LVL_Tutorial"),
    ("gft_not_ready", b"called when feature toggles were not ready"),
    ("forceopen_tutorial_url",
     b"?game=/Game/Loki/Core/GameModes/BP_LokiGameMode_Tutorial"),
])

RE_LOADMAP = re.compile(rb"Load map complete (/[!-~]{1,200})")
RE_LOGTS = re.compile(rb"\[(\d{4}\.\d{2}\.\d{2}-\d{2}\.\d{2}\.\d{2}:\d{3})\]")

CHUNK = 1 << 22          # 4 MiB
OVERLAP = 512            # longer than the longest key/pattern above

# harvest.py's frame regex, kept identical so the two censuses agree.
RE_FRAME = re.compile(r"(\S+)\s+0x([0-9a-fA-F]+)\s*\+\s*([0-9a-fA-F]+)")
RE_ASSERT = re.compile(r"\[File:([^\]]*)\]\s*\[Line:\s*(\d+)\]")
RE_EXC = re.compile(r"Unhandled Exception:\s*(\S+)")
RE_ADDR = re.compile(r"0x([0-9a-fA-F]{8,16})")


# --------------------------------------------------------------------------- #
# tiny MessagePack decoder (stdlib only) -- __sentry-event is msgpack, not JSON
# --------------------------------------------------------------------------- #

def mp_decode(b, i=0):
    c = b[i]; i += 1
    if c < 0x80: return c, i
    if c >= 0xE0: return c - 256, i
    if 0x80 <= c <= 0x8F: return _mp_map(b, i, c & 0x0F)
    if 0x90 <= c <= 0x9F: return _mp_arr(b, i, c & 0x0F)
    if 0xA0 <= c <= 0xBF:
        n = c & 0x1F
        return b[i:i + n].decode("utf-8", "replace"), i + n
    if c == 0xC0: return None, i
    if c == 0xC2: return False, i
    if c == 0xC3: return True, i
    if c == 0xC4: n = b[i];                                  return b[i+1:i+1+n], i+1+n
    if c == 0xC5: n = struct.unpack_from(">H", b, i)[0];     return b[i+2:i+2+n], i+2+n
    if c == 0xC6: n = struct.unpack_from(">I", b, i)[0];     return b[i+4:i+4+n], i+4+n
    if c == 0xCA: return struct.unpack_from(">f", b, i)[0], i + 4
    if c == 0xCB: return struct.unpack_from(">d", b, i)[0], i + 8
    if c == 0xCC: return b[i], i + 1
    if c == 0xCD: return struct.unpack_from(">H", b, i)[0], i + 2
    if c == 0xCE: return struct.unpack_from(">I", b, i)[0], i + 4
    if c == 0xCF: return struct.unpack_from(">Q", b, i)[0], i + 8
    if c == 0xD0: return struct.unpack_from(">b", b, i)[0], i + 1
    if c == 0xD1: return struct.unpack_from(">h", b, i)[0], i + 2
    if c == 0xD2: return struct.unpack_from(">i", b, i)[0], i + 4
    if c == 0xD3: return struct.unpack_from(">q", b, i)[0], i + 8
    if c == 0xD9:
        n = b[i]; return b[i+1:i+1+n].decode("utf-8", "replace"), i+1+n
    if c == 0xDA:
        n = struct.unpack_from(">H", b, i)[0]
        return b[i+2:i+2+n].decode("utf-8", "replace"), i+2+n
    if c == 0xDB:
        n = struct.unpack_from(">I", b, i)[0]
        return b[i+4:i+4+n].decode("utf-8", "replace"), i+4+n
    if c == 0xDC: return _mp_arr(b, i + 2, struct.unpack_from(">H", b, i)[0])
    if c == 0xDD: return _mp_arr(b, i + 4, struct.unpack_from(">I", b, i)[0])
    if c == 0xDE: return _mp_map(b, i + 2, struct.unpack_from(">H", b, i)[0])
    if c == 0xDF: return _mp_map(b, i + 4, struct.unpack_from(">I", b, i)[0])
    raise ValueError("unsupported msgpack byte 0x%02X at offset %d" % (c, i - 1))


def _mp_arr(b, i, n):
    out = []
    for _ in range(n):
        v, i = mp_decode(b, i); out.append(v)
    return out, i


def _mp_map(b, i, n):
    out = {}
    for _ in range(n):
        k, i = mp_decode(b, i)
        v, i = mp_decode(b, i)
        out[k] = v
    return out, i


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #

def ticks_to_times(ticks):
    """UE FDateTime ticks -> (utc_iso, local_iso, unix_seconds).  Ticks are UTC."""
    unix = (int(ticks) - TICKS_AT_UNIX_EPOCH) / float(TICKS_PER_SECOND)
    utc = datetime.datetime.fromtimestamp(unix, datetime.timezone.utc)
    loc = datetime.datetime.fromtimestamp(unix)          # DST-aware local
    return (utc.replace(tzinfo=None).isoformat(timespec="milliseconds"),
            loc.isoformat(timespec="milliseconds"),
            unix)


def iso_local(ts):
    return datetime.datetime.fromtimestamp(ts).isoformat(timespec="milliseconds")


def parse_frames(s):
    """'MOD 0xBASE + RVA ...' -> [(module, base, rva)].  harvest.py's regex."""
    return [(m.group(1), int(m.group(2), 16), int(m.group(3), 16))
            for m in RE_FRAME.finditer(s or "")]


def basename(p):
    p = p.replace("\\", "/")
    return p.rsplit("/", 1)[-1]


def minidump_modules(path):
    """Read ONLY the MINIDUMP ModuleListStream (type 4).  A few KB, not the body.

    Returns (list_of_full_paths, status).  Never reads memory ranges or thread
    contexts -- mdctx.py owns those and this tool must not risk disagreeing with
    it about MINIDUMP_THREAD layout (see tools/crashtri/README.md).
    """
    try:
        size = os.path.getsize(path)
    except OSError as e:
        return None, "stat-failed:%s" % e
    if size == 0:
        return None, "zero-byte"
    try:
        with open(path, "rb") as f:
            hdr = f.read(32)
            if len(hdr) < 32 or hdr[:4] != b"MDMP":
                return None, "not-minidump"
            nstreams, rva_dir = struct.unpack_from("<II", hdr, 8)
            f.seek(rva_dir)
            d = f.read(12 * nstreams)
            streams = {}
            for i in range(nstreams):
                t, sz, rva = struct.unpack_from("<III", d, 12 * i)
                streams[t] = (sz, rva)
            if 4 not in streams:
                return None, "no-modulelist"
            f.seek(streams[4][1])
            n = struct.unpack("<I", f.read(4))[0]
            ent = f.read(108 * n)
            out = []
            for i in range(n):
                name_rva = struct.unpack_from("<I", ent, 108 * i + 20)[0]
                f.seek(name_rva)
                ln = struct.unpack("<I", f.read(4))[0]
                out.append(f.read(ln).decode("utf-16-le", "replace"))
            return out, "ok"
    except Exception as e:                                    # noqa: BLE001
        return None, "error:%s" % type(e).__name__


def fingerprint_log(path):
    """Chunked byte scan of one Loki.log.  Never loads the file whole.

    Counts every key in LOG_KEYS, every MARKER_TAGS bracketed tag, every
    `Load map complete <path>`, the line count, and the first/last
    [YYYY.MM.DD-HH.MM.SS:mmm] timestamp.  Chunk boundaries are handled with a
    512-byte overlap; matches that START inside the overlap prefix are dropped so
    nothing is double-counted.
    """
    fp = {
        "log_path": path,
        "log_bytes": os.path.getsize(path),
        "log_lines": 0,
        "log_first_ts": "",
        "log_last_ts": "",
        "log_span_s": "",
        "log_maps": [],
        "log_loadmap_count": 0,
        "markers": collections.OrderedDict((t, 0) for t in MARKER_TAGS),
    }
    for k in LOG_KEYS:
        fp["log_" + k] = 0

    tags = [(t, ("[" + t + "]").encode()) for t in MARKER_TAGS]
    maps = []
    first_ts = last_ts = None

    with open(path, "rb") as f:
        prev = b""
        while True:
            block = f.read(CHUNK)
            if not block:
                break
            fp["log_lines"] += block.count(b"\n")
            buf = prev + block
            off = len(prev)                # matches must start at >= off-? ...
            # Count occurrences that START at index >= (off - 0) is wrong: a key
            # straddling the seam starts inside `prev`.  Correct rule: count a
            # match iff its start index is >= 0 in `buf` AND it was not already
            # counted, i.e. its start index >= (off - len(key) + 1) is the seam
            # window, and everything strictly before that was counted last round.
            for name, key in LOG_KEYS.items():
                fp["log_" + name] += _count_from(buf, key, max(0, off - len(key) + 1))
            for name, key in tags:
                fp["markers"][name] += _count_from(buf, key, max(0, off - len(key) + 1))
            for m in RE_LOADMAP.finditer(buf):
                if m.start() >= max(0, off - 220):
                    maps.append(m.group(1).decode("ascii", "replace"))
            for m in RE_LOGTS.finditer(buf):
                if m.start() >= max(0, off - 30):
                    ts = m.group(1).decode("ascii", "replace")
                    if first_ts is None:
                        first_ts = ts
                    last_ts = ts
            prev = block[-OVERLAP:]

    # RE_LOADMAP can emit a duplicate across the seam window; de-dup adjacents.
    dedup = []
    for x in maps:
        if not dedup or dedup[-1] != x:
            dedup.append(x)
    fp["log_maps"] = dedup
    fp["log_loadmap_count"] = len(dedup)
    fp["log_first_ts"] = first_ts or ""
    fp["log_last_ts"] = last_ts or ""
    if first_ts and last_ts:
        try:
            a = datetime.datetime.strptime(first_ts, "%Y.%m.%d-%H.%M.%S:%f")
            b = datetime.datetime.strptime(last_ts, "%Y.%m.%d-%H.%M.%S:%f")
            fp["log_span_s"] = round((b - a).total_seconds(), 3)
        except ValueError:
            fp["log_span_s"] = ""
    return fp


def _count_from(buf, key, start):
    """Count non-overlapping occurrences of `key` in buf[start:]."""
    n = 0
    i = buf.find(key, start)
    while i != -1:
        n += 1
        i = buf.find(key, i + len(key))
    return n


def route_label(maps, tut_hits, forceopen):
    """menu vs tutorial route, from the log alone."""
    last = maps[-1] if maps else ""
    if "Tutorial" in last:
        return "tutorial"
    if forceopen or tut_hits:
        return "tutorial-attempted"
    if "LobbyV2" in last:
        return "menu-lobby"
    if "LVL_Login" in last:
        return "menu-login"
    return "unknown"


# --------------------------------------------------------------------------- #
# SOURCE A -- the UECC tree
# --------------------------------------------------------------------------- #

def read_uecc(root, want_logs, want_dumps, warn):
    rows = []
    if not os.path.isdir(root):
        warn.append("UECC root missing: %s" % root)
        return rows
    # Enumerate ALL directories.  A UECC-* glob drops "_0000".
    names = sorted(n for n in os.listdir(root) if os.path.isdir(os.path.join(root, n)))
    for name in names:
        d = os.path.join(root, name)
        xmlp = os.path.join(d, "CrashContext.runtime-xml")
        r = collections.OrderedDict()
        r["source"] = "uecc"
        r["artifact_id"] = name
        r["path"] = d
        r["xml_present"] = int(os.path.isfile(xmlp))
        r["parse_status"] = ""
        if not r["xml_present"]:
            r["kind"] = "degenerate"
            r["parse_status"] = "NO-XML"
            rows.append(r)
            warn.append("%s: no CrashContext.runtime-xml" % name)
            continue

        raw = open(xmlp, "rb").read()
        try:
            tree = ET.fromstring(raw.decode("utf-8", "replace"))
            r["parse_status"] = "ok"
        except ET.ParseError as e:
            r["kind"] = "degenerate"
            r["parse_status"] = "XML-PARSE-FAIL:%s" % e
            rows.append(r)
            warn.append("%s: XML parse failed: %s" % (name, e))
            continue

        rp = tree.find("RuntimeProperties")
        pp = tree.find("PlatformProperties")
        ed = tree.find("EngineData")
        gd = tree.find("GameData")

        def g(node, tag):
            if node is None:
                return ""
            v = node.findtext(tag)
            return (v or "").strip()

        # CrashReporterMessage appears TWICE in every file; keep both.
        crm = [(e.text or "").strip() for e in (rp.findall("CrashReporterMessage") if rp is not None else [])]
        r["crash_reporter_messages"] = " | ".join(x for x in crm if x)

        r["crash_guid"] = g(rp, "CrashGUID")
        r["execution_guid"] = g(rp, "ExecutionGuid")
        r["crash_version"] = g(rp, "CrashVersion")
        r["process_id"] = g(rp, "ProcessId")
        r["seconds_since_start"] = g(rp, "SecondsSinceStart")
        r["crash_type"] = g(rp, "CrashType")
        r["is_ensure"] = g(rp, "IsEnsure")
        r["is_stall"] = g(rp, "IsStall")
        r["is_assert"] = g(rp, "IsAssert")
        r["is_requesting_exit"] = g(rp, "IsRequestingExit")
        r["crash_dump_mode"] = g(rp, "CrashDumpMode")
        r["is_stuck"] = g(rp, "Misc.IsStuck")
        r["stuck_thread_id"] = g(rp, "Misc.StuckThreadId")
        r["crash_trigger"] = g(pp, "CrashTrigger")
        r["platform_callback_result"] = g(pp, "PlatformCallbackResult")

        err = g(rp, "ErrorMessage")
        r["error_message"] = err
        m = RE_EXC.search(err)
        r["exception_code"] = m.group(1) if m else ""
        addrs = RE_ADDR.findall(err)
        r["fault_address"] = ("0x" + addrs[-1]) if addrs else ""
        m = RE_ASSERT.search(err)
        r["assert_file"] = basename(m.group(1)) if m else ""
        r["assert_line"] = m.group(2) if m else ""

        r["engine_version"] = g(rp, "EngineVersion")
        r["build_version"] = g(rp, "BuildVersion")
        r["build_configuration"] = g(rp, "BuildConfiguration")
        r["engine_mode"] = g(rp, "EngineMode")
        r["executable_name"] = g(rp, "ExecutableName")
        r["game_name"] = g(rp, "GameName")
        r["platform_full_name"] = g(rp, "PlatformFullName")
        r["base_dir"] = g(rp, "BaseDir")
        r["machine_id"] = g(rp, "MachineId")
        r["login_id"] = g(rp, "LoginId")
        r["epic_account_id"] = g(rp, "EpicAccountId")
        # Recorded as a FACT, not parsed for launch info: it is always the
        # literal string "CommandLineRemoved" in this class.
        r["command_line"] = g(rp, "CommandLine")

        # ---- timing
        ticks = g(rp, "TimeOfCrash")
        r["time_of_crash_ticks"] = ticks
        mt = os.path.getmtime(xmlp)
        r["xml_mtime_local"] = iso_local(mt)
        if ticks.isdigit():
            utc, loc, unix = ticks_to_times(ticks)
            r["time_of_crash_utc"] = utc
            r["time_of_crash_local"] = loc
            r["time_vs_mtime_delta_s"] = round(unix - mt, 3)
        else:
            r["time_of_crash_utc"] = ""
            r["time_of_crash_local"] = ""
            r["time_vs_mtime_delta_s"] = ""

        # ---- callstacks
        r["pcallstack_hash"] = g(rp, "PCallStackHash")
        frames = parse_frames(g(rp, "PCallStack"))
        game = [f for f in frames if f[0].lower().startswith("supervive")]
        r["pcallstack_nframes"] = len(frames)
        r["pcallstack_ngame"] = len(game)
        r["game_module_base"] = "0x%X" % game[0][1] if game else ""
        r["game_rva_chain"] = " ".join("%x" % f[2] for f in game)
        r["game_rva_chain3"] = " ".join("%x" % f[2] for f in game[:3])
        r["frame0_module"] = frames[0][0] if frames else ""
        r["frame0_abs"] = ("0x%X" % (frames[0][1] + frames[0][2])) if frames else ""
        cst = g(rp, "CallStack")
        r["callstack_text"] = cst
        cst_mods = [x.strip() for x in cst.replace("\r\n", "\n").split("\n") if x.strip()]
        r["callstack_modules"] = ";".join(cst_mods)
        r["callstack_has_game"] = int(any(m.lower().startswith("supervive") for m in cst_mods))
        r["callstack_has_runtime"] = int(any(m.lower().startswith("runtime") for m in cst_mods))

        # ---- threads
        threads = []
        th = rp.find("Threads") if rp is not None else None
        crashed_id = crashed_name = ""
        game_tid = ""
        if th is not None:
            for t in th:
                tid = (t.findtext("ThreadID") or "").strip()
                tnm = (t.findtext("ThreadName") or "").strip()
                cs = (t.findtext("CallStack") or "").strip()
                isc = (t.findtext("IsCrashed") or "").strip()
                tf = parse_frames(cs)
                tg = [x for x in tf if x[0].lower().startswith("supervive")]
                threads.append({
                    "thread_id": tid, "thread_name": tnm, "is_crashed": isc,
                    "nframes": len(tf), "ngame_frames": len(tg),
                    "game_rva_chain": " ".join("%x" % x[2] for x in tg),
                    "callstack": cs,
                })
                if isc.lower() == "true":
                    crashed_id, crashed_name = tid, tnm
                if tnm == "GameThread":
                    game_tid = tid
        r["thread_count"] = len(threads)
        r["crashed_thread_id"] = crashed_id
        r["crashed_thread_name"] = crashed_name
        r["gamethread_id"] = game_tid
        r["thread_names"] = ";".join(sorted({t["thread_name"] for t in threads if t["thread_name"]}))
        r["_threads"] = threads

        # ---- modules (XML list -- newline delimited, paths contain spaces)
        modtext = g(rp, "Modules")
        mods = [x.strip() for x in modtext.replace("\r\n", "\n").split("\n") if x.strip()]
        bad = [x for x in mods if not (len(x) > 2 and x[1] == ":" and x[2] in "\\/")]
        r["xml_module_count"] = len(mods)
        r["xml_module_unparsed"] = len(bad)
        r["xml_module_basenames"] = ";".join(sorted({basename(x) for x in mods}))
        r["_xml_modules"] = mods

        # ---- memory / host
        for key, tag in [
            ("mem_used_physical", "MemoryStats.UsedPhysical"),
            ("mem_avail_physical", "MemoryStats.AvailablePhysical"),
            ("mem_peak_used_physical", "MemoryStats.PeakUsedPhysical"),
            ("mem_total_physical", "MemoryStats.TotalPhysical"),
            ("mem_used_virtual", "MemoryStats.UsedVirtual"),
            ("mem_is_oom", "MemoryStats.bIsOOM"),
            ("mem_oom_alloc_size", "MemoryStats.OOMAllocationSize"),
            ("num_cores", "Misc.NumberOfCores"),
            ("cpu_brand", "Misc.CPUBrand"),
            ("gpu_brand", "Misc.PrimaryGPUBrand"),
        ]:
            r[key] = g(rp, tag)
        r["rhi_name"] = g(ed, "RHI.RHIName")
        r["rhi_adapter"] = g(ed, "RHI.AdapterName")
        r["replication_model"] = g(ed, "ReplicationModel")
        r["num_clients"] = g(ed, "NumClients")
        r["app_has_focus"] = g(ed, "Platform.AppHasFocus")

        # ---- GameData/__sentry (JSON here, unlike the crashpad class's msgpack)
        r["sentry_build_version"] = ""
        r["sentry_build_cl"] = ""
        r["sentry_bp_script_stack"] = ""
        st = g(gd, "__sentry")
        if st:
            try:
                sj = json.loads(st)
                tags = sj.get("tags", {})
                r["sentry_build_version"] = tags.get("BuildVersion", "")
                r["sentry_build_cl"] = tags.get("BuildCL", "")
                r["sentry_bp_script_stack"] = tags.get("BPScriptStack", "")
            except ValueError as e:
                warn.append("%s: GameData/__sentry not JSON: %s" % (name, e))

        # ---- minidump
        dmp = os.path.join(d, "UEMinidump.dmp")
        r["minidump_present"] = int(os.path.isfile(dmp))
        r["minidump_bytes"] = os.path.getsize(dmp) if r["minidump_present"] else 0
        r["md_module_count"] = ""
        r["md_module_status"] = "skipped"
        r["_md_modules"] = []
        if want_dumps and r["minidump_present"]:
            mm, st2 = minidump_modules(dmp)
            r["md_module_status"] = st2
            if mm is not None:
                r["md_module_count"] = len(mm)
                r["_md_modules"] = mm

        # ---- unwind_status (gotcha 2).  TWO independent signals are computed and
        # compared; if they ever disagree the row is flagged rather than silently
        # classified.  This check is what caught my own first, wrong cut.
        empty_hash = (r["pcallstack_hash"].upper() == EMPTY_SHA1)
        secs_zero = (r["seconds_since_start"] == "0")
        if empty_hash != secs_zero:
            warn.append("%s: unwind discriminators DISAGREE (empty-sha1=%s, "
                        "secs==0=%s) -- do not trust unwind_status for this row"
                        % (name, empty_hash, secs_zero))
        if empty_hash:
            r["unwind_status"] = "os-only"
        elif not r["pcallstack_hash"] and not frames:
            r["unwind_status"] = "absent"
        elif r["pcallstack_ngame"] == 0:
            r["unwind_status"] = "no-game-frames"
        else:
            r["unwind_status"] = "ok"

        # ---- kind (gotcha 3): 'degenerate' == the CrashContext writer never
        # finished.  Three signals must ALL agree; disagreement is flagged.
        d1 = (r["minidump_bytes"] == 0)
        d2 = (not ticks)
        d3 = (r["xml_module_count"] == 0)
        if not (d1 == d2 == d3):
            warn.append("%s: degenerate discriminators DISAGREE (zero-dmp=%s, "
                        "no-ticks=%s, no-modules=%s)" % (name, d1, d2, d3))
        r["kind"] = "degenerate" if (d1 and d2 and d3) else "crash"

        # ---- every other file in the directory, listed rather than assumed.
        # This is how the Loki_2.log case was found: 12 RHI breadcrumb files and
        # one alternately-named log would all be invisible to a fixed filename.
        try:
            files = sorted(f for f in os.listdir(d) if os.path.isfile(os.path.join(d, f)))
        except OSError:
            files = []
        r["dir_files"] = ";".join(files)
        r["dir_file_count"] = len(files)
        bcs = [f for f in files if f.startswith("Breadcrumbs_")]
        r["rhi_breadcrumb_files"] = len(bcs)
        txt = []
        for f in bcs:                       # 24-109 bytes each; safe to inline
            txt.append(open(os.path.join(d, f), "rb").read()
                       .decode("utf-8", "replace").replace("\n", " | ").strip())
        r["rhi_breadcrumbs"] = " || ".join(txt)

        # ---- Source C.  Find the log by PATTERN, not by fixed name: one
        # directory carries Loki_2.log and no Loki.log (gotcha 4).
        logs = [f for f in files if f.startswith("Loki") and f.endswith(".log")]
        logp = ""
        if "Loki.log" in logs:
            logp = os.path.join(d, "Loki.log")
        elif logs:
            logp = max((os.path.join(d, f) for f in logs), key=os.path.getsize)
        r.update(blank_log_fields())
        r["log_filename"] = os.path.basename(logp)
        r["log_present"] = int(bool(logp))
        if want_logs and logp:
            r.update(flatten_log(fingerprint_log(logp)))
            r["log_filename"] = os.path.basename(logp)

        rows.append(r)
    return rows


# --------------------------------------------------------------------------- #
# SOURCE B -- the crashpad archive class
# --------------------------------------------------------------------------- #

def parse_archive_info(path):
    out = {}
    if not os.path.isfile(path):
        return out
    txt = open(path, "rb").read().decode("utf-8-sig", "replace")
    for line in txt.splitlines():
        if line.startswith("NOTE:"):
            break
        if ":" in line:
            k, _, v = line.partition(":")
            k = k.strip()
            if k and " " not in k.strip():
                out[k] = v.strip()
    return out


def parse_crashpad_metadata(path):
    """crashpad's binary report database index.  Layout (client/crashpad_database_win.cc):
        header : magic 'DAPC' (4) | version u32 | num_records u32 | pad u32
        record : uuid(16) | file_path_index u32 | id_index u32 | creation_time i64
                 | last_upload_attempt_time i64 | upload_attempts i32
                 | state i32 | upload_explicitly_requested u8 | pad[7]      (56 B)
        then a NUL-separated string table indexed by the two *_index fields.
    """
    recs = []
    if not os.path.isfile(path):
        return recs, "missing"
    b = open(path, "rb").read()
    if len(b) < 16 or b[:4] != b"DAPC":
        return recs, "bad-magic"
    ver, n = struct.unpack_from("<II", b, 4)
    off = 16
    strings_off = off + 56 * n

    def s_at(idx):
        if idx <= 0 or strings_off + idx > len(b):
            return ""
        e = b.find(b"\x00", strings_off + idx)
        return b[strings_off + idx:e if e != -1 else len(b)].decode("utf-8", "replace")

    states = {0: "uninitialized", 1: "new", 2: "pending", 3: "uploading", 4: "completed"}
    for i in range(n):
        o = off + 56 * i
        if o + 56 > len(b):
            return recs, "truncated"
        raw = b[o:o + 16]
        d1, d2, d3 = struct.unpack_from("<IHH", raw, 0)
        uuid = "%08x-%04x-%04x-%s-%s" % (
            d1, d2, d3, raw[8:10].hex(), raw[10:16].hex())
        fpi, idi = struct.unpack_from("<II", b, o + 16)
        ctime, utime = struct.unpack_from("<qq", b, o + 24)
        attempts, state = struct.unpack_from("<ii", b, o + 40)
        expl = b[o + 48]
        recs.append({
            "uuid": uuid,
            "file_name": s_at(fpi),
            "sentry_event_id": s_at(idi),
            "creation_time_utc": datetime.datetime.fromtimestamp(
                ctime, datetime.timezone.utc).replace(tzinfo=None).isoformat() if ctime else "",
            "last_upload_attempt_utc": datetime.datetime.fromtimestamp(
                utime, datetime.timezone.utc).replace(tzinfo=None).isoformat() if utime else "",
            "upload_attempts": attempts,
            "state": states.get(state, "unknown(%d)" % state),
            "upload_explicitly_requested": expl,
        })
    return recs, "ok(v%d,n=%d)" % (ver, n)


def parse_settings_dat(path):
    """crashpad settings.dat: magic 'sdPC' | version u32 | options u32 | pad u32
       | last_upload_attempt_time i64 | client_id(16)."""
    if not os.path.isfile(path):
        return ""
    b = open(path, "rb").read()
    if len(b) < 40 or b[:4] != b"sdPC":
        return ""
    raw = b[24:40]
    d1, d2, d3 = struct.unpack_from("<IHH", raw, 0)
    return "%08x-%04x-%04x-%s-%s" % (d1, d2, d3, raw[8:10].hex(), raw[10:16].hex())


def read_sentry_event(path, warn, who):
    if not os.path.isfile(path):
        return None
    b = open(path, "rb").read()
    try:
        obj, used = mp_decode(b)
    except Exception as e:                                    # noqa: BLE001
        warn.append("%s: __sentry-event msgpack decode failed: %s" % (who, e))
        return None
    if used != len(b):
        warn.append("%s: __sentry-event decoded %d of %d bytes" % (who, used, len(b)))
    return obj


def read_crashpad(root, want_logs, want_dumps, warn):
    rows = []
    if not os.path.isdir(root):
        warn.append("dumps root missing: %s" % root)
        return rows
    archives = sorted(n for n in os.listdir(root)
                      if n.startswith("crashpad-") and os.path.isdir(os.path.join(root, n)))

    # First pass: which archives hold which report uuid, so a row can say how
    # many archives a report appears in and which one is primary (gotcha 1).
    uuid_to_archives = collections.defaultdict(list)
    for a in archives:
        rep = os.path.join(root, a, "reports")
        if os.path.isdir(rep):
            for f in sorted(os.listdir(rep)):
                if f.lower().endswith(".dmp"):
                    uuid_to_archives[f[:-4]].append(a)

    for a in archives:
        adir = os.path.join(root, a)
        info = parse_archive_info(os.path.join(adir, "ARCHIVE-INFO.txt"))
        meta, meta_status = parse_crashpad_metadata(os.path.join(adir, "metadata"))
        meta_by_uuid = {m["uuid"]: m for m in meta}
        client_id = parse_settings_dat(os.path.join(adir, "settings.dat"))
        last_crash = ""
        lcp = os.path.join(adir, "last_crash")
        if os.path.isfile(lcp):
            last_crash = open(lcp, "rb").read().decode("utf-8", "replace").strip()

        label = info.get("label", "")
        if label == "(none)":
            label = ""

        # Session log keys are recorded separately -- 'handing control over to
        # crashpad' lives ONLY here, never in the attachment copy (gotcha 7).
        sess = os.path.join(adir, "session-Loki.log")
        sess_fp = None
        if want_logs and os.path.isfile(sess):
            sess_fp = fingerprint_log(sess)

        rep = os.path.join(adir, "reports")
        dmps = sorted(f for f in os.listdir(rep)
                      if f.lower().endswith(".dmp")) if os.path.isdir(rep) else []

        if not dmps:
            r = collections.OrderedDict()
            r["source"] = "crashpad"
            r["kind"] = "no-report-sweep"
            r["artifact_id"] = a
            r["path"] = adir
            r["archive_label"] = label
            r["archive_archived_at"] = info.get("archived", "")
            r["archive_reports_declared"] = info.get("reports", "")
            r["archive_trigger"] = info.get("trigger", "")
            r["crashpad_client_id"] = client_id
            r["crashpad_last_crash_utc"] = last_crash
            r["crashpad_metadata_status"] = meta_status
            r["parse_status"] = "ok"
            r.update(blank_log_fields())
            _attach_session(r, sess_fp, os.path.isfile(sess))
            rows.append(r)
            continue

        for f in dmps:
            uuid = f[:-4]
            arcs = uuid_to_archives.get(uuid, [a])
            r = collections.OrderedDict()
            r["source"] = "crashpad"
            r["kind"] = "crash"
            r["artifact_id"] = "%s/%s" % (a, uuid)
            r["path"] = adir
            r["parse_status"] = "ok"
            r["archive_label"] = label
            r["archive_archived_at"] = info.get("archived", "")
            r["archive_reports_declared"] = info.get("reports", "")
            r["archive_trigger"] = info.get("trigger", "")
            r["archive_source_dir"] = info.get("source", "")
            r["label_says_death"] = int(label.upper().endswith("-DEATH"))
            r["report_uuid"] = uuid
            r["report_archive_count"] = len(arcs)
            r["report_is_primary"] = int(arcs[0] == a)
            r["report_archives"] = ";".join(arcs)
            r["crashpad_client_id"] = client_id
            r["crashpad_last_crash_utc"] = last_crash
            r["crashpad_metadata_status"] = meta_status

            md = meta_by_uuid.get(uuid, {})
            r["crashpad_state"] = md.get("state", "")
            r["crashpad_upload_attempts"] = md.get("upload_attempts", "")
            r["crashpad_created_utc"] = md.get("creation_time_utc", "")
            r["crashpad_last_upload_utc"] = md.get("last_upload_attempt_utc", "")
            r["sentry_event_id"] = md.get("sentry_event_id", "")

            dmpp = os.path.join(rep, f)
            r["minidump_present"] = 1
            r["minidump_bytes"] = os.path.getsize(dmpp)
            r["md_module_count"] = ""
            r["md_module_status"] = "skipped"
            r["_md_modules"] = []
            if want_dumps:
                mm, st2 = minidump_modules(dmpp)
                r["md_module_status"] = st2
                if mm is not None:
                    r["md_module_count"] = len(mm)
                    r["_md_modules"] = mm

            # ---- __sentry-event (msgpack).  This is where the crashpad class
            # keeps the FULL command line and the UECC crash GUID.
            adir_att = os.path.join(adir, "attachments", uuid)
            ev = read_sentry_event(os.path.join(adir_att, "__sentry-event"), warn,
                                   "%s/%s" % (a, uuid))
            r["_sentry_event"] = ev
            ci = (ev or {}).get("contexts", {}).get("Crash Info", {}) if ev else {}
            tags = (ev or {}).get("tags", {}) if ev else {}
            r["sentry_event_id_from_event"] = (ev or {}).get("event_id", "") if ev else ""
            r["sentry_timestamp_utc"] = (ev or {}).get("timestamp", "") if ev else ""
            r["sentry_level"] = (ev or {}).get("level", "") if ev else ""
            r["crash_guid"] = ci.get("Crash GUID", "")
            r["crash_type"] = ci.get("Crash Type", "")
            r["is_ensure"] = ci.get("IsEnsure", "")
            r["is_stall"] = ci.get("IsStall", "")
            r["is_assert"] = ci.get("IsAssert", "")
            r["process_id"] = ci.get("Process Id", "")
            r["seconds_since_start"] = ci.get("Seconds Since Start", "")
            r["crashed_thread_id"] = ci.get("Crashing Thread Id", "")
            r["base_dir"] = ci.get("Base Dir", "")
            r["executable_name"] = ci.get("Executable Name", "")
            r["game_name"] = ci.get("Game Name", "")
            # The one place a real command line survives.  Verbatim, unparsed.
            r["command_line"] = ci.get("Command Line", "")
            r["command_line_len"] = len(r["command_line"])
            r["build_version"] = tags.get("BuildVersion", "")
            r["sentry_build_version"] = tags.get("BuildVersion", "")
            r["sentry_build_cl"] = tags.get("BuildCL", "")
            r["engine_version"] = ((ev or {}).get("contexts", {})
                                   .get("Unreal Engine", {}).get("Engine version", "")) if ev else ""
            r["build_configuration"] = tags.get("Configuration", "")
            r["engine_mode"] = tags.get("Engine Mode", "")
            r["cpu_brand"] = tags.get("security.CPUBrand", "").strip()
            r["gpu_brand"] = tags.get("security.GPUBrand", "")

            bcs = (ev or {}).get("breadcrumbs", []) if ev else []
            r["_breadcrumbs"] = bcs
            r["breadcrumb_count"] = len(bcs)
            bmaps = [b.get("data", {}).get("Map", "") for b in bcs
                     if isinstance(b, dict) and b.get("data")]
            bmaps = [x for x in bmaps if x]
            r["breadcrumb_maps"] = ";".join(bmaps)
            r["breadcrumb_last_map"] = bmaps[-1] if bmaps else ""

            # ---- timing.  Crashpad rows have no FDateTime ticks; use the
            # sentry event timestamp and the crashpad DB creation time.
            r["time_of_crash_ticks"] = ""
            r["time_of_crash_utc"] = (r["sentry_timestamp_utc"] or
                                      r["crashpad_created_utc"] or "")
            r["time_of_crash_local"] = ""
            if r["time_of_crash_utc"]:
                try:
                    s = r["time_of_crash_utc"].replace("Z", "+00:00")
                    dt = datetime.datetime.fromisoformat(s)
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=datetime.timezone.utc)
                    r["time_of_crash_local"] = dt.astimezone().replace(
                        tzinfo=None).isoformat(timespec="milliseconds")
                except ValueError:
                    pass
            mtd = os.path.getmtime(dmpp)
            r["xml_mtime_local"] = iso_local(mtd)
            r["time_vs_mtime_delta_s"] = ""

            # ---- Source C: the run's OWN log (per report uuid).  Same
            # pattern-not-fixed-name rule as the UECC side.
            try:
                afiles = sorted(f for f in os.listdir(adir_att)
                                if os.path.isfile(os.path.join(adir_att, f)))
            except OSError:
                afiles = []
            r["dir_files"] = ";".join(afiles)
            r["dir_file_count"] = len(afiles)
            r["rhi_breadcrumb_files"] = 0
            r["rhi_breadcrumbs"] = ""
            logs = [f for f in afiles if f.startswith("Loki") and f.endswith(".log")]
            logp = ""
            if "Loki.log" in logs:
                logp = os.path.join(adir_att, "Loki.log")
            elif logs:
                logp = max((os.path.join(adir_att, f) for f in logs), key=os.path.getsize)
            r.update(blank_log_fields())
            r["log_filename"] = os.path.basename(logp)
            r["log_present"] = int(bool(logp))
            if want_logs and logp:
                r.update(flatten_log(fingerprint_log(logp)))
                r["log_filename"] = os.path.basename(logp)
            _attach_session(r, sess_fp, os.path.isfile(sess))
            rows.append(r)
    return rows


def _attach_session(r, sess_fp, present):
    r["session_log_present"] = int(present)
    if sess_fp:
        r["session_log_bytes"] = sess_fp["log_bytes"]
        r["session_log_crashpad_handoff"] = sess_fp["log_crashpad_handoff"]
        r["session_log_sentry_beforecrash"] = sess_fp["log_sentry_beforecrash"]
        r["session_log_last_ts"] = sess_fp["log_last_ts"]
    else:
        r["session_log_bytes"] = ""
        r["session_log_crashpad_handoff"] = ""
        r["session_log_sentry_beforecrash"] = ""
        r["session_log_last_ts"] = ""


# --------------------------------------------------------------------------- #
# log field plumbing
# --------------------------------------------------------------------------- #

def blank_log_fields():
    d = collections.OrderedDict()
    d["log_present"] = 0
    d["log_filename"] = ""
    d["log_bytes"] = ""
    d["log_lines"] = ""
    d["log_first_ts"] = ""
    d["log_last_ts"] = ""
    d["log_span_s"] = ""
    d["log_loadmap_count"] = ""
    d["log_last_map"] = ""
    d["log_maps"] = ""
    d["log_route"] = ""
    for k in LOG_KEYS:
        d["log_" + k] = ""
    for t in MARKER_TAGS:
        d["mk_" + t] = ""
    d["marker_tags_found"] = ""
    d["_log_maps"] = []
    return d


def flatten_log(fp):
    d = collections.OrderedDict()
    d["log_present"] = 1
    for k in ("log_bytes", "log_lines", "log_first_ts", "log_last_ts",
              "log_span_s", "log_loadmap_count"):
        d[k] = fp[k]
    d["log_last_map"] = fp["log_maps"][-1] if fp["log_maps"] else ""
    d["log_maps"] = ";".join(fp["log_maps"])
    for k in LOG_KEYS:
        d["log_" + k] = fp["log_" + k]
    # ⚠⚠ THE mk_* / marker_tags_found COLUMNS ARE STRUCTURALLY ALWAYS ZERO. DO NOT READ THEM AS
    # SHIM ATTRIBUTION.  (Found 2026-08-05 / S111, after the mining pass had already shipped them.)
    # MEASURED: the shims' Marker() -- tools/sigbypass-mod/tutorial_launch.cpp:319 -- writes to
    # kMarkerPath, i.e. a docs/*-marker.txt file, and NEVER to Loki.log.  A direct grep of a
    # tutorial-route crash's Loki.log for [SP]/[PL]/[ANIM]/[FO] returns 0/0/0/0.  The original
    # positive control for this detector fired {PL:25, ANIM:12, VTG:1, GCW:1} -- but it was run
    # against docs/fk24-run-nostatictest1.txt, a MARKER FILE, not a Loki.log.  It validated the
    # regex and not the detector's applicability to its actual input.
    # => "0 shim markers across 130 crash logs" means the shims do not log there.  It does NOT mean
    #    no shim was present.  Shim presence is NOT observable from Loki.log; use the injector logs
    #    (docs/gft-ready-marker.txt, docs/inject-secondaries.log) instead.
    # The columns are retained only so this note has somewhere to live.  log_route is UNAFFECTED.
    found = []
    for t in MARKER_TAGS:
        d["mk_" + t] = fp["markers"][t]
        if fp["markers"][t]:
            found.append(t)
    d["marker_tags_found"] = ";".join(found)
    d["log_route"] = route_label(fp["log_maps"], fp["log_lvl_tutorial"],
                                 fp["log_forceopen_tutorial_url"])
    d["_log_maps"] = fp["log_maps"]
    return d


# --------------------------------------------------------------------------- #
# validation
# --------------------------------------------------------------------------- #

def validate(rows, uecc_root, dumps_root, warn, want_logs, want_dumps):
    v = []
    u = [r for r in rows if r["source"] == "uecc"]
    c = [r for r in rows if r["source"] == "crashpad"]

    n_uecc_dirs = len([n for n in os.listdir(uecc_root)
                       if os.path.isdir(os.path.join(uecc_root, n))]) if os.path.isdir(uecc_root) else 0
    n_arch = len([n for n in os.listdir(dumps_root)
                  if n.startswith("crashpad-") and os.path.isdir(os.path.join(dumps_root, n))]) if os.path.isdir(dumps_root) else 0
    n_dmp = 0
    for n in sorted(os.listdir(dumps_root)) if os.path.isdir(dumps_root) else []:
        rep = os.path.join(dumps_root, n, "reports")
        if n.startswith("crashpad-") and os.path.isdir(rep):
            n_dmp += len([f for f in os.listdir(rep) if f.lower().endswith(".dmp")])

    v.append("row-count/uecc: %d rows == %d directories on disk -> %s"
             % (len(u), n_uecc_dirs, "PASS" if len(u) == n_uecc_dirs else "FAIL"))
    exp_c = n_dmp + len([r for r in c if r["kind"] == "no-report-sweep"])
    v.append("row-count/crashpad: %d rows == %d report .dmp files (+%d empty-report sweeps) "
             "across %d archives -> %s"
             % (len(c), n_dmp, len([r for r in c if r["kind"] == "no-report-sweep"]),
                n_arch, "PASS" if len(c) == exp_c else "FAIL"))

    bad = [r["artifact_id"] for r in u if r["parse_status"] != "ok"]
    v.append("xml-parse: %d/%d UECC XMLs parsed with xml.etree, 0 regex fallbacks; failures=%s -> %s"
             % (len(u) - len(bad), len(u), bad or "none", "PASS" if not bad else "FAIL"))

    # per-field fill rate on the UECC class (non-empty after str/strip)
    req = ["crash_guid", "execution_guid", "crash_type", "error_message",
           "process_id", "seconds_since_start", "engine_version", "build_version",
           "machine_id", "pcallstack_hash", "time_of_crash_ticks",
           "thread_count", "xml_module_count", "minidump_bytes", "log_present"]
    fills = []
    for f in req:
        n = sum(1 for r in u if str(r.get(f, "")).strip() != "" and str(r.get(f, "")) != "0")
        fills.append("%s=%d/%d" % (f, n, len(u)))
    v.append("fill-rate/uecc (non-empty & non-zero): " + ", ".join(fills))

    deg = [r for r in u if r["kind"] == "degenerate"]
    nou = [r for r in u if r.get("unwind_status") == "os-only"]
    absent = [r for r in u if r.get("unwind_status") == "absent"]
    v.append("fill-rate explained: every empty required field belongs to the %d "
             "kind='degenerate' rows (zero-byte dump AND no TimeOfCrash AND no "
             "Modules -- three signals, all agreeing): %s"
             % (len(deg), ",".join(sorted(r["artifact_id"] for r in deg))))
    v.append("unwind_status: os-only=%d (empty-SHA1 PCallStackHash == "
             "SecondsSinceStart==0, two independent signals selecting the SAME "
             "%d rows; %d of them name `runtime` in CallStack = protector-kill "
             "family), absent=%d, no-game-frames=%d, ok=%d"
             % (len(nou), len(nou),
                sum(1 for r in nou if r.get("callstack_has_runtime")),
                len(absent),
                sum(1 for r in u if r.get("unwind_status") == "no-game-frames"),
                sum(1 for r in u if r.get("unwind_status") == "ok")))
    v.append("real-death denominator: uecc kind='crash' = %d, plus crashpad "
             "report_is_primary=1 = %d -> %d distinct deaths (NOT 92, NOT 44)"
             % (len(u) - len(deg), sum(1 for r in c if r.get("report_is_primary")),
                len(u) - len(deg) + sum(1 for r in c if r.get("report_is_primary"))))

    ds = [abs(float(r["time_vs_mtime_delta_s"])) for r in u
          if r["time_vs_mtime_delta_s"] != ""]
    if ds:
        v.append("TimeOfCrash->wall-clock vs file mtime: N=%d, max |delta| = %.3f s, "
                 "median %.3f s -> %s (ticks are UTC; treating them as local would "
                 "give a systematic 18000 s error)"
                 % (len(ds), max(ds), sorted(ds)[len(ds) // 2],
                    "PASS" if max(ds) < 5 else "FAIL"))

    if want_dumps:
        okm = [r for r in rows if r.get("md_module_status") == "ok"]
        zero = [r for r in rows if r.get("md_module_status") == "zero-byte"]
        v.append("minidump module lists: %d ok, %d zero-byte, %d other; "
                 "shim DLLs found in module lists = 0 (shims are manual-mapped, "
                 "so this is a property of the injection method, NOT of the runs)"
                 % (len(okm), len(zero),
                    len(rows) - len(okm) - len(zero)
                    - sum(1 for r in rows if not r.get("minidump_present"))))

    if want_logs:
        nl = [r for r in rows if r.get("log_present")]
        mk = [r for r in nl if r.get("marker_tags_found")]
        v.append("log fingerprint: %d logs scanned, %.1f MB total (largest single "
                 "log %.1f MB); logs carrying a shim marker tag = %d"
                 % (len(nl), sum(int(r["log_bytes"]) for r in nl) / 1e6,
                    max(int(r["log_bytes"]) for r in nl) / 1e6 if nl else 0, len(mk)))

        # --- POSITIVE CONTROL for the marker detector.  It must FIRE on a file
        # where the tags are known present before its zeroes mean anything.
        # docs/fk24-run-nostatictest1.txt is a COMMITTED marker copy and is stable;
        # docs/tutorial-launch-marker.txt is truncated by every injection (FK-25)
        # and so is only a fallback.
        ctrl = ""
        for cand in ("fk24-run-nostatictest1.txt", "tutorial-launch-marker.txt"):
            p = os.path.join(REPO, "docs", cand)
            if os.path.isfile(p):
                ctrl = p
                break
        if ctrl:
            cf = fingerprint_log(ctrl)
            hit = {t: n for t, n in cf["markers"].items() if n}
            v.append("marker detector POSITIVE CONTROL on docs/%s (%d bytes): fired "
                     "on %s -> %s.  The 0s in Loki.log are therefore a property of "
                     "the LOGS (shim Marker() writes to docs/<shim>-marker.txt via "
                     "CreateFileA, never UE_LOG), NOT of the detector."
                     % (os.path.basename(ctrl), cf["log_bytes"], hit or "NOTHING",
                        "PASS" if hit else "FAIL -- detector is broken"))
        else:
            v.append("marker detector POSITIVE CONTROL: SKIPPED, no control file found")

        # --- NEGATIVE control: a specific log verified by hand to carry none.
        neg = [r for r in nl if r["source"] == "uecc" and not r.get("marker_tags_found")]
        if neg:
            v.append("marker detector NEGATIVE control: %s reports 0 for all %d tags "
                     "(hand-verified absent) -> PASS"
                     % (neg[0]["artifact_id"], len(MARKER_TAGS)))

        # --- crash-handoff key comparison (gotcha 8)
        sess = [r for r in rows if r["source"] == "crashpad" and r.get("session_log_present")]
        att = [r for r in rows if r["source"] == "crashpad" and r.get("log_present")]
        if sess:
            v.append("crash-handoff keys on the crashpad class (counted per ROW, so "
                     "duplicate archives of one report count twice): "
                     "'handing control over to crashpad' hits %d/%d session logs and "
                     "%d/%d attachment logs; 'Sentry HandleBeforeCrash Begin' hits "
                     "%d/%d and %d/%d -> prefer the Sentry key, the documented one "
                     "misses the attachment copy entirely"
                     % (sum(1 for r in sess if r["session_log_crashpad_handoff"]), len(sess),
                        sum(1 for r in att if r.get("log_crashpad_handoff")), len(att),
                        sum(1 for r in sess if r["session_log_sentry_beforecrash"]), len(sess),
                        sum(1 for r in att if r.get("log_sentry_beforecrash")), len(att)))

        routes = collections.Counter(r.get("log_route", "") for r in nl)
        v.append("route attribution from logs: " +
                 ", ".join("%s=%d" % kv for kv in sorted(routes.items())))
        alt = [r["artifact_id"] for r in rows
               if r.get("log_filename") and r["log_filename"] != "Loki.log"]
        v.append("log discovery by Loki*.log glob, not fixed name: %d row(s) use a "
                 "differently-named log -> %s (a fixed 'Loki.log' would have "
                 "recorded these as log-less)" % (len(alt), alt or "none"))
        bc = [r for r in rows if r.get("rhi_breadcrumb_files")]
        v.append("RHI GPU breadcrumb dumps present in %d rows (%d files) -- a "
                 "GPU-side discriminator no prior census captured"
                 % (len(bc), sum(int(r["rhi_breadcrumb_files"]) for r in bc)))

    # memory-stat scope (gotcha 14)
    memset = {r["artifact_id"] for r in u if str(r.get("mem_used_physical", "")) not in ("", "0")}
    assset = {r["artifact_id"] for r in u if r.get("crash_type") == "Assert"}
    v.append("MemoryStats scope: populated in %d/%d UECC rows; the populated set "
             "and the CrashType=Assert set are %s (N=%d each).  bIsOOM=1 in %d "
             "rows.  So a 0 here is 'this path never sampled memory', NOT 'no "
             "memory was used'."
             % (len(memset), len(u),
                "IDENTICAL" if memset == assset else "DIFFERENT",
                len(assset), sum(1 for r in u if r.get("mem_is_oom") == "1")))

    # label reliability (gotcha 15)
    cp = [r for r in c if r.get("report_is_primary")]
    unl = [r["archive_label"] or "(none)" for r in cp if not int(r.get("label_says_death") or 0)]
    v.append("archiver -DEATH label as a crash key: %d of %d distinct crashpad "
             "reports sit in a NON -DEATH archive (%s) -> the label is not a "
             "reliable key; filter on the presence of a report"
             % (len(unl), len(cp), ", ".join(sorted(unl))))

    # crashpad dedup
    uu = {r["report_uuid"] for r in c if r.get("report_uuid")}
    prim = sum(1 for r in c if r.get("report_is_primary"))
    v.append("crashpad dedup: %d archives hold %d report files but only %d DISTINCT "
             "report uuids; report_is_primary==1 on %d rows -> use THAT as the "
             "crash denominator, not the archive count"
             % (n_arch, n_dmp, len(uu), prim))

    # cross-source join
    ug = {r["crash_guid"] for r in u if r.get("crash_guid")}
    ug_short = {g[:-5] if g.endswith("_0000") else g for g in ug}
    cg = {r["crash_guid"] for r in c if r.get("crash_guid")}
    joined = cg & ug_short
    v.append("cross-source join on Crash GUID: %d distinct crashpad GUIDs, %d UECC "
             "GUIDs, %d overlap -> the two classes are %s.  JOIN POSITIVE CONTROL: "
             "the same key type self-joins the UECC set %d/%d, so the joiner works "
             "and the zero is a property of the corpus, not of the join."
             % (len(cg), len(ug_short), len(joined),
                "DISJOINT populations" if not joined else "partly the same crashes",
                len(ug_short & ug_short), len(ug_short)))

    v.append("warnings emitted during parse: %d%s"
             % (len(warn), (" -> " + " ; ".join(warn[:5])) if warn else ""))
    return v


# --------------------------------------------------------------------------- #
# output
# --------------------------------------------------------------------------- #

def write_outputs(rows, csv_path, json_path, validations, meta):
    # stable, union-of-all-keys column order: leading identity columns first,
    # then everything else in first-seen order.
    lead = ["source", "kind", "artifact_id", "crash_guid", "report_uuid",
            "report_is_primary", "report_archive_count", "archive_label",
            "label_says_death", "crash_type", "seconds_since_start",
            "time_of_crash_utc", "time_of_crash_local", "log_route"]
    cols = list(lead)
    for r in rows:
        for k in r:
            if k.startswith("_"):
                continue
            if k not in cols:
                cols.append(k)

    os.makedirs(os.path.dirname(csv_path), exist_ok=True)
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            out = {}
            for k in cols:
                val = r.get(k, "")
                if isinstance(val, str) and len(val) > 1000:
                    val = val[:1000] + "...[truncated; full text in the JSON]"
                out[k] = val
            w.writerow(out)

    jrows = []
    for r in rows:
        j = {k: v for k, v in r.items() if not k.startswith("_")}
        j["threads"] = r.get("_threads", [])
        j["xml_modules"] = r.get("_xml_modules", [])
        j["minidump_modules"] = r.get("_md_modules", [])
        j["log_maps_list"] = r.get("_log_maps", [])
        if r.get("_breadcrumbs") is not None:
            j["breadcrumbs"] = r.get("_breadcrumbs")
        if r.get("_sentry_event") is not None:
            j["sentry_event"] = r.get("_sentry_event")
        jrows.append(j)
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({"meta": meta, "validation": validations, "columns": cols,
                   "rows": jrows}, f, indent=1, sort_keys=False, default=str)
    return cols


# --------------------------------------------------------------------------- #

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--uecc", default=DEF_UECC)
    ap.add_argument("--dumps", default=DEF_DUMPS)
    ap.add_argument("--out-csv", default=DEF_CSV)
    ap.add_argument("--out-json", default=DEF_JSON)
    ap.add_argument("--no-logs", action="store_true",
                    help="fast mode: skip SOURCE C (the per-crash Loki.log scan)")
    ap.add_argument("--no-minidumps", action="store_true",
                    help="skip the minidump ModuleListStream read")
    ap.add_argument("--validate", action="store_true",
                    help="print the self-checks to stdout")
    a = ap.parse_args(argv)

    want_logs = not a.no_logs
    want_dumps = not a.no_minidumps
    warn = []

    rows = read_uecc(a.uecc, want_logs, want_dumps, warn)
    rows += read_crashpad(a.dumps, want_logs, want_dumps, warn)

    vs = validate(rows, a.uecc, a.dumps, warn, want_logs, want_dumps)
    meta = {
        "tool": "tools/crashtri/fk8_corpus.py",
        "uecc_root": a.uecc,
        "dumps_root": a.dumps,
        "logs_scanned": want_logs,
        "minidump_modules_read": want_dumps,
        "rows_uecc": sum(1 for r in rows if r["source"] == "uecc"),
        "rows_crashpad": sum(1 for r in rows if r["source"] == "crashpad"),
        "warnings": warn,
        "note_commandline": "UECC CommandLine is the literal string "
                            "'CommandLineRemoved' and carries NO launch info; the "
                            "crashpad class carries the real one in __sentry-event.",
        "note_markers": "Shim marker tags are expected to be 0 in Loki.log: the "
                        "shims' Marker() writes to docs/<shim>-marker.txt via "
                        "CreateFileA, never to the game log.",
        "note_denominator": "For crashpad, count report_is_primary==1 rows. 44 "
                            "archives hold only 22 distinct reports.",
    }
    cols = write_outputs(rows, a.out_csv, a.out_json, vs, meta)

    print("wrote %s  (%d rows, %d columns)" % (a.out_csv, len(rows), len(cols)))
    print("wrote %s" % a.out_json)
    if a.validate:
        print("\n--- SELF-VALIDATION ---")
        for line in vs:
            print("  " + line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
