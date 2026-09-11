#!/usr/bin/env python3
r"""Round-trip + non-regression validation of the generated usmaps.

1. Both outputs parse with the project's independent reader (usmap_lite) and
   consume exactly 0 trailing bytes.
2. Every one of the base usmap's 11,344 structs and 2,226 enums survives the
   merge BIT-IDENTICALLY (name, super, propcount, every property tuple).
3. The 91 AS entries are present in the merged file and match the standalone
   supplement exactly.
4. Every StructProperty / EnumProperty / super reference in the merged file that
   originates from the supplement resolves inside the merged file.
"""
import os, sys
sys.path.insert(0, r"G:\git\Supervive Revival Project\tools\asdump")
from usmap_lite import U

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = r"G:\git\Supervive Revival Project\tools\extractor\mappings.usmap"
SUP = os.path.join(HERE, "angelscript.usmap")
MERGED = os.path.join(HERE, "mappings+as.usmap")

b, s, m = U(BASE), U(SUP), U(MERGED)
for nm, u in (("base", b), ("supplement", s), ("merged", m)):
    print("%-11s v%d names=%-6d enums=%-5d structs=%-6d trailing=%d"
          % (nm, u.ver, len(u.names), len(u.enums), len(u.structs), u.remaining))
    assert u.remaining == 0, "trailing bytes in " + nm

print()
# --- 2. non-regression -----------------------------------------------------
miss = diff = 0
for k, v in b.structs.items():
    if k not in m.structs:
        miss += 1
        continue
    if m.structs[k] != v:
        diff += 1
        if diff <= 5:
            print("   DIFF struct", k)
print("base structs preserved: %d/%d  (missing=%d changed=%d)"
      % (len(b.structs) - miss - diff, len(b.structs), miss, diff))
emiss = ediff = 0
for k, v in b.enums.items():
    if k not in m.enums:
        emiss += 1
    elif m.enums[k] != v:
        ediff += 1
print("base enums   preserved: %d/%d  (missing=%d changed=%d)"
      % (len(b.enums) - emiss - ediff, len(b.enums), emiss, ediff))
print("struct-name ORDER preserved for the base prefix:",
      m.order[:len(b.order)] == b.order)

# --- 3. supplement present and identical ----------------------------------
bad = 0
for k, v in s.structs.items():
    if k not in m.structs or m.structs[k] != v:
        bad += 1
        print("   MISMATCH", k)
print("supplement structs in merged, identical: %d/%d" % (len(s.structs) - bad, len(s.structs)))
print("supplement enums   in merged, identical: %d/%d"
      % (sum(1 for k, v in s.enums.items() if m.enums.get(k) == v), len(s.enums)))
print("collisions with base struct names: %s"
      % (sorted(set(s.structs) & set(b.structs)) or "none"))
print("collisions with base enum names:   %s"
      % (sorted(set(s.enums) & set(b.enums)) or "none"))

# --- 4. dangling refs in the merged file, restricted to supplement entries --
import re
dang = []
for k in s.structs:
    sup_, pc, props = m.structs[k]
    if sup_ is not None and sup_ not in m.structs:
        dang.append(("super", sup_, k))
    for _si, _d, pn, pt in props:
        # usmap_lite renders StructProperty as F<Name>; guard against matching
        # the literal type names FloatProperty / FieldPathProperty.
        for mm in re.finditer(r"(?<![A-Za-z0-9_])F([A-Za-z_][A-Za-z0-9_]*)", pt):
            nm = mm.group(1)
            if "F" + nm in ("FloatProperty", "FieldPathProperty"):
                continue
            if nm not in m.structs:
                dang.append(("struct", nm, "%s.%s" % (k, pn)))
        for mm in re.finditer(r"enum<([^:]+):", pt):
            if mm.group(1) not in m.enums:
                dang.append(("enum", mm.group(1), "%s.%s" % (k, pn)))
print("dangling refs from supplement entries: %d %s" % (len(dang), dang[:8]))

# --- extra: schema-index sanity -------------------------------------------
bad_idx = [k for k, (sup_, pc, props) in s.structs.items()
           if [p[0] for p in props] != list(range(len(props))) or pc != len(props)]
print("supplement entries with non-sequential SchemaIdx or pc!=len:", bad_idx or "none")
