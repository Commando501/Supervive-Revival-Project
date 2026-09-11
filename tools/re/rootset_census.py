# rootset_census.py -- FK-27 successor. WHAT does this build's GC actually exclude from marking?
# READ-ONLY RPM. No injection, no writes, no thread suspension, no code patching. Menu is fine.
#
#   usage:  python tools\re\rootset_census.py
#           python tools\re\rootset_census.py --passes 3 --interval 25    # watch across a GC pass
#
# WHY. FK-27 (docs/s110-item-watch-gc-mechanism.md S4d) measured that poking bit 30
# (EInternalObjectFlags::RootSet) into a shim-loaded object's FUObjectItem is INERT -- the object is
# traversed and collected anyway. That is settled. But FK-27 closed on OUTCOME and never established
# the MECHANISM, and its own evidence contains an unresolved tension:
#
#     * objects carrying bit 30 NATURALLY are never marked        (measured 0% of ~4,915)
#     * objects on which the shim POKED bit 30 are marked, and collected
#
# Same bit, opposite treatment => the GC is not keying on bit 30. Something else distinguishes the two
# populations, and no one has asked what.
#
# THE HYPOTHESIS THIS PROBE TESTS. UE keeps a "disregard for GC" / permanent object pool: everything
# allocated before FUObjectArray::CloseDisregardForGC() lands in a low index range and the reachability
# sweep simply STARTS ITERATING PAST IT. Native UClasses -- exactly the population S109 used as its
# "rooted reference set" -- are allocated in that window. If that is what is happening, then bit 30 on
# those objects is a CONSEQUENCE of being permanent, not the cause of their exclusion, and poking it
# onto a high-index object gives it the flag but not the index. Everything FK-27 measured follows.
#
# THE DISCRIMINATOR, and it is a single static census:
#
#     * bit-30 objects confined to a low index prefix, nothing above it       => index-based exclusion
#       (disregard set). The flag is bookkeeping. Poking it can never work, for anyone.
#     * bit-30 objects present at HIGH indices and NOT carrying a reachability
#       value                                                                 => the flag IS honoured
#       naturally at high index, the disregard hypothesis is REFUTED, and the shim's failure needs a
#       different explanation (wrong bit? wrong item? written too late?).
#     * bit-30 objects at high indices that ARE marked                        => bit 30 is not RootSet
#       at all and FK-27 is misnamed -- the honest claim would be "we never set RootSet".
#
# WHAT THIS INSTRUMENT DOES ABOUT BEING AN INSTRUMENT (docs/method-rules.md S1). Four controls, each of
# which CAN fail, printed before any finding:
#   C1  the FUObjectArray header parses and the live count is in a plausible range
#   C2  a dominant low reachability bit exists (>=40% of the population) -- else the build changed
#   C3  UClass objects carry bit 30 at high frequency -- if they do not, bit 30 is not what we think
#   C4  FName resolution returns real names -- else every class-based split below is noise
# If a control fails the run is declared VOID for negative conclusions rather than scored.
#
# COST: one full strided-free pass over the object array (~4.7 MB) per sample. Nothing is written.
import argparse, ctypes, os, struct, sys, time
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import item_watch as IW          # reuse the CALIBRATED primitives; do not re-derive offsets

STRIDE, PERCHUNK, ITEM_FMT = IW.STRIDE, IW.PERCHUNK, IW.ITEM_FMT
ROOTBIT = 30
REACH_BITS = 0b111


def log(s):
    print(s, flush=True)


# ================================================================================================
# full-resolution census -- every index, no striding
# ================================================================================================
def full_census(w, chunks):
    """-> list of (index, flags, clusterRootIndex, objAddr) for every LIVE slot, plus free count."""
    rows = []
    free = 0
    for ci, (addr, cnt) in enumerate(chunks):
        if not addr:
            free += cnt
            continue
        data = w.rpm_into(addr, cnt * STRIDE)
        if data is None:
            log("  !! chunk %d unreadable -- census INCOMPLETE, treat totals as lower bounds" % ci)
            continue
        base_idx = ci * PERCHUNK
        for j, (o, fl, cl, se) in enumerate(struct.iter_unpack(ITEM_FMT, data.tobytes())):
            if o:
                rows.append((base_idx + j, fl & 0xFFFFFFFF, cl, o))
            else:
                free += 1
    return rows, free


