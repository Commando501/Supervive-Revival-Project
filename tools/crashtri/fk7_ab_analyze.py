#!/usr/bin/env python3
"""
fk7_ab_analyze.py -- read docs/fk7-ab-results.csv and report the S112 FK-7 A/B, exactly as
pre-registered in docs/s112-fk7-ab-preregistration.md.

The pre-registration fixes the analysis in advance; this script implements it and nothing else:

  * unit of analysis = the ARMED WINDOW (outcome DIED or SURVIVED). VOID_ARM, VOID_DIED_PREARM and
    STAGE_FAIL are excluded from the primary denominator -- a run where the shim never armed is not
    evidence about a shim.
  * primary test = Fisher's exact, two-sided, on deaths x arm.
  * sensitivity = the same test with VOID_DIED_PREARM recounted as deaths.
  * the interim boundary (N=6/arm, p<0.005) is reported so an early stop stays honest.

No SciPy on this machine, so Fisher's exact is computed directly from the hypergeometric
distribution with exact integer arithmetic -- no floating-point factorials, no approximation.

Usage:
    python tools/crashtri/fk7_ab_analyze.py [docs/fk7-ab-results.csv]
"""
import csv
import sys
from collections import Counter, defaultdict
from math import comb

DEFAULT_CSV = "docs/fk7-ab-results.csv"
COUNTED = ("DIED", "SURVIVED")


def fisher_exact_two_sided(a, b, c, d):
    """Two-sided Fisher's exact p for the 2x2 [[a,b],[c,d]].

    Sums the probability of every table with the same margins whose probability does not exceed
    the observed table's, which is the conventional two-sided definition. Exact rationals via
    integer binomials, so there is no cancellation error at the small counts this experiment has.
    """
    row1, row2 = a + b, c + d
    col1 = a + c
    total = row1 + row2
    if total == 0 or row1 == 0 or row2 == 0 or col1 == 0 or (b + d) == 0:
        return 1.0
    denom = comb(total, col1)

    def prob(x):
        return comb(row1, x) * comb(row2, col1 - x) / denom

    lo = max(0, col1 - row2)
    hi = min(row1, col1)
    observed = prob(a)
    # a strict > would drop ties; the convention keeps tables as extreme as the observed one.
    tol = observed * (1 + 1e-9)
    return min(1.0, sum(prob(x) for x in range(lo, hi + 1) if prob(x) <= tol))


def load(path):
    with open(path, newline="", encoding="utf-8-sig") as fh:
        return list(csv.DictReader(fh))


