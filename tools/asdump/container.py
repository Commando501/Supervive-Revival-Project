#!/usr/bin/env python3
"""
container.py -- exact walker for SUPERVIVE's UE-Angelscript `PrecompiledScript.Cache`.

WHAT THE FILE IS
    A raw `FMemoryWriter` dump of `FAngelscriptPrecompiledData`
    (UnrealEngine-Angelscript, Engine/Plugins/Angelscript/Source/AngelscriptCode/
     Private/StaticJIT/PrecompiledData.h), written by `-as-generate-precompiled-data`.
    No magic, no chunk table, no compression, NO ALIGNMENT PADDING: one flat
    little-endian FArchive stream that can only be read by replaying the exact
    `operator<<` order of every struct.

WHICH REVISION
    SUPERVIVE's fork predates Hazelight commit 661ba173 (2024-10-07,
    "Optimize disk size of precompiled data by about 10% by bitpacking bools")
    and postdates 9ccb5964 (2024-03-26).  So EVERY `bool` is still an individual
    4-byte legacy UBOOL -- there are no bitpacked flag masks -- and the module
    record still carries the FunctionImports/CodeHash/ImportedModules fields that
    fc6a09a0 (2025-05-14) later deleted.  Using master's layout does NOT parse.

PRIMITIVES (little-endian, unaligned)
    uint8/int8   1 byte
    int32/uint32 4 bytes          int64/uint64 8 bytes
    bool         4 bytes          <- FArchive serialises C++ bool as legacy UBOOL
    FGuid        4 x uint32 (A,B,C,D)
    FString           int32 n; n>0 -> n ANSI bytes INCLUDING the NUL terminator
                               n<0 -> -n UTF-16 code units; n==0 -> nothing follows
    FStringInArchive  int32 len; len!=0 -> len+1 bytes (len chars THEN a NUL)
                                 len==0 -> NOTHING follows (not even the NUL)
    TArray<T>    int32 num; then num elements (int32/uint8 are bulk-serialised,
                 which is byte-identical to element-by-element)
    TMap<K,V>    int32 num; then num x (K, V)      (TMap -> TSet -> TSparseArray)

Usage:
    python container.py                    # full validating walk + report
    python container.py --modules          # one line per module
    python container.py --functions        # one line per function record
    python container.py --bytecode N       # hexdump the Nth function's bytecode
    python container.py --regions          # byte-accounting of the whole file

    from container import parse_file, iter_modules, iter_functions
"""

import struct
import sys

DEFAULT_PATH = (r"G:\git\GAME BACKUPS FOR REVERSE ENGINEERING\SUPERVIVE"
                r"\Loki\Script\PrecompiledScript.Cache")


class ParseError(Exception):
    pass


# ---------------------------------------------------------------------------
# FArchive reader
# ---------------------------------------------------------------------------

