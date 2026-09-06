#!/usr/bin/env python3
r"""FK-1 Track A -- emit a .usmap supplement for the 110 Angelscript-declared types.

Source of truth = Loki/Script/PrecompiledScript.Cache (exact declarations; see
tools/asdump/FORMAT.md) + Binds.Cache (native type struct-vs-class + /Script path).

Outputs (all under the scratchpad unless -o says otherwise):
    as_schema.json          intermediate, human-readable class -> props -> types
    angelscript.usmap       supplement ONLY (round-trip testable, not standalone-usable)
    mappings+as.usmap       canonical extractor usmap with the supplement APPENDED

Naming conventions -- MEASURED against this build:
  * UClass  : A/U prefix stripped.  AssetRegistry.bin shows
              /Script/Angelscript.BarracudaMinionWaypoint for script ABarracudaMinionWaypoint.
  * UScriptStruct : F prefix stripped (usmap has `Vector`, `GameplayTag`, `BarracudaPhase`).
  * UEnum   : name kept verbatim (usmap has `ELokiMovementInputDirection`), members
              stored fully qualified `EnumName::Member`.
"""
import argparse, collections, json, os, struct, sys

AS_DIR = r"G:\git\Supervive Revival Project\tools\asdump"
sys.path.insert(0, AS_DIR)
import asdump as A                                            # noqa: E402

CANON_USMAP = r"G:\git\Supervive Revival Project\tools\extractor\mappings.usmap"

# EPropertyType byte tags (CUE4Parse / usmap v0)
(BYTE, BOOL, INT, FLOAT, OBJECT, NAME, DELEGATE, DOUBLE, ARRAY, STRUCT, STR,
 TEXT, INTERFACE, MCDELEGATE, WEAKOBJ, LAZYOBJ, ASSETOBJ, SOFTOBJ, U64, U32,
 U16, I64, I16, I8, MAP, SET, ENUM, FIELDPATH, OPTIONAL) = range(29)

PT_NAME = {BYTE: "ByteProperty", BOOL: "BoolProperty", INT: "IntProperty",
           FLOAT: "FloatProperty", OBJECT: "ObjectProperty", NAME: "NameProperty",
           DELEGATE: "DelegateProperty", DOUBLE: "DoubleProperty",
           ARRAY: "ArrayProperty", STRUCT: "StructProperty", STR: "StrProperty",
           TEXT: "TextProperty", INTERFACE: "InterfaceProperty",
           MCDELEGATE: "MulticastDelegateProperty", WEAKOBJ: "WeakObjectProperty",
           LAZYOBJ: "LazyObjectProperty", ASSETOBJ: "AssetObjectProperty",
           SOFTOBJ: "SoftObjectProperty", U64: "UInt64Property", U32: "UInt32Property",
           U16: "UInt16Property", I64: "Int64Property", I16: "Int16Property",
           I8: "Int8Property", MAP: "MapProperty", SET: "SetProperty",
           ENUM: "EnumProperty", FIELDPATH: "FieldPathProperty",
           OPTIONAL: "OptionalProperty"}

# AngelScript primitive token -> usmap type.  Tokens from asdump.TOKEN_PRIMITIVE,
# which were themselves verified against Binds.Cache declaration strings.
PRIM = {"bool": BOOL, "int": INT, "int8": I8, "int16": I16, "int64": I64,
        "uint": U32, "uint8": BYTE, "uint16": U16, "uint64": U64,
        "float": FLOAT, "float32": FLOAT, "float64": DOUBLE, "double": DOUBLE}

# AS wrapper types that are NOT UE structs
CONTAINERS = {"TArray": ARRAY, "TSet": SET}


def strip_prefix(n, kinds="AUF"):
    return n[1:] if len(n) > 1 and n[0] in kinds and n[1].isupper() else n


class Ty(object):
    """A usmap property-type node."""
    __slots__ = ("t", "name", "inner", "value", "note")

    def __init__(self, t, name=None, inner=None, value=None, note=""):
        self.t, self.name, self.inner, self.value, self.note = t, name, inner, value, note

    def render(self):
        b = PT_NAME[self.t]
        if self.t == STRUCT:
            return "Struct<%s>" % self.name
        if self.t == ENUM:
            return "Enum<%s:%s>" % (self.name, self.inner.render())
        if self.t in (ARRAY, SET, OPTIONAL):
            return "%s<%s>" % (b[:-8], self.inner.render())
        if self.t == MAP:
            return "Map<%s,%s>" % (self.inner.render(), self.value.render())
        return b


