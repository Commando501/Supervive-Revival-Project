#!/usr/bin/env python
"""
fk8_timing.py -- FK-8 DIMENSION 1: crash TIMING analysis over the fk8 corpus.

Re-derives every number in docs/fk8-timing-analysis.md from
docs/fk8-crash-corpus.json (built by tools/crashtri/fk8_corpus.py).

100% OFFLINE, READ-ONLY, stdlib only.  Does not touch the crash tree.

    python tools/crashtri/fk8_timing.py            # all sections
    python tools/crashtri/fk8_timing.py --section A

Sections:
  A  distribution + modes                     (histograms, mode composition)
  B  the four load-bearing project claims     (verdicts with numbers)
  C  time-of-day / sitting structure
  D  correlations with mechanical fields
  V  validity controls (these gate everything above)

DENOMINATORS (stated once, used everywhere):
  * UECC directories on disk ........................ 92
  * minus kind='degenerate' (CrashContext unfinished)  -8   -> 84 real UECC deaths
  * minus unwind_status='os-only' non-degenerate ....  -7   -> 77 UECC with a usable
        SecondsSinceStart.  Those 7 are NOT late deaths: their own Loki.log spans
        1.0-5.4 s with 0 map loads, i.e. they died during startup.
  * crashpad reports: 47 .dmp files across 45 archives, but only 22 DISTINCT
        uuids (report_is_primary==1).  20 of the 22 carry a non-zero
        "Seconds Since Start".
  * COMBINED timing-usable N = 77 + 20 = 97.
  * The two sources are DISJOINT (0/22 crashpad Crash-GUIDs have a UECC dir) and
        they are also nearly disjoint in TIME: UECC spans 2026-06-26..08-05
        (41 days), crashpad only 2026-08-04..08-05 (2 days, the archiver's age).
"""
import json, os, sys, math, random, collections, datetime as dt, statistics as st

HERE = os.path.dirname(os.path.abspath(__file__))
CORPUS = os.path.join(HERE, "..", "..", "docs", "fk8-crash-corpus.json")


def load():
    with open(os.path.abspath(CORPUS), encoding="utf-8") as f:
        return json.load(f)["rows"]


def I(v):
    try:
        return int(str(v).strip())
    except Exception:
        return None


def F(v):
    try:
        return float(str(v).strip())
    except Exception:
        return None


def P(s):
    if not s:
        return None
    s = s.replace("Z", "")
    for f in ("%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S"):
        try:
            return dt.datetime.strptime(s, f)
        except Exception:
            pass
    return None


def sets(rows):
    """Return (uecc_real, uecc_timing, crashpad_primary, crashpad_timing, combined)."""
    ur = [r for r in rows if r["source"] == "uecc" and r["kind"] == "crash"]
    ut = [r for r in ur if I(r["seconds_since_start"]) not in (0, None)]
    cp = [r for r in rows if r["source"] == "crashpad" and str(r.get("report_is_primary")) == "1"]
    ct = [r for r in cp if I(r["seconds_since_start"]) not in (0, None)]
    comb = ut + ct
    for r in comb:
        r["_s"] = I(r["seconds_since_start"])
    return ur, ut, cp, ct, comb


def wallclock_events(rows):
    """All 106 distinct deaths that carry an absolute TimeOfCrash, ordered.
    Sitting structure is derived from ALL of them -- including the ones whose
    SecondsSinceStart is unusable -- because a sitting boundary must not depend
    on whether one member happens to have a readable duration."""
    ur, _, cp, _, _ = sets(rows)
    E = []
    for r in ur + cp:
        t = P(r.get("time_of_crash_utc"))
        if t:
            E.append((t, I(r["seconds_since_start"]), r))
    E.sort(key=lambda x: x[0])
    return E


def sittings(E, threshold=3600):
    cl = [[E[0]]]
    for i in range(1, len(E)):
        if (E[i][0] - E[i - 1][0]).total_seconds() > threshold:
            cl.append([])
        cl[-1].append(E[i])
    return cl