class Ar:
    """Unaligned little-endian FArchive reader."""

    __slots__ = ("d", "o", "n")

    def __init__(self, data, off=0):
        self.d = data
        self.o = off
        self.n = len(data)

    def u8(self):
        o = self.o
        if o + 1 > self.n:
            raise ParseError(f"u8 past EOF at {o:#x}")
        self.o = o + 1
        return self.d[o]

    def i32(self):
        o = self.o
        if o + 4 > self.n:
            raise ParseError(f"i32 past EOF at {o:#x}")
        self.o = o + 4
        return struct.unpack_from("<i", self.d, o)[0]

    def u32(self):
        o = self.o
        if o + 4 > self.n:
            raise ParseError(f"u32 past EOF at {o:#x}")
        self.o = o + 4
        return struct.unpack_from("<I", self.d, o)[0]

    def i64(self):
        o = self.o
        if o + 8 > self.n:
            raise ParseError(f"i64 past EOF at {o:#x}")
        self.o = o + 8
        return struct.unpack_from("<q", self.d, o)[0]

    def u64(self):
        o = self.o
        if o + 8 > self.n:
            raise ParseError(f"u64 past EOF at {o:#x}")
        self.o = o + 8
        return struct.unpack_from("<Q", self.d, o)[0]

    def b(self):
        """C++ `bool` == 4-byte legacy UBOOL. Values other than 0/1 mean we
        have lost sync, so this doubles as a very strong parse check."""
        at = self.o
        v = self.u32()
        if v > 1:
            raise ParseError(f"bool has value {v:#x} at {at:#x} (lost sync)")
        return v != 0

    def guid(self):
        return tuple(self.u32() for _ in range(4))

    def raw(self, k):
        o = self.o
        if o + k > self.n:
            raise ParseError(f"raw({k}) past EOF at {o:#x}")
        self.o = o + k
        return self.d[o:o + k]

    # -- strings ------------------------------------------------------------
    def fstring(self):
        """UE FString. Length INCLUDES the NUL terminator."""
        at = self.o
        n = self.i32()
        if n == 0:
            return ""
        if n < 0:
            return self.raw(-n * 2)[:-2].decode("utf-16-le")
        b = self.raw(n)
        if b[-1] != 0:
            raise ParseError(f"FString not NUL-terminated at {at:#x}")
        return b[:-1].decode("latin1")

    def sia(self):
        """FStringInArchive. Length EXCLUDES the NUL; len+1 bytes follow.
        Length 0 writes NOTHING (the writer skips Serialize entirely)."""
        at = self.o
        n = self.i32()
        if n == 0:
            return ""
        if n < 0 or self.o + n + 1 > self.n:
            raise ParseError(f"FStringInArchive bad len {n} at {at:#x}")
        b = self.raw(n + 1)
        if b[-1] != 0:
            raise ParseError(f"FStringInArchive not NUL-terminated at {at:#x}")
        return b[:-1].decode("latin1")

    # -- containers ---------------------------------------------------------
    def count(self, what, elem_min=0):
        at = self.o
        n = self.i32()
        if n < 0 or (elem_min and at + 4 + n * elem_min > self.n):
            raise ParseError(f"{what}: absurd count {n} at {at:#x}")
        return n

    def arr(self, fn, what="array", elem_min=0):
        return [fn() for _ in range(self.count(what, elem_min))]

    def arr_i32(self, what="int32[]"):
        n = self.count(what, 4)
        o = self.o
        self.o = o + n * 4
        return list(struct.unpack_from(f"<{n}i", self.d, o)) if n else []

    def arr_i64(self, what="int64[]"):
        n = self.count(what, 8)
        o = self.o
        self.o = o + n * 8
        return list(struct.unpack_from(f"<{n}q", self.d, o)) if n else []

    def arr_sia(self, what="FStringInArchive[]"):
        return [self.sia() for _ in range(self.count(what, 4))]

    def tmap(self, keyfn, valfn, what="TMap"):
        return [(keyfn(), valfn()) for _ in range(self.count(what, 4))]


# ---------------------------------------------------------------------------
# struct readers -- the order below IS the file format
# ---------------------------------------------------------------------------

# FAngelscriptPrecompiledReference == int64 OldReference.
# The ORIGINAL in-process pointer captured at save time (asCObjectType*,
# asCScriptFunction*, asCGlobalProperty* ...).  NOT a file offset: it is the KEY
# into the TypeReferences / FunctionReferences / GlobalReferences /
# PropertyReferences maps in the trailer, which say what it named.
def rd_ref(a):
    return a.i64()


def rd_datatype(a):
    """FAngelscriptPrecompiledDataType -- EXACTLY 36 bytes (6 bools + i64 + i32)."""
    return {
        "bIsReference": a.b(),
        "bIsObjectConst": a.b(),
        "bIsObjectHandle": a.b(),
        "bIsConstHandle": a.b(),
        "bIsAuto": a.b(),
        "bIfHandleThenConst": a.b(),
        "TypeInfo": a.i64(),
        "TokenType": a.i32(),
    }


DT_SIZE = 36

FUNC_BOOLS = ("bBlueprintCallable", "bBlueprintOverride", "bBlueprintEvent",
              "bBlueprintPure", "bNetFunction", "bNetMulticast", "bNetClient",
              "bNetServer", "bNetValidate", "bUnreliable",
              "bBlueprintAuthorityOnly", "bExec", "bCanOverrideEvent",
              "bDevFunction", "bIsStatic", "bIsConstMethod", "bThreadSafe",
              "bIsNoOp")


