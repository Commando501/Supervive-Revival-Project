# skeptic_track.py -- ADVERSARIAL replication of rootset_census.py's track(). READ-ONLY RPM.
#
# Written to REFUTE the N1-N4 claim, not to confirm it. Five things the original track() cannot do,
# each of which is a candidate instrument artifact in the original:
#
#  D1  RAW FLAG WORDS. track() records only a boolean (fl & (1<<cur)). That cannot distinguish
#      "the object was RE-MARKED (2 -> 1 -> 4)" from "the object carries several low bits at once and
#      therefore trivially always matches". Here every sample stores the full 32-bit word.
#
#  D2  TORN CENSUS. track() derives `cur` from the SAME full_census pass that reads the targets. That
#      read walks chunks in index order over ~0.2-0.5 s, so an object read early can legitimately hold
#      the OLD value while `cur` already reads NEW -- a pure phase artifact scored as "missed".
#      Here: population sample -> target burst -> population sample AGAIN. If the two population
#      samples disagree on the dominant bit, the sample is flagged MID-ROTATION and reported
#      separately instead of being silently scored.
#
#  D3  INDEX CONFOUND. track()'s ORDINARY control is `[:40]` of unrooted objects at idx >= boundary,
#      i.e. the 40 LOWEST indices just above the boundary (~39.3k), while HI-ROOTED spans 45k-186k.
#      Group membership is therefore confounded with array position and with census read order.
#      Here an extra INDEX-MATCHED control: for each hi-rooted object, the nearest live unrooted
#      object by index. Same read position, same chunk, different rootedness -- one variable.
#
#  D4  ADDRESS REUSE. track() keys objects by address and never revalidates. A slot freed and
#      reissued at the same address is invisible (`disappeared=0` cannot catch it). Here every
#      sample checks that item[idx].Object is still the SAME pointer, and class+name are re-resolved
#      at the end and diffed against the start.
#
#  D5  NO TIMING. track() reports a count, not WHEN. The claimant's mechanistic reading ("roots seed
#      the traversal so they are never caught stale") predicts misses cluster immediately after a
#      rotation. Here every miss carries its sample index and its offset from the last rotation.
#
# Also emits the exact group membership so two runs can be checked for being the SAME objects.
#
# usage:  python scratchpad\fk27\skeptic_track.py --duration 200 --period 0.5 --tag fast
import argparse, os, struct, sys, time
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
RE_DIR = os.path.abspath(os.path.join(HERE, "..", "..", "tools", "re"))
sys.path.insert(0, RE_DIR)
import item_watch as IW

STRIDE, PERCHUNK, ITEM_FMT = IW.STRIDE, IW.PERCHUNK, IW.ITEM_FMT
ROOTBIT = 30
RB = 1 << ROOTBIT
LOWMASK = 0b111


def log(s=""):
    print(s, flush=True)


def full_census(w, chunks):
    rows = []
    free = 0
    for ci, (addr, cnt) in enumerate(chunks):
        if not addr:
            free += cnt
            continue
        data = w.rpm_into(addr, cnt * STRIDE)
        if data is None:
            log("  !! chunk %d unreadable" % ci)
            continue
        base_idx = ci * PERCHUNK
        for j, (o, fl, cl, se) in enumerate(struct.iter_unpack(ITEM_FMT, data.tobytes())):
            if o:
                rows.append((base_idx + j, fl & 0xFFFFFFFF, cl, o))
            else:
                free += 1
    return rows, free