def dominant_reach_bit(rows):
    """The reachability flag is a VALUE rotating through bits 0/1/2 (FK-28). Find the current one."""
    acc = [0] * 8
    for _, fl, _, _ in rows:
        for b in range(8):
            if fl & (1 << b):
                acc[b] += 1
    tot = len(rows) or 1
    pct = [100.0 * c / tot for c in acc]
    best = max(range(8), key=lambda b: pct[b])
    return (best if pct[best] >= 40.0 else None), pct


# ================================================================================================
# controls
# ================================================================================================
def run_controls(w, chunks, rows, reach_bit, pct):
    ok = True
    log("")
    log("CONTROLS (each can fail; a failure voids negative conclusions)")

    n = len(rows)
    c1 = 50_000 <= n <= 1_000_000
    log("  C1 live-object count in a plausible range : %-7s (live=%d)" % ("PASS" if c1 else "FAIL", n))
    ok &= c1

    c2 = reach_bit is not None
    log("  C2 a dominant low reachability bit exists : %-7s (%s)"
        % ("PASS" if c2 else "FAIL",
           ("bit%d at %.1f%%" % (reach_bit, pct[reach_bit])) if c2 else
           ("no low bit >=40%%; low-bit pcts = %s" % ["%.1f" % p for p in pct[:4]])))
    ok &= c2

    # C3: UClass objects must carry bit 30. Sample by resolving class names.
    cls_root = cls_tot = 0
    sampled = 0
    for idx, fl, _, o in rows:
        if sampled >= 4000:
            break
        sampled += 1
        cn = w.ocls_name(o)
        if cn == "Class":
            cls_tot += 1
            if fl & (1 << ROOTBIT):
                cls_root += 1
    frac = (100.0 * cls_root / cls_tot) if cls_tot else -1.0
    c3 = cls_tot >= 20 and frac >= 90.0
    log("  C3 UClass objects carry bit %d            : %-7s (%d/%d = %.1f%% of sampled UClasses)"
        % (ROOTBIT, "PASS" if c3 else "FAIL", cls_root, cls_tot, frac))
    ok &= c3

    names = [w.oname(o) for _, _, _, o in rows[:40]]
    good = sum(1 for x in names if x and x != "?")
    c4 = good >= 30
    log("  C4 FName resolution works                 : %-7s (%d/40 names resolved)"
        % ("PASS" if c4 else "FAIL", good))
    ok &= c4
    return ok