def rd_function(a, kind="function"):
    """FAngelscriptPrecompiledFunction."""
    start = a.o
    f = {"_kind": kind, "_off": start}
    f["FunctionName"] = a.sia()
    f["Namespace"] = a.sia()
    f["ReturnType"] = rd_datatype(a)
    f["ParameterTypes"] = a.arr(lambda: rd_datatype(a), "ParameterTypes", DT_SIZE)
    f["ParameterNames"] = a.arr_sia("ParameterNames")
    f["ParameterFlags"] = a.arr_i32("ParameterFlags")
    f["ParameterDefaultArgs"] = a.arr_sia("ParameterDefaultArgs")
    f["FunctionTraits"] = a.i32()

    # ---- THE ANGELSCRIPT VM BYTECODE ------------------------------------
    # TArray<int32> memcpy'd verbatim out of asCScriptFunction::scriptData->
    # byteCode, so the count is in asDWORDs (4 bytes each) and the payload is
    # the untouched instruction stream: byte 0 of each dword is the opcode.
    bc_at = a.o
    nbc = a.count("ByteCode", 4)
    f["_bytecode_off"] = bc_at + 4
    f["_bytecode_dwords"] = nbc
    f["_bytecode_bytes"] = nbc * 4
    f["ByteCode"] = a.raw(nbc * 4)

    f["ByteCodeReferences"] = a.arr_i32("ByteCodeReferences")  # never populated
    f["VariableSpace"] = a.i32()
    f["ObjVariableTypes"] = a.arr_i64("ObjVariableTypes")
    f["ObjVariablePos"] = a.arr_i32("ObjVariablePos")
    f["ObjVariablesOnHeap"] = a.i32()
    f["VariableInfoProgramPos"] = a.arr_i32("VariableInfoProgramPos")
    f["VariableInfoOffset"] = a.arr_i32("VariableInfoOffset")
    f["VariableInfoOption"] = a.arr_i32("VariableInfoOption")
    f["StackNeeded"] = a.i32()
    f["Id"] = a.u32()
    f["DeclaredAt"] = a.i32()                     # 0: shipping build strips it
    f["LineNumbers"] = a.arr_i32("LineNumbers")   # empty: ditto

    f["bIsUFunction"] = a.b()
    if f["bIsUFunction"]:
        f["UnrealFunctionName"] = a.sia()
        f["MetaSpec"] = a.arr_sia("MetaSpec")
        f["MetaValues"] = a.arr_sia("MetaValues")
        flags = [n for n in FUNC_BOOLS if a.b()]
        f["Flags"] = flags
    f["_end"] = a.o
    f["_size"] = a.o - start
    return f


def rd_property(a):
    """FAngelscriptPrecompiledProperty."""
    start = a.o
    p = {"_off": start, "Name": a.sia(), "Type": rd_datatype(a)}
    p["bIsPrivate"] = a.b()
    p["bIsProtected"] = a.b()
    p["bIsUnrealProperty"] = a.b()
    if p["bIsUnrealProperty"]:
        p["MetaSpec"] = a.arr_sia("prop.MetaSpec")
        p["MetaValues"] = a.arr_sia("prop.MetaValues")
        flags = []
        for n in ("bBlueprintReadable", "bBlueprintWritable", "bEditConst",
                  "bEditableOnDefaults", "bEditableOnInstance",
                  "bInstancedReference", "bPersistentInstance",
                  "bAdvancedDisplay", "bTransient", "bReplicated",
                  "bSkipReplication", "bSkipSerialization", "bSaveGame"):
            if a.b():
                flags.append(n)
        if "bReplicated" in flags:
            p["ReplicationCondition"] = a.i32()          # int32, not uint8
            if a.b():
                flags.append("bRepNotify")
        for n in ("bConfig", "bInterp", "bAssetRegistrySearchable"):
            if a.b():
                flags.append(n)
        p["Flags"] = flags
    p["_end"] = a.o
    p["_size"] = a.o - start
    return p


def rd_class(a):
    """FAngelscriptPrecompiledClass."""
    start = a.o
    c = {"_off": start, "ClassName": a.sia(), "Namespace": a.sia(),
         "Flags": a.i32()}
    c["Properties"] = a.arr(lambda: rd_property(a), "Properties", 48)
    c["Methods"] = a.arr(lambda: rd_function(a, "method"), "Methods", 100)
    c["MethodTable"] = a.arr_i32("MethodTable")
    c["DerivedFrom"] = rd_ref(a)
    c["ShadowType"] = rd_ref(a)
    c["Constructors"] = a.arr(lambda: rd_function(a, "ctor"), "Constructors", 100)
    c["FactoryRefs"] = a.arr_i64("FactoryRefs")
    c["BehaviorRefs"] = a.arr_i64("BehaviorRefs")
    c["BehaviorFunctions"] = a.arr(lambda: rd_function(a, "behavior"),
                                   "BehaviorFunctions", 100)
    c["BehaviorFunctionTypes"] = a.arr_i32("BehaviorFunctionTypes")

    c["bIsInPreprocessor"] = a.b()
    if c["bIsInPreprocessor"]:
        c["SuperClass"] = a.sia()
        c["CodeSuperClass"] = a.sia()
        for n in ("bSuperIsCodeClass", "bAbstract", "bTransient",
                  "bHideDropdown", "bDefaultToInstanced", "bEditInlineNew",
                  "bIsDeprecatedClass"):
            c[n] = a.b()
        c["ConfigName"] = a.sia()
        c["StaticClassGlobalVariableName"] = a.sia()
        c["bPlaceable"] = a.b()                 # NOTE: after the two strings
        c["MetaSpec"] = a.arr_sia("class.MetaSpec")
        c["MetaValues"] = a.arr_sia("class.MetaValues")
        c["ComposeOntoClassName"] = a.sia()
    c["_end"] = a.o
    c["_size"] = a.o - start
    return c