def pop_sample(w, chunks, stride=16):
    """Strided population read -> (dominant low bit, [pct0..pct7], n). Cheap enough to run TWICE
    around every target burst, which is what makes the mid-rotation self-test possible."""
    acc = [0] * 8
    live = 0
    step = STRIDE * stride
    for addr, n in chunks:
        if not addr:
            continue
        data = w.rpm_into(addr, n * STRIDE)
        if data is None:
            return None, None, 0
        raw = data.tobytes()
        for off in range(0, len(raw) - STRIDE + 1, step):
            if int.from_bytes(raw[off:off + 8], "little"):
                live += 1
                fl = int.from_bytes(raw[off + 8:off + 12], "little")
                for b in range(3):
                    if fl & (1 << b):
                        acc[b] += 1
    if not live:
        return None, None, 0
    pct = [100.0 * c / live for c in acc]
    best = max(range(3), key=lambda b: pct[b])
    return (best if pct[best] >= 40.0 else None), pct, live


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--duration", type=float, default=200.0)
    ap.add_argument("--period", type=float, default=1.0)
    ap.add_argument("--tag", default="skeptic")
    a = ap.parse_args()

    pid = IW.autodetect_pid()
    base = IW.autodetect_base(pid) if pid else None
    if not pid or not base:
        log("game not running"); sys.exit(2)
    w = IW.Watch(pid, base, log)
    objectsPtr, numEl = w.header()
    log("pid=%d base=0x%X objects=0x%X numEl=%d" % (pid, base, objectsPtr, numEl))

    chunks = w.chunks(objectsPtr, numEl)
    rows, free = full_census(w, chunks)
    live = {idx: (fl, o) for idx, fl, _, o in rows}
    bnd = next((i for i in range(numEl) if i not in live), numEl)
    log("live=%d free=%d  first-free(boundary)=%d" % (len(rows), free, bnd))

    hi_rooted = [(idx, o) for idx, fl, _, o in rows if (fl & RB) and idx >= bnd]
    ordinary = [(idx, o) for idx, fl, _, o in rows if not (fl & RB) and idx >= bnd][:40]
    permanent = [(idx, o) for idx, fl, _, o in rows if (fl & RB) and idx < bnd][:40]

    # D3 -- index-matched control: nearest live unrooted neighbour for each hi-rooted object.
    unrooted_idx = sorted(idx for idx, fl, _, o in rows if not (fl & RB) and idx >= bnd)
    import bisect
    matched, used = [], set()
    for idx, _o in hi_rooted:
        p = bisect.bisect_left(unrooted_idx, idx)
        best = None
        for cand in (unrooted_idx[max(0, p - 3):p + 4]):
            if cand in used:
                continue
            if best is None or abs(cand - idx) < abs(best - idx):
                best = cand
        if best is not None:
            used.add(best)
            matched.append((best, live[best][1]))

    groups = [("HI-ROOTED", hi_rooted), ("ORDINARY-lowidx", ordinary),
              ("ORDINARY-idxmatched", matched), ("PERMANENT", permanent)]

    log("")
    log("GROUP MEMBERSHIP (print it so two runs can be diffed -- track() never did)")
    for nm, g in groups:
        log("  %-20s n=%-3d idx=%s" % (nm, len(g), ",".join(str(i) for i, _ in g)))

    ident0 = {}
    for nm, g in groups:
        for idx, o in g:
            ident0[(nm, idx)] = (o, w.ocls_name(o), w.oname(o))

    # item addresses, resolved once -- reading the item directly avoids the torn full-census walk
    iaddr = {}
    for nm, g in groups:
        for idx, o in g:
            iaddr[(nm, idx)] = w.item_addr(idx, chunks)

    csvp = os.path.join(HERE, "skeptic-track-%s.csv" % a.tag)
    cf = open(csvp, "w", encoding="utf-8", buffering=1)
    cf.write("sample,t,cur_before,cur_after,midrot,pct0,pct1,pct2,group,idx,obj,flags,low,match\n")

    hist = defaultdict(list)      # (group, idx) -> list of (sample, t, flags, cur, midrot, identok)
    rots = []                     # (sample, t, oldbit, newbit)
    t0 = time.time()
    last = None
    s = 0
    midrot_n = 0
    while time.time() - t0 < a.duration:
        tick = time.time()
        cur_b, pct_b, _ = pop_sample(w, chunks)
        # --- target burst: ~150 tiny reads, milliseconds, all at one instant -------------------
        snap = {}
        for nm, g in groups:
            for idx, o in g:
                raw = w.rpm(iaddr[(nm, idx)], STRIDE)
                if raw is None:
                    snap[(nm, idx)] = None
                    continue
                oo, fl, cl, se = struct.unpack(ITEM_FMT, raw)
                snap[(nm, idx)] = (oo, fl & 0xFFFFFFFF)
        cur_a, pct_a, _ = pop_sample(w, chunks)
        mid = (cur_b != cur_a)
        if mid:
            midrot_n += 1
        cur = cur_b if not mid else None
        if cur is not None and cur != last:
            if last is not None:
                rots.append((s, tick - t0, last, cur))
                log("  [s=%3d t=%7.1f] rotation bit%d -> bit%d" % (s, tick - t0, last, cur))
            last = cur
        for nm, g in groups:
            for idx, o in g:
                e = snap[(nm, idx)]
                if e is None:
                    hist[(nm, idx)].append((s, tick - t0, None, cur, mid, False))
                    continue
                oo, fl = e
                identok = (oo == o)
                m = None if cur is None else bool(fl & (1 << cur))
                hist[(nm, idx)].append((s, tick - t0, fl, cur, mid, identok))
                cf.write("%d,%.3f,%s,%s,%d,%.1f,%.1f,%.1f,%s,%d,0x%X,%08X,%d,%s\n"
                         % (s, tick - t0, cur_b, cur_a, int(mid), pct_b[0], pct_b[1], pct_b[2],
                            nm, idx, oo, fl, fl & LOWMASK, m))
        s += 1
        slack = a.period - (time.time() - tick)
        if slack > 0:
            time.sleep(slack)
    cf.close()

    log("")
    log("=" * 96)
    log("RESULTS  samples=%d  period=%.2f s  duration=%.0f s" % (s, a.period, time.time() - t0))
    log("  rotations: %s" % ", ".join("s%d/t%.1f bit%d->bit%d" % r for r in rots))
    log("  MID-ROTATION samples (the two population reads disagreed): %d of %d" % (midrot_n, s))
    log("=" * 96)

    # D4 -- identity revalidation
    bad_ident = 0
    for nm, g in groups:
        for idx, o in g:
            cur_o = w.rpm(iaddr[(nm, idx)], 8)
            cur_o = int.from_bytes(cur_o, "little") if cur_o else 0
            c1 = (cur_o, w.ocls_name(cur_o) if cur_o else "-", w.oname(cur_o) if cur_o else "-")
            if c1 != ident0[(nm, idx)]:
                bad_ident += 1
                log("  IDENTITY CHANGED %s #%d: %s -> %s" % (nm, idx, ident0[(nm, idx)], c1))
    log("  D4 identity revalidation: %d of %d tracked slots changed object/class/name"
        % (bad_ident, len(ident0)))

    log("")
    log("  %-22s  n   always  missed   always/missed(excl midrot)   distinct-low-words-seen" % "group")
    for nm, g in groups:
        always = missed = 0
        always_x = missed_x = 0
        lowsets = Counter()
        for idx, o in g:
            h = hist[(nm, idx)]
            bad = [x for x in h if x[3] is not None and x[2] is not None and not (x[2] & (1 << x[3]))]
            bad_x = [x for x in bad if not x[4]]
            if bad:
                missed += 1
            else:
                always += 1
            if bad_x:
                missed_x += 1
            else:
                always_x += 1
            lows = tuple(sorted({x[2] & LOWMASK for x in h if x[2] is not None}))
            lowsets[lows] += 1
        log("  %-22s %3d  %5d   %5d   %5d/%-5d          %s"
            % (nm, len(g), always, missed, always_x, missed_x,
               "; ".join("%s x%d" % (list(k), v) for k, v in lowsets.most_common(4))))

    # D5 -- WHEN did the misses happen?
    log("")
    log("  D5 -- miss timing. sample index of every miss, per group (excl. mid-rotation samples):")
    for nm, g in groups:
        if nm == "PERMANENT":
            log("    %-22s (all-miss by construction: these carry no low bit at all)" % nm)
            continue
        allbad = Counter()
        for idx, o in g:
            for x in hist[(nm, idx)]:
                if x[3] is not None and x[2] is not None and not (x[2] & (1 << x[3])) and not x[4]:
                    allbad[x[0]] += 1
        if not allbad:
            log("    %-22s no misses at all" % nm)
        else:
            log("    %-22s %s" % (nm, ", ".join("s%d:%dobj" % (k, v) for k, v in sorted(allbad.items()))))

    # D1 -- did the low nibble actually ROTATE for the rooted set? (the re-marking question)
    log("")
    log("  D1 -- raw low-nibble sequence for HI-ROOTED (first 8 objects) and 4 matched controls:")
    for nm in ("HI-ROOTED", "ORDINARY-idxmatched"):
        g = dict(groups)[nm]
        for idx, o in g[:8 if nm == "HI-ROOTED" else 4]:
            seq = []
            for x in hist[(nm, idx)]:
                v = "?" if x[2] is None else str(x[2] & LOWMASK)
                if not seq or seq[-1][0] != v:
                    seq.append((v, x[0]))
            log("    %-20s #%-7d %s" % (nm, idx,
                                        " -> ".join("%s@s%d" % (v, i) for v, i in seq)))
    log("")
    log("  csv: %s" % csvp)


if __name__ == "__main__":
    main()
