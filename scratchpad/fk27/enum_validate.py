# enum_validate.py -- IS THE STOCK EInternalObjectFlags NUMBERING IN FORCE IN THIS BUILD?
# READ-ONLY RPM.
#
# WHY. The claim "bit 30 == RootSet" currently rests on (a) stock-UE engine knowledge and (b) the fact
# that the 32 high-index bit-30 objects have names that LOOK like textbook AddToRoot() callers. The
# probe's own control C3 ("100% of sampled UClasses carry bit 30") CANNOT DISCRIMINATE, because every
# UClass is also in the permanent pool -- C3 reads identically whether bit 30 means "RootSet" or
# "permanent". So the label is an INFERENCE, and this project's dominant failure mode is exactly an
# inference of that shape hardening into a measurement.
#
# THE DISCRIMINATOR. Do not try to identify bit 30 directly. Instead test whether the WHOLE
# EInternalObjectFlags TABLE is at its stock bit positions in this build, using flags whose truth can be
# checked against a SEPARATE field. If several independent bits sit exactly where stock UE puts them,
# then bit 30 = RootSet follows from the same table; if any of them is displaced, the table is
# non-stock here and the RootSet label is unsafe.
#
#   C-alpha  bit24 ClusterRoot        <=> FUObjectItem.ClusterRootIndex <  0     [item-internal]
#            (UE: SetClusterIndex(i) stores ClusterRootIndex = -i-1, so a cluster root is negative)
#   C-beta   bit23 ReachableInCluster  => FUObjectItem.ClusterRootIndex >  0     [item-internal]
#            (a clustered non-root stores its owner's positive index)
#   C-gamma  bit25 Native             <=> UObjectBase.ObjectFlags bit2 RF_MarkAsNative   [cross-object]
#   C-delta  bits 0/1/2 rotate        == ReachabilityFlag0/1/2   (already settled, FK-28)
#   C-eps    bit30                    <=  UObjectBase.ObjectFlags bit7 RF_MarkAsRootSet  [one-way:
#            UE sets internal RootSet for any object constructed with RF_MarkAsRootSet; the converse
#            does NOT hold because AddToRoot() sets only the internal flag]
#
# alpha and beta are the strongest: they compare a FLAG BIT against a NUMERIC FIELD four bytes away in
# the same record, so no second object read, no name resolution, and nothing that can be confounded by
# the permanent pool. They can fail.
#
# PREDICTIONS REGISTERED BEFORE THE RUN:
#   P1 C-alpha agreement >= 99%          (else the table is non-stock; the whole label is void)
#   P2 C-beta  agreement >= 99%
#   P3 C-gamma agreement >= 99%
#   P4 C-eps   : every RF_MarkAsRootSet object carries bit30 (0 violations)
#   P5 the 20 live objects in the prefix that LACK bit30 are ordinary engine objects, not a second pool
import os, struct, sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..", "tools", "re")))
import item_watch as IW

STRIDE, PERCHUNK, ITEM_FMT = IW.STRIDE, IW.PERCHUNK, IW.ITEM_FMT
RB = 1 << 30


def log(s=""):
    print(s, flush=True)


