#!/usr/bin/env python3
import os, re, sys, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from binds import parse_binds, parse_headers

structs, classes, r, sz = parse_binds()
pairs, hr, hsz = parse_headers()
mod = lambda p: p[len("/Script/"):].split(".")[0] if p.startswith("/Script/") else ""

NAME = re.compile(r"^(?:.+?[\s&*>])?([A-Za-z_][A-Za-z0-9_]*)\s*\(")
diff = same = 0
examples = []
defaults = wctx = 0
for c in classes:
    for m in c.methods:
        mm = NAME.match(m.decl)
        asname = mm.group(1) if mm else None
        if asname and asname != m.unreal_path:
            diff += 1
            if len(examples) < 12:
                examples.append((c.type_name, m.unreal_path, asname, m.script_name))
        elif asname:
            same += 1
        if "=" in m.decl:
            defaults += 1
        if "__WorldContext" in m.decl:
            wctx += 1
print(f"methods where the ANGELSCRIPT name != the UFunction name: {diff}  (same: {same})")
for e in examples:
    print(f"   {e[0]}: UFunction={e[1]!r}  angelscript={e[2]!r}  ScriptName={e[3]!r}")
print(f"\nmethods whose declaration carries DEFAULT ARGUMENT VALUES: {defaults}")
print(f"methods using the __WorldContext default marker: {wctx}")

# script-name aliases
alias = [(c.type_name, m.unreal_path, m.script_name) for c in classes for m in c.methods if m.script_name]
print(f"methods with an explicit ScriptName alias: {len(alias)}")

# module rollup for methods
mm2 = collections.Counter()
for c in classes:
    mm2[mod(c.unreal_path)] += len(c.methods)
print("\nmethods by module (top 12):")
for k, v in mm2.most_common(12):
    print(f"   {v:>6}  {k}")

# how many bind types resolve to a Loki source header
lok = [(u, h) for u, h in pairs if "/Loki/" in h.replace("\\", "/")]
print(f"\nheader links pointing into the Loki game source tree: {len(lok)}")
dirs = collections.Counter()
for u, h in lok:
    p = h.replace("\\", "/").split("/")
    try:
        i = p.index("Loki")
        dirs["/".join(p[i:i + 4])] += 1
    except ValueError:
        pass
print("Loki source subtrees (top 22):")
for k, v in dirs.most_common(22):
    print(f"   {v:>5}  {k}")