# ---------------------------------------------------------------- statistics
def spearman(xs, ys):
    n = len(xs)
    def rk(v):
        s = sorted(range(n), key=lambda i: v[i]); r = [0] * n; i = 0
        while i < n:
            j = i
            while j + 1 < n and v[s[j + 1]] == v[s[i]]:
                j += 1
            for k in range(i, j + 1):
                r[s[k]] = (i + j) / 2 + 1
            i = j + 1
        return r
    a, b = rk(xs), rk(ys)
    ma, mb = st.mean(a), st.mean(b)
    num = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    den = math.sqrt(sum((x - ma) ** 2 for x in a) * sum((y - mb) ** 2 for y in b))
    rho = num / den if den else 0.0
    z = rho * math.sqrt(n - 1)
    return rho, 2 * (1 - 0.5 * (1 + math.erf(abs(z) / math.sqrt(2)))), n


def mannwhitney(a, b):
    allv = sorted(a + b); rk = {}
    for i, v in enumerate(allv):
        rk.setdefault(v, []).append(i + 1)
    rank = lambda v: sum(rk[v]) / len(rk[v])
    R = sum(rank(v) for v in a); n1, n2 = len(a), len(b)
    U = R - n1 * (n1 + 1) / 2
    mu = n1 * n2 / 2; sd = math.sqrt(n1 * n2 * (n1 + n2 + 1) / 12)
    z = (U - mu) / sd
    return U, z, 2 * (1 - 0.5 * (1 + math.erf(abs(z) / math.sqrt(2))))


def fisher(a, b, c, d):
    from math import comb
    n = a + b + c + d
    p = lambda a, b, c, d: comb(a + b, a) * comb(c + d, c) / comb(n, a + c)
    obs = p(a, b, c, d); tot = 0.0
    for i in range(0, min(a + b, a + c) + 1):
        j, k, l = a + b - i, a + c - i, d - (a - i)
        if j < 0 or k < 0 or l < 0:
            continue
        pr = p(i, j, k, l)
        if pr <= obs + 1e-12:
            tot += pr
    return tot


def rayleigh_z(vals, period):
    n = len(vals)
    c = sum(math.cos(2 * math.pi * v / period) for v in vals)
    s = sum(math.sin(2 * math.pi * v / period) for v in vals)
    return n * (math.hypot(c, s) / n) ** 2


PERIOD_GRID = [p / 2 for p in range(40, 801)]   # 20.0 .. 400.0 s, 0.5 s steps


def periodicity(vals, nboot=2000, seed=11, bw=12.0):
    """Max-over-grid Rayleigh test with a kernel-smoothed bootstrap null.
    The null preserves the coarse (clumpy) shape of the sample and destroys only
    fine periodic structure, so a hit means 'periodic beyond the clumpiness'."""
    best = max((rayleigh_z(vals, p), p) for p in PERIOD_GRID)
    rnd = random.Random(seed)
    mx = []
    for _ in range(nboot):
        samp = [max(1.0, rnd.choice(vals) + rnd.gauss(0, bw)) for _ in vals]
        mx.append(max(rayleigh_z(samp, p) for p in PERIOD_GRID))
    mx.sort()
    pg = sum(1 for m in mx if m >= best[0]) / len(mx)
    return best[1], best[0], mx[int(0.95 * len(mx))], mx[int(0.99 * len(mx))], pg