def rd_enum(a):
    start = a.o
    e = {"_off": start, "Name": a.sia(), "Namespace": a.sia()}
    e["EnumNames"] = a.arr_sia("EnumNames")
    e["EnumValues"] = a.arr_i32("EnumValues")
    e["_end"] = a.o
    e["_size"] = a.o - start
    return e


def rd_globalvar(a):
    start = a.o
    g = {"_off": start, "Name": a.sia(), "Namespace": a.sia(),
         "Type": rd_datatype(a)}
    g["bIsDefaultInit"] = a.b()
    if not g["bIsDefaultInit"]:
        g["bIsPureConstant"] = a.b()
        if g["bIsPureConstant"]:
            g["PureConstantValue"] = a.u64()
        else:
            g["bHasInitFunction"] = a.b()
            g["InitFunc"] = rd_function(a, "globalinit")
    g["_end"] = a.o
    g["_size"] = a.o - start
    return g


def rd_funcsig(a):
    """FAngelscriptPrecompiledFunctionSignature (no ParameterNames!)."""
    s = {"Name": a.sia(), "Namespace": a.sia()}
    s["ParameterTypes"] = a.arr(lambda: rd_datatype(a), "sig.ParameterTypes",
                                DT_SIZE)
    s["ParameterFlags"] = a.arr_i32("sig.ParameterFlags")
    s["ParameterDefaultArgs"] = a.arr_sia("sig.ParameterDefaultArgs")
    s["ReturnType"] = rd_datatype(a)
    return s


def rd_funcimport(a):
    return {"ImportedFromModule": a.sia(), "Signature": rd_funcsig(a)}


def rd_module(a):
    """FAngelscriptPrecompiledModule (the TMap *value*)."""
    start = a.o
    m = {"_off": start, "ModuleName": a.sia()}
    m["Functions"] = a.arr(lambda: rd_function(a, "global"), "Functions", 100)
    m["Classes"] = a.arr(lambda: rd_class(a), "Classes", 100)
    m["Enums"] = a.arr(lambda: rd_enum(a), "Enums", 12)
    m["GlobalVariables"] = a.arr(lambda: rd_globalvar(a), "GlobalVariables", 44)
    m["FunctionImports"] = a.arr(lambda: rd_funcimport(a), "FunctionImports", 50)
    m["CodeHash"] = a.i64()
    m["ImportedModules"] = a.arr_sia("ImportedModules")
    m["StaticsClassName"] = a.sia()
    m["DeclaredEvents"] = a.arr_sia("DeclaredEvents")
    m["DeclaredDelegates"] = a.arr_sia("DeclaredDelegates")
    m["ScriptRelativeFilename"] = a.sia()
    m["PostInitFunctions"] = a.arr_sia("PostInitFunctions")
    m["_end"] = a.o
    m["_size"] = a.o - start
    return m


# --------------------------- trailer records -------------------------------

def rd_typeref(a):
    r = {"Name": a.sia(), "Module": a.sia(), "Namespace": a.sia()}
    r["SubTypes"] = a.arr(lambda: rd_datatype(a), "SubTypes", DT_SIZE)
    return r


def rd_funcref(a):
    r = {"Name": a.sia(), "Module": a.sia(), "Namespace": a.sia(),
         "bIsConst": a.b(), "bIsImportedDecl": a.b(), "bIsMethod": a.b(),
         "ObjectType": rd_ref(a)}
    r["ParameterTypes"] = a.arr(lambda: rd_datatype(a), "ref.ParameterTypes",
                                DT_SIZE)
    r["ReturnType"] = rd_datatype(a)
    return r


def rd_globalref(a):
    return {"Name": a.sia(), "Module": a.sia(), "Namespace": a.sia(),
            "bIsString": a.b()}


def rd_propref(a):
    return {"Name": a.sia(), "OldTypeId": a.i32()}


# ---------------------------------------------------------------------------
# top level
# ---------------------------------------------------------------------------

