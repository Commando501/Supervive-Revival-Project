# Diff the CLIENT's observed routes against the server's REGISTERED routes.
# Anything the client asks for that has no explicit registration falls to main.go's "/" catch-all,
# which answers 200 {} -- indistinguishable, from the log alone, from a real handler.
import json, re, subprocess, sys, collections

SP = "C:/Users/eastr/AppData/Local/Temp/claude/G--git-Supervive-Revival-Project/27df21eb-7a4a-491d-ad5c-b757ac28a76c/scratchpad"
obs = json.load(open(f"{SP}/endpoint_surface.json"))
routes = [l.strip() for l in open(f"{SP}/routes.txt") if l.strip()]

# Build matchers for Go 1.22 mux patterns: {x} matches one segment, {x...} matches the rest.
pats = []
for r in routes:
    if " " in r:
        meth, path = r.split(" ", 1)
    else:
        meth, path = "*", r
    rx = "^"
    for seg in path.split("/"):
        if not seg:
            continue
        if seg.endswith("...}") and seg.startswith("{"):
            rx += "/.*"
        elif seg.startswith("{") and seg.endswith("}"):
            rx += "/[^/]+"
        else:
            rx += "/" + re.escape(seg)
    rx = (rx or "^/") + "$"
    pats.append((meth, re.compile(rx), r))


def served(method, path):
    for meth, rx, raw in pats:
        if raw in ("/", "GET /{$}"):
            continue
        if meth not in ("*", method):
            continue
        if rx.match(path):
            return raw
    return None


unserved, servedrows = [], []
for key, e in obs.items():
    method, route = key.split(" ", 1)
    # use the concrete sample so {id}-style placeholders don't do the matching for us
    concrete = e["sample"].split("?", 1)[0]
    hit = served(method, concrete)
    (servedrows if hit else unserved).append((e["count"], method, route, hit, e))

print("=" * 100)
print("UNSERVED -- client asks, no handler exists, falls to the catch-all 200 {}")
print("=" * 100)
print(f"{'cnt':>5}  {'method':<6} route")
for cnt, method, route, _hit, e in sorted(unserved, key=lambda r: -r[0]):
    print(f"{cnt:>5}  {method:<6} {route}")
    for q in e["queries"][:3]:
        print(f"           ?{q}")
print(f"\n  {len(unserved)} unserved routes, {sum(r[0] for r in unserved)} requests")
print(f"  {len(servedrows)} served routes, {sum(r[0] for r in servedrows)} requests")
