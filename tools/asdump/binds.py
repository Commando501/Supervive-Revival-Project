#!/usr/bin/env python3
r"""
binds.py -- parser for SUPERVIVE (UE5.4 / Hazelight UE-Angelscript fork) engine<->script
             binding caches:
                 Loki/Script/Binds.Cache
                 Loki/Script/Binds.Cache.Headers

FORMAT (ground truth: Angelscript plugin's AngelscriptBindDatabase.{h,cpp},
`FAngelscriptBindDatabase::Serialize` -> `Archive << Structs; Archive << Classes;`
Everything is plain UE FArchive binary serialization -- there is NO header, NO magic,
NO guid, NO version on this file. It starts immediately with the first TArray count.)

  FString  (UE)   : int32 SaveNum
                      SaveNum == 0  -> empty string, NOTHING follows
                      SaveNum >  0  -> SaveNum ANSI bytes, INCLUDING the trailing NUL
                      SaveNum <  0  -> (-SaveNum) UTF-16LE code units, INCLUDING the NUL
                    => the "inconsistent NUL" appearance is just: empty strings write a
                       bare 0 length and no bytes.
  bool     (UE)   : int32 (4 bytes), 0 or 1
  int8            : 1 byte, signed
  TArray<T>       : int32 Num, then Num x T

  Binds.Cache
    int32 StructCount
    FAngelscriptStructBind[StructCount]
    int32 ClassCount
    FAngelscriptClassBind[ClassCount]
    <EOF>

  FAngelscriptStructBind
    FString TypeName            e.g. "FARFilter"
    FString UnrealPath          e.g. "/Script/CoreUObject.ARFilter"
    TArray<FAngelscriptPropertyBind> Properties

  FAngelscriptClassBind
    FString TypeName            e.g. "UTypedElementHandleLibrary" / "ALokiAirship"
    FString UnrealPath          e.g. "/Script/Loki.LokiAirship"
    TArray<FAngelscriptMethodBind>   Methods
    TArray<FAngelscriptPropertyBind> Properties

  FAngelscriptPropertyBind         (fixed 32 bytes of tail when GeneratedName is empty)
    FString Declaration         angelscript decl, e.g. "TArray<FName> PackageNames"
    FString UnrealPath          property name (NOT a full path in this build)
    bool    bCanWrite
    bool    bCanRead
    bool    bCanEdit
    bool    bGeneratedGetter
    bool    bGeneratedSetter
    FString GeneratedName
    bool    bGeneratedHandle
    bool    bGeneratedUnresolvedObject

  FAngelscriptMethodBind
    FString Declaration         full angelscript signature,
                                e.g. "bool Equal(const FScriptTypedElementHandle& LHS,...)"
    FString UnrealPath          UFunction name (NOT a full path in this build)
    bool    bStaticInUnreal
    bool    bStaticInScript
    bool    bGlobalScope
    bool    bNotAngelscriptProperty
    bool    bTrivial
    int8    WorldContextArgument            (-1 == none)
    int8    DeterminesOutputTypeArgument    (-1 == none)
    FString ClassName           angelscript-side owning type / mixin namespace
    FString ScriptName          script-facing alias (often empty)

  Binds.Cache.Headers
    int32 Count
    FAngelscriptClassHeader[Count]:
       FString UnrealPath       "/Script/Module.Class"
       FString Header           absolute C++ header path on the build machine

Usage:
  python binds.py                 # parse + validate + write CSVs into ./out
  python binds.py --stats         # extra analysis
"""

import csv
import os
import struct
import sys
import collections

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(SCRIPT_DIR, "out")

BINDS = r"G:\git\GAME BACKUPS FOR REVERSE ENGINEERING\SUPERVIVE\Loki\Script\Binds.Cache"
HEADERS = r"G:\git\GAME BACKUPS FOR REVERSE ENGINEERING\SUPERVIVE\Loki\Script\Binds.Cache.Headers"