class Classifier(object):
    def __init__(self, cache, binds, base_structs=(), base_enums=()):
        self.cache, self.binds = cache, binds
        # The canonical usmap is a second, independent witness for
        # "is this name a UScriptStruct / UEnum".  Needed because AngelScript
        # registers the math primitives (FVector, FRotator, FRandomStream, ...)
        # natively rather than through Binds.Cache, so they are ABSENT there.
        self.base_structs = set(base_structs)
        self.base_enums = set(base_enums)
        # script value types split into real structs vs delegates.  A script
        # delegate is a value type whose ONLY member is `_Inner` of the
        # AngelScript-internal type `_FMulticastScriptDelegate`.
        self.script_structs, self.script_delegates = set(), set()
        for _m, k in cache.classes:
            if k.name not in cache.script_value_types:
                continue
            inner = [p for p in k.properties
                     if cache.type_name(p.type) == "_FMulticastScriptDelegate"]
            (self.script_delegates if inner and len(k.properties) == 1
             else self.script_structs).add(k.name)
        self.script_ref = set(k.name for _m, k in cache.classes) \
            - cache.script_value_types
        self.unresolved = collections.Counter()

    def is_enum_name(self, n):
        if n in self.cache.script_enums:
            return True
        if n in self.cache.script_classes:
            return False
        if n in self.binds.struct_names or n in self.binds.class_names:
            return False
        if n in self.base_enums:
            return True
        if strip_prefix(n) in self.base_structs:
            return False
        return len(n) > 1 and n[0] == "E" and n[1].isupper()

    def of(self, dt, depth=0):
        c = self.cache
        if depth > 6:
            return Ty(BYTE, note="depth")
        if not dt.type_info:
            nm = A.TOKEN_PRIMITIVE.get(dt.token)
            if nm in PRIM:
                return Ty(PRIM[nm])
            self.unresolved["token:%s" % nm] += 1
            return Ty(BYTE, note="unknown primitive %s" % nm)
        tr = c.type_refs.get(dt.type_info)
        if tr is None:
            self.unresolved["UNRESOLVED_TYPEINFO"] += 1
            return Ty(BYTE, note="unresolved typeinfo")
        n = tr.name
        # containers
        if n in CONTAINERS and tr.subtypes:
            return Ty(CONTAINERS[n], inner=self.of(tr.subtypes[0], depth + 1))
        if n == "TMap" and len(tr.subtypes) == 2:
            return Ty(MAP, inner=self.of(tr.subtypes[0], depth + 1),
                      value=self.of(tr.subtypes[1], depth + 1))
        if n in ("TSubclassOf",):
            return Ty(OBJECT, note="TSubclassOf -> FClassProperty (ObjectProperty)")
        if n in ("TWeakObjectPtr",):
            return Ty(WEAKOBJ)
        if n in ("TSoftObjectPtr", "TSoftClassPtr"):
            return Ty(SOFTOBJ)
        if n == "TOptional" and tr.subtypes:
            return Ty(OPTIONAL, inner=self.of(tr.subtypes[0], depth + 1))
        # scalar named types
        if n == "FString":
            return Ty(STR)
        if n == "FName":
            return Ty(NAME)
        if n == "FText":
            return Ty(TEXT)
        if self.is_enum_name(n):
            # AngelScript enums are 4 bytes; UE-Angelscript builds FEnumProperty
            # over an int32.  (inferred -- see the findings doc; testable by
            # byte-count desync.)
            return Ty(ENUM, name=n, inner=Ty(INT))
        if dt.handle or n in self.binds.class_names or n in self.script_ref:
            return Ty(OBJECT)
        if n in self.script_delegates:
            return Ty(MCDELEGATE)
        if n in self.script_structs:
            return Ty(STRUCT, name=strip_prefix(n))
        if n in self.binds.struct_names:
            return Ty(STRUCT, name=strip_prefix(n))
        if n == "_FMulticastScriptDelegate":
            return Ty(MCDELEGATE)
        # Absent from Binds.Cache: fall back to the canonical usmap, which is an
        # independent witness.  This is what recovers FVector / FRotator /
        # FRandomStream -- AngelScript registers those natively.
        if strip_prefix(n) in self.base_structs:
            self.unresolved["struct-via-usmap:%s" % n] += 1
            return Ty(STRUCT, name=strip_prefix(n))
        # F-prefixed, unknown to Binds.Cache AND to the usmap, not a script type:
        # in this corpus these are all native multicast delegate signatures.
        if n.startswith("F"):
            self.unresolved["assumed-delegate:%s" % n] += 1
            return Ty(MCDELEGATE, note="assumed native delegate")
        self.unresolved["UNKNOWN:%s" % n] += 1
        return Ty(BYTE, note="unknown %s" % n)


