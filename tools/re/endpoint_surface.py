# endpoint_surface.py -- enumerate the CLIENT's complete HTTP surface from docs/capture.log.
#
# WHY: S121's biggest result was that a feature toggle is a probe for hidden BACKEND surface --
# enabling `leaderboards` made the client call three endpoints it had never been observed to call.
# This inverts that: instead of flipping toggles one at a time and watching, read the whole
# conversation that ALREADY happened and enumerate every endpoint the client asked for.
#
# ⚠ THE USER-AGENT TRAP HAS FIRED TWICE IN THIS PROJECT (CLAUDE.md records both). Our own
# curl/Invoke-WebRequest probes land in the same log and read exactly like client traffic.
# The game is `Loki/UE5-CL-0`. This script filters on that and PRINTS the rejected count so the
# filter itself is visible rather than silent.
import re, sys, collections, json

path = sys.argv[1] if len(sys.argv) > 1 else "docs/capture.log"
GAME_UA = "Loki/UE5-CL-0"

req_re = re.compile(r"^#(\d+)\s+(\d\d:\d\d:\d\d\.\d+)\s+([A-Z]+)\s+(\S+)")
status_re = re.compile(r"^\s+->\s+(\d+)")
ua_re = re.compile(r"^\s+User-Agent:\s*(.*)$")

records = []
cur = None
with open(path, "r", encoding="utf-8", errors="replace") as f:
    for line in f:
        m = req_re.match(line)
        if m:
            if cur:
                records.append(cur)
            cur = {"n": int(m.group(1)), "t": m.group(2), "method": m.group(3),
                   "url": m.group(4), "status": None, "ua": ""}
            continue
        if cur is None:
            continue
        ms = status_re.match(line)
        if ms and cur["status"] is None:
            cur["status"] = int(ms.group(1))
            continue
        mu = ua_re.match(line)
        if mu and not cur["ua"]:
            cur["ua"] = mu.group(1).strip()
if cur:
    records.append(cur)

game = [r for r in records if GAME_UA in r["ua"]]
other = [r for r in records if GAME_UA not in r["ua"]]

print(f"total request records : {len(records)}")
print(f"  game ({GAME_UA})    : {len(game)}")
print(f"  NOT the game (excluded, would have contaminated counts): {len(other)}")
ua_counts = collections.Counter(r["ua"].split(" ")[0] for r in other)
for ua, c in ua_counts.most_common():
    print(f"      {c:5}  {ua or '(no UA)'}")
print()


def normalize(url):
    """Collapse ids/GUIDs/queries so distinct ROUTES group together."""
    p = url.split("?", 1)[0]
    parts = []
    for seg in p.split("/"):
        if re.fullmatch(r"[0-9a-fA-F]{16,}", seg):
            parts.append("{id}")
        elif re.fullmatch(r"[0-9a-fA-F-]{30,}", seg):
            parts.append("{guid}")
        elif re.fullmatch(r"\d+", seg):
            parts.append("{n}")
        elif re.fullmatch(r"party-[0-9a-zA-Z-]+", seg):
            parts.append("{party}")
        else:
            parts.append(seg)
    return "/".join(parts)


agg = collections.OrderedDict()
for r in game:
    key = (r["method"], normalize(r["url"]))
    e = agg.setdefault(key, {"count": 0, "statuses": collections.Counter(),
                             "first": r["t"], "last": r["t"], "sample": r["url"], "queries": set()})
    e["count"] += 1
    e["statuses"][r["status"]] += 1
    e["last"] = r["t"]
    if "?" in r["url"]:
        e["queries"].add(r["url"].split("?", 1)[1][:200])

print(f"distinct CLIENT routes: {len(agg)}\n")
print(f"{'cnt':>5}  {'method':<6} {'route':<62} first        statuses")
print("-" * 118)
for (method, route), e in sorted(agg.items(), key=lambda kv: -kv[1]["count"]):
    st = ",".join(f"{k}x{v}" for k, v in sorted(e["statuses"].items(), key=lambda x: str(x[0])))
    print(f"{e['count']:>5}  {method:<6} {route:<62} {e['first']}  {st}")

out = {f"{m} {r}": {"count": e["count"], "sample": e["sample"],
                    "queries": sorted(e["queries"])[:6],
                    "statuses": {str(k): v for k, v in e["statuses"].items()}}
       for (m, r), e in agg.items()}
with open(sys.argv[2] if len(sys.argv) > 2 else "endpoint_surface.json", "w") as f:
    json.dump(out, f, indent=2)
print(f"\nwrote json -> {sys.argv[2] if len(sys.argv) > 2 else 'endpoint_surface.json'}")