def parse_file(path=DEFAULT_PATH):
    """Walk the whole cache. Raises ParseError on any inconsistency."""
    with open(path, "rb") as fh:
        data = fh.read()
    a = Ar(data)
    out = {"_path": path, "_size": len(data), "_data": data}

    out["DataGuid"] = a.guid()
    out["BuildIdentifier"] = a.i32()

    mods_at = a.o
    nmod = a.count("Modules")
    mods = []
    for _ in range(nmod):
        key_at = a.o
        key = a.fstring()
        mod = rd_module(a)
        mod["_key"] = key
        mod["_record_off"] = key_at
        mod["_record_size"] = a.o - key_at
        mods.append(mod)
    out["Modules"] = mods
    out["_modules_off"] = mods_at
    out["_modules_end"] = a.o

    out["_trailer_off"] = a.o
    out["_off_TypeReferences"] = a.o
    out["TypeReferences"] = a.tmap(a.i64, lambda: rd_typeref(a),
                                   "TypeReferences")
    out["_off_TypeIdReferenceToPointer"] = a.o
    out["TypeIdReferenceToPointer"] = a.tmap(a.i32, a.i64,
                                             "TypeIdReferenceToPointer")
    out["_off_FunctionReferences"] = a.o
    out["FunctionReferences"] = a.tmap(a.i64, lambda: rd_funcref(a),
                                       "FunctionReferences")
    out["_off_FunctionIdReferenceToPointer"] = a.o
    out["FunctionIdReferenceToPointer"] = a.tmap(a.i32, a.i64,
                                                 "FunctionIdReferenceToPointer")
    out["_off_GlobalReferences"] = a.o
    out["GlobalReferences"] = a.tmap(a.i64, lambda: rd_globalref(a),
                                     "GlobalReferences")
    out["_off_StaticNames"] = a.o
    out["StaticNames"] = a.arr_sia("StaticNames")
    out["_off_PropertyReferences"] = a.o
    out["PropertyReferences"] = a.tmap(a.i64, lambda: rd_propref(a),
                                       "PropertyReferences")

    out["_end"] = a.o
    out["_trailing_slack"] = len(data) - a.o
    return out


def iter_modules(parsed):
    for i, m in enumerate(parsed["Modules"]):
        yield i, m


def iter_functions(module):
    """Yield (owner, kind, function) for EVERY function record in a module:
    module-level globals, class methods, class constructors, class behaviours
    and global-variable initialiser functions."""
    for f in module["Functions"]:
        yield module["ModuleName"], "global", f
    for c in module["Classes"]:
        owner = c["ClassName"]
        for f in c["Methods"]:
            yield owner, "method", f
        for f in c["Constructors"]:
            yield owner, "ctor", f
        for f in c["BehaviorFunctions"]:
            yield owner, "behavior", f
    for g in module["GlobalVariables"]:
        if "InitFunc" in g:
            yield module["ModuleName"], "globalinit", g["InitFunc"]


def all_functions(parsed):
    for _, m in iter_modules(parsed):
        for owner, kind, f in iter_functions(m):
            yield m, owner, kind, f


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _stats(p):
    st = {"classes": 0, "properties": 0, "enums": 0, "globals": 0,
          "functions": 0, "bytecode": 0, "kinds": {}, "imports": 0}
    for _, m in iter_modules(p):
        st["classes"] += len(m["Classes"])
        st["enums"] += len(m["Enums"])
        st["globals"] += len(m["GlobalVariables"])
        st["imports"] += len(m["FunctionImports"])
        for c in m["Classes"]:
            st["properties"] += len(c["Properties"])
        for _o, k, f in iter_functions(m):
            st["functions"] += 1
            st["kinds"][k] = st["kinds"].get(k, 0) + 1
            st["bytecode"] += f["_bytecode_bytes"]
    return st


