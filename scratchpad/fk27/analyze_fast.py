# analyze_fast.py -- read skeptic-track-fast.csv and answer, from RAW FLAG WORDS rather than the
# original probe's boolean, the only question that matters: WHEN does each group acquire the new
# reachability value relative to when the population-majority vote ("cur") flips?
import csv, os, sys
from collections import defaultdict, Counter

HERE = os.path.dirname(os.path.abspath(__file__))
p = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "skeptic-track-fast.csv")

rows = list(csv.DictReader(open(p, newline="", encoding="utf-8")))
bysample = defaultdict(lambda: defaultdict(Counter))   # sample -> group -> Counter(low)
t_of = {}
cur_of = {}
for r in rows:
    s = int(r["sample"])
    bysample[s][r["group"]][int(r["low"])] += 1
    t_of[s] = float(r["t"])
    cur_of[s] = r["cur_before"]

groups = ["HI-ROOTED", "ORDINARY-idxmatched", "ORDINARY-lowidx", "PERMANENT"]
print("Per-sample distribution of the LOW NIBBLE (the reachability VALUE), by group.")
print("'cur' is what dominant_reach_bit() -- the original probe's yardstick -- reported.")
print("")
print("%5s %7s %5s | %-26s | %-26s | %-26s" % ("smp", "t", "cur", *groups[:3]))
prev = None
for s in sorted(bysample):
    line = []
    for g in groups[:3]:
        c = bysample[s][g]
        line.append(" ".join("%d:%d" % (k, v) for k, v in sorted(c.items())))
    key = tuple(line)
    if key != prev or s in (0, max(bysample)):
        print("%5d %7.1f %5s | %-26s | %-26s | %-26s" % (s, t_of[s], cur_of[s], *line))
        prev = key

print("")
print("=" * 100)
print("FIRST SAMPLE AT WHICH EACH GROUP IS FULLY CONVERTED TO EACH NEW VALUE")
print("=" * 100)
# find, per group, the sample at which the first object and the last object acquire each new value
order = sorted(bysample)
seen_vals = []
for s in order:
    v = bysample[s]["HI-ROOTED"]
    dom = max(v, key=lambda k: v[k])
    if not seen_vals or seen_vals[-1][1] != dom:
        seen_vals.append((s, dom))
for g in groups[:3]:
    print("  %s" % g)
    for (s0, val) in seen_vals:
        first = last = None
        for s in order:
            c = bysample[s][g]
            n = c.get(val, 0)
            tot = sum(c.values())
            if n > 0 and first is None:
                first = s
            if n == tot and tot > 0 and last is None:
                last = s
        if first is not None:
            print("    value %d : first object at s%-4d (t=%6.1f) ; ALL objects by s%-4s (t=%s)"
                  % (val, first, t_of[first], last,
                     ("%6.1f" % t_of[last]) if last is not None else "  never"))

print("")
print("=" * 100)
print("THE PERSISTENT STRAGGLERS -- ORDINARY-lowidx objects that hold a stale value for a long time")
print("=" * 100)
peridx = defaultdict(list)
for r in rows:
    if r["group"] == "ORDINARY-lowidx":
        peridx[int(r["idx"])].append((int(r["sample"]), int(r["low"])))
for idx in sorted(peridx):
    seq = []
    for s, low in peridx[idx]:
        if not seq or seq[-1][0] != low:
            seq.append((low, s))
    if len(seq) <= 4:
        print("  #%-7d %s" % (idx, " -> ".join("%d@s%d" % (v, i) for v, i in seq)))