class Reader:
    """Minimal UE FArchive-compatible little-endian reader."""

    def __init__(self, data):
        self.d = data
        self.o = 0
        self.n = len(data)
        # diagnostics
        self.str_ansi = 0
        self.str_utf16 = 0
        self.str_empty = 0
        self.str_no_nul = []      # offsets of strings not NUL-terminated (spec violation)

    def eof(self):
        return self.o >= self.n

    def i32(self):
        v = struct.unpack_from("<i", self.d, self.o)[0]
        self.o += 4
        return v

    def i8(self):
        v = struct.unpack_from("<b", self.d, self.o)[0]
        self.o += 1
        return v

    def boolean(self):
        """UE serializes bool as int32."""
        v = self.i32()
        if v not in (0, 1):
            raise ValueError(f"bool out of range ({v}) at {self.o - 4:#x}")
        return bool(v)

    def string(self):
        start = self.o
        num = self.i32()
        if num == 0:
            self.str_empty += 1
            return ""
        if num < 0:
            # UTF-16LE, |num| code units including the terminating NUL
            cnt = -num
            nb = cnt * 2
            if self.o + nb > self.n:
                raise ValueError(f"utf16 string overruns file at {start:#x} (num={num})")
            raw = self.d[self.o:self.o + nb]
            self.o += nb
            self.str_utf16 += 1
            if raw[-2:] != b"\x00\x00":
                self.str_no_nul.append(start)
                return raw.decode("utf-16-le", "replace")
            return raw[:-2].decode("utf-16-le", "replace")
        if num > 1 << 22 or self.o + num > self.n:
            raise ValueError(f"implausible string length {num} at {start:#x}")
        raw = self.d[self.o:self.o + num]
        self.o += num
        self.str_ansi += 1
        if raw[-1] != 0:
            self.str_no_nul.append(start)
            return raw.decode("utf-8", "replace")
        return raw[:-1].decode("utf-8", "replace")

    def array(self, fn, what="array"):
        cnt = self.i32()
        if cnt < 0 or cnt > 4_000_000:
            raise ValueError(f"implausible {what} count {cnt} at {self.o - 4:#x}")
        return [fn() for _ in range(cnt)]


# --------------------------------------------------------------------------- records

class PropertyBind:
    __slots__ = ("decl", "unreal_path", "can_write", "can_read", "can_edit",
                 "gen_getter", "gen_setter", "gen_name", "gen_handle",
                 "gen_unresolved", "offset")

    def __init__(self, r):
        self.offset = r.o
        self.decl = r.string()
        self.unreal_path = r.string()
        self.can_write = r.boolean()
        self.can_read = r.boolean()
        self.can_edit = r.boolean()
        self.gen_getter = r.boolean()
        self.gen_setter = r.boolean()
        self.gen_name = r.string()
        self.gen_handle = r.boolean()
        self.gen_unresolved = r.boolean()


class MethodBind:
    __slots__ = ("decl", "unreal_path", "static_unreal", "static_script", "global_scope",
                 "not_as_property", "trivial", "world_ctx_arg", "determines_output_arg",
                 "class_name", "script_name", "offset")

    def __init__(self, r):
        self.offset = r.o
        self.decl = r.string()
        self.unreal_path = r.string()
        self.static_unreal = r.boolean()
        self.static_script = r.boolean()
        self.global_scope = r.boolean()
        self.not_as_property = r.boolean()
        self.trivial = r.boolean()
        self.world_ctx_arg = r.i8()
        self.determines_output_arg = r.i8()
        self.class_name = r.string()
        self.script_name = r.string()


class StructBind:
    __slots__ = ("type_name", "unreal_path", "properties", "offset")

    def __init__(self, r):
        self.offset = r.o
        self.type_name = r.string()
        self.unreal_path = r.string()
        self.properties = r.array(lambda: PropertyBind(r), "struct properties")


class ClassBind:
    __slots__ = ("type_name", "unreal_path", "methods", "properties", "offset")

    def __init__(self, r):
        self.offset = r.o
        self.type_name = r.string()
        self.unreal_path = r.string()
        self.methods = r.array(lambda: MethodBind(r), "class methods")
        self.properties = r.array(lambda: PropertyBind(r), "class properties")


def parse_binds(path=BINDS):
    data = open(path, "rb").read()
    r = Reader(data)
    structs = r.array(lambda: StructBind(r), "Structs")
    classes = r.array(lambda: ClassBind(r), "Classes")
    return structs, classes, r, len(data)


def parse_headers(path=HEADERS):
    data = open(path, "rb").read()
    r = Reader(data)
    pairs = r.array(lambda: (r.string(), r.string()), "Headers")
    return pairs, r, len(data)


# --------------------------------------------------------------------------- main

