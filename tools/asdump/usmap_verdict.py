#!/usr/bin/env python3
r"""Final verdict: accuracy of mappings.usmap container ELEMENT types on /Script/Loki
types, measured against Binds.Cache (engine-authored ground truth)."""
import os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from usmap_lite import U
from binds import parse_binds

a = U(r"G:\git\Supervive Revival Project\tools\usmapdump\mappings.usmap")
structs, classes, r, sz = parse_binds()
mod = lambda p: p[len("/Script/"):].split(".")[0] if p.startswith("/Script/") else ""
obj = lambda p: p.rpartition(".")[2]
loki = [(c.type_name, c.unreal_path, c.properties) for c in classes if mod(c.unreal_path) == "Loki"] + \
       [(s.type_name, s.unreal_path, s.properties) for s in structs if mod(s.unreal_path) == "Loki"]

DECL = re.compile(r"^(.+?)\s+([A-Za-z_][A-Za-z0-9_]*)\Z")
CONT = re.compile(r"^T(Array|Set)<(F[A-Z][A-Za-z0-9_]*)>\Z")

tot = right = 0
wrong = []
for tn, up, props in loki:
    un = obj(up)
    if un not in a.structs:
        continue
    um = {n: t for _, _, n, t in a.structs[un][2]}
    for pr in props:
        m = DECL.match(pr.decl.strip())
        if not m:
            continue
        ty, nm = m.group(1), m.group(2)
        ty = ty.replace("const ", "").replace("&", "").strip()
        mm = CONT.match(ty)
        if not mm or nm not in um:
            continue
        tot += 1
        want = f"{mm.group(1)}<{mm.group(2)}>"
        if um[nm] == want:
            right += 1
        else:
            wrong.append((un, nm, want, um[nm]))

print(f"/Script/Loki TArray/TSet-of-STRUCT properties present in BOTH sources: {tot}")
print(f"   usmap element type CORRECT: {right}    WRONG: {len(wrong)}"
      f"    ({right / max(tot,1):.1%} correct)")
print()
for w in wrong[:20]:
    print(f"   {w[0]}.{w[1]}\n        truth (Binds.Cache) = {w[2]}\n        mappings.usmap      = {w[3]}")