def _report(p):
    g = p["DataGuid"]
    sz = p["_size"]
    print(f"file            : {p['_path']}")
    print(f"size            : {sz:,} bytes")
    print(f"DataGuid        : {g[0]:08X}-{g[1]:08X}-{g[2]:08X}-{g[3]:08X}"
          "   (random per save, NOT a format magic)")
    print(f"BuildIdentifier : {p['BuildIdentifier']}"
          f"  ({'UE_BUILD_SHIPPING' if p['BuildIdentifier'] == 4 else '?'})")
    print()
    mo, me = p["_modules_off"], p["_modules_end"]
    print(f"Modules  : {len(p['Modules']):>3}  "
          f"[{mo:#010x}..{me:#010x}]  {me - mo:>9,} bytes  "
          f"{100.0 * (me - mo) / sz:5.1f}%")
    tr = sz - p["_trailer_off"]
    print(f"Trailer  :       [{p['_trailer_off']:#010x}..EOF]        "
          f"{tr:>9,} bytes  {100.0 * tr / sz:5.1f}%")
    for label, key, off in (
            ("TypeReferences", "TypeReferences", "_off_TypeReferences"),
            ("TypeIdReferenceToPointer", "TypeIdReferenceToPointer",
             "_off_TypeIdReferenceToPointer"),
            ("FunctionReferences", "FunctionReferences",
             "_off_FunctionReferences"),
            ("FunctionIdReferenceToPointer", "FunctionIdReferenceToPointer",
             "_off_FunctionIdReferenceToPointer"),
            ("GlobalReferences", "GlobalReferences", "_off_GlobalReferences"),
            ("StaticNames", "StaticNames", "_off_StaticNames"),
            ("PropertyReferences", "PropertyReferences",
             "_off_PropertyReferences")):
        print(f"    {label:<30}{len(p[key]):>8,} entries  @{p[off]:#010x}")
    print()
    print(f"stream ended at : {p['_end']:#010x}   (EOF = {sz:#010x})")
    ok = p["_trailing_slack"] == 0
    print(f"trailing slack  : {p['_trailing_slack']} byte(s)   "
          f"{'<== EXACT, walk validated' if ok else '<== MISMATCH'}")
    print()
    st = _stats(p)
    print(f"classes         : {st['classes']:,}")
    print(f"properties      : {st['properties']:,}")
    print(f"enums           : {st['enums']:,}")
    print(f"global vars     : {st['globals']:,}")
    print(f"function imports: {st['imports']:,}")
    print(f"functions       : {st['functions']:,}   " +
          "  ".join(f"{k}={v:,}" for k, v in sorted(st["kinds"].items())))
    print(f"bytecode total  : {st['bytecode']:,} bytes "
          f"({100.0 * st['bytecode'] / sz:.1f}% of the file)")
    return ok


def _regions(p):
    sz = p["_size"]
    rows = [("header (FGuid + BuildIdentifier)", 0, 20),
            ("Modules TMap count", 20, 24)]
    for i, m in enumerate(p["Modules"]):
        rows.append((f"module[{i:2}] {m['ModuleName']}", m["_record_off"],
                     m["_record_off"] + m["_record_size"]))
    rows += [("TypeReferences", p["_off_TypeReferences"],
              p["_off_TypeIdReferenceToPointer"]),
             ("TypeIdReferenceToPointer", p["_off_TypeIdReferenceToPointer"],
              p["_off_FunctionReferences"]),
             ("FunctionReferences", p["_off_FunctionReferences"],
              p["_off_FunctionIdReferenceToPointer"]),
             ("FunctionIdReferenceToPointer",
              p["_off_FunctionIdReferenceToPointer"],
              p["_off_GlobalReferences"]),
             ("GlobalReferences", p["_off_GlobalReferences"],
              p["_off_StaticNames"]),
             ("StaticNames", p["_off_StaticNames"],
              p["_off_PropertyReferences"]),
             ("PropertyReferences", p["_off_PropertyReferences"], p["_end"])]
    cur = 0
    total = 0
    for name, s, e in rows:
        if s != cur:
            print(f"  !! GAP {cur:#010x}..{s:#010x}")
        print(f"  {s:#010x}..{e:#010x} {e - s:>9,}  {100.0 * (e - s) / sz:5.2f}%  {name}")
        total += e - s
        cur = e
    print(f"  accounted: {total:,} / {sz:,} bytes  "
          f"({100.0 * total / sz:.4f}%)   unaccounted: {sz - total}")