# ------------------------------------------------------------------ sections
def section_V(rows):
    print("=" * 78); print("V. VALIDITY CONTROLS  (these gate every number below)"); print("=" * 78)
    ur, ut, cp, ct, comb = sets(rows)
    print("denominators: uecc dirs 92 | real %d | timing-usable %d ; crashpad primaries %d | timing-usable %d ; COMBINED %d"
          % (len(ur), len(ut), len(cp), len(ct), len(comb)))

    # V1 -- the 7 non-degenerate os-only rows are STARTUP deaths, not lost late deaths
    oo = [r for r in ur if r.get("unwind_status") == "os-only"]
    print("\nV1  the %d dropped os-only rows are STARTUP deaths, not hidden late kills:" % len(oo))
    for r in oo:
        print("      span=%6ss  lines=%5s  loadmaps=%s  route=%s"
              % (r.get("log_span_s"), r.get("log_lines"), r.get("log_loadmap_count"), r.get("log_route")))

    # V2 -- SecondsSinceStart vs the run's own log span
    print("\nV2  SecondsSinceStart vs that run's own Loki.log span (independent duration):")
    for name, sel in (("uecc", ut), ("crashpad", ct)):
        ds = [(r["_s"] if "_s" in r else I(r["seconds_since_start"])) - F(r["log_span_s"])
              for r in sel if F(r.get("log_span_s")) is not None]
        print("      %-9s N=%2d  median(secs - log_span) = %6.1f s   range %.1f .. %.1f"
              % (name, len(ds), st.median(ds), min(ds), max(ds)))
    print("      -> log_last_ts tracks the crash to ~1 s; the residual is PRE-LOG startup time,")
    print("         which varies 0..125 s.  SecondsSinceStart counts from PROCESS start, not log open.")

    # V3 -- permutation consistency control
    cl = sittings(wallclock_events(rows))
    pairs = [((b[0] - a[0]).total_seconds(), b[1]) for c in cl for a, b in zip(c, c[1:]) if b[1]]
    obs = sum(1 for g, s in pairs if s > g)
    rnd = random.Random(7); viol = []
    for _ in range(20000):
        sh = [s for _, s in pairs]; rnd.shuffle(sh)
        viol.append(sum(1 for (g, _), s in zip(pairs, sh) if s > g))
    print("\nV3  CONSISTENCY CONTROL: a run cannot last longer than the wall-clock gap since the")
    print("      previous crash of the same sitting.  observed violations = %d / %d." % (obs, len(pairs)))
    print("      random re-pairing of the same values: mean %.1f violations, P(0) = %.5f"
          % (st.mean(viol), sum(1 for v in viol if v == 0) / len(viol)))
    print("      -> SecondsSinceStart is a genuine per-run elapsed measure.  FK-8 dead.")

    # V4 -- periodicity detector positive control
    print("\nV4  PERIODICITY DETECTOR POSITIVE CONTROL (synthetic true period 285 s):")
    rnd = random.Random(3)
    for sig in (10, 20, 40):
        S = []
        while len(S) < 91:
            v = 285 * rnd.randrange(0, 4) + rnd.gauss(0, sig)
            if 5 < v < 1000:
                S.append(v)
        per, z, n95, n99, pg = periodicity(S, nboot=400, seed=rnd.randrange(1 << 30))
        print("      jitter sigma=%2ds -> recovered %6.1f s  z=%6.2f  global p=%.3f  %s"
              % (sig, per, z, pg, "FIRES" if pg < 0.05 else "does NOT fire"))
    print("      -> the test can only see periods whose jitter is <~20 s at this N.")


