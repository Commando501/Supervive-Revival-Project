# item_watch.py -- S110 TASK ONE. Watch a UObject's FUObjectItem ACROSS ITS DEATH and say WHY it died.
# READ-ONLY RPM. No injection, no writes, no thread suspension, no code patching.
#
#   usage (menu, development):   item_watch.py --class AnimSequence --duration 120
#   usage (tutorial sitting):    item_watch.py --marker --duration 400
#   usage (explicit):            item_watch.py --addr 0x226FBC09E00
#
# WHY (S109 -> S110). The tutorial hero's run AnimSequence stops being a valid object 2-8 s after the
# body is built, and the shim only knows that via GcAlive() (tutorial_launch.cpp:1392):
#
#     vt = *(uintptr_t*)obj;  if (vt < base || vt-base > 0x0B000000) return false;   // vtable
#     if (*(uint32_t*)(obj+0x20) == 0) return false;                                 // NamePrivate
#
# That single predicate fires for a GC collection, a package unload, an explicit teardown, OR a slot
# recycled under a new object -- and EVERY S109 conclusion about "garbage-collected" rests on it.
# S109 eliminated the two cheap explanations: the FUObjectItem layout is correct (docs/s109-dump-
# forensics.md S25) and rooting the object (verified by readback, flags 00000004 -> 40000004) does
# NOT keep it alive (S24). What is left is a question about SEMANTICS, and it is answerable by
# watching the object's array slot instead of the object.
#
# THE DISCRIMINATOR (all read-only, none of it requires a write):
#   * item.SerialNumber changes, or item.Object becomes a DIFFERENT object  => the slot was RECYCLED:
#     the object was really destroyed and its index reissued. Decisive for "real destruction".
#   * item.Object -> 0 with Flags -> 0                                      => FUObjectArray::FreeUObjectIndex
#     ran, i.e. ~UObjectBase executed. Real destruction, whoever ordered it.
#   * Unreachable appears in item.Flags before that                         => the reachability pass did NOT
#     consider the object rooted. If we poked RootSet and it still got marked, the poked bit is NOT honoured.
#   * NEITHER moves while the object's vtable/NamePrivate go bad            => out-of-band teardown (package
#     unload, stream-out, explicit destroy, or the pointer was never what we thought) -- GC never involved.
#
# ** Sample the baseline BEFORE it is needed. ** If you only start reading once GcAlive fails you cannot
# tell a recycled slot from a destroyed one. Every target is snapshotted at acquisition, at t=0.
#
# WHAT THIS INSTRUMENT DOES ABOUT BEING AN INSTRUMENT (docs/next-session-prompt-s110.md S5;
# memory/supervive-instrument-artifact-pattern.md). Three of S109's five artifacts were gates that
# could not fail. So:
#   1. UObjectBase.InternalIndex and UObjectBase.ObjectFlags offsets are CALIBRATED live, each against a
#      control that CAN fail (index must equal the array slot; RF_ClassDefaultObject must be ~100% on
#      Default__* and rare elsewhere). Unresolved => reported as UNRESOLVED and simply not used.
#   2. Which bit is Unreachable is MEASURED, not assumed: a reachability pass marks most of the heap
#      transiently, so the sweep reports population bit frequencies and names the bit that spikes.
#      The stock EInternalObjectFlags mapping is printed as a LABEL only and no verdict depends on it.
#   3. DECOYS. N random objects are watched alongside the target. If the run ends with zero decoy
#      events AND zero target events, the watcher never demonstrated it can see a change, and the run
#      is declared VOID for negative conclusions rather than scored as "nothing happened".
#   4. The maximum observed sampling gap is recorded and printed. It is the aliasing bound: any state
#      shorter than that could have been missed, and the verdict says so instead of pretending.
#
# COST/PERTURBATION: ~2 RPMs per target per tick (default 50 ms) plus one strided array sweep per
# second (~4.7 MB read, parsed 1-in-8). No handles held on the game beyond PROCESS_VM_READ.
import argparse, ctypes, os, random, re, struct, sys, time, traceback
from collections import Counter
from ctypes import wintypes

PROCNAME = "SUPERVIVE-Win64-Shipping.exe"
REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))

# ---- this build's constants (tutorial_launch.cpp:23-25) ----------------------------------------
RVA_NAMEPOOL   = 0x9D81450
RVA_OBJOBJECTS = 0x9E38930
PERCHUNK       = 65536
STRIDE         = 0x18
ITEM_FMT       = "<Qiii4x"          # Object@0x00, Flags@0x08, ClusterRootIndex@0x0C, SerialNumber@0x10
assert struct.calcsize(ITEM_FMT) == STRIDE
CLASS_OFF      = 0x18               # NON-STANDARD in this build (stock is 0x10)
NAME_OFF       = 0x20               # NON-STANDARD in this build (stock is 0x18)
OBJHDR         = 0x30               # bytes of UObjectBase we snapshot each tick

# Stock UE5 EInternalObjectFlags -- LABELS ONLY. S109 already measured bit 1 set on 81% of ordinary
# objects and 0% of natives, which is not in this enum, so the mapping is NOT assumed to be complete.
IFLAG_NAMES = {20: "LoaderImport?", 23: "ReachableInCluster?", 24: "ClusterRoot?", 25: "Native",
               26: "Async?", 27: "AsyncLoading?", 28: "Unreachable?", 29: "Garbage/PendingKill?",
               30: "RootSet", 31: "PendingConstruction?"}
# Stock UE5 EObjectFlags -- LABELS ONLY.
OFLAG_NAMES = {0: "Public", 1: "Standalone", 2: "MarkAsNative", 3: "Transactional",
               4: "ClassDefaultObject", 5: "ArchetypeObject", 6: "Transient", 7: "MarkAsRootSet",
               8: "TagGarbageTemp", 9: "NeedInitialization", 10: "NeedLoad", 11: "KeepForCooker",
               12: "NeedPostLoad", 13: "NeedPostLoadSubobjects", 14: "NewerVersionExists",
               15: "BeginDestroyed", 16: "FinishDestroyed", 17: "BeingRegenerated",
               18: "DefaultSubObject", 19: "WasLoaded", 20: "TextExportTransient",
               21: "LoadCompleted", 22: "InheritableComponentTemplate", 23: "DuplicateTransient",
               24: "StrongRefOnFrame", 25: "NonPIEDuplicateTransient", 26: "MirroredGarbage",
               27: "WillBeLoaded", 28: "HasExternalPackage", 29: "PendingKill", 30: "Garbage",
               31: "AllocatedInSharedPage"}
RF_CDO = 1 << 4

# ================================================================================================
# process access
# ================================================================================================
k32 = ctypes.WinDLL("kernel32", use_last_error=True)
k32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
k32.OpenProcess.restype = wintypes.HANDLE
k32.ReadProcessMemory.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.c_void_p,
                                  ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
k32.ReadProcessMemory.restype = wintypes.BOOL
k32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
k32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
k32.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
k32.GetExitCodeProcess.restype = wintypes.BOOL

