"""S153 page-cluster analysis of the 4,910 DARK native UFunctions.

For each dark thunk in scratchpad/s153_native_ufunction_sweep.csv, group by
the page it sits on (thunk_rva & ~0xFFF). A single live UFunction call whose
thunk sits on a dark page triggers protector demand-decryption of that whole
4 KiB page, which unblocks offline grading of every UFunction whose thunk
also sits there (S118's "driving a path decrypts it" method).

Output: a ranked list of the highest-yield dark pages, so a preregistered
live session can prioritize firing the single most productive verb.
"""
import csv, sys
from collections import defaultdict

CSV = "scratchpad/s153_native_ufunction_sweep.csv"

# Load
rows = []
with open(CSV, encoding="ascii") as f:
    r = csv.DictReader(f)
    for row in r:
        rows.append(row)

print(f"Total UFunction rows: {len(rows)}")

# Cluster DARK by page
by_page = defaultdict(list)  # page -> [(class, name, thunk_rva)]
for row in rows:
    if row["verdict"] != "DARK":
        continue
    thunk = int(row["thunk_rva"], 16)
    page = thunk & ~0xFFF
    by_page[page].append((row["class"], row["name"], thunk))

total_dark = sum(len(v) for v in by_page.values())
print(f"DARK entries: {total_dark} on {len(by_page)} distinct pages")
print()

# Rank by count
ranked = sorted(by_page.items(), key=lambda kv: len(kv[1]), reverse=True)

# Head of distribution
print(f"=== Distribution ===")
print(f"Pages with 1 dark UFunction:  {sum(1 for p,vs in ranked if len(vs)==1)}")
print(f"Pages with 2-4:               {sum(1 for p,vs in ranked if 2<=len(vs)<=4)}")
print(f"Pages with 5-9:               {sum(1 for p,vs in ranked if 5<=len(vs)<=9)}")
print(f"Pages with 10+:               {sum(1 for p,vs in ranked if len(vs)>=10)}")
print()

# Percentile analysis: what fraction of DARK UFunctions are on the top-N pages?
cum = 0
for pct in (0.1, 0.25, 0.50, 0.75, 0.90, 1.00):
    n_pages = int(len(ranked) * pct + 0.5) or 1
    cum_dark = sum(len(v) for _, v in ranked[:n_pages])
    print(f"  top {pct*100:>4.0f}% of pages ({n_pages:>4d}) = {cum_dark:>4d} dark UFunctions ({100*cum_dark/total_dark:.1f}%)")
print()

# Top 30 pages with class summary
print(f"=== Top 30 highest-yield DARK pages (fire ONE thunk on each -> N verbs graded) ===")
print(f"{'page':12s} {'count':>5s}  classes (unique on this page)")
print("-" * 100)
for page, verbs in ranked[:30]:
    classes = set(v[0] for v in verbs)
    class_str = ", ".join(sorted(classes))
    if len(class_str) > 80:
        class_str = class_str[:77] + "..."
    print(f"0x{page:08X}   {len(verbs):>5d}  {class_str}")

# Top 10 pages, verbose (list every verb)
print()
print(f"=== Top 10 pages — full verb list (highest-yield fire targets) ===")
for page, verbs in ranked[:10]:
    classes = set(v[0] for v in verbs)
    print(f"\nPAGE 0x{page:08X}  ({len(verbs)} dark UFunctions, {len(classes)} classes)")
    # Group by class
    by_cls = defaultdict(list)
    for cls, name, thunk in verbs:
        by_cls[cls].append((name, thunk))
    for cls in sorted(by_cls):
        verbs_on_cls = sorted(by_cls[cls])
        print(f"  {cls}:")
        for name, thunk in verbs_on_cls:
            print(f"    {name:50s}  thunk=0x{thunk:X}")

# --- Loki-only view: exclude stock UE classes ---
print()
print(f"=== Top 20 Loki-only DARK pages (excludes UEngine/UnrealEd/etc.) ===")
loki_ranked = []
for page, verbs in ranked:
    loki_verbs = [v for v in verbs if 'Loki' in v[0]]
    if loki_verbs:
        loki_ranked.append((page, loki_verbs, len(verbs)))
loki_ranked.sort(key=lambda x: len(x[1]), reverse=True)
print(f"{'page':12s} {'loki':>5s} / {'total':>5s}  loki classes")
print("-" * 100)
for page, loki_verbs, total in loki_ranked[:20]:
    classes = set(v[0] for v in loki_verbs)
    print(f"0x{page:08X}   {len(loki_verbs):>5d} / {total:>5d}  {', '.join(sorted(classes))[:80]}")

# --- The single-fire recommendation ---
print()
print("=== SINGLE-FIRE RECOMMENDATIONS (fire ONE UFunction to unblock N more) ===")
print()
print(f"Top page overall: 0x{ranked[0][0]:08X} — {len(ranked[0][1])} dark verbs")
top_page, top_verbs = ranked[0]
# Pick the most-obviously-named callable
callable_hints = ("Get", "Is", "Has", "Show", "Init", "Set", "Add", "Enable", "Client")
picked = None
for cls, name, thunk in top_verbs:
    if any(name.startswith(h) for h in callable_hints):
        picked = (cls, name, thunk)
        break
if picked is None:
    picked = top_verbs[0]
print(f"  Recommend firing: {picked[0]}::{picked[1]}  thunk=0x{picked[2]:X}")
print(f"  Expected yield:  ~{len(top_verbs)} verbs offline-gradable after decryption")
print(f"  Requires:        live game process, S55 CallNativeGuarded primitive")

if loki_ranked:
    print()
    print(f"Top LOKI-only page: 0x{loki_ranked[0][0]:08X} — {len(loki_ranked[0][1])} dark loki verbs")
    lp, lv, lt = loki_ranked[0]
    picked_loki = None
    for cls, name, thunk in lv:
        if any(name.startswith(h) for h in callable_hints):
            picked_loki = (cls, name, thunk)
            break
    if picked_loki is None:
        picked_loki = lv[0]
    print(f"  Recommend firing: {picked_loki[0]}::{picked_loki[1]}  thunk=0x{picked_loki[2]:X}")
    print(f"  Expected yield:  ~{lt} verbs total ({len(lv)} loki-family)")