# ---------------------------------------------------------------------------
def build_schema(cache, binds, base_structs=(), base_enums=()):
    cl = Classifier(cache, binds, base_structs, base_enums)
    out = []
    for m in cache.modules:
        for k in m.classes:
            if k.name in cl.script_delegates:
                continue                       # UDelegateFunction, not a UStruct
            is_struct = k.name in cl.script_structs
            ue = strip_prefix(k.name)
            sup = None
            if not is_struct:
                sup = strip_prefix(k.super_class) if k.super_class else None
            props = []
            for p in k.properties:
                ty = cl.of(p.type)
                props.append({
                    "name": p.name, "as_type": cache.type_name(p.type),
                    "usmap": ty, "usmap_render": ty.render(),
                    "uproperty": p.is_uproperty,
                    "flags": sorted(f for f, v in (p.flags or {}).items() if v),
                    "rep_condition": p.rep_condition, "rep_notify": p.rep_notify,
                })
            out.append({"module": m.name, "as_name": k.name, "ue_name": ue,
                        "kind": "struct" if is_struct else "class",
                        "as_super": k.super_class, "ue_super": sup,
                        "code_super": k.code_super_class, "props": props})
    enums = []
    for m in cache.modules:
        for e in m.enums:
            enums.append({"module": m.name, "name": e.name,
                          "members": list(zip(e.names, e.values))})
    return out, enums, cl


# ---------------------------------------------------------------------------
# usmap binary I/O
# ---------------------------------------------------------------------------
class Body(object):
    def __init__(self):
        self.b = bytearray()

    def u8(self, v):
        self.b.append(v & 0xFF)

    def u16(self, v):
        self.b += struct.pack("<H", v)

    def u32(self, v):
        self.b += struct.pack("<I", v & 0xFFFFFFFF)

    def raw(self, p):
        self.b += p


class NameTable(object):
    def __init__(self, existing=None):
        self.arr = list(existing or [])
        self.idx = {}
        for i, s in enumerate(self.arr):
            self.idx.setdefault(s, i)
        self.base = len(self.arr)

    def add(self, s):
        if s is None or s == "":
            return 0xFFFFFFFF
        i = self.idx.get(s)
        if i is None:
            i = len(self.arr)
            self.arr.append(s)
            self.idx[s] = i
        return i

    def new_names(self):
        return self.arr[self.base:]


def write_type(b, nt, ty):
    b.u8(ty.t)
    if ty.t == STRUCT:
        b.u32(nt.add(ty.name))
    elif ty.t == ENUM:
        write_type(b, nt, ty.inner)
        b.u32(nt.add(ty.name))
    elif ty.t in (ARRAY, SET, OPTIONAL):
        write_type(b, nt, ty.inner)
    elif ty.t == MAP:
        write_type(b, nt, ty.inner)
        write_type(b, nt, ty.value)


def encode_structs(nt, schema):
    b = Body()
    for s in schema:
        b.u32(nt.add(s["ue_name"]))
        b.u32(nt.add(s["ue_super"]) if s["ue_super"] else 0xFFFFFFFF)
        b.u16(len(s["props"]))          # PropertyCount   (all ArrayDim == 1)
        b.u16(len(s["props"]))          # SerializablePropertyCount
        for i, p in enumerate(s["props"]):
            b.u16(i)                    # SchemaIdx, relative to THIS struct
            b.u8(1)                     # ArrayDim
            b.u32(nt.add(p["name"]))
            write_type(b, nt, p["usmap"])
    return b.b