class PE32W(ctypes.Structure):
    _fields_ = [("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD),
                ("th32ProcessID", wintypes.DWORD), ("th32DefaultHeapID", ctypes.POINTER(ctypes.c_ulong)),
                ("th32ModuleID", wintypes.DWORD), ("cntThreads", wintypes.DWORD),
                ("th32ParentProcessID", wintypes.DWORD), ("pcPriClassBase", ctypes.c_long),
                ("dwFlags", wintypes.DWORD), ("szExeFile", wintypes.WCHAR * 260)]

class ME32W(ctypes.Structure):
    _fields_ = [("dwSize", wintypes.DWORD), ("th32ModuleID", wintypes.DWORD),
                ("th32ProcessID", wintypes.DWORD), ("GlblcntUsage", wintypes.DWORD),
                ("ProccntUsage", wintypes.DWORD), ("modBaseAddr", ctypes.POINTER(ctypes.c_byte)),
                ("modBaseSize", wintypes.DWORD), ("hModule", wintypes.HMODULE),
                ("szModule", wintypes.WCHAR * 256), ("szExePath", wintypes.WCHAR * 260)]

def autodetect_pid():
    snap = k32.CreateToolhelp32Snapshot(0x2, 0)
    if snap == wintypes.HANDLE(-1).value: return None
    e = PE32W(); e.dwSize = ctypes.sizeof(PE32W)
    ok = k32.Process32FirstW(snap, ctypes.byref(e)); found = None
    while ok:
        if e.szExeFile == PROCNAME: found = e.th32ProcessID; break
        ok = k32.Process32NextW(snap, ctypes.byref(e))
    k32.CloseHandle(snap); return found

def autodetect_base(pid):
    snap = k32.CreateToolhelp32Snapshot(0x18, pid)
    if snap == wintypes.HANDLE(-1).value: return None
    e = ME32W(); e.dwSize = ctypes.sizeof(ME32W)
    ok = k32.Module32FirstW(snap, ctypes.byref(e)); base = None
    while ok:
        if e.szModule == PROCNAME:
            base = ctypes.cast(e.modBaseAddr, ctypes.c_void_p).value; break
        ok = k32.Module32NextW(snap, ctypes.byref(e))
    k32.CloseHandle(snap); return base

# ================================================================================================
# the watcher
# ================================================================================================
class Watch:
    def __init__(self, pid, base, log):
        self.pid, self.base, self.log = pid, base, log
        # least privilege first; the packer does not object to VM_READ, but fall back if it ever does.
        self.h = k32.OpenProcess(0x0410, False, pid) or k32.OpenProcess(0x1F0FFF, False, pid)
        if not self.h:
            log("OpenProcess failed (err %d) -- run ELEVATED and check the PID" % ctypes.get_last_error())
            sys.exit(2)
        self._buf = (ctypes.c_ubyte * (PERCHUNK * STRIDE))()
        self._got = ctypes.c_size_t(0)
        self._names = {}
        self.rpm_calls = 0
        self.idxOff = None        # UObjectBase.InternalIndex   (calibrated)
        self.flagsOff = None      # UObjectBase.ObjectFlags     (calibrated)

    # ---- raw reads ------------------------------------------------------------------------------
    def rpm(self, addr, n):
        if not addr or n <= 0: return None
        b = (ctypes.c_ubyte * n)()
        self.rpm_calls += 1
        if not k32.ReadProcessMemory(self.h, ctypes.c_void_p(addr), b, n, ctypes.byref(self._got)) \
           or self._got.value != n:
            return None
        return bytes(b)

    def rpm_into(self, addr, n):
        """read into the preallocated chunk buffer -- avoids a 1.5 MB alloc per sweep."""
        self.rpm_calls += 1
        if not k32.ReadProcessMemory(self.h, ctypes.c_void_p(addr), self._buf, n, ctypes.byref(self._got)) \
           or self._got.value != n:
            return None
        return memoryview(self._buf)[:n]

    def alive_proc(self):
        code = wintypes.DWORD(0)
        if not k32.GetExitCodeProcess(self.h, ctypes.byref(code)): return False
        return code.value == 259    # STILL_ACTIVE

    # ---- FName ----------------------------------------------------------------------------------
    def fname(self, idx):
        if idx in self._names: return self._names[idx]
        blk, off = idx >> 16, (idx & 0xFFFF) << 1
        r = "?"
        bp = self.rpm(self.base + RVA_NAMEPOOL + blk * 8, 8)
        if bp:
            bp = int.from_bytes(bp, "little")
            if looksptr(bp):
                hd = self.rpm(bp + off, 2)
                if hd:
                    hd = int.from_bytes(hd, "little"); ln, wide = hd >> 6, hd & 1
                    if 0 < ln < 200:
                        s = self.rpm(bp + off + 2, ln * (2 if wide else 1))
                        if s:
                            r = ("".join(chr(s[i*2] | (s[i*2+1] << 8)) for i in range(ln))
                                 if wide else s.decode("latin1", "replace"))
        self._names[idx] = r
        return r

    def oname(self, o):
        b = self.rpm(o + NAME_OFF, 4)
        return self.fname(int.from_bytes(b, "little")) if b else "?"

    def ocls_name(self, o):
        b = self.rpm(o + CLASS_OFF, 8)
        if not b: return "?"
        c = int.from_bytes(b, "little")
        return self.oname(c) if looksptr(c) else "?"

    # ---- FUObjectArray --------------------------------------------------------------------------
    def header(self):
        hdr = self.rpm(self.base + RVA_OBJOBJECTS, 0x20)
        if not hdr: return None, 0
        objectsPtr = int.from_bytes(hdr[0:8], "little")
        numEl = int.from_bytes(hdr[0x14:0x18], "little")
        if not looksptr(objectsPtr) or not (0 < numEl < 8_000_000): return None, 0
        return objectsPtr, numEl

    def chunks(self, objectsPtr, numEl):
        """-> [(chunkAddr, count)] in index order."""
        n = (numEl + PERCHUNK - 1) // PERCHUNK
        raw = self.rpm(objectsPtr, n * 8)
        if not raw: return []
        out = []
        for ci in range(n):
            c = int.from_bytes(raw[ci*8:ci*8+8], "little")
            cnt = min(PERCHUNK, numEl - ci * PERCHUNK)
            out.append((c if looksptr(c) else 0, cnt))
        return out

    def item_addr(self, idx, chunks):
        ci, j = idx // PERCHUNK, idx % PERCHUNK
        if ci >= len(chunks) or not chunks[ci][0]: return 0
        return chunks[ci][0] + j * STRIDE

def looksptr(v): return 0x10000 <= v < 0x0001_0000_0000_0000 and (v & 7) == 0

def bits_set(v):
    v &= 0xFFFFFFFF
    out = []
    while v:
        low = v & -v
        out.append(low.bit_length() - 1)
        v ^= low
    return out

def fmt_iflags(v):
    if v == 0: return "00000000"
    lab = ",".join("%d:%s" % (b, IFLAG_NAMES.get(b, "?")) for b in bits_set(v))
    return "%08X [%s]" % (v & 0xFFFFFFFF, lab)

def fmt_oflags(v):
    if v == 0: return "00000000"
    lab = ",".join(OFLAG_NAMES.get(b, "bit%d" % b) for b in bits_set(v))
    return "%08X [%s]" % (v & 0xFFFFFFFF, lab)

# ================================================================================================
# a watched object
# ================================================================================================
class Target:
    def __init__(self, tag, idx, itemAddr, obj, name, cls, t0):
        self.tag, self.idx, self.itemAddr, self.obj = tag, idx, itemAddr, obj
        self.name, self.cls, self.t0 = name, cls, t0
        self.base_item = None       # (obj, flags, cluster, serial) at acquisition
        self.base_hdr = None
        self.item = None
        self.hdr = None
        self.events = []            # (t, what)
        self.unreach_seen = None    # t at which any NEW item-flag bit appeared
        self.freed_at = None        # t at which item.Object went 0
        self.recycled_at = None     # t at which serial changed or a different object appeared
        self.weakref_at = None      # t at which SerialNumber went 0 -> N (lazy, NOT a recycle)
        self.notmarked_at = None    # t at which it stopped carrying the current reachability flag
        self._unmarked_streak = 0
        self.state = None           # ROOTED / LIVE / ROOTED+MARK / UNMARKED (see obj_state)
        self.objdead_at = None      # t at which GcAlive's own predicate first failed
        self.dead_reported = False

    def label(self):
        return "%s/%s#%d" % (self.cls, self.name, self.idx)

# ================================================================================================
def main():
    ap = argparse.ArgumentParser(description="watch a UObject's FUObjectItem across its death (read-only)")
    ap.add_argument("--pid", default="auto")
    ap.add_argument("--base", default="auto")
    ap.add_argument("--addr", action="append", default=[], help="watch this object address (repeatable)")
    ap.add_argument("--marker", nargs="?", const="", default=None,
                    help="tail a shim marker file and watch every UObject pointer it prints "
                         "(default docs/tutorial-launch-marker.txt)")
    ap.add_argument("--cls", "--class", dest="cls", default=None,
                    help="scan for live instances of this class (substring match), e.g. AnimSequence")
    ap.add_argument("--name", default=None, help="with --cls: object-name substring filter")
    ap.add_argument("--marker-all", action="store_true",
                    help="adopt EVERY pointer the marker prints, not just loaded assets/components")
    ap.add_argument("--max-targets", type=int, default=12)
    ap.add_argument("--interval-ms", type=int, default=50,
                    help="target sampling period. 50 (not the sketch's 250) because Unreachable is "
                         "transient -- the purge can follow the mark within one frame")
    ap.add_argument("--sweep-ms", type=int, default=250, help="population sweep period (0 = off)")
    ap.add_argument("--sweep-stride", type=int, default=8, help="parse 1 item in N during the sweep")
    ap.add_argument("--decoys", type=int, default=256, help="control objects watched at sweep cadence")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--duration", type=float, default=600.0)
    ap.add_argument("--post-death", type=float, default=90.0,
                    help="keep watching this long after the last target dies, to catch a LATE recycle")
    ap.add_argument("--label", default="s110")
    ap.add_argument("--outdir", default=os.path.join(REPO, "docs"))
    ap.add_argument("--csv-all", action="store_true", help="log every sample, not just changes")
    a = ap.parse_args()

    stamp = time.strftime("%Y%m%d-%H%M%S")
    os.makedirs(a.outdir, exist_ok=True)
    logpath = os.path.join(a.outdir, "s110-itemwatch-%s-%s.log" % (a.label, stamp))
    csvpath = os.path.join(a.outdir, "s110-itemwatch-%s-%s.csv" % (a.label, stamp))
    lf = open(logpath, "w", encoding="utf-8", buffering=1)
    def log(s=""):
        print(s)
        lf.write(s + "\n")

    pid = autodetect_pid() if a.pid == "auto" else int(a.pid, 0)
    if not pid:
        log("could not find '%s' -- is the game running?" % PROCNAME); sys.exit(1)
    base = autodetect_base(pid) if a.base == "auto" else int(a.base, 16)
    if not base:
        log("could not resolve module base for pid %d" % pid); sys.exit(1)

    w = Watch(pid, base, log)
    log("=" * 100)
    log("item_watch  %s   pid=%d  base=0x%X" % (time.strftime("%Y-%m-%d %H:%M:%S"), pid, base))
    log("log=%s" % logpath)
    log("csv=%s" % csvpath)
    log("=" * 100)

    objectsPtr, numEl = w.header()
    if not objectsPtr:
        log("FUObjectArray header does not parse at base+0x%X -- wrong base or wrong build" % RVA_OBJOBJECTS)
        sys.exit(1)
    log("FUObjectArray @0x%X  objects=0x%X  numElements=%d" % (base + RVA_OBJOBJECTS, objectsPtr, numEl))

    # ------------------------------------------------------------------------------------------
    # snapshot + calibration
    # ------------------------------------------------------------------------------------------
    chunks = w.chunks(objectsPtr, numEl)
    log("chunks: %s" % ", ".join("0x%X(%d)" % c for c in chunks))
    obj2idx, live_idx = build_index(w, chunks)
    log("live objects: %d of %d slots" % (len(live_idx), numEl))
    if len(live_idx) < 1000:
        log("only %d live objects -- that is not a running UE process; refusing to continue" % len(live_idx))
        sys.exit(1)

    calibrate(w, chunks, live_idx, log)

    # ------------------------------------------------------------------------------------------
    # decoys: the control that proves this watcher can see a change at all
    # ------------------------------------------------------------------------------------------
    rnd = random.Random(a.seed)
    decoys = {}
    if a.decoys > 0:
        pool = sorted(live_idx)
        tail = pool[int(len(pool) * 0.8):]           # recently allocated -> where the churn is
        pick = set(rnd.sample(pool, min(a.decoys // 2, len(pool))))
        pick |= set(rnd.sample(tail, min(a.decoys - len(pick), len(tail))))
        for i in pick:
            ia = w.item_addr(i, chunks)
            raw = w.rpm(ia, STRIDE)
            if raw: decoys[i] = (ia, struct.unpack(ITEM_FMT, raw))
        log("decoys: %d control objects (half uniform, half from the top 20%% of indices, seed=%d)"
            % (len(decoys), a.seed))

    # ------------------------------------------------------------------------------------------
    # acquire targets
    # ------------------------------------------------------------------------------------------
    t0 = time.perf_counter()
    targets = []
    tail = None
    if a.marker is not None:
        markerPath = a.marker or os.path.join(REPO, "docs", "tutorial-launch-marker.txt")
        log("marker: %s" % markerPath)
        tail = MarkerTail(markerPath, log, a.marker_all)
    seen_marker_ptrs = set()
    last_reindex = t0

    for s in a.addr:
        add_target(w, targets, obj2idx, chunks, int(s, 16), "--addr", t0, log, a.max_targets)

    if a.cls:
        log("scanning %d live objects for class~=%r name~=%r ..." % (len(live_idx), a.cls, a.name))
        t = time.perf_counter()
        hits = scan_class(w, chunks, live_idx, a.cls, a.name)
        log("  scan took %.1f s, %d hit(s)" % (time.perf_counter() - t, len(hits)))
        for (o, i, nm, cn) in hits[:a.max_targets]:
            add_target(w, targets, obj2idx, chunks, o, "scan", t0, log, a.max_targets)

    # ------------------------------------------------------------------------------------------
    # register the interpretation BEFORE the data arrives
    # ------------------------------------------------------------------------------------------
    log()
    log("--- VERDICT TABLE, registered before the run (docs/next-session-prompt-s110.md S0) --------")
    log("  A  item.SerialNumber changes, or item.Object -> a DIFFERENT object")
    log("     => SLOT RECYCLED. The object was really destroyed and the index reissued.")
    log("  B  item.Object -> 0 (and Flags -> 0), no recycle yet")
    log("     => FreeUObjectIndex ran: ~UObjectBase executed. Real destruction.")
    log("  C  a new item-flag bit appears before B, and that bit is the one the sweep sees spike")
    log("     population-wide  => the REACHABILITY PASS marked it. If we rooted it, the poked bit")
    log("     is NOT honoured by this build's GC.")
    log("  D  neither the item nor the sweep moves, but the object's vtable/NamePrivate go bad")
    log("     => OUT-OF-BAND teardown (package unload / stream-out / explicit destroy), or the")
    log("     pointer was never the object we thought. GC was never involved.")
    log("  VOID  no target event AND no decoy event => the watcher never showed it can see a change.")
    log("-" * 100)
    log()

    # ------------------------------------------------------------------------------------------
    # the loop
    # ------------------------------------------------------------------------------------------
    cf = open(csvpath, "w", encoding="utf-8", buffering=1)
    cf.write("t_s,kind,tag,idx,item_obj,item_flags,item_cluster,item_serial,"
             "obj_vt,obj_flags,obj_idx,obj_class,obj_name,gcalive,note\n")

    interval = a.interval_ms / 1000.0
    sweep_iv = a.sweep_ms / 1000.0 if a.sweep_ms > 0 else 0
    next_sweep = t0
    next_marker = t0
    next_beat = t0 + 5.0
    last_tick = t0
    max_gap = 0.0
    ticks = 0
    base_bits = None
    prev_pct = None
    cur_reach = None
    gcpass = 0
    exc_count = 0
    prev_live = 0
    live_hist = []
    sweeps = 0
    decoy_events = 0
    gc_passes = []
    unreach_bit_votes = Counter()
    deadline = t0 + a.duration
    all_dead_at = None

    log("[t=   0.000] watching %d target(s); interval=%d ms sweep=%d ms (stride 1/%d)"
        % (len(targets), a.interval_ms, a.sweep_ms, a.sweep_stride))
    try:
        while True:
            now = time.perf_counter()
            if now >= deadline:
                log("[t=%8.3f] duration reached" % (now - t0)); break
            if not w.alive_proc():
                log("[t=%8.3f] *** THE GAME PROCESS EXITED *** (watch ends here; this is not a target event)"
                    % (now - t0))
                break

            gap = now - last_tick
            if ticks and gap > max_gap: max_gap = gap
            last_tick = now
            ticks += 1

            # ---- targets, fast ------------------------------------------------------------------
            # Every section below is individually guarded. A tutorial armed window costs a whole
            # launch to reach, so a transient read failure must never take the run's data with it --
            # and the count of swallowed exceptions is REPORTED, never hidden.
            try:
                for tg in targets:
                    sample_target(w, tg, now - t0, log, cf, a.csv_all)
            except Exception:
                exc_count += 1
                log("[t=%8.3f] probe exception in target sampling (caught):\n%s"
                    % (now - t0, traceback.format_exc()))

            # ---- marker: pick up new pointers as the shim prints them ----------------------------
            if tail and now >= next_marker:
              next_marker = now + 0.25
              try:
                for ptr, itemhint, src in tail.poll():
                    if len(targets) >= a.max_targets: break
                    if ptr in seen_marker_ptrs: continue
                    seen_marker_ptrs.add(ptr)
                    # a pointer only becomes a target if it IS in the object array -- self-validating.
                    # Rebuilding the index costs ~0.1 s, so throttle it: a freshly created object will
                    # be picked up on the next rebuild, still within a second of the shim printing it.
                    if ptr not in obj2idx and now - last_reindex > 1.0:
                        obj2idx, live_idx = build_index(w, chunks); last_reindex = now
                    if ptr in obj2idx:
                        add_target(w, targets, obj2idx, chunks, ptr, src, t0, log, a.max_targets,
                                   itemhint)
                    else:
                        seen_marker_ptrs.discard(ptr)   # retry next poll; it may not exist yet
              except Exception:
                exc_count += 1
                log("[t=%8.3f] probe exception in marker tail (caught):\n%s"
                    % (now - t0, traceback.format_exc()))

            # ---- population sweep ---------------------------------------------------------------
            # Two independent GC witnesses, because they alias differently:
            #   MARK  -- a flag bit's population share jumps. The reachability pass is only a few ms
            #            wide, so this is the one likely to be MISSED; treat its absence as no evidence.
            #   PURGE -- the live-object count DROPS. That state persists, so at this cadence it is
            #            hard to miss, and it is what actually destroys objects.
            if sweep_iv and now >= next_sweep:
              next_sweep = now + sweep_iv
              try:
                objectsPtr2, numEl2 = w.header()
                if objectsPtr2 and numEl2 != numEl:
                    numEl = numEl2; chunks = w.chunks(objectsPtr2, numEl)
                st = sweep(w, chunks, a.sweep_stride)
                if st:
                    sweeps += 1
                    live, freeslots, cnt = st["live"] * a.sweep_stride, st["free"] * a.sweep_stride, st["flagcnt"]
                    pct = bitpcts(cnt, st["live"])
                    live_hist.append((now - t0, live))
                    reach = dominant_low_bit(pct)
                    if base_bits is None:
                        base_bits = pct; prev_live = live; prev_pct = pct; cur_reach = reach
                        log("[t=%8.3f] SWEEP#1  live~%d free~%d  (1-in-%d sample, scaled)  bits: %s"
                            % (now - t0, live, freeslots, a.sweep_stride, topbits(pct)))
                        log("           reachability flag currently = bit %s  (%s)"
                            % (cur_reach, "the bit most live objects carry; see the header note"))
                        r, rr, o, orr = contingency(cnt, cur_reach)
                        log("           RootSet(bit30) vs reachability flag, over %d sampled live objects:"
                            % (r + o))
                        log("             rooted     %6d, of which %6d (%3.0f%%) carry the current flag"
                            % (r, rr, 100.0 * rr / max(1, r)))
                        log("             not rooted %6d, of which %6d (%3.0f%%) carry the current flag"
                            % (o, orr, 100.0 * orr / max(1, o)))
                    else:
                        # (1) REACHABILITY FLIP -- the whole population swaps which low bit it carries.
                        # MEASURED 2026-08-05: 232 of 256 control objects went 00000004 -> 00000002 inside
                        # one 250 ms sweep. That is one completed GC reachability pass, and it is the
                        # cleanest GC clock this process exposes. Edge-triggered, not level.
                        if reach is not None and cur_reach is not None and reach != cur_reach:
                            gcpass += 1
                            gc_passes.append((now - t0, "reach-flip", "bit%s->bit%s" % (cur_reach, reach)))
                            log("[t=%8.3f] *** GC PASS #%d *** reachability flag bit%s -> bit%s "
                                "(live~%d, %+d objects)"
                                % (now - t0, gcpass, cur_reach, reach, live, live - prev_live))
                            cur_reach = reach
                        elif reach is not None:
                            cur_reach = reach
                        # (2) PURGE -- live count drops. Persistent, so hard to alias past.
                        drop = prev_live - live
                        if drop >= max(200, prev_live // 200):
                            gc_passes.append((now - t0, "purge", drop))
                            log("[t=%8.3f] *** PURGE VISIBLE *** live %d -> %d (-%d objects destroyed "
                                "since the previous sweep)" % (now - t0, prev_live, live, drop))
                        # (3) anything else moving population-wide, vs the PREVIOUS sweep (not the first,
                        # or a single flip reprints forever -- it did, in the 14:09 run).
                        spikes = [(b, pct[b] - prev_pct[b]) for b in range(8, 32)
                                  if abs(pct[b] - prev_pct[b]) > 5.0]
                        if spikes:
                            for b, d in spikes: unreach_bit_votes[b] += 1
                            gc_passes.append((now - t0, "flagmove", [b for b, _ in spikes]))
                            log("[t=%8.3f] *** POPULATION FLAG MOVE *** live~%d  %s"
                                % (now - t0, live,
                                   ", ".join("bit%d(%s) %+.0fpp" % (b, IFLAG_NAMES.get(b, "?"), d)
                                             for b, d in spikes)))
                        prev_live = live; prev_pct = pct
                    # (4) does each target still carry the CURRENT reachable flag? An object the GC
                    # declines to mark is, by this build's own definition, unreachable.
                    if cur_reach is not None:
                        for tg in targets:
                            check_reachable(tg, cur_reach, now - t0, log)
                    # decoys ride the sweep -- they are inside the chunks we just read
                    de = check_decoys(w, decoys, chunks)
                    if de:
                        decoy_events += len(de)
                        log("[t=%8.3f] decoy control: %d slot(s) changed (%s)"
                            % (now - t0, len(de), "; ".join(de[:3])))
                    cf.write("%.3f,sweep,,,,,,,,,,,,,live=%d free=%d reachbit=%s bit30=%.1f\n"
                             % (now - t0, live, freeslots, cur_reach, pct[30]))
              except Exception:
                exc_count += 1
                log("[t=%8.3f] probe exception in population sweep (caught):\n%s"
                    % (now - t0, traceback.format_exc()))

            # ---- heartbeat ----------------------------------------------------------------------
            if now >= next_beat:
                next_beat = now + 5.0
                for tg in targets:
                    if tg.freed_at is None and tg.recycled_at is None:
                        io, ifl, icl, ise = tg.item
                        log("[t=%8.3f] alive  %-38s item{obj=0x%X flags=%08X ser=%d} obj{%s}"
                            % (now - t0, tg.label(), io, ifl & 0xFFFFFFFF, ise,
                               "gcAlive" if gcalive(w, tg) else "GCALIVE-FALSE"))

            # ---- stop rule ----------------------------------------------------------------------
            if targets and all(t.freed_at is not None or t.recycled_at is not None or
                               t.objdead_at is not None for t in targets):
                if all_dead_at is None:
                    all_dead_at = now
                    log("[t=%8.3f] every target is down; holding %.0f s more for a LATE recycle"
                        % (now - t0, a.post_death))
                elif now - all_dead_at >= a.post_death:
                    log("[t=%8.3f] post-death hold complete" % (now - t0)); break

            slack = interval - (time.perf_counter() - now)
            if slack > 0: time.sleep(slack)
    except KeyboardInterrupt:
        log("\n[t=%8.3f] interrupted" % (time.perf_counter() - t0))

    # ------------------------------------------------------------------------------------------
    # verdict
    # ------------------------------------------------------------------------------------------
    tend = time.perf_counter() - t0
    log()
    log("=" * 100)
    log("SUMMARY  observed %.1f s, %d ticks, %d sweeps, %d RPM calls" % (tend, ticks, sweeps, w.rpm_calls))
    log("  max observed sampling gap: %.0f ms  <- ALIASING BOUND: any state shorter than this could"
        % (max_gap * 1000))
    log("     have been missed, and no 'X never happened' claim below is stronger than that.")
    log("  decoy control: %d event(s) across %d control objects" % (decoy_events, len(decoys)))
    if exc_count:
        log("  ** %d probe exception(s) were caught and swallowed during the watch -- see above. **"
            % exc_count)
    flips = [g for g in gc_passes if g[1] == "reach-flip"]
    if flips:
        log("  GC PASSES (reachability-flag flips): %d in %.0f s  ->  t = %s"
            % (len(flips), tend, ", ".join("%.1f" % g[0] for g in flips)))
        log("     final reachable-flag bit: %s" % cur_reach)
    else:
        log("  GC PASSES: NONE. The population's reachability flag never flipped in %d sweeps over %.0f s,"
            % (sweeps, tend))
        log("     so no completed GC reachability pass is visible in this window at all.")
    if gc_passes:
        log("  GC activity seen at t = %s" % ", ".join("%.1f(%s)" % (g[0], g[1]) for g in gc_passes))
    else:
        log("  NO GC activity of either kind (no purge, no flag spike) in %d sweeps over %.0f s."
            % (sweeps, tend))
    if live_hist:
        lo = min(live_hist, key=lambda x: x[1]); hi = max(live_hist, key=lambda x: x[1])
        log("  live-object count: start %d, min %d @t=%.1f, max %d @t=%.1f, end %d"
            % (live_hist[0][1], lo[1], lo[0], hi[1], hi[0], live_hist[-1][1]))
    log()

    any_event = False
    for tg in targets:
        log("-" * 100)
        log("TARGET %s   acquired t=%.3f from %s" % (tg.label(), tg.t0, tg.tag))
        log("  obj=0x%X  item=0x%X  idx=%d" % (tg.obj, tg.itemAddr, tg.idx))
        bo, bf, bc, bs = tg.base_item
        log("  BASELINE item{obj=0x%X flags=%s cluster=%d serial=%d}" % (bo, fmt_iflags(bf), bc, bs))
        for (t, what) in tg.events:
            log("    t=%8.3f  %s" % (t, what))
            any_event = True
        if not tg.events:
            log("    (no change observed)")
        log("  VERDICT: %s" % verdict(tg, gc_passes, max_gap))
    if not targets:
        log("NO TARGETS WERE EVER ACQUIRED -- nothing was watched. This run measures nothing.")
    elif not any_event and decoy_events == 0:
        log()
        log("*** VOID *** neither the targets nor the %d decoys ever changed. The watcher never" % len(decoys))
        log("    demonstrated it can see a change, so 'nothing happened' is NOT a finding here.")
    log("=" * 100)
    log("log: %s" % logpath)
    log("csv: %s" % csvpath)
    cf.close(); lf.close()

# ================================================================================================
def build_index(w, chunks):
    """{objAddr: index} plus the set of live indices. One pass over every chunk."""
    obj2idx, live = {}, set()
    for ci, (addr, cnt) in enumerate(chunks):
        if not addr: continue
        data = w.rpm_into(addr, cnt * STRIDE)
        if data is None: continue
        for j, (o, fl, cl, se) in enumerate(struct.iter_unpack(ITEM_FMT, data)):
            if o:
                obj2idx[o] = ci * PERCHUNK + j
                live.add(ci * PERCHUNK + j)
    return obj2idx, live

def sweep(w, chunks, stride):
    """strided population census: live/free counts + a histogram of the item flag word."""
    live = free = 0
    cnt = Counter()
    step = STRIDE * max(1, stride)
    for addr, n in chunks:
        if not addr: continue
        data = w.rpm_into(addr, n * STRIDE)
        if data is None: return None
        raw = data.tobytes()
        for off in range(0, len(raw) - STRIDE + 1, step):
            o = int.from_bytes(raw[off:off+8], "little")
            if o:
                live += 1
                cnt[int.from_bytes(raw[off+8:off+12], "little")] += 1
            else:
                free += 1
    return {"live": live, "free": free, "flagcnt": cnt}

def bitpcts(cnt, total):
    acc = [0] * 32
    for val, n in cnt.items():
        for b in bits_set(val): acc[b] += n
    return [(100.0 * c / total if total else 0.0) for c in acc]

def topbits(pct):
    return ", ".join("bit%d %.0f%%" % (b, pct[b]) for b in range(32) if pct[b] >= 1.0)

def dominant_low_bit(pct, floor=40.0):
    """This build does NOT use a sticky 'Unreachable' bit the way stock UE4 documentation implies.
    MEASURED at the menu 2026-08-05: every live object carries exactly one of the low bits, and the
    WHOLE POPULATION swaps which one on a GC pass (0x00000004 -> 0x00000002 on 232/256 controls inside
    one 250 ms sweep, and 0x00000002 -> 0x00000004 between two runs two minutes apart). That is an
    alternating reachability flag: 'reachable in the current cycle' is a VALUE, not a fixed bit, so an
    object is unreachable when it FAILS to carry the current one. Returns that bit, or None."""
    best = max(range(8), key=lambda b: pct[b])
    return best if pct[best] >= floor else None

def contingency(cnt, reach_bit, rootbit=30):
    """Joint distribution of RootSet vs 'carries the current reachability flag', straight out of the
    flag-value histogram the sweep already built. This is the read-only half of the question S109 left
    open ('does the GC honour a directly-poked RootSet bit?'): if rooted objects are simply EXCLUDED
    from marking, then poking RootSet leaves an object holding a stale reachability value, and whatever
    reads 'unreachable' as 'value != current' sees it as garbage even though we rooted it."""
    rf = 1 << reach_bit if reach_bit is not None else 0
    rb = 1 << rootbit
    root = root_reach = other = other_reach = 0
    for val, n in cnt.items():
        v = val & 0xFFFFFFFF
        if v & rb:
            root += n
            if v & rf: root_reach += n
        else:
            other += n
            if v & rf: other_reach += n
    return root, root_reach, other, other_reach

# The four states an item's flag word can be in, given the CURRENT reachability flag value.
# MEASURED at the menu 2026-08-05 over 22,152 sampled live objects: the population splits almost
# perfectly into two of them -- rooted 4915, of which 6 (0%) carry the flag; not rooted 17237, of
# which 17234 (100%) do. So ROOTED and LIVE are the only normal states, ROOTED+MARK essentially does
# not occur, and UNMARKED is what a garbage candidate looks like.
#
# ⚠⚠ S123: THE SENTENCE ABOVE IS A POOLING ARTIFACT AND ITS CONCLUSION IS WRONG. The counts are real
# but "rooted" lumped together two populations with opposite behaviour:
#   * ~39,275 DISREGARD-FOR-GC POOL objects (InternalIndex < GUObjectArray.ObjFirstGCIndex == 39295)
#     -- never traversed, never marked, never freed. Excluded by INDEX, not by any flag. These are
#     the "0%", and they are also why native UClasses look rooted-and-never-marked.
#   * exactly 32 REAL AddToRoot() callers at high index -- ALWAYS marked, every pass. That is S110's
#     "6 of 4915", and ROOTED+MARK is their normal state, not a rarity.
# So "ROOTED and LIVE are the only normal states" is false, and a ROOTED+MARK reading is not a
# warning sign. Use tools/re/rootset_census.py, which splits by index.
# docs/fk27-successor-gc-rooting-settled.md
REACH_BITS = 0b111      # measured: the flag rotates through bits 0, 1 and 2
def obj_state(flags, reach_bit, rootbit=30):
    root = bool(flags & (1 << rootbit))
    mark = bool(flags & (1 << reach_bit)) if reach_bit is not None else False
    stale = bool(flags & REACH_BITS) and not mark     # marked in an EARLIER cycle, not re-marked in this one
    if root and mark:     return "ROOTED+MARK"   # ⚠ S123 CORRECTION: this is NOT a chimera and NOT
                                                 # anomalous. It is the NORMAL, CONTINUOUS state of a
                                                 # genuinely rooted NON-PERMANENT object -- measured on
                                                 # all 32 real AddToRoot() callers, every GC pass. Real
                                                 # roots seed the traversal and ARE marked by it.
                                                 # The old "0.03% of the natural population" reading
                                                 # pooled 39,275 disregard-POOL objects (index < 39295,
                                                 # never traversed at all) with 32 real roots and
                                                 # reported the pool's property as the root set's.
                                                 # docs/fk27-successor-gc-rooting-settled.md
    if root and stale:    return "ROOTED+STALE"  # rooted, but still carrying a PREVIOUS cycle's mark and not
                                                 # re-marked in this one -- the traversal did not reach it
    if root:              return "ROOTED"        # normal root-set object: no low bit at all, never marked
    if mark:              return "LIVE"          # normal reachable object
    if stale:             return "STALE"         # was reachable, was not re-marked this cycle => garbage
    return "UNMARKED"                            # no mark of any age and not rooted => garbage candidate

def check_reachable(tg, reach_bit, t, log):
    """Track the target's state transitions. UNMARKED for 2+ consecutive sweeps is this build's own
    definition of unreachable; one sweep of lag right after a flip is normal, not evidence."""
    if tg.item is None or tg.item[0] == 0: return     # freed: the flag word means nothing now
    st = obj_state(tg.item[1], reach_bit)
    if st != tg.state:
        if tg.state is not None:
            tg.events.append((t, "state %s -> %s   (flags=%08X, current reachability bit is %d)"
                              % (tg.state, st, tg.item[1] & 0xFFFFFFFF, reach_bit)))
            log("[t=%8.3f] %-30s state %s -> %s" % (t, tg.label()[:30], tg.state, st))
        tg.state = st
    if st in ("UNMARKED", "STALE", "ROOTED+STALE"):
        tg._unmarked_streak += 1
        if tg._unmarked_streak == 2 and tg.notmarked_at is None:
            tg.notmarked_at = t
            tg.events.append((t, "%s for 2 consecutive sweeps -- the GC traversal did not mark it in the "
                                 "current cycle. In THIS build that IS 'unreachable'." % st))
    else:
        tg._unmarked_streak = 0

def check_decoys(w, decoys, chunks):
    out = []
    for idx, (ia, before) in list(decoys.items()):
        raw = w.rpm(ia, STRIDE)
        if raw is None: continue
        cur = struct.unpack(ITEM_FMT, raw)
        if cur != before:
            what = []
            if cur[0] != before[0]: what.append("obj 0x%X->0x%X" % (before[0], cur[0]))
            if cur[1] != before[1]: what.append("flags %08X->%08X" % (before[1] & 0xFFFFFFFF, cur[1] & 0xFFFFFFFF))
            if cur[3] != before[3]: what.append("serial %d->%d" % (before[3], cur[3]))
            out.append("#%d %s" % (idx, " ".join(what)))
            decoys[idx] = (ia, cur)
    return out

def calibrate(w, chunks, live_idx, log):
    """Find UObjectBase.InternalIndex and .ObjectFlags empirically. Both checks CAN fail."""
    rnd = random.Random(7)
    sample = rnd.sample(sorted(live_idx), min(400, len(live_idx)))
    recs = []
    for i in sample:
        ia = w.item_addr(i, chunks)
        raw = w.rpm(ia, STRIDE)
        if not raw: continue
        o = struct.unpack(ITEM_FMT, raw)[0]
        if not looksptr(o): continue
        hdr = w.rpm(o, OBJHDR)
        if not hdr: continue
        recs.append((i, o, hdr))
    log()
    log("--- CALIBRATION (%d sampled objects) --------------------------------------------------" % len(recs))
    if len(recs) < 50:
        log("  too few readable objects to calibrate; InternalIndex/ObjectFlags will read UNRESOLVED")
        return

    # (1) InternalIndex: the dword that equals the object's own array slot.
    hits = []
    for off in range(0, OBJHDR, 4):
        n = sum(1 for (i, o, h) in recs if int.from_bytes(h[off:off+4], "little") == i)
        if n * 100 >= 95 * len(recs): hits.append((off, n))
    if len(hits) == 1:
        w.idxOff = hits[0][0]
        log("  InternalIndex @0x%02X  (matches the array slot for %d/%d objects)"
            % (w.idxOff, hits[0][1], len(recs)))
    elif not hits:
        log("  InternalIndex  UNRESOLVED -- no dword in the first 0x%X bytes equals the array slot." % OBJHDR)
        log("                 (not fatal: the index comes from the array scan; this was a cross-check)")
    else:
        log("  InternalIndex AMBIGUOUS at %s -- not adopted" % ", ".join("0x%02X" % o for o, _ in hits))

    # (2) ObjectFlags: RF_ClassDefaultObject must be ~universal on Default__* and rare elsewhere.
    cdo, ord_ = [], []
    for (i, o, h) in recs:
        nm = w.fname(int.from_bytes(h[NAME_OFF:NAME_OFF+4], "little"))
        (cdo if nm.startswith("Default__") else ord_).append(h)
    if len(cdo) >= 5:
        cands = []
        for off in range(0, OBJHDR, 4):
            if off in (CLASS_OFF, NAME_OFF, 0x00, 0x28): continue
            pc = sum(1 for h in cdo if int.from_bytes(h[off:off+4], "little") & RF_CDO) * 100 // len(cdo)
            po = sum(1 for h in ord_ if int.from_bytes(h[off:off+4], "little") & RF_CDO) * 100 // max(1, len(ord_))
            if pc >= 95 and po <= 5: cands.append((off, pc, po))
        if len(cands) == 1:
            w.flagsOff = cands[0][0]
            log("  ObjectFlags  @0x%02X  (RF_ClassDefaultObject on %d%% of %d CDOs, %d%% of %d others)"
                % (w.flagsOff, cands[0][1], len(cdo), cands[0][2], len(ord_)))
        elif not cands:
            log("  ObjectFlags  UNRESOLVED -- no dword carries RF_ClassDefaultObject on the %d CDOs sampled."
                % len(cdo))
            log("                 Not used, not guessed. (The item flag word is the load-bearing one.)")
        else:
            log("  ObjectFlags  AMBIGUOUS at %s -- not adopted" % ", ".join("0x%02X" % c[0] for c in cands))
    else:
        log("  ObjectFlags  NOT TESTED -- only %d CDOs in the sample (need >=5)" % len(cdo))
    log("-" * 100)

def scan_class(w, chunks, live_idx, clsfilt, namefilt):
    """Full scan: one 12-byte read per live object gives class ptr + name id together."""
    cf, nf = clsfilt.lower(), (namefilt.lower() if namefilt else None)
    clsname = {}
    hits = []
    for idx in sorted(live_idx):
        ia = w.item_addr(idx, chunks)
        raw = w.rpm(ia, 8)
        if not raw: continue
        o = int.from_bytes(raw, "little")
        if not looksptr(o): continue
        h = w.rpm(o + CLASS_OFF, (NAME_OFF - CLASS_OFF) + 4)
        if not h: continue
        c = int.from_bytes(h[0:8], "little")
        if not looksptr(c): continue
        if c not in clsname: clsname[c] = w.oname(c)
        cn = clsname[c]
        if cf not in cn.lower(): continue
        nm = w.fname(int.from_bytes(h[NAME_OFF-CLASS_OFF:NAME_OFF-CLASS_OFF+4], "little"))
        if nm.startswith("Default__"): continue
        if nf and nf not in nm.lower(): continue
        hits.append((o, idx, nm, cn))
    return hits

# The shim lines worth watching, most specific first. `item=` where the shim printed it, so the two
# instruments can be cross-checked against each other instead of merely agreeing by construction.
_MARKER_PATS = [
    (re.compile(r"\[GC\]\s+ROOT\s+(\S+)\s+0x([0-9A-Fa-f]+)\s+\(([^)]*)\)\s+item=0x([0-9A-Fa-f]+)"),
     lambda m: (int(m.group(2), 16), int(m.group(4), 16), "ROOT %s (%s)" % (m.group(1), m.group(3)))),
    (re.compile(r"\[ANIM\]\s+run anim\s+(\S+)\s+=\s+0x([0-9A-Fa-f]+)"),
     lambda m: (int(m.group(2), 16), 0, "run anim %s" % m.group(1))),
    (re.compile(r"LoadAsset_Blocking\s+ok\s+->\s+0x([0-9A-Fa-f]+)\s+\(([^)]*)\)"),
     lambda m: (int(m.group(1), 16), 0, "LoadAsset_Blocking (%s)" % m.group(2))),
    (re.compile(r"AddComponentByClass\s+ok\s+->\s+comp=0x([0-9A-Fa-f]+)\(([^)]*)\)"),
     lambda m: (int(m.group(1), 16), 0, "body component (%s)" % m.group(2))),
]
_HEX = re.compile(r"0x([0-9A-Fa-f]{8,16})")

class MarkerTail:
    """Follows a shim marker file. Two traps this handles explicitly:
       FK-25 -- Marker() opens CREATE_ALWAYS, so EVERY injection truncates the file. A shrinking
                file is a new writer, not an error: rewind to 0 rather than going deaf.
       STALE -- if the file predates this probe it is the PREVIOUS run's pointers, which mean nothing
                in this process. Skip what is already there, and say how much was skipped."""
    def __init__(self, path, log, adopt_all=False, stale_s=10.0):
        self.path, self.log, self.adopt_all = path, log, adopt_all
        self.pos = 0
        try:
            age = time.time() - os.path.getmtime(path)
            txt = open(path, "r", encoding="utf-8", errors="replace").read()
            if age > stale_s:
                self.pos = len(txt)
                log("  marker is %.0f s old (previous run): skipping its %d existing lines; only "
                    "pointers written from now on are adopted" % (age, txt.count("\n")))
            else:
                log("  marker is live (%.0f s old): parsing all %d existing lines" % (age, txt.count("\n")))
        except OSError:
            log("  marker not present yet -- will start reading when the shim creates it")

    def poll(self):
        out = []
        try:
            txt = open(self.path, "r", encoding="utf-8", errors="replace").read()
        except OSError:
            return out
        if len(txt) < self.pos:
            self.log("  marker TRUNCATED (FK-25: a new injection reopened it CREATE_ALWAYS) -- rewinding")
            self.pos = 0
        cut = txt.rfind("\n", self.pos)          # never consume a half-written line
        if cut < 0: return out
        chunk, self.pos = txt[self.pos:cut + 1], cut + 1
        for line in chunk.splitlines():
            hit = False
            for pat, ex in _MARKER_PATS:
                m = pat.search(line)
                if m:
                    out.append(ex(m)); hit = True
            if not hit and self.adopt_all:
                for m in _HEX.finditer(line):
                    v = int(m.group(1), 16)
                    if looksptr(v): out.append((v, 0, "line: " + line.strip()[:50]))
        return out

def add_target(w, targets, obj2idx, chunks, obj, tag, t0, log, maxn, itemhint=0):
    if len(targets) >= maxn: return
    if any(t.obj == obj for t in targets): return
    idx = obj2idx.get(obj)
    if idx is None:
        log("  [skip] 0x%X is not in the object array (%s)" % (obj, tag)); return
    ia = w.item_addr(idx, chunks)
    raw = w.rpm(ia, STRIDE)
    if not raw:
        log("  [skip] 0x%X item unreadable" % obj); return
    it = struct.unpack(ITEM_FMT, raw)
    nm, cn = w.oname(obj), w.ocls_name(obj)
    tg = Target(tag, idx, ia, obj, nm, cn, time.perf_counter() - t0)
    tg.base_item = it; tg.item = it
    tg.hdr = tg.base_hdr = w.rpm(obj, OBJHDR)
    targets.append(tg)
    log("[t=%8.3f] +TARGET %-38s obj=0x%X item=0x%X idx=%d" % (tg.t0, tg.label(), obj, ia, idx))
    log("           baseline item{obj=0x%X flags=%s cluster=%d serial=%d}"
        % (it[0], fmt_iflags(it[1]), it[2], it[3]))
    if w.flagsOff is not None and tg.base_hdr:
        log("           baseline obj {ObjectFlags=%s}"
            % fmt_oflags(int.from_bytes(tg.base_hdr[w.flagsOff:w.flagsOff+4], "little")))
    # ---- two cross-checks that CAN disagree -------------------------------------------------
    if itemhint:
        log("           item addr: probe 0x%X vs shim-printed 0x%X  -> %s"
            % (ia, itemhint, "AGREE" if ia == itemhint else "*** DISAGREE -- one of us is wrong ***"))
    if w.idxOff is not None and tg.base_hdr:
        oi = int.from_bytes(tg.base_hdr[w.idxOff:w.idxOff+4], "little")
        log("           InternalIndex: object says %d, array slot is %d -> %s"
            % (oi, idx, "AGREE" if oi == idx else "*** DISAGREE -- this is not that object's slot ***"))
    log("           from %s" % tag)

def gcalive(w, tg):
    """the shim's own GcAlive predicate, replicated exactly, so the two instruments are comparable."""
    h = w.rpm(tg.obj, NAME_OFF + 4)
    if not h: return False
    vt = int.from_bytes(h[0:8], "little")
    if vt < w.base or (vt - w.base) > 0x0B000000: return False
    return int.from_bytes(h[NAME_OFF:NAME_OFF+4], "little") != 0

def sample_target(w, tg, t, log, cf, csv_all):
    raw = w.rpm(tg.itemAddr, STRIDE)
    if raw is None: return
    cur = struct.unpack(ITEM_FMT, raw)
    hdr = w.rpm(tg.obj, OBJHDR)
    changed = (cur != tg.item)
    ga = gcalive(w, tg)

    if changed:
        po, pf, pc, ps = tg.item
        co, cfl, cc, cs = cur
        if co != po:
            if co == 0:
                tg.freed_at = tg.freed_at or t
                tg.events.append((t, "item.Object 0x%X -> 0   [FreeUObjectIndex ran: the UObject was destroyed]" % po))
            elif po == 0:
                tg.recycled_at = tg.recycled_at or t
                tg.events.append((t, "item.Object 0 -> 0x%X   [SLOT REUSED by a new object]" % co))
            else:
                tg.recycled_at = tg.recycled_at or t
                tg.events.append((t, "item.Object 0x%X -> 0x%X   [SLOT RECYCLED under a different object]" % (po, co)))
        if cs != ps:
            # ** TRAP, measured 2026-08-05 by the decoy control before it could mislead a verdict. **
            # "SerialNumber changes => the slot was recycled" (the S110 sketch's rule) is WRONG as
            # stated. UE allocates serial numbers LAZILY, in FUObjectArray::AllocateSerialNumber, the
            # first time anything makes an FWeakObjectPtr to the object -- a live, untouched decoy went
            # 0 -> 3373 inside 20 s at the menu. So 0 -> N is a WEAK POINTER BEING TAKEN, and only a
            # change between two NON-ZERO values (or one accompanying an Object change) is a reissue.
            if ps == 0:
                tg.weakref_at = tg.weakref_at or t
                tg.events.append((t, "item.SerialNumber 0 -> %d   [lazy AllocateSerialNumber: something "
                                     "took a WEAK POINTER to this object -- NOT a recycle]" % cs))
            elif cs == 0:
                # Second half of the same trap, and it cost a wrong verdict on the FIRST tutorial run:
                # FreeUObjectIndex CLEARS the serial (MEASURED 2026-08-05: the run anim went
                # 63939 -> 0 in the same 50 ms tick as NamePrivate -> 0 and RF_FinishDestroyed).
                # N -> 0 is the object being FREED, not its index being handed to someone else.
                tg.events.append((t, "item.SerialNumber %d -> 0   [cleared by FreeUObjectIndex -- part "
                                     "of this object's destruction, NOT a reissue]" % ps))
            else:
                tg.recycled_at = tg.recycled_at or t
                tg.events.append((t, "item.SerialNumber %d -> %d   [non-zero reissue => the index was "
                                     "handed to a new object]" % (ps, cs)))
        if cfl != pf:
            gained = bits_set(cfl & ~pf); lost = bits_set(pf & ~cfl)
            if gained and tg.unreach_seen is None: tg.unreach_seen = t
            tg.events.append((t, "item.Flags %08X -> %08X   [+%s  -%s]"
                              % (pf & 0xFFFFFFFF, cfl & 0xFFFFFFFF,
                                 ",".join("bit%d(%s)" % (b, IFLAG_NAMES.get(b, "?")) for b in gained) or "-",
                                 ",".join("bit%d(%s)" % (b, IFLAG_NAMES.get(b, "?")) for b in lost) or "-")))
        if cc != pc:
            tg.events.append((t, "item.ClusterRootIndex %d -> %d" % (pc, cc)))
        tg.item = cur

    if hdr and tg.hdr and hdr != tg.hdr:
        pv = int.from_bytes(tg.hdr[0:8], "little"); cv = int.from_bytes(hdr[0:8], "little")
        pn = int.from_bytes(tg.hdr[NAME_OFF:NAME_OFF+4], "little")
        cn = int.from_bytes(hdr[NAME_OFF:NAME_OFF+4], "little")
        if pv != cv:
            tg.events.append((t, "obj.vtable 0x%X -> 0x%X   [%s]"
                              % (pv, cv, "still in image" if w.base <= cv <= w.base + 0x0B000000
                                 else "OUT OF IMAGE -- freed/overwritten")))
        if pn != cn:
            tg.events.append((t, "obj.NamePrivate %d -> %d   [%s]"
                              % (pn, cn, "NAME_None: ~UObject ran LowLevelRename" if cn == 0 else "renamed")))
        if w.flagsOff is not None:
            pf2 = int.from_bytes(tg.hdr[w.flagsOff:w.flagsOff+4], "little")
            cf2 = int.from_bytes(hdr[w.flagsOff:w.flagsOff+4], "little")
            if pf2 != cf2:
                g = bits_set(cf2 & ~pf2); l = bits_set(pf2 & ~cf2)
                tg.events.append((t, "obj.ObjectFlags %08X -> %08X   [+%s  -%s]"
                                  % (pf2, cf2,
                                     ",".join(OFLAG_NAMES.get(b, "bit%d" % b) for b in g) or "-",
                                     ",".join(OFLAG_NAMES.get(b, "bit%d" % b) for b in l) or "-")))
        tg.hdr = hdr

    if not ga and tg.objdead_at is None:
        tg.objdead_at = t
        tg.events.append((t, "*** GcAlive() would now return FALSE -- this is the exact moment the shim "
                             "declares the asset dead ***"))

    if changed or csv_all or (not ga and not tg.dead_reported):
        io, ifl, icl, ise = cur
        vt = int.from_bytes(hdr[0:8], "little") if hdr else 0
        of = (int.from_bytes(hdr[w.flagsOff:w.flagsOff+4], "little")
              if (hdr and w.flagsOff is not None) else 0)
        oi = (int.from_bytes(hdr[w.idxOff:w.idxOff+4], "little")
              if (hdr and w.idxOff is not None) else -1)
        ocl = int.from_bytes(hdr[CLASS_OFF:CLASS_OFF+8], "little") if hdr else 0
        onm = int.from_bytes(hdr[NAME_OFF:NAME_OFF+4], "little") if hdr else 0
        cf.write("%.3f,target,%s,%d,0x%X,%08X,%d,%d,0x%X,%08X,%d,0x%X,%d,%d,\n"
                 % (t, tg.label(), tg.idx, io, ifl & 0xFFFFFFFF, icl, ise, vt, of, oi, ocl, onm, 1 if ga else 0))
    if not ga: tg.dead_reported = True

    if changed:
        for (tt, what) in tg.events[-4:]:
            if tt == t: log("[t=%8.3f] %-30s %s" % (t, tg.label()[:30], what))

def verdict(tg, gc_passes, max_gap):
    near = [g for g in gc_passes
            if tg.objdead_at is not None and abs(g[0] - tg.objdead_at) < 3.0]
    if tg.recycled_at is not None:
        v = "A  SLOT RECYCLED at t=%.3f -- the object was really destroyed and its index reissued." % tg.recycled_at
    elif tg.freed_at is not None:
        v = "B  FREED at t=%.3f -- FreeUObjectIndex ran, so ~UObjectBase executed. Real destruction." % tg.freed_at
    elif tg.objdead_at is not None:
        v = ("D  OUT-OF-BAND at t=%.3f -- the object's vtable/name went bad while its array slot was "
             "NEVER touched (no free, no recycle, no flag change). UE's GC frees the slot when it "
             "destroys an object, so this was not a collection." % tg.objdead_at)
    else:
        return "alive at end of watch -- no death observed (aliasing bound %.0f ms)" % (max_gap * 1000)
    if tg.unreach_seen is not None:
        v += ("\n           C  a NEW item-flag bit appeared first, at t=%.3f (%.3f s before the object "
              "went bad) -- something marked this slot." % (tg.unreach_seen, (tg.objdead_at or tg.freed_at or 0) - tg.unreach_seen))
    else:
        v += ("\n           NOT C: no item-flag bit ever changed while this object was watched, at a "
              "%.0f ms aliasing bound." % (max_gap * 1000))
    if tg.notmarked_at is not None:
        v += ("\n           C' at t=%.3f this object was UNMARKED for 2+ sweeps -- neither rooted nor "
              "marked reachable. In THIS build that IS 'unreachable', so the GC had it as garbage."
              % tg.notmarked_at)
    if tg.state == "ROOTED+MARK":
        v += ("\n           NOTE it ended in the CHIMERA state (RootSet OR'd onto an object that already "
              "carried a reachability value) -- 0.03%% of the natural population looks like this.")
    if tg.weakref_at is not None:
        v += ("\n           NOTE a weak pointer was taken on this object at t=%.3f (lazy serial "
              "allocation) -- something in the engine WAS referencing it." % tg.weakref_at)
    if near:
        v += "\n           GC activity (%s) was visible at t=%.1f, i.e. concurrent with the death." % (near[0][1], near[0][0])
    elif gc_passes:
        v += "\n           GC activity was seen (t=%s) but NONE within 3 s of the death -- so the death " \
             "does not line up with a collection." % ", ".join("%.1f(%s)" % (g[0], g[1]) for g in gc_passes)
    else:
        v += ("\n           NO GC activity of either kind was seen at any point in this watch, so nothing "
              "supports 'it was garbage-collected'.")
    return v

if __name__ == "__main__":
    main()