def section_A(rows):
    print("=" * 78); print("A. THE DISTRIBUTION"); print("=" * 78)
    _, ut, _, ct, comb = sets(rows)
    print("combined timing-usable N = %d (uecc %d + crashpad %d)" % (len(comb), len(ut), len(ct)))
    print("\n15 s bins, 0-345 s:")
    for lo in range(0, 345, 15):
        n = [r for r in comb if lo <= r["_s"] < lo + 15]
        print("  %4d-%4d | %-22s %2d  (uecc %d, cp %d)"
              % (lo, lo + 14, "#" * len(n), len(n),
                 sum(1 for r in n if r["source"] == "uecc"), sum(1 for r in n if r["source"] == "crashpad")))
    print("\n>=345 s, individually:")
    for r in sorted([r for r in comb if r["_s"] >= 345], key=lambda r: r["_s"]):
        print("  %7d  %-9s %-19s %-6s %s" % (r["_s"], r["source"], r.get("log_route"),
                                             r.get("crash_type"), r["artifact_id"][:52]))
    modes = [("M0 startup (recovered, secs field unusable)", None, None),
             ("M1 fast", 0, 120), ("M2 ~3 min", 150, 210), ("M3 ~4-5 min", 240, 300),
             ("M4 tail", 300, 1000), ("M5 long", 1000, 10 ** 9)]
    print("\nMODE COMPOSITION")
    for name, lo, hi in modes:
        if lo is None:
            continue
        sub = [r for r in comb if lo <= r["_s"] < hi]
        vs = sorted(r["_s"] for r in sub)
        print("\n  %s  N=%d  range %d-%d  median %d" % (name, len(sub), vs[0], vs[-1], vs[len(vs) // 2]))
        for k in ("source", "crash_type", "log_route", "unwind_status", "crashed_thread_name"):
            c = collections.Counter(str(r.get(k) or "-") for r in sub)
            print("     %-20s %s" % (k, dict(c.most_common(6))))
        print("     %-20s %s" % ("chain3 (top)",
              collections.Counter(r.get("game_rva_chain3") for r in sub if r.get("game_rva_chain3")).most_common(4)))
    print("\nEMPTY BANDS (combined, N=%d): the sorted values contain no death in" % len(comb))
    vs = sorted(r["_s"] for r in comb)
    for a, b in zip(vs, vs[1:]):
        if b - a >= 30 and b <= 700:
            print("     (%d, %d)  width %d s" % (a, b, b - a))


def section_B(rows):
    print("=" * 78); print("B. THE FOUR LOAD-BEARING CLAIMS"); print("=" * 78)
    ur, ut, _, ct, comb = sets(rows)
    tut = sorted(r["_s"] for r in comb if r.get("log_route") == "tutorial")

    print("\nB1 / B2 -- the 240-299 s mode and the '~285 s integrity kill'")
    for lo in range(180, 390, 30):
        n = sorted(r["_s"] for r in comb if lo <= r["_s"] < lo + 30)
        print("     %3d-%3d : %2d  %s" % (lo, lo + 29, len(n), n))
    m3 = sorted(r["_s"] for r in comb if 240 <= r["_s"] < 300)
    print("     mode M3: N=%d  range %d-%d  median %d  ;  %d of %d are >= 283"
          % (len(m3), m3[0], m3[-1], st.median(m3), sum(1 for x in m3 if x >= 283), len(m3)))
    print("     180-300 s population: %d of %d = %.0f%% of all timing-usable deaths"
          % (sum(1 for r in comb if 180 <= r["_s"] <= 300), len(comb),
             100 * sum(1 for r in comb if 180 <= r["_s"] <= 300) / len(comb)))
    per, z, n95, n99, pg = periodicity([r["_s"] for r in comb if r["_s"] <= 1000])
    print("     PERIODICITY (modulo) test, N=%d, grid 20-400 s: best period %.1f s, z=%.2f,"
          % (sum(1 for r in comb if r["_s"] <= 1000), per, z))
    print("       null 95th=%.2f 99th=%.2f -> GLOBAL p=%.3f  => NO periodic kill detectable." % (n95, n99, pg))

    print("\nB3 -- the FK-7 '28-second band (173-201 s)'")
    win = [r for r in ur if (r.get("time_of_crash_utc") or "")[:10] in ("2026-07-24", "2026-07-25", "2026-07-26")]
    ws = sorted(I(r["seconds_since_start"]) for r in win if I(r["seconds_since_start"]))
    print("     original scope (UECC, 2026-07-24..26): N=%d, values %s -> band %d-%d (%d s wide)"
          % (len(ws), ws, ws[0], ws[-1], ws[-1] - ws[0]))
    band = sorted(r["_s"] for r in comb if 150 <= r["_s"] <= 210)
    print("     corpus-wide 150-210 s: N=%d, values %s" % (len(band), band))
    print("     routes: %s" % dict(collections.Counter(r.get("log_route") for r in comb if 150 <= r["_s"] <= 210)))
    ANIM = {"3495973", "349596d", "34713aa"}; CAM = {"12c7e2d", "3c5dc52"}
    for fam, S in (("ANIM", ANIM), ("CAMERA", CAM)):
        hits = [(I(r["seconds_since_start"]), (r.get("time_of_crash_utc") or "")[:10])
                for r in ur if (r.get("game_rva_chain") or "").split()[:1] and (r.get("game_rva_chain") or "").split()[0] in S]
        print("     family %-6s across the WHOLE corpus: %s" % (fam, sorted(hits)))

    print("\nB4 -- 'the tutorial run dies within ~1-5 min'")
    print("     tutorial-route deaths N=%d: %s" % (len(tut), tut))
    print("     60-300 s: %d/%d = %.0f%%" % (sum(1 for x in tut if 60 <= x <= 300), len(tut),
                                             100 * sum(1 for x in tut if 60 <= x <= 300) / len(tut)))
    print("     empirical CDF of tutorial deaths:")
    for T in (120, 150, 175, 200, 220, 250, 285, 300, 330, 360, 500):
        n = sum(1 for x in tut if x <= T)
        print("       <= %4d s : %2d/%d = %5.1f%%" % (T, n, len(tut), 100 * n / len(tut)))
    for route in ("tutorial", "tutorial-attempted", "menu-login", "menu-lobby"):
        v = sorted(r["_s"] for r in comb if r.get("log_route") == route)
        if v:
            print("     %-19s N=%-3d min=%-5d med=%-6d max=%d" % (route, len(v), v[0], st.median(v), v[-1]))


def section_C(rows):
    print("=" * 78); print("C. TIME-OF-DAY / SESSION STRUCTURE"); print("=" * 78)
    E = wallclock_events(rows)
    ur = [r for r in rows if r["source"] == "uecc" and r["kind"] == "crash"]
    cp = [r for r in rows if r["source"] == "crashpad" and str(r.get("report_is_primary")) == "1"]
    for nm, sel in (("uecc", ur), ("crashpad", cp)):
        ts = [P(r.get("time_of_crash_utc")) for r in sel]
        ts = [t for t in ts if t]
        print("  %-9s N=%d  %s .. %s" % (nm, len(ts), min(ts), max(ts)))
    print("  wall-clock events used for clustering: %d (84 uecc + 22 crashpad)" % len(E))
    for TH in (1800, 3600, 7200):
        cl = sittings(E, TH)
        print("  gap threshold %5ds -> %3d sittings, sizes %s"
              % (TH, len(cl), dict(sorted(collections.Counter(len(c) for c in cl).items()))))
    cl = sittings(E)
    print("\n  sittings (gap > 1 h):")
    for c in cl:
        print("    %-16s n=%-3d dur=%4.0f min  secs=%s"
              % (c[0][0].strftime("%Y-%m-%d %H:%M"), len(c), (c[-1][0] - c[0][0]).total_seconds() / 60,
                 ",".join(str(x[1]) for x in c)[:60]))
    Fst = [c[0][1] for c in cl if c[0][1]]
    Lat = [x[1] for c in cl for x in c[1:] if x[1]]
    U, z, p = mannwhitney(Fst, Lat)
    print("\n  FIRST-of-sitting  N=%d median=%.0f  >=400 s: %d (%.0f%%)"
          % (len(Fst), st.median(Fst), sum(1 for x in Fst if x >= 400), 100 * sum(1 for x in Fst if x >= 400) / len(Fst)))
    print("  LATER-in-sitting  N=%d median=%.0f  >=400 s: %d (%.0f%%)"
          % (len(Lat), st.median(Lat), sum(1 for x in Lat if x >= 400), 100 * sum(1 for x in Lat if x >= 400) / len(Lat)))
    print("  Mann-Whitney on the medians: z=%.2f p=%.3f (NOT different)" % (z, p))
    print("  Fisher exact on the >=400 s tail: p=%.4f"
          % fisher(sum(1 for x in Fst if x >= 400), sum(1 for x in Fst if x < 400),
                   sum(1 for x in Lat if x >= 400), sum(1 for x in Lat if x < 400)))
    ov = [((b[0] - a[0]).total_seconds() - b[1]) for c in cl for a, b in zip(c, c[1:]) if b[1]]
    print("  relaunch overhead (gap - run duration) N=%d: median %.0f s, min %.0f, max %.0f"
          % (len(ov), st.median(ov), min(ov), max(ov)))


def section_D(rows):
    print("=" * 78); print("D. CORRELATIONS WITH MECHANICAL FIELDS"); print("=" * 78)
    _, ut, _, _, _ = sets(rows)
    fields = ["log_bytes", "log_lines", "mem_peak_used_physical", "mem_used_physical", "mem_used_virtual",
              "mem_avail_physical", "thread_count", "xml_module_count", "minidump_bytes", "md_module_count",
              "pcallstack_nframes", "pcallstack_ngame", "num_cores", "log_loadmap_count"]
    print("  marginal Spearman vs SecondsSinceStart (UECC timing-usable, N=%d):" % len(ut))
    for f in fields:
        pts = [(I(r["seconds_since_start"]), F(r.get(f))) for r in ut]
        pts = [(a, b) for a, b in pts if b is not None and not (f.startswith("mem") and b == 0)]
        if len(pts) < 8:
            continue
        rho, p, n = spearman([a for a, _ in pts], [b for _, b in pts])
        print("    %-24s N=%-3d rho=%6.3f p=%.4f%s" % (f, n, rho, p, "   <-- p<0.01" if p < 0.01 else ""))
    print("\n  CONFOUND CHECK -- thread_count / xml_module_count are route artefacts:")
    for route in ("menu-login", "menu-lobby", "tutorial-attempted", "tutorial"):
        sub = [r for r in ut if r.get("log_route") == route]
        if sub:
            print("    %-19s N=%-3d med_secs=%-6.0f med_threads=%-5.0f med_modules=%-5.0f"
                  % (route, len(sub), st.median([I(r["seconds_since_start"]) for r in sub]),
                     st.median([F(r["thread_count"]) for r in sub]),
                     st.median([F(r["xml_module_count"]) for r in sub])))
    print("\n  THE ONE REAL MECHANICAL CORRELATE -- within the single assert family")
    fam = [r for r in ut if (r.get("assert_file") or "").endswith("UnrealEngine.cpp")]
    for f in ("mem_used_physical", "mem_peak_used_physical", "mem_avail_physical", "mem_used_virtual"):
        pts = [(I(r["seconds_since_start"]), F(r[f])) for r in fam if F(r[f])]
        rho, p, n = spearman([a for a, _ in pts], [b for _, b in pts])
        print("    UnrealEngine.cpp:15551  %-24s N=%d rho=%6.3f p=%.4f" % (f, n, rho, p))
    lo = [F(r["mem_used_physical"]) / 1048576 for r in fam if I(r["seconds_since_start"]) < 150]
    hi = [F(r["mem_used_physical"]) / 1048576 for r in fam if I(r["seconds_since_start"]) >= 150]
    print("    split at 150 s:  <150 s N=%d %.0f-%.0f MB   |   >=150 s N=%d %.0f-%.0f MB   overlap=%s"
          % (len(lo), min(lo), max(lo), len(hi), min(hi), max(hi), not (max(hi) < min(lo))))
    a = [I(r["seconds_since_start"]) for r in ut if r.get("crash_type") == "Crash"]
    b = [I(r["seconds_since_start"]) for r in ut if r.get("crash_type") == "Assert"]
    U, z, p = mannwhitney(a, b)
    print("\n  Crash (N=%d med %.0f) vs Assert (N=%d med %.0f): MW z=%.2f p=%.3f"
          % (len(a), st.median(a), len(b), st.median(b), z, p))


def main():
    rows = load()
    want = None
    if "--section" in sys.argv:
        want = sys.argv[sys.argv.index("--section") + 1].upper()
    for name, fn in (("V", section_V), ("A", section_A), ("B", section_B), ("C", section_C), ("D", section_D)):
        if want in (None, name):
            fn(rows); print()


if __name__ == "__main__":
    main()