# ================================================================================================
# the measurement
# ================================================================================================
def analyse(w, rows, reach_bit):
    rb = 1 << ROOTBIT
    rf = (1 << reach_bit) if reach_bit is not None else 0

    rooted = [r for r in rows if r[1] & rb]
    plain = [r for r in rows if not (r[1] & rb)]

    log("")
    log("=" * 96)
    log("1. GLOBAL CONTINGENCY  (full resolution -- S110 sampled 1-in-8 and got 4915 / 17237)")
    log("=" * 96)
    r_mark = sum(1 for r in rooted if r[1] & rf)
    p_mark = sum(1 for r in plain if r[1] & rf)
    log("  bit%d SET   : %6d objects, %6d (%5.1f%%) carry the current reachability value"
        % (ROOTBIT, len(rooted), r_mark, 100.0 * r_mark / max(1, len(rooted))))
    log("  bit%d CLEAR : %6d objects, %6d (%5.1f%%) carry it"
        % (ROOTBIT, len(plain), p_mark, 100.0 * p_mark / max(1, len(plain))))

    log("")
    log("=" * 96)
    log("2. THE NEW MEASUREMENT -- INDEX DISTRIBUTION OF bit%d" % ROOTBIT)
    log("=" * 96)
    if not rooted:
        log("  no bit%d objects at all -- nothing to say. (C3 should have caught this.)" % ROOTBIT)
        return
    ridx = sorted(r[0] for r in rooted)
    pidx = sorted(r[0] for r in plain)
    log("  bit%d objects   : n=%-6d  index min=%-7d max=%-7d  median=%d"
        % (ROOTBIT, len(ridx), ridx[0], ridx[-1], ridx[len(ridx) // 2]))
    log("  other objects  : n=%-6d  index min=%-7d max=%-7d  median=%d"
        % (len(pidx), pidx[0], pidx[-1], pidx[len(pidx) // 2]))

    # Where does the rooted population stop being dense? Walk the index axis in buckets.
    hi = max(ridx[-1], pidx[-1] if pidx else 0)
    nb = 40
    step = max(1, (hi + 1 + nb - 1) // nb)
    buck_r = Counter()
    buck_t = Counter()
    for idx, fl, _, _ in rows:
        b = idx // step
        buck_t[b] += 1
        if fl & rb:
            buck_r[b] += 1
    log("")
    log("  index bucket (width %d)          live   bit%d   %%rooted" % (step, ROOTBIT))
    for b in range(nb + 1):
        if not buck_t[b]:
            continue
        log("    [%8d .. %8d)  %7d %6d   %6.2f%%"
            % (b * step, (b + 1) * step, buck_t[b], buck_r[b],
               100.0 * buck_r[b] / buck_t[b]))

    # The decisive question: high-index rooted objects -- do they exist, and are they marked?
    log("")
    log("=" * 96)
    log("3. THE DISCRIMINATOR -- do bit%d objects exist at HIGH index, and are they marked?" % ROOTBIT)
    log("=" * 96)
    # "High" = above the last index at which rooted density is still >50% in its bucket.
    dense = [b for b in range(nb + 1) if buck_t[b] and (buck_r[b] / buck_t[b]) > 0.5]
    boundary = ((max(dense) + 1) * step) if dense else 0
    log("  last index bucket where bit%d density > 50%%  -> boundary estimate = %d" % (ROOTBIT, boundary))
    hi_rooted = [r for r in rooted if r[0] >= boundary]
    log("  bit%d objects at index >= %d : %d" % (ROOTBIT, boundary, len(hi_rooted)))
    if hi_rooted:
        marked = sum(1 for r in hi_rooted if r[1] & rf)
        stale = sum(1 for r in hi_rooted if (r[1] & REACH_BITS) and not (r[1] & rf))
        none_ = sum(1 for r in hi_rooted if not (r[1] & REACH_BITS))
        log("      carrying the CURRENT reachability value : %d (%.1f%%)"
            % (marked, 100.0 * marked / len(hi_rooted)))
        log("      carrying a STALE  reachability value    : %d" % stale)
        log("      carrying NO reachability value at all   : %d" % none_)
        log("")
        log("  sample of high-index bit%d objects (index, flags, class, name):" % ROOTBIT)
        for idx, fl, cl, o in sorted(hi_rooted, key=lambda r: -r[0])[:25]:
            log("      %-8d %08X  %-34s %s" % (idx, fl, w.ocls_name(o)[:34], w.oname(o)[:40]))

    # Interpretation, stated so it can be wrong.
    log("")
    log("  READING:")
    if not hi_rooted:
        log("    bit%d is CONFINED to a low index prefix. Consistent with an INDEX-BASED exclusion" % ROOTBIT)
        log("    (UE disregard-for-GC / permanent pool): the flag would be a consequence of being")
        log("    permanent, not the cause of exclusion. Poking it onto a high-index object cannot work.")
    else:
        mk = sum(1 for r in hi_rooted if r[1] & rf)
        if mk == 0:
            log("    bit%d objects DO exist above the boundary and NONE is marked => the flag IS" % ROOTBIT)
            log("    honoured at high index. The disregard-set hypothesis is REFUTED and the shim's")
            log("    failure needs a different explanation (wrong item? written after the gather?).")
        elif mk == len(hi_rooted):
            log("    every high-index bit%d object IS marked => bit %d does not exclude anything." % (ROOTBIT, ROOTBIT))
            log("    FK-27 would be misnamed: the honest claim is 'we never set RootSet'.")
        else:
            log("    MIXED (%d of %d high-index bit%d objects marked) -- neither hypothesis is clean;"
                % (mk, len(hi_rooted), ROOTBIT))
            log("    split them by class before concluding anything.")

    # Cluster hypothesis, cheap to check while we are here.
    log("")
    log("=" * 96)
    log("4. CLUSTER FIELD (ClusterRootIndex@0x0C) -- competing hypothesis (c)")
    log("=" * 96)
    cr = Counter()
    for _, _, cl, _ in rows:
        cr["nonzero" if cl not in (0, -1) else ("minus1" if cl == -1 else "zero")] += 1
    log("  across all live objects: %s" % dict(cr))
    crr = Counter()
    for _, _, cl, _ in rooted:
        crr["nonzero" if cl not in (0, -1) else ("minus1" if cl == -1 else "zero")] += 1
    log("  across bit%d objects   : %s" % (ROOTBIT, dict(crr)))

    # Class composition of the rooted population -- is it "natives only"?
    log("")
    log("=" * 96)
    log("5. CLASS COMPOSITION of the bit%d population (top 20, sampled)" % ROOTBIT)
    log("=" * 96)
    comp = Counter()
    for idx, fl, cl, o in rooted[:6000]:
        comp[w.ocls_name(o)] += 1
    for cn, n in comp.most_common(20):
        log("    %-40s %6d" % (cn[:40], n))


def boundary_scan(rows, numEl):
    """Nail the disregard-for-GC boundary exactly.

    A permanent (disregard) pool has two independent signatures that do NOT have to agree, so
    reporting both is the control: (a) no slot below the boundary is ever FREE, because permanent
    objects are never destroyed; (b) every object below it carries bit 30. If the two boundaries
    coincide, that is a real structural edge and not an artifact of either test."""
    live = {}
    for idx, fl, _, _ in rows:
        live[idx] = fl
    rb = 1 << ROOTBIT

    first_free = None
    for i in range(numEl):
        if i not in live:
            first_free = i
            break
    first_unrooted = None
    for i in range(numEl):
        fl = live.get(i)
        if fl is None:
            continue
        if not (fl & rb):
            first_unrooted = i
            break
    last_rooted = max((idx for idx, fl in live.items() if fl & rb), default=None)

    log("")
    log("=" * 96)
    log("2b. THE DISREGARD BOUNDARY -- two independent signatures")
    log("=" * 96)
    log("  first FREE slot                         : %s" % first_free)
    log("  first LIVE object without bit%d          : %s" % (ROOTBIT, first_unrooted))
    log("  last  LIVE object with    bit%d          : %s" % (ROOTBIT, last_rooted))
    # ⚠ P8: the original compared the two boundaries by INDEX DISTANCE and printed a scary
    # "DISAGREE by 7038 slots". The meaningful quantity is the POPULATION that disagrees -- which is
    # 20 objects, not 7038 slots. An index gap is not a disagreement if almost nothing lives in it.
    if first_free is not None:
        n_unrooted_below = sum(1 for i, fl in live.items() if i < first_free and not (fl & rb))
        log("  live objects below the first free slot that lack bit%d : %d" % (ROOTBIT, n_unrooted_below))
        log("     (this, not the index distance, is the real disagreement between the two signatures)")
    # ⚠⚠ AND THE HONEST CAVEAT, from the S123 adversarial review: "zero holes" is NOT a specific
    # signature of a disregard pool. Measured in this same process, [45000..169999] -- 125,000 slots,
    # 3.2x the prefix -- ALSO has zero holes and is NOT rooted. Worse, "no holes below the first
    # hole" is true by definition. So do NOT argue the pool boundary from hole density, and do not
    # compute a uniformity probability against a scattered-free-slot model: 5,705 of the 7,282 free
    # slots form ONE contiguous run starting at the boundary. The boundary is established instead by
    # GUObjectArray.ObjFirstGCIndex, read directly at base+0x9E38920.
    # how dense is the prefix, really
    if first_free is not None:
        pre = [i for i in range(first_free)]
        prerooted = sum(1 for i in pre if live.get(i, 0) & rb)
        log("  prefix [0..%d): %d slots, %d live, %d rooted (%.3f%%)"
            % (first_free, len(pre), sum(1 for i in pre if i in live), prerooted,
               100.0 * prerooted / max(1, len(pre))))
    return first_free, first_unrooted


def track(w, objectsPtr, numEl, duration, period):
    """Follow the HIGH-INDEX rooted objects (real AddToRoot() callers) plus ordinary controls across
    GC passes. The question: does a genuinely-rooted, non-permanent object get RE-MARKED on every
    rotation? If yes, root-set membership is honoured through the MARKING phase, and the shim's poked
    object -- which went ROOTED+STALE and died -- was never in whatever the gather reads."""
    rb = 1 << ROOTBIT
    chunks = w.chunks(objectsPtr, numEl)
    rows, _ = full_census(w, chunks)
    reach_bit, _ = dominant_reach_bit(rows)
    live = {idx: fl for idx, fl, _, _ in rows}
    bnd = next((i for i in range(numEl) if i not in live), numEl)

    hi_rooted = [(idx, o) for idx, fl, _, o in rows if (fl & rb) and idx >= bnd]
    ctrl = [(idx, o) for idx, fl, _, o in rows if not (fl & rb) and idx >= bnd][:40]
    lo_rooted = [(idx, o) for idx, fl, _, o in rows if (fl & rb) and idx < bnd][:40]

    log("")
    log("=" * 96)
    log("6. TRACKING ACROSS GC PASSES  (%.0f s, sampling every %.1f s)" % (duration, period))
    log("=" * 96)
    log("  boundary=%d   high-index rooted=%d   ordinary controls=%d   permanent-pool controls=%d"
        % (bnd, len(hi_rooted), len(ctrl), len(lo_rooted)))
    log("  NOTE the GC period at rest is ~61.1 s, so a %.0f s run should cross %.1f passes."
        % (duration, duration / 61.1))

    groups = [("HI-ROOTED (real AddToRoot)", hi_rooted),
              ("ORDINARY  (control)", ctrl),
              ("PERMANENT (control)", lo_rooted)]

    # ⚠⚠ P2, THE DEFECT THAT MADE THE FIRST VERSION OF THIS FUNCTION WORTHLESS (S123 skeptic review).
    # The original recorded a BOOLEAN "does this object carry the value dominant_reach_bit() currently
    # returns". That comparator is a LAGGING MAJORITY VOTE (~15 s lag measured), and its polarity
    # INVERTS during a mark ramp -- so it measured "was marked LAST", not "was re-marked". At a 0.5 s
    # period it reported 0/32 for the same objects that read 32/32 at 0.4 s. A derived boolean threw
    # the evidence away and replaced it with an artifact of the derivation.
    # THE FIX: record the RAW FLAG WORD. Everything else is computed afterwards, from data that still
    # exists, and the raw low nibbles are printed so a reader can audit the inference themselves.
    hist = {o: [] for _, g in groups for _, o in g}
    stamps = []
    t0 = time.time()
    while time.time() - t0 < duration:
        chunks = w.chunks(objectsPtr, numEl)
        rows, _ = full_census(w, chunks)
        objs = {o: fl for _, fl, _, o in rows}
        stamps.append(time.time() - t0)
        for _, g in groups:
            for idx, o in g:
                hist[o].append(objs.get(o))     # raw flag word, or None if the object is gone
        time.sleep(period)

    # A rotation is a change in the POPULATION's modal low nibble between consecutive samples.
    # ⚠ P9: the FIRST sample is not a rotation. The original counted it, inflating every run by one.
    pop = []
    for k in range(len(stamps)):
        c = Counter()
        for _, g in groups:
            for idx, o in g:
                fl = hist[o][k]
                if fl is not None:
                    c[fl & REACH_BITS] += 1
        pop.append(c.most_common(1)[0][0] if c else None)
    rots = [(stamps[k], pop[k - 1], pop[k]) for k in range(1, len(pop)) if pop[k] != pop[k - 1]]
    for t, a, b in rots:
        log("  [t=%7.1f] modal low nibble %s -> %s" % (t, a, b))
    log("")
    log("  rotations CROSSED (first sample excluded): %d" % len(rots))
    if len(rots) < 1:
        log("  >> NO ROTATION CROSSED. This run cannot answer the re-marking question. VOID for it.")
        return

    log("")
    log("  raw low-nibble history per group (each column is one sample; this is the DATA, the")
    log("  summary below is an inference from it):")
    for name, g in groups:
        seqs = Counter()
        gone = 0
        for idx, o in g:
            h = hist[o]
            if any(x is None for x in h):
                gone += 1
            seqs["".join("." if x is None else "%X" % (x & REACH_BITS) for x in h)] += 1
        log("    %s   (n=%d, disappeared=%d)" % (name, len(g), gone))
        for s, n in seqs.most_common(4):
            log("      x%-4d %s" % (n, s[:110]))
        if len(seqs) > 4:
            log("      ... %d further distinct sequences" % (len(seqs) - 4))
    log("")
    log("  ⚠ The PERMANENT row is a TAUTOLOGY, not a finding: pool objects carry no low bits at all,")
    log("    so 'never carried the current value' is guaranteed by construction. It is a sanity check.")
    log("  ⚠ 'roots are marked first' can only be read from a sample that lands DURING a mark ramp.")
    log("    Most passes here complete in under 0.4 s, so most runs will show no ramp and cannot")
    log("    speak to ordering. Do not infer ordering from a run with no ramp.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pid", type=lambda s: int(s, 0), default=None)
    ap.add_argument("--passes", type=int, default=1,
                    help="repeat the census N times (use with --interval to cross a GC pass)")
    ap.add_argument("--interval", type=float, default=25.0, help="seconds between passes")
    ap.add_argument("--track", type=float, default=0.0,
                    help="after the census, follow rooted vs ordinary objects for N seconds")
    ap.add_argument("--track-period", type=float, default=3.0)
    a = ap.parse_args()

    pid = a.pid or IW.autodetect_pid()
    if not pid:
        log("game not running (%s not found)" % IW.PROCNAME)
        sys.exit(2)
    base = IW.autodetect_base(pid)
    if not base:
        log("could not resolve module base for pid %d" % pid)
        sys.exit(2)
    log("pid=%d base=0x%X" % (pid, base))

    w = IW.Watch(pid, base, log)
    objectsPtr, numEl = w.header()
    if not objectsPtr:
        log("FUObjectArray header did not parse at base+0x%X -- VOID" % IW.RVA_OBJOBJECTS)
        sys.exit(3)
    log("FUObjectArray: objects=0x%X numElements=%d" % (objectsPtr, numEl))

    for p in range(a.passes):
        if p:
            log("\n... sleeping %.1f s ...\n" % a.interval)
            time.sleep(a.interval)
        chunks = w.chunks(objectsPtr, numEl)
        t0 = time.time()
        rows, free = full_census(w, chunks)
        reach_bit, pct = dominant_reach_bit(rows)
        log("")
        log("#" * 96)
        log("PASS %d/%d   live=%d free=%d   sweep took %.2f s   current reachability bit = %s"
            % (p + 1, a.passes, len(rows), free, time.time() - t0,
               ("bit%d" % reach_bit) if reach_bit is not None else "UNRESOLVED"))
        log("#" * 96)
        ok = run_controls(w, chunks, rows, reach_bit, pct)
        if not ok:
            log("\n  >> AT LEAST ONE CONTROL FAILED. This pass is VOID for negative conclusions.")
        analyse(w, rows, reach_bit)
        boundary_scan(rows, numEl)

    if a.track > 0:
        track(w, objectsPtr, numEl, a.track, a.track_period)


if __name__ == "__main__":
    main()