def main():
    pid = IW.autodetect_pid()
    base = IW.autodetect_base(pid) if pid else None
    if not pid:
        log("game not running"); sys.exit(2)
    w = IW.Watch(pid, base, log)
    objectsPtr, numEl = w.header()
    chunks = w.chunks(objectsPtr, numEl)
    log("pid=%d base=0x%X numEl=%d" % (pid, base, numEl))

    rows = []
    freeidx = []
    for ci, (addr, cnt) in enumerate(chunks):
        if not addr:
            continue
        data = w.rpm_into(addr, cnt * STRIDE)
        if data is None:
            log("chunk %d unreadable -- VOID" % ci); sys.exit(3)
        b = ci * PERCHUNK
        for j, (o, fl, cl, se) in enumerate(struct.iter_unpack(ITEM_FMT, data.tobytes())):
            if o:
                rows.append((b + j, fl & 0xFFFFFFFF, cl, o))
            else:
                freeidx.append(b + j)
    log("live=%d free=%d" % (len(rows), len(freeidx)))

    # ---------------------------------------------------------------- item-internal controls
    def agree(bit, pred):
        tp = fp = fn = tn = 0
        for idx, fl, cl, o in rows:
            f = bool(fl & (1 << bit))
            p = pred(cl)
            if f and p: tp += 1
            elif f and not p: fp += 1
            elif not f and p: fn += 1
            else: tn += 1
        n = len(rows)
        return tp, fp, fn, tn, 100.0 * (tp + tn) / n

    log("")
    log("=" * 96)
    log("IS THE STOCK EInternalObjectFlags TABLE IN FORCE? (independent of any RootSet assumption)")
    log("=" * 96)
    for bit, name, pred in ((24, "ClusterRoot   <=> ClusterRootIndex < 0", lambda c: c < 0),
                            (23, "ReachableInCl <=> ClusterRootIndex > 0", lambda c: c > 0)):
        tp, fp, fn, tn, acc = agree(bit, pred)
        verdict = "PASS" if acc >= 99.0 and (tp + fn) > 0 else "FAIL"
        log("  C bit%-2d %-40s %s  agree=%.3f%%  (flag&pred=%d flagonly=%d predonly=%d neither=%d)"
            % (bit, name, verdict, acc, tp, fp, fn, tn))

    # ---------------------------------------------------------------- cross-object controls
    # sample objects and read UObjectBase.ObjectFlags@0x0C (calibrated S110 4a, control = RF_CDO)
    import random
    rnd = random.Random(11)
    samp = rnd.sample(rows, min(6000, len(rows)))
    cdo_hit = cdo_tot = 0
    n25 = Counter()
    n30 = Counter()
    read = 0
    for idx, fl, cl, o in samp:
        hdr = w.rpm(o, 0x24)
        if not hdr:
            continue
        read += 1
        of = int.from_bytes(hdr[0x0C:0x10], "little")
        nm = w.fname(int.from_bytes(hdr[0x20:0x24], "little"))
        if nm.startswith("Default__"):
            cdo_tot += 1
            if of & (1 << 4):
                cdo_hit += 1
        n25[(bool(fl & (1 << 25)), bool(of & (1 << 2)))] += 1     # Native  vs RF_MarkAsNative
        n30[(bool(fl & RB), bool(of & (1 << 7)))] += 1            # bit30   vs RF_MarkAsRootSet
    log("")
    log("  POSITIVE CONTROL for ObjectFlags@0x0C: RF_ClassDefaultObject on %d/%d Default__ objects (%.1f%%)"
        % (cdo_hit, cdo_tot, 100.0 * cdo_hit / max(1, cdo_tot)))
    log("  (if that is not ~100%% every cross-object row below is void)")

    def tab(name, c, lab_a, lab_b):
        tot = sum(c.values())
        acc = 100.0 * (c[(True, True)] + c[(False, False)]) / max(1, tot)
        log("  %-46s agree=%6.2f%%   both=%-6d %s-only=%-6d %s-only=%-6d neither=%d"
            % (name, acc, c[(True, True)], lab_a, c[(True, False)], lab_b, c[(False, True)],
               c[(False, False)]))
        return acc

    log("")
    log("  cross-object, %d objects read:" % read)
    tab("C bit25 Native  vs RF_MarkAsNative(objflag b2)", n25, "b25", "RF")
    tab("C bit30 ?????   vs RF_MarkAsRootSet(objflag b7)", n30, "b30", "RF")
    log("     ^ for bit30 the ONLY prediction stock UE makes is the ONE-WAY implication")
    log("       RF_MarkAsRootSet => internal RootSet.  So 'RF-only' MUST be 0; 'b30-only' is expected")
    log("       to be large, because AddToRoot() and the permanent pool set the internal flag alone.")

    # ---------------------------------------------------------------- the prefix, exactly
    log("")
    log("=" * 96)
    log("THE 'PERMANENT PREFIX' -- what is actually there")
    log("=" * 96)
    live = {idx: (fl, cl, o) for idx, fl, cl, o in rows}
    first_free = freeidx[0] if freeidx else numEl
    log("  first free slot = %d ; total free = %d" % (first_free, len(freeidx)))
    # free-slot distribution: is the free set concentrated, making 'no holes below X' cheap?
    buckets = Counter(i // 10000 for i in freeidx)
    log("  free slots by 10k index bucket: %s"
        % ", ".join("%dk:%d" % (k * 10, v) for k, v in sorted(buckets.items())))
    gaps = []
    prev = None
    runstart = None
    for i in freeidx:
        if prev is not None and i == prev + 1:
            pass
        else:
            if runstart is not None:
                gaps.append((runstart, prev))
            runstart = i
        prev = i
    if runstart is not None:
        gaps.append((runstart, prev))
    gaps.sort(key=lambda g: -(g[1] - g[0]))
    log("  largest CONTIGUOUS free runs: %s"
        % ", ".join("[%d..%d]=%d" % (a, b, b - a + 1) for a, b in gaps[:6]))
    log("  number of distinct free runs: %d" % len(gaps))

    unrooted_pre = [(i, live[i]) for i in range(first_free) if i in live and not (live[i][0] & RB)]
    log("")
    log("  live objects BELOW the first free slot that LACK bit30: %d" % len(unrooted_pre))
    for i, (fl, cl, o) in unrooted_pre[:40]:
        log("    idx=%-7d flags=%08X cluster=%-8d %-32s %s"
            % (i, fl, cl, w.ocls_name(o)[:32], w.oname(o)[:44]))

    # ---------------------------------------------------------------- the 32, in full
    hi = sorted([(idx, fl, cl, o) for idx, fl, cl, o in rows if (fl & RB) and idx >= first_free])
    log("")
    log("=" * 96)
    log("EVERY high-index bit30 object (n=%d) -- the claim's 'real AddToRoot callers'" % len(hi))
    log("=" * 96)
    for idx, fl, cl, o in hi:
        hdr = w.rpm(o, 0x24)
        of = int.from_bytes(hdr[0x0C:0x10], "little") if hdr else 0
        log("    idx=%-7d item=%08X objflags=%08X %-34s %s"
            % (idx, fl, of, w.ocls_name(o)[:34], w.oname(o)[:40]))

    # ---------------------------------------------------------------- false-negative hunt
    log("")
    log("=" * 96)
    log("FALSE-NEGATIVE HUNT -- high-index objects one would EXPECT to be rooted. Are they in the 32?")
    log("=" * 96)
    want = ("GameEngine", "GameInstance", "GameViewportClient", "AssetManager", "Canvas",
            "World", "LocalPlayer", "PlayerController", "GameUserSettings", "CrowdManager",
            "EngineSubsystem", "ImageCache", "SlateThemeManager", "GCObjectReferencer")
    hits = Counter()
    rowsbycls = {}
    for idx, fl, cl, o in rows:
        cn = w.ocls_name(o)
        for wq in want:
            if wq.lower() in cn.lower():
                rowsbycls.setdefault(wq, []).append((idx, fl, cn, w.oname(o)))
    for wq in want:
        g = rowsbycls.get(wq, [])
        if not g:
            log("  %-20s  no live instance" % wq)
            continue
        rooted = [x for x in g if x[1] & RB]
        hi_r = [x for x in rooted if x[0] >= first_free]
        hi_u = [x for x in g if not (x[1] & RB) and x[0] >= first_free]
        log("  %-20s n=%-5d rooted=%-5d  hi-idx rooted=%-3d  hi-idx UNROOTED=%-4d %s"
            % (wq, len(g), len(rooted), len(hi_r), len(hi_u),
               ("  e.g. UNROOTED: " + ", ".join("%s#%d" % (x[3][:24], x[0]) for x in hi_u[:3]))
               if hi_u else ""))


if __name__ == "__main__":
    main()