def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    want_stats = "--stats" in sys.argv

    print("=" * 78)
    print("Binds.Cache")
    print("=" * 78)
    structs, classes, r, size = parse_binds()
    print(f"  file size            : {size:,} bytes")
    print(f"  Structs (TArray)     : {len(structs):,}")
    print(f"  Classes (TArray)     : {len(classes):,}")
    print(f"  consumed             : {r.o:,} / {size:,}   remaining = {size - r.o}")
    if r.o == size:
        print("  ** BYTE-EXACT: parser consumed the file to the last byte **")
    else:
        print(f"  !! {size - r.o} bytes unconsumed; tail = {r.d[r.o:r.o+64].hex()}")
    print(f"  strings: ansi={r.str_ansi:,} utf16={r.str_utf16:,} empty={r.str_empty:,} "
          f"not-NUL-terminated={len(r.str_no_nul)}")

    sprops = sum(len(s.properties) for s in structs)
    cprops = sum(len(c.properties) for c in classes)
    cmeth = sum(len(c.methods) for c in classes)
    print(f"  struct properties    : {sprops:,}")
    print(f"  class  properties    : {cprops:,}")
    print(f"  class  methods       : {cmeth:,}")
    print(f"  TOTAL bound members  : {sprops + cprops + cmeth:,}")

    # ---- CSV: types
    p = os.path.join(OUT_DIR, "binds_types.csv")
    with open(p, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["kind", "index", "type_name", "unreal_path", "module",
                    "num_methods", "num_properties", "file_offset"])
        for i, s in enumerate(structs):
            mod = s.unreal_path.split("/")[-1].split(".")[0] if "." in s.unreal_path else ""
            w.writerow(["struct", i, s.type_name, s.unreal_path, mod,
                        0, len(s.properties), hex(s.offset)])
        for i, c in enumerate(classes):
            mod = c.unreal_path.split("/")[-1].split(".")[0] if "." in c.unreal_path else ""
            w.writerow(["class", i, c.type_name, c.unreal_path, mod,
                        len(c.methods), len(c.properties), hex(c.offset)])
    print(f"  wrote {p}")

    # ---- CSV: members
    p = os.path.join(OUT_DIR, "binds_members.csv")
    with open(p, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["owner_kind", "owner_index", "owner_type", "owner_unreal_path",
                    "member_kind", "member_index", "declaration", "unreal_name",
                    "as_class_name", "script_name",
                    "static_in_unreal", "static_in_script", "global_scope",
                    "not_as_property", "trivial",
                    "world_context_arg", "determines_output_arg",
                    "can_write", "can_read", "can_edit",
                    "gen_getter", "gen_setter", "gen_name",
                    "gen_handle", "gen_unresolved_object", "file_offset"])

        def prop_row(kind, idx, tname, tpath, j, pr):
            w.writerow([kind, idx, tname, tpath, "property", j, pr.decl, pr.unreal_path,
                        "", "", "", "", "", "", "", "", "",
                        int(pr.can_write), int(pr.can_read), int(pr.can_edit),
                        int(pr.gen_getter), int(pr.gen_setter), pr.gen_name,
                        int(pr.gen_handle), int(pr.gen_unresolved), hex(pr.offset)])

        for i, s in enumerate(structs):
            for j, pr in enumerate(s.properties):
                prop_row("struct", i, s.type_name, s.unreal_path, j, pr)
        for i, c in enumerate(classes):
            for j, m in enumerate(c.methods):
                w.writerow(["class", i, c.type_name, c.unreal_path, "method", j,
                            m.decl, m.unreal_path, m.class_name, m.script_name,
                            int(m.static_unreal), int(m.static_script),
                            int(m.global_scope), int(m.not_as_property),
                            int(m.trivial), m.world_ctx_arg, m.determines_output_arg,
                            "", "", "", "", "", "", "", "", hex(m.offset)])
            for j, pr in enumerate(c.properties):
                prop_row("class", i, c.type_name, c.unreal_path, j, pr)
    print(f"  wrote {p}")

    print()
    print("=" * 78)
    print("Binds.Cache.Headers")
    print("=" * 78)
    pairs, hr, hsize = parse_headers()
    print(f"  file size            : {hsize:,} bytes")
    print(f"  entries              : {len(pairs):,}")
    print(f"  consumed             : {hr.o:,} / {hsize:,}   remaining = {hsize - hr.o}")
    if hr.o == hsize:
        print("  ** BYTE-EXACT: parser consumed the file to the last byte **")
    else:
        print(f"  !! tail = {hr.d[hr.o:hr.o+64].hex()}")
    print(f"  strings: ansi={hr.str_ansi:,} utf16={hr.str_utf16:,} empty={hr.str_empty:,} "
          f"not-NUL-terminated={len(hr.str_no_nul)}")

    p = os.path.join(OUT_DIR, "binds_headers.csv")
    with open(p, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["index", "unreal_path", "module", "object", "header_path"])
        for i, (up, hp) in enumerate(pairs):
            mod, _, obj = up.rpartition(".")
            mod = mod.split("/")[-1]
            w.writerow([i, up, mod, obj, hp])
    print(f"  wrote {p}")

    if want_stats:
        stats(structs, classes, pairs)