def verify_bytecode(p):
    """INDEPENDENT proof that _bytecode_off / _bytecode_dwords are right.

    Decode every function's ByteCode payload as an AngelScript instruction
    stream using the fork's own asBCInfo/asBCTypeSize tables: read byte 0 of
    each dword as the opcode, advance by that opcode's size in dwords.  A
    correct offset+length means every stream lands EXACTLY on its end.  A
    wrong one desynchronises within a handful of instructions."""
    try:
        from asopcodes import OPNAME, OPSIZE
    except ImportError:
        print("asopcodes.py not found -- skipping bytecode verification")
        return True
    total = ok = empty = 0
    bad = []
    instrs = 0
    histo = {}
    for m, owner, kind, f in all_functions(p):
        n = f["_bytecode_dwords"]
        total += 1
        if n == 0:
            empty += 1
            continue
        bc = f["ByteCode"]
        i = 0
        while i < n:
            op = bc[i * 4]
            sz = OPSIZE[op]
            if sz == 0:                      # INFO / dummy: never in a real stream
                bad.append((m["ModuleName"], owner, f["FunctionName"],
                            f"invalid opcode {op} ({OPNAME[op]}) at dword {i}"))
                break
            histo[op] = histo.get(op, 0) + 1
            instrs += 1
            i += sz
        else:
            if i == n:
                ok += 1
                continue
            bad.append((m["ModuleName"], owner, f["FunctionName"],
                        f"overran: ended at dword {i} of {n}"))
    print(f"bytecode verify : {ok:,}/{total - empty:,} non-empty streams decoded "
          f"to EXACTLY their declared length  ({empty:,} empty)")
    print(f"                  {instrs:,} instructions, "
          f"{len(histo)} distinct opcodes")
    top = sorted(histo.items(), key=lambda kv: -kv[1])[:10]
    print("                  top opcodes: " +
          ", ".join(f"{OPNAME[o]}({c:,})" for o, c in top))
    for b in bad[:10]:
        print(f"   FAIL {b[0]} {b[1]}::{b[2]}: {b[3]}")
    return not bad


BEHAVIOR_SLOTS = ("factory", "listFactory", "copyfactory", "construct",
                  "copyconstruct", "destruct", "copy")


def crosscheck(p):
    """Structural invariants + full reference resolution.

    Two DIFFERENT kinds of int64 live in FAngelscriptPrecompiledReference:
      * a real captured POINTER  -> key into TypeReferences / FunctionReferences
                                    / GlobalReferences / PropertyReferences
      * a small function/type ID -> key into FunctionIdReferenceToPointer /
                                    TypeIdReferenceToPointer, which then maps
                                    to the pointer.  FactoryRefs and
                                    BehaviorRefs are ID-valued (ReferenceFunctionId).
    """
    types = dict(p["TypeReferences"])
    funcs = dict(p["FunctionReferences"])
    fid = dict(p["FunctionIdReferenceToPointer"])
    fns = list(all_functions(p))
    n = len(fns)
    fails = []

    def inv(label, ok, detail=""):
        print(f"  {'ok  ' if ok else 'FAIL'} {label}{detail}")
        if not ok:
            fails.append(label)

    inv("parallel parameter arrays are equal length",
        all(len(f["ParameterNames"]) == len(f["ParameterFlags"])
            == len(f["ParameterDefaultArgs"]) == len(f["ParameterTypes"])
            for *_, f in fns), f"   ({n:,} functions)")
    inv("ObjVariableTypes / ObjVariablePos parallel",
        all(len(f["ObjVariableTypes"]) == len(f["ObjVariablePos"])
            for *_, f in fns))
    inv("VariableInfo{ProgramPos,Offset,Option} parallel",
        all(len(f["VariableInfoProgramPos"]) == len(f["VariableInfoOffset"])
            == len(f["VariableInfoOption"]) for *_, f in fns))
    inv("MetaSpec / MetaValues parallel",
        all(len(f["MetaSpec"]) == len(f["MetaValues"])
            for *_, f in fns if f["bIsUFunction"]))
    inv("BehaviorRefs is always exactly 7 entries",
        all(len(c["BehaviorRefs"]) == 7
            for _, m in iter_modules(p) for c in m["Classes"]))
    ids = [f["Id"] for *_, f in fns]
    inv("function Ids are unique", len(ids) == len(set(ids)),
        f"   ({len(set(ids)):,} distinct)")
    inv("DeclaredAt == 0 everywhere (shipping build strips it)",
        all(f["DeclaredAt"] == 0 for *_, f in fns))
    inv("LineNumbers empty everywhere (shipping build strips it)",
        all(not f["LineNumbers"] for *_, f in fns))
    inv("ByteCodeReferences empty everywhere (never populated)",
        all(not f["ByteCodeReferences"] for *_, f in fns))

    ptr_used = ptr_bad = 0
    for _m, _o, _k, f in fns:
        for v in ([f["ReturnType"]["TypeInfo"]]
                  + [t["TypeInfo"] for t in f["ParameterTypes"]]
                  + f["ObjVariableTypes"]):
            if v:
                ptr_used += 1
                ptr_bad += v not in types
    for _, m in iter_modules(p):
        for gv in m["GlobalVariables"]:
            v = gv["Type"]["TypeInfo"]
            if v:
                ptr_used += 1
                ptr_bad += v not in types
        for c in m["Classes"]:
            for v in (c["DerivedFrom"], c["ShadowType"]):
                if v:
                    ptr_used += 1
                    ptr_bad += v not in types
            for pr in c["Properties"]:
                v = pr["Type"]["TypeInfo"]
                if v:
                    ptr_used += 1
                    ptr_bad += v not in types
    inv("pointer-valued TypeInfo refs resolve in TypeReferences",
        ptr_bad == 0, f"   ({ptr_used:,} used, {ptr_bad} unresolved)")

    id_used = id_bad = 0
    for _, m in iter_modules(p):
        for c in m["Classes"]:
            for v in c["FactoryRefs"] + c["BehaviorRefs"]:
                if v:
                    id_used += 1
                    id_bad += v not in fid
    inv("id-valued Factory/BehaviorRefs resolve via "
        "FunctionIdReferenceToPointer", id_bad == 0,
        f"   ({id_used:,} used, {id_bad} unresolved)")
    inv("every FunctionIdReferenceToPointer value is in FunctionReferences",
        all(v in funcs for v in fid.values()))
    inv("every TypeIdReferenceToPointer value is in TypeReferences",
        all(v in types for _k, v in p["TypeIdReferenceToPointer"]))
    return not fails