def encode_enums(nt, enums):
    b = Body()
    for e in enums:
        b.u32(nt.add(e["name"]))
        mem = e["members"]
        b.u8(min(len(mem), 255))
        for nm, _v in mem[:255]:
            b.u32(nt.add("%s::%s" % (e["name"], nm)))
    return b.b


def write_usmap(path, names, enum_blob, enum_count, struct_blob, struct_count):
    body = Body()
    body.u32(len(names))
    for s in names:
        e = s.encode("utf-8")
        assert len(e) < 256, s
        body.u8(len(e))
        body.raw(e)
    body.u32(enum_count)
    body.raw(enum_blob)
    body.u32(struct_count)
    body.raw(struct_blob)
    raw = bytes(body.b)
    hdr = struct.pack("<HBBII", 0x30C4, 0, 0, len(raw), len(raw))
    with open(path, "wb") as fh:
        fh.write(hdr + raw)
    return len(hdr) + len(raw)


def split_existing(path):
    """Return (names, enum_blob, enum_count, struct_blob, struct_count).
    Regions are kept as raw bytes so appended names never disturb old indices."""
    d = open(path, "rb").read()
    magic, ver, comp = struct.unpack_from("<HBB", d, 0)
    assert magic == 0x30C4 and comp == 0, (hex(magic), comp)
    csize, dsize = struct.unpack_from("<II", d, 4)
    body = d[12:12 + csize]
    assert len(body) == csize == dsize
    o = 0

    def u8():
        nonlocal o
        v = body[o]; o += 1; return v

    def u16():
        nonlocal o
        v = struct.unpack_from("<H", body, o)[0]; o += 2; return v

    def u32():
        nonlocal o
        v = struct.unpack_from("<I", body, o)[0]; o += 4; return v

    names = []
    for _ in range(u32()):
        n = u8()
        names.append(body[o:o + n].decode("utf-8", "replace")); o += n
    ec = u32(); estart = o
    for _ in range(ec):
        u32()
        for _ in range(u8()):
            u32()
    enum_blob = body[estart:o]
    sc = u32(); sstart = o

    def ptype():
        t = u8()
        if t == ENUM:
            ptype(); u32()
        elif t == STRUCT:
            u32()
        elif t in (ARRAY, SET, OPTIONAL):
            ptype()
        elif t == MAP:
            ptype(); ptype()

    for _ in range(sc):
        u32(); u32(); u16(); sp = u16()
        for _ in range(sp):
            u16(); u8(); u32(); ptype()
    struct_blob = body[sstart:o]
    assert o == len(body), (o, len(body))
    return names, enum_blob, ec, struct_blob, sc


# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--script-dir", default=A.DEFAULT_SCRIPT_DIR)
    ap.add_argument("--base", default=CANON_USMAP)
    ap.add_argument("-o", "--outdir", default=os.path.dirname(os.path.abspath(__file__)))
    ap.add_argument("--enum-underlying", default="int",
                    choices=("int", "byte"),
                    help="FEnumProperty underlying type for script enum members")
    ap.add_argument("--all-members", action="store_true",
                    help="ARM A (FALSIFIED): emit every script member, not just UPROPERTY ones")
    ap.add_argument("--reverse-props", action="store_true",
                    help="ARM C: emit each type's members in REVERSE declaration order")
    ap.add_argument("--tag", default="", help="suffix for output filenames")
    args = ap.parse_args()

    sys.path.insert(0, AS_DIR)
    from usmap_lite import U
    base = U(args.base)
    cache = A.load_cache(os.path.join(args.script_dir, "PrecompiledScript.Cache"))
    binds = A.load_binds(os.path.join(args.script_dir, "Binds.Cache"),
                         os.path.join(args.script_dir, "Binds.Cache.Headers"))
    schema, enums, cl = build_schema(cache, binds,
                                     set(base.structs), set(base.enums))
    if args.enum_underlying == "byte":
        def fix(ty):
            if ty is None:
                return
            if ty.t == ENUM:
                ty.inner = Ty(BYTE)
            for sub in (ty.inner, ty.value):
                fix(sub)
        for s in schema:
            for p in s["props"]:
                fix(p["usmap"])

    # MEASURED (S113): UE-Angelscript reflects ONLY UPROPERTY()-marked script
    # members into the UClass serialization schema.  Emitting every member
    # (--all-members) desynchronises the unversioned stream -- see the findings
    # doc, arm A vs arm B on BP_AimingLaser_HuntressV2 / BP_Airdoo.
    if not args.all_members:
        for s in schema:
            s["props"] = [p for p in s["props"] if p["uproperty"]]
    if args.reverse_props:
        for s in schema:
            s["props"] = list(reversed(s["props"]))

    os.makedirs(args.outdir, exist_ok=True)
    # -- intermediate JSON --------------------------------------------------
    js = []
    for s in schema:
        js.append({k: v for k, v in s.items() if k != "props"})
        js[-1]["props"] = [{k: v for k, v in p.items() if k != "usmap"}
                           for p in s["props"]]
    jpath = os.path.join(args.outdir, "as_schema%s.json" % args.tag)
    with open(jpath, "w", encoding="utf-8") as fh:
        json.dump({"types": js, "enums": enums}, fh, indent=1)

    nclass = sum(1 for s in schema if s["kind"] == "class")
    nstruct = sum(1 for s in schema if s["kind"] == "struct")
    nprop = sum(len(s["props"]) for s in schema)
    print("schema: %d classes + %d structs = %d entries, %d properties, %d enums"
          % (nclass, nstruct, len(schema), nprop, len(enums)))
    print("delegates excluded (UDelegateFunction, not UStruct): %d"
          % len(cl.script_delegates))
    if cl.unresolved:
        print("classifier fallbacks:")
        for k, v in cl.unresolved.most_common():
            print("   %4d  %s" % (v, k))

    # -- referential integrity vs. the merged universe ---------------------
    known_structs = set(base.structs) | set(s["ue_name"] for s in schema)
    known_enums = set(base.enums) | set(e["name"] for e in enums)
    bad = []

    def walk(ty, owner):
        if ty is None:
            return
        if ty.t == STRUCT and ty.name not in known_structs:
            bad.append(("StructProperty", ty.name, owner))
        if ty.t == ENUM and ty.name not in known_enums:
            bad.append(("EnumProperty", ty.name, owner))
        walk(ty.inner, owner)
        walk(ty.value, owner)

    for s in schema:
        if s["ue_super"] and s["ue_super"] not in known_structs:
            bad.append(("super", s["ue_super"], s["ue_name"]))
        for p in s["props"]:
            walk(p["usmap"], "%s.%s" % (s["ue_name"], p["name"]))
    print("referential integrity: %d dangling references" % len(bad))
    for kind, nm, owner in bad:
        print("   DANGLING %-16s %-44s <- %s" % (kind, nm, owner))

    # -- standalone supplement ---------------------------------------------
    nt = NameTable()
    eb = encode_enums(nt, enums)
    sb = encode_structs(nt, schema)
    p1 = os.path.join(args.outdir, "angelscript%s.usmap" % args.tag)
    n1 = write_usmap(p1, nt.arr, eb, len(enums), sb, len(schema))
    print("wrote %s  (%d bytes, %d names)" % (p1, n1, len(nt.arr)))

    # -- merged ------------------------------------------------------------
    onames, oeb, oec, osb, osc = split_existing(args.base)
    nt2 = NameTable(onames)
    eb2 = encode_enums(nt2, enums)
    sb2 = encode_structs(nt2, schema)
    p2 = os.path.join(args.outdir, "mappings+as%s.usmap" % args.tag)
    n2 = write_usmap(p2, nt2.arr, oeb + eb2, oec + len(enums),
                     osb + sb2, osc + len(schema))
    print("wrote %s  (%d bytes; +%d names +%d enums +%d structs over base)"
          % (p2, n2, len(nt2.new_names()), len(enums), len(schema)))


if __name__ == "__main__":
    main()