def stats(structs, classes, pairs):
    print()
    print("=" * 78)
    print("ANALYSIS")
    print("=" * 78)

    def modof(pth):
        if not pth.startswith("/Script/"):
            return "(none)"
        return pth[len("/Script/"):].split(".")[0]

    mods = collections.Counter()
    for s in structs:
        mods[modof(s.unreal_path)] += 1
    for c in classes:
        mods[modof(c.unreal_path)] += 1
    print("\nTop modules by bound type count:")
    for m, n in mods.most_common(25):
        print(f"   {n:>6}  {m}")

    loki_c = [c for c in classes if modof(c.unreal_path) == "Loki"]
    loki_s = [s for s in structs if modof(s.unreal_path) == "Loki"]
    print(f"\n/Script/Loki: {len(loki_c)} classes, {len(loki_s)} structs, "
          f"{sum(len(c.methods) for c in loki_c)} methods, "
          f"{sum(len(c.properties) for c in loki_c)} class props, "
          f"{sum(len(s.properties) for s in loki_s)} struct props")

    # flag sanity: proves the field split is right
    fl = collections.Counter()
    for c in classes:
        for m in c.methods:
            fl["static_unreal"] += m.static_unreal
            fl["static_script"] += m.static_script
            fl["global_scope"] += m.global_scope
            fl["not_as_property"] += m.not_as_property
            fl["trivial"] += m.trivial
            if m.world_ctx_arg != -1:
                fl["world_ctx_set"] += 1
            if m.determines_output_arg != -1:
                fl["determines_output_set"] += 1
            if m.script_name:
                fl["has_script_name"] += 1
    print("\nMethod flag totals:", dict(fl))

    pf = collections.Counter()
    for lst in (structs, classes):
        for t in lst:
            for pr in t.properties:
                pf["can_write"] += pr.can_write
                pf["can_read"] += pr.can_read
                pf["can_edit"] += pr.can_edit
                pf["gen_getter"] += pr.gen_getter
                pf["gen_setter"] += pr.gen_setter
                pf["gen_handle"] += pr.gen_handle
                pf["gen_unresolved"] += pr.gen_unresolved
                if pr.gen_name:
                    pf["has_gen_name"] += 1
    print("Property flag totals:", dict(pf))

    # duplicate declarations => is (ClassName, Declaration) a unique key?
    seen = collections.Counter()
    for c in classes:
        for m in c.methods:
            seen[(c.unreal_path, m.decl)] += 1
    dupes = {k: v for k, v in seen.items() if v > 1}
    print(f"\n(owner, declaration) collisions among methods: {len(dupes)}")
    for k, v in list(dupes.items())[:10]:
        print("   ", v, k)

    seen2 = collections.Counter()
    for c in classes:
        for m in c.methods:
            seen2[(m.class_name, m.decl)] += 1
    d2 = {k: v for k, v in seen2.items() if v > 1}
    print(f"(as_class_name, declaration) collisions among methods: {len(d2)}")

    ns = collections.Counter(m.class_name for c in classes for m in c.methods)
    print(f"\ndistinct as_class_name values: {len(ns)}; top:")
    for k, v in ns.most_common(10):
        print(f"   {v:>6}  {k!r}")

    # headers coverage
    hp = {u for u, _ in pairs}
    allp = {s.unreal_path for s in structs} | {c.unreal_path for c in classes}
    print(f"\nHeaders entries: {len(pairs)}; distinct unreal paths in Headers: {len(hp)}")
    print(f"bind types not in Headers: {len(allp - hp)}")
    print(f"Headers paths not a bound type (enums/delegates): {len(hp - allp)}")


if __name__ == "__main__":
    main()