def bar(n, total, width=24):
    if total == 0:
        return ""
    filled = int(round(width * n / total))
    return "#" * filled + "." * (width - filled)


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_CSV
    try:
        rows = load(path)
    except FileNotFoundError:
        print(f"no results yet at {path}")
        return 1

    by_arm = defaultdict(list)
    for r in rows:
        by_arm[r["arm"]].append(r)

    print(f"=== S112 FK-7 A/B  --  {len(rows)} launches recorded, {path}\n")

    # STAGE_DEATH is its own column on purpose: it is a DEATH (the game died with only the staging
    # shims resident, before the probe was injected), but it is NOT an armed window and it is
    # arm-neutral. Folding it into STAGE_FAIL would hide a real hazard; folding it into DIED would
    # attribute an arm-neutral death to an arm. It also has to appear here for the columns to sum
    # to `total` -- this header claims nothing is hidden, so nothing may be.
    print("outcome ledger (every launch, nothing hidden):")
    print(f"  {'arm':<12} {'DIED':>5} {'SURV':>5} {'VOID_ARM':>9} {'PREARM':>7} "
          f"{'STG_DEATH':>10} {'STAGE_FAIL':>11} {'total':>6}")
    for arm in sorted(by_arm):
        c = Counter(r["outcome"] for r in by_arm[arm])
        known = (c['DIED'] + c['SURVIVED'] + c['VOID_ARM'] + c['VOID_DIED_PREARM']
                 + c['STAGE_DEATH'] + c['STAGE_FAIL'])
        flag = "" if known == len(by_arm[arm]) else f"  <-- {len(by_arm[arm])-known} UNACCOUNTED"
        print(f"  {arm:<12} {c['DIED']:>5} {c['SURVIVED']:>5} {c['VOID_ARM']:>9} "
              f"{c['VOID_DIED_PREARM']:>7} {c['STAGE_DEATH']:>10} {c['STAGE_FAIL']:>11} "
              f"{len(by_arm[arm]):>6}{flag}")
    print()

    # the arm-neutral staging hazard, reported in its own right -- five of these were classified
    # OURS/protector with only gft+fo resident, i.e. before RM_PLAY's standing patch existed
    sd = sum(1 for r in rows if r["outcome"] == "STAGE_DEATH")
    nonarmed = sum(1 for r in rows if r["outcome"] in ("STAGE_DEATH", "STAGE_FAIL"))
    if nonarmed:
        print(f"staging hazard (arm-neutral): {sd}/{nonarmed} launches that never armed died "
              f"during staging, probe never injected\n")

    # ---- primary
    print("PRIMARY -- deaths among armed windows (the pre-registered denominator):")
    stats = {}
    for arm in sorted(by_arm):
        armed = [r for r in by_arm[arm] if r["outcome"] in COUNTED]
        died = sum(1 for r in armed if r["outcome"] == "DIED")
        stats[arm] = (died, len(armed))
        pct = f"{100*died/len(armed):.0f}%" if armed else "n/a"
        print(f"  {arm:<12} {died:>3}/{len(armed):<3} {pct:>5}  {bar(died, len(armed))}")
    print()

    if "control" in stats and "treatment" in stats:
        (dc, nc), (dt, nt) = stats["control"], stats["treatment"]
        if nc and nt:
            p = fisher_exact_two_sided(dc, nc - dc, dt, nt - dt)
            print(f"  Fisher's exact (two-sided): p = {p:.5f}   "
                  f"[control {dc}/{nc} vs treatment {dt}/{nt}]")
            n_min = min(nc, nt)
            if n_min < 6:
                print(f"  -> below the interim look (N=6/arm); {6-n_min} more armed window(s) per arm.")
            elif n_min < 10:
                verdict = "STOP -- boundary met" if p < 0.005 else "CONTINUE to N=10/arm"
                print(f"  -> interim look at N={n_min}/arm, boundary p<0.005: {verdict}")
            else:
                if p < 0.05:
                    print("  -> target N reached and significant.")
                else:
                    print("  -> target N reached, NOT significant. The honest report is "
                          "'inconclusive at this N' -- do not round this.")
            print()

    # ---- sensitivity
    print("SENSITIVITY -- VOID_DIED_PREARM recounted as deaths:")
    s2 = {}
    for arm in sorted(by_arm):
        rs = [r for r in by_arm[arm] if r["outcome"] in COUNTED + ("VOID_DIED_PREARM",)]
        died = sum(1 for r in rs if r["outcome"] in ("DIED", "VOID_DIED_PREARM"))
        s2[arm] = (died, len(rs))
        pct = f"{100*died/len(rs):.0f}%" if rs else "n/a"
        print(f"  {arm:<12} {died:>3}/{len(rs):<3} {pct:>5}")
    if "control" in s2 and "treatment" in s2:
        (dc, nc), (dt, nt) = s2["control"], s2["treatment"]
        if nc and nt:
            print(f"  Fisher's exact (two-sided): p = {fisher_exact_two_sided(dc, nc-dc, dt, nt-dt):.5f}")
    print()

    # ---- the positive control's own health. A quiet control is VOID, not a pass; if it is quiet
    #      ASYMMETRICALLY, the comparison is broken rather than merely underpowered, so it is
    #      checked explicitly instead of being inferred from the ledger.
    print("POSITIVE CONTROL ([PL] init complete) -- fired / probe-injected launches:")
    for arm in sorted(by_arm):
        # STAGE_FAIL and STAGE_DEATH both end BEFORE the probe is injected, so neither is a chance
        # for the control to fire. Including them understates the arming rate and manufactures a
        # false "arming is failing" alarm -- which would wrongly cast doubt on this arm's survivals,
        # the one outcome the experiment most needs to be able to trust.
        inj = [r for r in by_arm[arm] if r["outcome"] not in ("STAGE_FAIL", "STAGE_DEATH")]
        fired = sum(1 for r in inj if r["armed"] == "yes")
        rate = f"{100*fired/len(inj):.0f}%" if inj else "n/a"
        flag = ""
        if inj and fired / len(inj) < 0.5:
            flag = "   <-- ARMING IS FAILING; treat this arm's survivals as suspect"
        print(f"  {arm:<12} {fired:>3}/{len(inj):<3} {rate:>5}{flag}")
    print()

    # ---- deaths, with the fault family left blank until classified by hand
    deaths = [r for r in rows if r["outcome"] in ("DIED", "VOID_DIED_PREARM")]
    if deaths:
        print("DEATHS -- classify each by FAULT FAMILY before counting it; never by elapsed time:")
        for r in sorted(deaths, key=lambda r: r["label"]):
            print(f"  {r['label']:<16} {r['arm']:<10} {r['outcome']:<17} "
                  f"arm+{r['died_after_arm_s'] or '?':>4}s  "
                  f"crashpad={r['new_crashpad']:<4} uecc={r['new_uecc'] or '-'}")
        print("\n  note: `died_after_arm_s` is measured from PROBE INJECTION, which is "
              "staging-invariant.\n        It is a descriptor, NOT a classifier.")
    else:
        print("DEATHS: none recorded yet.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