def disasm(f, limit=None):
    """Rough linear disassembly of one function's bytecode."""
    from asopcodes import OPNAME, OPSIZE
    bc = f["ByteCode"]
    n = f["_bytecode_dwords"]
    i = 0
    out = []
    while i < n and (limit is None or len(out) < limit):
        op = bc[i * 4]
        sz = OPSIZE[op] or 1
        words = struct.unpack_from(f"<{sz}I", bc, i * 4)
        out.append((i, f["_bytecode_off"] + i * 4, op, OPNAME[op], words))
        i += sz
    return out


def _hexdump(b, base=0, limit=None):
    if limit is not None:
        b = b[:limit]
    for i in range(0, len(b), 16):
        ch = b[i:i + 16]
        print(f"  {base + i:08x}  " + " ".join(f"{x:02x}" for x in ch).ljust(47)
              + "  |" + "".join(chr(x) if 32 <= x < 127 else "." for x in ch) + "|")


def main(argv):
    path = DEFAULT_PATH
    args = list(argv[1:])
    if args and not args[0].startswith("--"):
        path = args.pop(0)
    p = parse_file(path)

    if "--modules" in args:
        for i, m in iter_modules(p):
            print(f"[{i:2}] {m['_record_off']:#010x} +{m['_record_size']:<7} "
                  f"fn={len(m['Functions']):<3} cls={len(m['Classes']):<3} "
                  f"enum={len(m['Enums']):<3} gv={len(m['GlobalVariables']):<3} "
                  f"imp={len(m['FunctionImports']):<3} "
                  f"{m['ModuleName']:<62} {m['ScriptRelativeFilename']}")
        return 0
    if "--functions" in args:
        for n, (m, owner, kind, f) in enumerate(all_functions(p)):
            print(f"{n:5} {f['_off']:#010x} +{f['_size']:<6} "
                  f"bc={f['_bytecode_dwords']:<5}dw@{f['_bytecode_off']:#010x} "
                  f"{kind:<10} {owner}::{f['FunctionName']}")
        return 0
    if "--bytecode" in args:
        idx = int(args[args.index("--bytecode") + 1])
        for n, (m, owner, kind, f) in enumerate(all_functions(p)):
            if n == idx:
                print(f"{m['ModuleName']} :: {owner}::{f['FunctionName']} "
                      f"({kind})  {f['_bytecode_dwords']} dwords "
                      f"@{f['_bytecode_off']:#010x}")
                _hexdump(f["ByteCode"], f["_bytecode_off"], 1024)
                return 0
        print("index out of range")
        return 1
    if "--regions" in args:
        _regions(p)
        return 0
    if "--disasm" in args:
        idx = int(args[args.index("--disasm") + 1])
        for n, (m, owner, kind, f) in enumerate(all_functions(p)):
            if n == idx:
                print(f"{m['ModuleName']} :: {owner}::{f['FunctionName']} "
                      f"({kind})  {f['_bytecode_dwords']} dwords "
                      f"@{f['_bytecode_off']:#010x}  "
                      f"stackNeeded={f['StackNeeded']} "
                      f"varSpace={f['VariableSpace']}")
                for dw, off, op, name, words in disasm(f):
                    ws = " ".join(f"{w:08x}" for w in words)
                    print(f"  {off:#010x} [{dw:4}] {op:3} {name:<14} {ws}")
                return 0
        print("index out of range")
        return 1

    ok = _report(p)
    print()
    ok = verify_bytecode(p) and ok
    print("\ncross-checks:")
    ok = crosscheck(p) and ok
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
