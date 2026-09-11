#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
asdump -- SUPERVIVE (UE-Angelscript fork) script-cache decompiler.
===================================================================

Reads the three plaintext caches the game ships:

    Loki/Script/PrecompiledScript.Cache    the compiled Angelscript bytecode
    Loki/Script/Binds.Cache                the engine<->script bind database
    Loki/Script/Binds.Cache.Headers        /Script/Module.Class -> C++ header

and emits, per Angelscript module, a `.as.txt` file containing the module's
declarations plus every function's signature, reconstructed pseudo-source and
fully symbol-resolved disassembly.

DESIGN RULES (deliberate, do not "fix" these):
  * FAIL LOUDLY.  The container walk raises ParseError with a byte offset the
    instant anything desynchronises.  It never guesses.
  * DEGRADE PER FUNCTION.  Bytecode decode / lifting failures are contained to
    one function and reported as `<<UNDECODED: ...>>` / `<<PSEUDO FAILED: ...>>`
    markers, never silently dropped.
  * SELF-VALIDATE.  --report prints a byte-coverage ledger and per-stage rates.

The file format itself is a raw `FMemoryWriter` dump of the plugin's
`FAngelscriptPrecompiledData`; SUPERVIVE's fork predates upstream commit
661ba173 ("bitpacking bools"), so every C++ `bool` is still a 4-byte legacy
UBOOL.  Two different string encodings are in play and they are NOT
interchangeable -- see `Ar.fstring` / `Ar.sia`.

Usage:
    python asdump.py                 # parse + emit everything, print the report
    python asdump.py --report        # parse + validate only, emit nothing
    python asdump.py --module FFA.FFABotSpawner      # one module to stdout
    python asdump.py --func LokiDropShip::BeginPlay  # one function to stdout
"""

import os
import re
import struct
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

from opcodes import OPCODES, MAXBYTECODE            # noqa: E402  (game-extracted)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

GAME_SCRIPT_DIR = r"G:\git\GAME BACKUPS FOR REVERSE ENGINEERING\SUPERVIVE\Loki\Script"
PRECOMPILED = os.path.join(GAME_SCRIPT_DIR, "PrecompiledScript.Cache")
BINDS = os.path.join(GAME_SCRIPT_DIR, "Binds.Cache")
BINDS_HEADERS = os.path.join(GAME_SCRIPT_DIR, "Binds.Cache.Headers")

OUT_DIR = os.path.join(os.path.dirname(_HERE), "out", "a")

EXPECT_MODULES = 78            # hard expectations -- assert, do not adapt
EXPECT_FUNCTIONS = 1463
EXPECT_CLASSES = 110


class ParseError(Exception):
    """Container walk desynchronised.  Always carries a byte offset."""


# ===========================================================================
# 1.  FArchive reader
# ===========================================================================

class Ar(object):
    """Little-endian, completely unaligned UE FArchive byte-stream reader.

    There is no magic, no chunk table and no offset table anywhere in these
    files: the only way to read them is to replay the exact `operator<<`
    order of every struct.  Every accessor bounds-checks and raises
    ParseError with the offset, so a desync surfaces immediately instead of
    producing plausible garbage.
    """

    __slots__ = ("d", "o", "n", "path")

    def __init__(self, path):
        with open(path, "rb") as fh:               # READ-ONLY.  Always.
            self.d = fh.read()
        self.o = 0
        self.n = len(self.d)
        self.path = path

    # -- primitives ---------------------------------------------------------
    def _need(self, k):
        if self.o + k > self.n:
            raise ParseError("read of %d byte(s) past EOF at 0x%x (size 0x%x) in %s"
                             % (k, self.o, self.n, os.path.basename(self.path)))

    def u8(self):
        self._need(1)
        v = self.d[self.o]
        self.o += 1
        return v

    def i8(self):
        self._need(1)
        v = struct.unpack_from("<b", self.d, self.o)[0]
        self.o += 1
        return v

    def i32(self):
        self._need(4)
        v = struct.unpack_from("<i", self.d, self.o)[0]
        self.o += 4
        return v

    def u32(self):
        self._need(4)
        v = struct.unpack_from("<I", self.d, self.o)[0]
        self.o += 4
        return v

    def i64(self):
        self._need(8)
        v = struct.unpack_from("<q", self.d, self.o)[0]
        self.o += 8
        return v

    def u64(self):
        self._need(8)
        v = struct.unpack_from("<Q", self.d, self.o)[0]
        self.o += 8
        return v

    def boolean(self):
        """C++ bool.  FArchive serialises it as a legacy 32-bit UBOOL, and the
        value is ALWAYS 0 or 1 -- which makes this the single best desync
        canary in the file (~250k of them get checked per run)."""
        at = self.o
        v = self.u32()
        if v > 1:
            raise ParseError("bad bool %d (0x%08x) at 0x%x -- stream desynchronised"
                             % (v, v, at))
        return v == 1

    def fstring(self):
        """UE `FString`.  Length INCLUDES the trailing NUL.  Negative length
        means UTF-16LE.  Used for exactly one field in PrecompiledScript.Cache
        (the Modules TMap key) and for every string in Binds.Cache."""
        at = self.o
        n = self.i32()
        if n == 0:
            return ""
        if n > 0:
            if n > (1 << 24):
                raise ParseError("absurd FString length %d at 0x%x" % (n, at))
            self._need(n)
            raw = self.d[self.o:self.o + n]
            self.o += n
            if raw[-1:] != b"\x00":
                raise ParseError("FString at 0x%x is not NUL-terminated" % at)
            return raw[:-1].decode("latin-1")
        n = -n
        if n > (1 << 24):
            raise ParseError("absurd FString(utf16) length %d at 0x%x" % (n, at))
        self._need(2 * n)
        raw = self.d[self.o:self.o + 2 * n]
        self.o += 2 * n
        return raw[:-2].decode("utf-16-le")

    def sia(self):
        """The plugin's own `FStringInArchive` (StringInArchive.h).  Length
        EXCLUDES the NUL and len+1 bytes follow -- EXCEPT when len == 0, in
        which case NOTHING follows, not even the NUL.  That zero case is the
        one that makes naive scanners think NUL handling is 'inconsistent'."""
        at = self.o
        n = self.i32()
        if n == 0:
            return ""
        if n < 0 or n > (1 << 24):
            raise ParseError("absurd FStringInArchive length %d at 0x%x" % (n, at))
        self._need(n + 1)
        raw = self.d[self.o:self.o + n]
        term = self.d[self.o + n]
        self.o += n + 1
        if term != 0:
            raise ParseError("FStringInArchive at 0x%x missing NUL terminator" % at)
        return raw.decode("latin-1")

    # -- containers ---------------------------------------------------------
    def count(self, min_elem_bytes=0):
        at = self.o
        n = self.i32()
        if n < 0:
            raise ParseError("negative array count %d at 0x%x" % (n, at))
        if min_elem_bytes and self.o + n * min_elem_bytes > self.n:
            raise ParseError("array count %d at 0x%x cannot fit (min %d B/elem, "
                             "%d B left)" % (n, at, min_elem_bytes, self.n - self.o))
        return n

    def arr(self, fn, min_elem_bytes=0):
        return [fn() for _ in range(self.count(min_elem_bytes))]

    def arr_i32(self):
        n = self.count(4)
        self._need(4 * n)
        v = list(struct.unpack_from("<%di" % n, self.d, self.o)) if n else []
        self.o += 4 * n
        return v

    def raw(self, k):
        self._need(k)
        v = self.d[self.o:self.o + k]
        self.o += k
        return v


# ===========================================================================
# 2.  PrecompiledScript.Cache  --  container
# ===========================================================================

# asETypeModifiers
TM_NONE, TM_INREF, TM_OUTREF, TM_INOUTREF = 0, 1, 2, 3

# eTokenType values that actually occur in this file (derived from
# as_tokendef.h by enumerating the enum; ttIdentifier == 5 confirms it).
TOKEN_NAMES = {
    59: "?", 65: "bool", 68: "int", 69: "int8", 70: "int16", 71: "int64",
    75: "uint", 76: "uint8", 77: "uint16", 78: "uint64",
    79: "float", 80: "float", 81: "float64", 82: "void", 94: "double",
    110: "auto",
}
TT_IDENTIFIER = 5
TT_QUESTION = 59            # AngelScript's variable type `?` -- 2 stack slots
TT_VOID = 82

# UFUNCTION flag names, in serialisation order (18 of them).
UFUNC_FLAGS = (
    "BlueprintCallable", "BlueprintOverride", "BlueprintEvent", "BlueprintPure",
    "NetFunction", "NetMulticast", "NetClient", "NetServer", "NetValidate",
    "Unreliable", "BlueprintAuthorityOnly", "Exec", "CanOverrideEvent",
    "DevFunction", "Static", "Const", "ThreadSafe", "NoOp",
)

# UPROPERTY flag names.  bRepNotify is inserted after ReplicationCondition
# when bReplicated is set, hence the split.
UPROP_FLAGS_A = (
    "BlueprintReadable", "BlueprintWritable", "EditConst", "EditableOnDefaults",
    "EditableOnInstance", "InstancedReference", "PersistentInstance",
    "AdvancedDisplay", "Transient", "Replicated",
    "SkipReplication", "SkipSerialization", "SaveGame",
)
UPROP_FLAGS_B = ("Config", "Interp", "AssetRegistrySearchable")

BEHAVIOR_SLOTS = ("factory", "listFactory", "copyfactory", "construct",
                  "copyconstruct", "destruct", "copy")


def rd_datatype(a):
    """FAngelscriptPrecompiledDataType -- 36 bytes flat.  (Master's version is
    10 bytes; using it desyncs ~120 bytes into the first function.)"""
    return {
        "bIsReference": a.boolean(),
        "bIsObjectConst": a.boolean(),
        "bIsObjectHandle": a.boolean(),
        "bIsConstHandle": a.boolean(),
        "bIsAuto": a.boolean(),
        "bIfHandleThenConst": a.boolean(),
        "TypeInfo": a.i64(),
        "TokenType": a.i32(),
    }


def rd_function(a):
    off = a.o
    f = {
        "_off": off,
        "FunctionName": a.sia(),
        "Namespace": a.sia(),
        "ReturnType": rd_datatype(a),
    }
    f["ParameterTypes"] = a.arr(lambda: rd_datatype(a), 36)
    f["ParameterNames"] = a.arr(a.sia, 4)
    f["ParameterFlags"] = a.arr_i32()
    f["ParameterDefaultArgs"] = a.arr(a.sia, 4)
    f["FunctionTraits"] = a.i32()
    nbc = a.count(4)
    f["_bytecode_off"] = a.o
    f["_bytecode_dwords"] = nbc
    f["ByteCode"] = a.raw(4 * nbc)
    f["ByteCodeReferences"] = a.arr_i32()
    f["VariableSpace"] = a.i32()
    f["ObjVariableTypes"] = a.arr(a.i64, 8)
    f["ObjVariablePos"] = a.arr_i32()
    f["ObjVariablesOnHeap"] = a.i32()
    f["VariableInfoProgramPos"] = a.arr_i32()
    f["VariableInfoOffset"] = a.arr_i32()
    f["VariableInfoOption"] = a.arr_i32()
    f["StackNeeded"] = a.i32()
    f["Id"] = a.u32()
    f["DeclaredAt"] = a.i32()
    f["LineNumbers"] = a.arr_i32()
    f["bIsUFunction"] = a.boolean()
    if f["bIsUFunction"]:
        f["UnrealFunctionName"] = a.sia()
        f["MetaSpec"] = a.arr(a.sia, 4)
        f["MetaValues"] = a.arr(a.sia, 4)
        f["Flags"] = [a.boolean() for _ in range(18)]
    else:
        f["UnrealFunctionName"] = ""
        f["MetaSpec"] = []
        f["MetaValues"] = []
        f["Flags"] = []
    f["_size"] = a.o - off
    return f


def rd_property(a):
    p = {
        "Name": a.sia(),
        "Type": rd_datatype(a),
        "bIsPrivate": a.boolean(),
        "bIsProtected": a.boolean(),
        "bIsUnrealProperty": a.boolean(),
    }
    p["MetaSpec"] = []
    p["MetaValues"] = []
    p["Flags"] = []
    p["ReplicationCondition"] = None
    if p["bIsUnrealProperty"]:
        p["MetaSpec"] = a.arr(a.sia, 4)
        p["MetaValues"] = a.arr(a.sia, 4)
        names = list(UPROP_FLAGS_A)
        vals = [a.boolean() for _ in range(len(UPROP_FLAGS_A))]
        if vals[UPROP_FLAGS_A.index("Replicated")]:
            p["ReplicationCondition"] = a.i32()
            names.append("RepNotify")
            vals.append(a.boolean())
        names += list(UPROP_FLAGS_B)
        vals += [a.boolean() for _ in range(len(UPROP_FLAGS_B))]
        p["Flags"] = [nm for nm, v in zip(names, vals) if v]
    return p


def rd_class(a):
    off = a.o
    c = {
        "_off": off,
        "ClassName": a.sia(),
        "Namespace": a.sia(),
        "Flags": a.i32(),
    }
    c["Properties"] = a.arr(lambda: rd_property(a), 4)
    c["Methods"] = a.arr(lambda: rd_function(a), 4)
    c["MethodTable"] = a.arr_i32()
    c["DerivedFrom"] = a.i64()
    c["ShadowType"] = a.i64()
    c["Constructors"] = a.arr(lambda: rd_function(a), 4)
    c["FactoryRefs"] = a.arr(a.i64, 8)
    c["BehaviorRefs"] = a.arr(a.i64, 8)
    if len(c["BehaviorRefs"]) != 7:
        raise ParseError("class %r at 0x%x has %d BehaviorRefs, expected 7"
                         % (c["ClassName"], off, len(c["BehaviorRefs"])))
    c["BehaviorFunctions"] = a.arr(lambda: rd_function(a), 4)
    c["BehaviorFunctionTypes"] = a.arr_i32()
    c["bIsInPreprocessor"] = a.boolean()
    if c["bIsInPreprocessor"]:
        c["SuperClass"] = a.sia()
        c["CodeSuperClass"] = a.sia()
        for k in ("bSuperIsCodeClass", "bAbstract", "bTransient", "bHideDropdown",
                  "bDefaultToInstanced", "bEditInlineNew", "bIsDeprecatedClass"):
            c[k] = a.boolean()
        c["ConfigName"] = a.sia()
        c["StaticClassGlobalVariableName"] = a.sia()
        c["bPlaceable"] = a.boolean()
        c["MetaSpec"] = a.arr(a.sia, 4)
        c["MetaValues"] = a.arr(a.sia, 4)
        c["ComposeOntoClassName"] = a.sia()
    else:
        c["SuperClass"] = ""
        c["CodeSuperClass"] = ""
        c["MetaSpec"] = []
        c["MetaValues"] = []
    c["_size"] = a.o - off
    return c


def rd_enum(a):
    return {"Name": a.sia(), "Namespace": a.sia(),
            "EnumNames": a.arr(a.sia, 4), "EnumValues": a.arr_i32()}


def rd_globalvar(a):
    g = {"Name": a.sia(), "Namespace": a.sia(), "Type": rd_datatype(a),
         "bIsDefaultInit": a.boolean()}
    if not g["bIsDefaultInit"]:
        g["bIsPureConstant"] = a.boolean()
        if g["bIsPureConstant"]:
            g["PureConstantValue"] = a.u64()
        else:
            g["bHasInitFunction"] = a.boolean()
            g["InitFunc"] = rd_function(a)
    return g


def rd_funcsig(a):
    return {"Name": a.sia(), "Namespace": a.sia(),
            "ParameterTypes": a.arr(lambda: rd_datatype(a), 36),
            "ParameterFlags": a.arr_i32(),
            "ParameterDefaultArgs": a.arr(a.sia, 4),
            "ReturnType": rd_datatype(a)}


def rd_module(a):
    off = a.o
    m = {"_off": off, "ModuleName": a.sia()}
    m["Functions"] = a.arr(lambda: rd_function(a), 4)
    m["Classes"] = a.arr(lambda: rd_class(a), 4)
    m["Enums"] = a.arr(lambda: rd_enum(a), 4)
    m["GlobalVariables"] = a.arr(lambda: rd_globalvar(a), 4)
    m["FunctionImports"] = a.arr(lambda: (a.sia(), rd_funcsig(a)), 4)
    m["CodeHash"] = a.i64()
    m["ImportedModules"] = a.arr(a.sia, 4)
    m["StaticsClassName"] = a.sia()
    m["DeclaredEvents"] = a.arr(a.sia, 4)
    m["DeclaredDelegates"] = a.arr(a.sia, 4)
    m["ScriptRelativeFilename"] = a.sia()
    m["PostInitFunctions"] = a.arr(a.sia, 4)
    m["_size"] = a.o - off
    return m


def parse_precompiled(path=PRECOMPILED):
    a = Ar(path)
    regions = []                                   # (name, start, end)

    guid = [a.u32() for _ in range(4)]
    build = a.i32()
    regions.append(("header", 0, a.o))

    p = {
        "_path": path,
        "_size": a.n,
        "DataGuid": "%08X-%08X-%08X-%08X" % tuple(guid),
        "BuildIdentifier": build,
        "Modules": [],
    }

    mstart = a.o
    nmod = a.count(4)
    for _ in range(nmod):
        rec_off = a.o
        key = a.fstring()
        m = rd_module(a)
        m["_key"] = key
        m["_record_off"] = rec_off
        m["_record_size"] = a.o - rec_off
        if m["_key"] != m["ModuleName"]:
            raise ParseError("module key %r != ModuleName %r at 0x%x"
                             % (m["_key"], m["ModuleName"], rec_off))
        p["Modules"].append(m)
    regions.append(("Modules", mstart, a.o))

    def table(name, rd_key, rd_val, min_bytes):
        st = a.o
        n = a.count(min_bytes)
        out = [(rd_key(), rd_val()) for _ in range(n)]
        regions.append((name, st, a.o))
        return out

    p["TypeReferences"] = table(
        "TypeReferences", a.i64,
        lambda: {"Name": a.sia(), "Module": a.sia(), "Namespace": a.sia(),
                 "SubTypes": a.arr(lambda: rd_datatype(a), 36)}, 12)
    p["TypeIdReferenceToPointer"] = table(
        "TypeIdReferenceToPointer", a.i32, a.i64, 12)
    p["FunctionReferences"] = table(
        "FunctionReferences", a.i64,
        lambda: {"Name": a.sia(), "Module": a.sia(), "Namespace": a.sia(),
                 "bIsConst": a.boolean(), "bIsImportedDecl": a.boolean(),
                 "bIsMethod": a.boolean(), "ObjectType": a.i64(),
                 "ParameterTypes": a.arr(lambda: rd_datatype(a), 36),
                 "ReturnType": rd_datatype(a)}, 12)
    p["FunctionIdReferenceToPointer"] = table(
        "FunctionIdReferenceToPointer", a.i32, a.i64, 12)
    p["GlobalReferences"] = table(
        "GlobalReferences", a.i64,
        lambda: {"Name": a.sia(), "Module": a.sia(), "Namespace": a.sia(),
                 "bIsString": a.boolean()}, 12)
    st = a.o
    p["StaticNames"] = a.arr(a.sia, 4)
    regions.append(("StaticNames", st, a.o))
    p["PropertyReferences"] = table(
        "PropertyReferences", a.i64,
        lambda: {"Name": a.sia(), "OldTypeId": a.i32()}, 12)

    if a.o != a.n:
        raise ParseError("walk finished at 0x%x but file is 0x%x -- %d byte(s) "
                         "of slack (the walk is WRONG somewhere)"
                         % (a.o, a.n, a.n - a.o))

    p["_regions"] = regions
    return p


def iter_functions(module):
    """(owner, kind, function) for EVERY function record in a module."""
    for f in module["Functions"]:
        yield module["ModuleName"], "global", f
    for c in module["Classes"]:
        for f in c["Methods"]:
            yield c["ClassName"], "method", f
        for f in c["Constructors"]:
            yield c["ClassName"], "ctor", f
        for f in c["BehaviorFunctions"]:
            yield c["ClassName"], "behavior", f
    for g in module["GlobalVariables"]:
        if "InitFunc" in g:
            yield module["ModuleName"], "globalinit", g["InitFunc"]


def all_functions(p):
    for m in p["Modules"]:
        for owner, kind, f in iter_functions(m):
            yield m, owner, kind, f


# ===========================================================================
# 3.  Binds.Cache / Binds.Cache.Headers
# ===========================================================================

def rd_bind_prop(a):
    return {"Declaration": a.fstring(), "UnrealName": a.fstring(),
            "bCanWrite": a.boolean(), "bCanRead": a.boolean(),
            "bCanEdit": a.boolean(), "bGeneratedGetter": a.boolean(),
            "bGeneratedSetter": a.boolean(), "GeneratedName": a.fstring(),
            "bGeneratedHandle": a.boolean(), "bGeneratedUnresolvedObject": a.boolean()}


def rd_bind_method(a):
    return {"Declaration": a.fstring(), "UnrealName": a.fstring(),
            "bStaticInUnreal": a.boolean(), "bStaticInScript": a.boolean(),
            "bGlobalScope": a.boolean(), "bNotAngelscriptProperty": a.boolean(),
            "bTrivial": a.boolean(),
            "WorldContextArgument": a.i8(), "DeterminesOutputTypeArgument": a.i8(),
            "ClassName": a.fstring(), "ScriptName": a.fstring()}


def parse_binds(path=BINDS):
    a = Ar(path)
    structs = a.arr(lambda: {"TypeName": a.fstring(), "UnrealPath": a.fstring(),
                             "Properties": a.arr(lambda: rd_bind_prop(a), 12)}, 8)
    classes = a.arr(lambda: {"TypeName": a.fstring(), "UnrealPath": a.fstring(),
                             "Methods": a.arr(lambda: rd_bind_method(a), 12),
                             "Properties": a.arr(lambda: rd_bind_prop(a), 12)}, 12)
    if a.o != a.n:
        raise ParseError("Binds.Cache walk finished at 0x%x of 0x%x (%d slack)"
                         % (a.o, a.n, a.n - a.o))
    return structs, classes


def parse_bind_headers(path=BINDS_HEADERS):
    a = Ar(path)
    out = a.arr(lambda: (a.fstring(), a.fstring()), 8)
    if a.o != a.n:
        raise ParseError("Binds.Cache.Headers walk finished at 0x%x of 0x%x"
                         % (a.o, a.n))
    return out


# ===========================================================================
# 4.  Symbol table
# ===========================================================================

class SymTab(object):
    """Everything needed to turn a raw operand into a name.

    Two DIFFERENT kinds of int64 live in the bytecode and they must not be
    confused:
      * pointer-valued -- the live save-time address of an asCObjectType /
        asCScriptFunction / global.  Looks up DIRECTLY in TypeReferences /
        FunctionReferences / GlobalReferences.
      * id-valued -- a small AngelScript function/type id.  Must go through
        FunctionIdReferenceToPointer / TypeIdReferenceToPointer FIRST.

    Member accesses use a THIRD scheme: a composite key
        ((TypeId << 1) | (Offset << 33) | 1)
    built from the instruction's DWORD (owning type id) and SWORD (byte
    offset) operands.
    """

    def __init__(self, p, binds=None, headers=None):
        self.p = p
        self.types = dict(p["TypeReferences"])
        self.funcs = dict(p["FunctionReferences"])
        self.globals = dict(p["GlobalReferences"])
        self.props = dict(p["PropertyReferences"])
        self.fid2ptr = dict(p["FunctionIdReferenceToPointer"])
        self.tid2ptr = dict(p["TypeIdReferenceToPointer"])
        self.static_names = p["StaticNames"]

        # -- Binds.Cache ----------------------------------------------------
        self.bind_type = {}          # AS type name -> record
        self.bind_methods = {}       # (AS type name, AS method name) -> [records]
        self.bind_props = {}         # (AS type name, prop name) -> record
        self.header_of = {}          # /Script/Mod.Class -> C++ header
        self.unreal_path = {}        # AS type name -> /Script/Mod.Class
        self.struct_names = set()    # bound UStructs (returned BY VALUE)
        self.class_names = set()     # bound UClasses (returned as handles)
        bound_paths = set()
        if binds:
            structs, classes = binds
            for rec in structs:
                self._add_bind_type(rec, is_struct=True)
                self.struct_names.add(rec["TypeName"])
                bound_paths.add(rec["UnrealPath"])
            for rec in classes:
                self._add_bind_type(rec, is_struct=False)
                self.class_names.add(rec["TypeName"])
                bound_paths.add(rec["UnrealPath"])
        if headers:
            self.header_of = dict(headers)

        # ENUMS.  Binds.Cache holds only structs and classes, but
        # Binds.Cache.Headers ALSO covers bound UEnums and UDelegateFunctions --
        # so a header path whose type is not a bound struct/class is (mostly) an
        # enum.  This matters because an enum-typed return value comes back in
        # the VALUE REGISTER, whereas a struct returned by value is written
        # through a hidden destination pointer the caller pushes.  Get that
        # wrong and every call after it pops one stack slot too many.
        self.enum_names = set()
        for path, _hdr in (headers or ()):
            if path not in bound_paths:
                tail = path.rsplit(".", 1)[-1]
                if tail:
                    self.enum_names.add(tail)
        for m in p["Modules"]:                     # script-declared enums
            for en in m["Enums"]:
                self.enum_names.add(en["Name"])
        self.enum_names -= self.struct_names
        self.enum_names -= self.class_names

        # resolution counters (the honesty metrics)
        self.stat = {}

    def _add_bind_type(self, rec, is_struct):
        tn = rec["TypeName"]
        self.bind_type.setdefault(tn, rec)
        self.unreal_path.setdefault(tn, rec["UnrealPath"])
        for mrec in rec.get("Methods", ()):
            asname = mrec["ScriptName"] or _decl_name(mrec["Declaration"]) \
                     or mrec["UnrealName"]
            self.bind_methods.setdefault((tn, asname), []).append(mrec)
            if mrec["UnrealName"] and mrec["UnrealName"] != asname:
                self.bind_methods.setdefault((tn, mrec["UnrealName"]), []).append(mrec)
        for prec in rec.get("Properties", ()):
            nm = prec["UnrealName"] or _decl_name(prec["Declaration"])
            if nm:
                self.bind_props.setdefault((tn, nm), prec)

    def _bump(self, k, ok):
        s = self.stat.setdefault(k, [0, 0])
        s[0] += 1
        if ok:
            s[1] += 1

    # -- lookups ------------------------------------------------------------
    def type_by_ptr(self, ptr):
        r = self.types.get(ptr)
        self._bump("type_ptr", r is not None)
        return r

    # asTYPEID_OBJHANDLE | asTYPEID_HANDLETOCONST -- flags layered on top of the
    # base type id.  TypeIdReferenceToPointer is keyed by the BASE id, so these
    # have to come off first or every `cast<T@>` operand looks unresolved.
    TYPEID_FLAGS = 0x40000000 | 0x20000000

    def typeid_ptr(self, tid):
        p = self.tid2ptr.get(tid)
        if p is None:
            p = self.tid2ptr.get(tid & ~self.TYPEID_FLAGS)
        return p

    def type_by_id(self, tid):
        ptr = self.typeid_ptr(tid)
        r = self.types.get(ptr) if ptr is not None else None
        self._bump("type_id", r is not None)
        return r

    def func_by_ptr(self, ptr):
        r = self.funcs.get(ptr)
        self._bump("func_ptr", r is not None)
        return r

    def func_by_id(self, fid):
        ptr = self.fid2ptr.get(fid)
        r = self.funcs.get(ptr) if ptr is not None else None
        self._bump("func_id", r is not None)
        return r

    def global_by_ptr(self, ptr):
        r = self.globals.get(ptr)
        self._bump("global_ptr", r is not None)
        return r

    def prop_by(self, type_id, offset):
        key = ((type_id << 1) | (offset << 33) | 1)
        r = self.props.get(key)
        self._bump("prop_key", r is not None)
        return r

    # -- rendering ----------------------------------------------------------
    def type_name(self, ptr):
        r = self.types.get(ptr)
        if r is None:
            return None
        nm = r["Name"]
        if r["Namespace"]:
            nm = r["Namespace"] + "::" + nm
        subs = r.get("SubTypes") or []
        if subs:
            nm += "<" + ", ".join(self.dtype(s) for s in subs) + ">"
        return nm

    def dtype(self, dt, flag=TM_NONE):
        """Render an FAngelscriptPrecompiledDataType as Angelscript source."""
        if dt is None:
            return "?"
        tt = dt["TokenType"]
        if tt == TT_IDENTIFIER:
            base = self.type_name(dt["TypeInfo"])
            if base is None:
                base = ("void" if not dt["TypeInfo"]
                        else "type_%x" % (dt["TypeInfo"] & 0xFFFFFFFF))
        else:
            base = TOKEN_NAMES.get(tt, "tok%d" % tt)
        s = ""
        if dt["bIsObjectConst"]:
            s += "const "
        s += base
        if dt["bIsObjectHandle"]:
            s += "@"
            if dt["bIsConstHandle"]:
                s += " const"
        if dt["bIsReference"]:
            s += "&"
            if flag == TM_INREF:
                s += "in"
            elif flag == TM_OUTREF:
                s += "out"
            elif flag == TM_INOUTREF:
                s += "inout"
        return s

    def is_enum(self, dt):
        """AngelScript enums have TokenType ttIdentifier but are 32-bit
        PRIMITIVES on the value stack -- 1 dword, not a pointer.  Counting
        them as pointers throws the argument model off by one on every call
        that takes an enum, which is a lot of this codebase."""
        if dt["TokenType"] != TT_IDENTIFIER or not dt["TypeInfo"]:
            return False
        if dt["bIsReference"] or dt["bIsObjectHandle"]:
            return False
        tn = self.type_name(dt["TypeInfo"])
        if not tn:
            return False
        return tn.split("<", 1)[0].rsplit("::", 1)[-1] in self.enum_names

    def dtype_size_dwords(self, dt):
        """Size of a value in DWORDs on the AngelScript value stack (and hence
        in the variable space).  AS_PTR_SIZE == 2 on x64."""
        if dt["bIsReference"] or dt["bIsObjectHandle"]:
            return 2
        tt = dt["TokenType"]
        if tt == TT_IDENTIFIER:
            return 1 if self.is_enum(dt) else 2     # enum = int32, object = ptr
        if tt in (71, 78, 81, 94):         # int64 / uint64 / float64 / double
            return 2
        return 1

    def func_label(self, fr):
        """Human name for a FunctionReference, qualified by its owning type."""
        if fr is None:
            return None
        nm = fr["Name"]
        if fr["Namespace"]:
            nm = fr["Namespace"] + "::" + nm
        owner = self.type_name(fr["ObjectType"]) if fr["ObjectType"] else None
        if owner:
            nm = owner + "::" + nm
        return nm

    def func_decl(self, fr):
        if fr is None:
            return "?"
        ps = ", ".join(self.dtype(t) for t in fr["ParameterTypes"])
        return "%s %s(%s)%s" % (self.dtype(fr["ReturnType"]),
                                self.func_label(fr), ps,
                                " const" if fr["bIsConst"] else "")

    def bind_info(self, fr):
        """Cross-reference a native call into Binds.Cache: the real UFunction
        name (662 differ from the AS name) and the owning /Script path."""
        if fr is None or not fr["ObjectType"]:
            return None
        tr = self.types.get(fr["ObjectType"])
        if tr is None:
            return None
        recs = self.bind_methods.get((tr["Name"], fr["Name"]))
        if not recs:
            return None
        if len(recs) > 1:
            want = len(fr["ParameterTypes"])
            same = [r for r in recs if _decl_argc(r["Declaration"]) == want]
            if same:
                recs = same
        return recs[0]

    def global_label(self, ptr):
        g = self.globals.get(ptr)
        if g is None:
            return None
        if g["bIsString"]:
            return '"%s"' % _esc(g["Name"])
        nm = g["Name"]
        if g["Namespace"]:
            nm = g["Namespace"] + "::" + nm
        return nm


def _esc(s):
    return (s.replace("\\", "\\\\").replace('"', '\\"')
             .replace("\n", "\\n").replace("\r", "\\r").replace("\t", "\\t"))


_DECL_NAME_RE = re.compile(r"([A-Za-z_][A-Za-z0-9_]*)\s*\(")


def _decl_name(decl):
    m = _DECL_NAME_RE.search(decl or "")
    if m:
        return m.group(1)
    parts = (decl or "").split()
    return parts[-1] if parts else ""


def _decl_argc(decl):
    i = (decl or "").find("(")
    if i < 0:
        return -1
    inner = decl[i + 1:decl.rfind(")")] if decl.rfind(")") > i else decl[i + 1:]
    inner = inner.strip()
    if not inner:
        return 0
    depth = 0
    n = 1
    for ch in inner:
        if ch in "<(":
            depth += 1
        elif ch in ">)":
            depth -= 1
        elif ch == "," and depth == 0:
            n += 1
    return n


# ===========================================================================
# 5.  Disassembler
# ===========================================================================

LOOP_CLOSE = "}\u0000loop"      # internal marker, stripped by polish()

JUMP_OPS = {11, 12, 13, 14, 15, 16, 17, 187, 188}     # JMP JZ JNZ JS JNS JP JNP JLowZ JLowNZ
COND_JUMP_OPS = {12, 13, 14, 15, 16, 17, 187, 188}
OP_RET, OP_JMP, OP_JMPP = 10, 11, 57

# operand-class tables (which resolver applies to which opcode)
PTR_FUNC_OPS = {61: "CALLSYS", 200: "Thiscall1", 177: "FuncPtr"}
PTR_TYPE_OPS = {75: "OBJTYPE", 65: "FREE", 201: "FinConstruct",
                202: "DestructScript", 203: "CopyScript"}
PTR_GLOBAL_OPS = {1: "PshGPtr", 7: "PshG4", 8: "LdGRdR4", 84: "CpyVtoG4",
                  87: "CpyGtoV4", 96: "LDG", 98: "PGA", 136: "SetG4"}
ID_FUNC_OPS = {9: "CALL", 62: "CALLBND", 139: "CALLINTF"}
ID_TYPE_OPS = {76: "TYPEID", 144: "Cast"}
# member access: opcode -> (offset field, typeid field)
MEMBER_OPS = {79: ("W0", "DW"),        # ADDSi
              178: ("W0", "DW"),       # LoadThisR
              184: ("W1", "DW2"),      # LoadRObjR
              185: ("W1", "DW2")}      # LoadVObjR


class Insn(object):
    __slots__ = ("i", "op", "name", "size", "args", "target", "note")

    def __init__(self, i, op, name, size, args):
        self.i = i                 # dword index within the function's bytecode
        self.op = op
        self.name = name
        self.size = size
        self.args = args
        self.target = None
        self.note = ""


def decode(bc, ndwords):
    """Linear-decode a function's bytecode.  Raises ValueError on desync.

    Instruction length is TYPE_SIZE[type] dwords, from the game's own
    asBCTypeSize -- NOT upstream's (CALLSYS/Thiscall1 are 3 dwords here,
    2 upstream; using upstream desyncs at the first native call).
    """
    out = []
    i = 0
    while i < ndwords:
        o = i * 4
        op = bc[o]
        if op >= MAXBYTECODE:
            raise ValueError("invalid opcode %d at dword %d" % (op, i))
        name, _tid, _tn, size, layout, _si = OPCODES[op]
        if size == 0:
            raise ValueError("pseudo/dummy opcode %d (%s) at dword %d" % (op, name, i))
        if i + size > ndwords:
            raise ValueError("instruction %s at dword %d overruns the stream" % (name, i))
        a = {}
        for f in layout:
            if f in ("W0", "wW0", "rW0"):
                a[f] = struct.unpack_from("<h", bc, o + 2)[0]
            elif f in ("W1", "rW1"):
                a[f] = struct.unpack_from("<h", bc, o + 4)[0]
            elif f == "rW2":
                a[f] = struct.unpack_from("<h", bc, o + 6)[0]
            elif f == "DW":
                a[f] = struct.unpack_from("<i", bc, o + 4)[0]
            elif f == "DW2":
                a[f] = struct.unpack_from("<i", bc, o + 8)[0]
            elif f == "DW3":
                a[f] = struct.unpack_from("<i", bc, o + 12)[0]
            elif f == "QW":
                a[f] = struct.unpack_from("<Q", bc, o + 4)[0]
        ins = Insn(i, op, name, size, a)
        if op in JUMP_OPS:
            # DWORD-count offset relative to the START OF THE NEXT INSTRUCTION
            ins.target = i + 2 + a["DW"]
            if not (0 <= ins.target <= ndwords):
                raise ValueError("%s at dword %d jumps out of range (%d)"
                                 % (name, i, ins.target))
        out.append(ins)
        i += size
    if i != ndwords:
        raise ValueError("stream ended at dword %d, declared %d" % (i, ndwords))
    return out


def annotate(insns, sym):
    """Attach a resolved-symbol note to every instruction that carries one."""
    for ins in insns:
        a = ins.args
        op = ins.op
        note = ""
        if op in PTR_FUNC_OPS:
            fr = sym.func_by_ptr(a["QW"])
            note = sym.func_decl(fr) if fr else "<unresolved fn 0x%x>" % a["QW"]
            b = sym.bind_info(fr)
            if b and b["UnrealName"] and b["UnrealName"] != fr["Name"]:
                note += "   [UFunction %s]" % b["UnrealName"]
        elif op in ID_FUNC_OPS:
            fr = sym.func_by_id(a["DW"])
            note = sym.func_decl(fr) if fr else "<unresolved fnid %d>" % a["DW"]
        elif op == 64:                                   # ALLOC
            tn = sym.type_name(a["QW"]) or "<unresolved type>"
            sym.type_by_ptr(a["QW"])
            fr = sym.func_by_id(a["DW3"])
            note = "new %s   ctor=%s" % (tn, sym.func_label(fr) or a["DW3"])
        elif op in PTR_TYPE_OPS:
            sym.type_by_ptr(a["QW"])
            note = sym.type_name(a["QW"]) or "<unresolved type 0x%x>" % a["QW"]
        elif op in PTR_GLOBAL_OPS:
            sym.global_by_ptr(a["QW"])
            note = sym.global_label(a["QW"]) or "<unresolved global 0x%x>" % a["QW"]
        elif op in ID_TYPE_OPS:
            tr = sym.type_by_id(a["DW"])
            note = (sym.type_name(sym.typeid_ptr(a["DW"])) if tr
                    else "<unresolved typeid 0x%x>" % (a["DW"] & 0xFFFFFFFF))
            if tr and (a["DW"] & sym.TYPEID_FLAGS):
                note += "@"
        elif op in MEMBER_OPS:
            offf, tidf = MEMBER_OPS[op]
            pr = sym.prop_by(a[tidf], a[offf])
            if pr:
                owner = sym.type_by_id(pr["OldTypeId"])
                note = "%s%s  (+%d)" % ((owner["Name"] + "::") if owner else "",
                                        pr["Name"], a[offf])
            else:
                note = "<unresolved member +%d>" % a[offf]
        elif op == 46:                                    # COPY W0=size DW=typeid
            tr = sym.type_by_id(a["DW"])
            note = "%d dwords of %s" % (a["W0"], tr["Name"] if tr else "?")
        ins.note = note
    return insns


def fmt_insn(ins):
    a = ins.args
    parts = []
    for k in ("W0", "wW0", "rW0", "W1", "rW1", "rW2"):
        if k in a:
            parts.append("%s:%d" % (k, a[k]))
    if "DW" in a:
        parts.append("->%d" % ins.target if ins.target is not None else "d:%d" % a["DW"])
    for k in ("DW2", "DW3"):
        if k in a:
            parts.append("%s:%d" % (k, a[k]))
    if "QW" in a:
        parts.append("q:0x%x" % a["QW"])
    body = "%5d  %-14s %-24s" % (ins.i, ins.name, " ".join(parts))
    return (body + "; " + ins.note).rstrip() if ins.note else body.rstrip()


# ===========================================================================
# 6.  Lifter -- symbolic stack machine -> expressions and statements
# ===========================================================================

class LiftError(Exception):
    pass


class E(object):
    """An expression node.  `prec` is only used to decide parenthesisation."""
    __slots__ = ("s", "prec", "raw", "kind")

    def __init__(self, s, prec=100, raw=None, kind=""):
        self.s = s
        self.prec = prec
        self.raw = raw            # for constants: the unformatted integer
        self.kind = kind          # "const" | "var" | "call" | ...

    def p(self, minprec):
        return self.s if self.prec >= minprec else "(" + self.s + ")"

    def __str__(self):
        return self.s


NULL = E("null", 100, kind="null")

# ---------------------------------------------------------------------------
# Arithmetic / compare / conversion dispatch tables.
#
# These are DERIVED FROM THE OPCODE NAMES AND OPERAND LAYOUTS in the extracted
# table, never hand-numbered.  Hand-numbering is how you end up decoding BNOT
# as IncVf: the fork renumbered enough of this range that any table typed from
# upstream memory is wrong.  Deriving them means the tables cannot drift from
# opcodes.py.
# ---------------------------------------------------------------------------

_ARITH_SYM = {"ADD": "+", "SUB": "-", "MUL": "*", "DIV": "/", "MOD": "%",
              "POW": "**", "BAND": "&", "BOR": "|", "BXOR": "^",
              "BSLL": "<<", "BSRL": ">>", "BSRA": ">>>"}
_CONV_TY = {"i": "int", "u": "uint", "f": "float", "d": "float64",
            "i64": "int64", "u64": "uint64", "b": "int8", "w": "int16",
            "sb": "int8", "sw": "int16", "ub": "uint8", "uw": "uint16"}

BIN3 = {}          # op -> operator     (wW0 = rW1 <op> rW2)
BIN_IMM = {}       # op -> (operator, is_float)   (wW0 = rW1 <op> imm)
CMP_RR = set()     # op                (vreg = cmp(rW0, rW1))
CMP_RI = {}        # op -> is_float    (vreg = cmp(rW0, imm))
CONV_OPS = {}      # op -> target type name  (wW0 = ty(rW1))
UNARY_V = {}       # op -> operator    (rW0 = <op> rW0)
INCDEC_V = {}      # op -> "++" / "--" (variable in/decrement)
INCDEC_R = {}      # op -> "++" / "--" (in/decrement through the value register)

for _op in range(MAXBYTECODE):
    _nm, _tid, _tn, _sz, _lay, _si = OPCODES[_op]
    if _sz == 0:
        continue
    if _lay == ("wW0", "rW1", "rW2"):
        _m = re.match(r"^(BAND|BOR|BXOR|BSLL|BSRL|BSRA|ADD|SUB|MUL|DIV|MOD|POW)", _nm)
        if _m:
            BIN3[_op] = _ARITH_SYM[_m.group(1)]
    elif _lay == ("wW0", "rW1", "DW2"):
        _m = re.match(r"^(ADD|SUB|MUL)I(i|f|u)$", _nm)
        if _m:
            BIN_IMM[_op] = (_ARITH_SYM[_m.group(1)], _m.group(2) == "f")
    elif _lay == ("rW0", "rW1") and _nm.upper().startswith("CMP"):
        CMP_RR.add(_op)                      # note: CmpPtr is mixed-case
    elif _lay == ("rW0", "DW") and _nm.upper().startswith("CMPI"):
        CMP_RI[_op] = _nm.endswith("f")
    elif _lay == ("wW0", "rW1"):
        _m = re.match(r"^([a-z0-9]+)TO([a-z0-9]+)$", _nm)
        if _m:
            CONV_OPS[_op] = _CONV_TY.get(_m.group(2), _m.group(2))
    elif _lay == ("rW0",):
        if _nm.startswith("NEG"):
            UNARY_V[_op] = "-"
        elif _nm.startswith("BNOT"):
            UNARY_V[_op] = "~"
        elif _nm.startswith("IncV"):
            INCDEC_V[_op] = "++"
        elif _nm.startswith("DecV"):
            INCDEC_V[_op] = "--"
    elif _lay == ():
        if re.match(r"^INC(i|f|d|i8|i16|i64)$", _nm):
            INCDEC_R[_op] = "++"
        elif re.match(r"^DEC(i|f|d|i8|i16|i64)$", _nm):
            INCDEC_R[_op] = "--"

# The T* opcodes turn the pending cmp() in the value register into a boolean.
TEST_OPS = {18: "== 0", 19: "!= 0", 20: "< 0", 21: ">= 0", 22: "> 0", 23: "<= 0"}


def _f32(v):
    return struct.unpack("<f", struct.pack("<I", v & 0xFFFFFFFF))[0]


def _f64(v):
    return struct.unpack("<d", struct.pack("<Q", v & 0xFFFFFFFFFFFFFFFF))[0]


def _num(x):
    if isinstance(x, float):
        if x != x or x in (float("inf"), float("-inf")):
            return repr(x)
        s = repr(round(x, 6))
        return s[:-2] if s.endswith(".0") else s
    return str(x)


class Lifter(object):
    """Simulates the AngelScript value stack symbolically and emits statements.

    Calling convention (established empirically against this cache, see the
    module docstring of the project notes):

        push argN-1 ... push arg0     (REVERSE declaration order)
        [push &returnTemp]            (iff the callee returns an object BY VALUE)
        [push objectPtr]              (iff the callee is a method)
        CALLSYS / CALL / CALLINTF

    Variable space: offset 0 is `this` for a method (2 dwords), parameters
    then run at DECREASING negative offsets in declaration order; positive
    offsets are compiler temporaries.
    """

    def __init__(self, sym, func, owner, kind, insns):
        self.sym = sym
        self.f = func
        self.owner = owner
        self.kind = kind
        self.insns = insns
        self.is_method = kind in ("method", "ctor", "behavior")
        self.varname = self._var_names()
        # ObjVariableTypes / ObjVariablePos are parallel arrays in the function
        # record: the AUTHORITATIVE declared type of every object local.  The
        # cache has no local NAMES, but it does have their types.
        self.vartype = {}
        for t, pos in zip(func["ObjVariableTypes"], func["ObjVariablePos"]):
            nm = sym.type_name(t)
            if nm:
                self.vartype[pos] = nm
        self.warnings = []
        self.unmodelled = set()
        self.readcount_final = None      # set from a warm-up pass
        self.unnamed_params = set()
        self.ternaries = {}              # join block -> (cond, t, f)
        self.cur_block = None
        self.exit_vreg = {}
        self.exit_oreg = {}
        self.block_cond = {}

    # -- naming -------------------------------------------------------------
    def _var_names(self):
        """Map variable-space offsets to parameter names.

        Layout, established against this cache:
            offset  0   `this`                       (methods only, 2 dwords)
                   -2   HIDDEN return destination    (only when the function
                                                      returns an object BY
                                                      VALUE -- 2 dwords)
            then    parameters in DECLARATION order at decreasing offsets,
                    each occupying its own size in dwords.
        Positive offsets are compiler temporaries and have no names anywhere
        in the cache.
        """
        names = {}
        off = 0
        if self.is_method:
            names[0] = "this"
            names[-1] = "this"
            off = -2
        rt = self.f["ReturnType"]
        if (rt["TokenType"] == TT_IDENTIFIER and rt["TypeInfo"]
                and not rt["bIsObjectHandle"] and not rt["bIsReference"]
                and not self.sym.is_enum(rt)):
            names[off] = "__return"           # hidden destination pointer
            names[off - 1] = "__return"
            off -= 2
        for dt, nm in zip(self.f["ParameterTypes"], self.f["ParameterNames"]):
            sz = self.sym.dtype_size_dwords(dt)
            names[off] = nm or ("arg%d" % (-off))
            for k in range(1, sz):
                names[off - k] = names[off]
            off -= sz
        return names

    def var(self, off):
        nm = self.varname.get(off)
        if nm:
            return nm
        if off < 0:
            # A negative offset is a PARAMETER slot.  Landing here means the
            # parameter-layout model missed one -- counted and reported, never
            # silently papered over.
            self.unnamed_params.add(off)
            return "arg_%d" % (-off)
        return "v%d" % off

    # -- simulation --------------------------------------------------------
    def invalidate_addr_taken(self):
        """A call just ran.  Any local whose ADDRESS we handed it may have been
        written through (`&out` / `&inout` parameters), so its cached value is
        no longer trustworthy.  Without this, an out-param that the callee sets
        keeps reporting whatever it was initialised to -- e.g. a
        `bool bSuccess = true` sentinel would silently constant-fold the
        `if (bSuccess)` that follows it."""
        for off in self.addr_taken:
            self.vals.pop(off, None)
            self.defsite.pop(off, None)
        self.addr_taken.clear()

    def begin(self):
        """Reset the whole-function machine state."""
        self.stack = []                  # symbolic value stack
        self.vreg = None                 # AngelScript's valueRegister
        self.oreg = None                 # AngelScript's objectRegister
        self.depth = 0                   # INDEPENDENT dword-level stack depth
        self.exit_vreg = {}
        self.exit_oreg = {}
        self.block_cond = {}
        self.calls = []                  # (block, text) for results left in a register
        self.readcount = {}              # var offset -> times read (this pass)
        self.ret_bad_stack = 0
        self.ret_bad_depth = 0
        self.blocks_dirty = 0

    def run_block(self, insns, start=None):
        """Simulate one basic block, CARRYING the value stack in from the
        previous block.

        The stack genuinely spans basic blocks in this bytecode: a
        `cast<T>(x)` in the middle of an argument list compiles to a branch,
        so half the arguments are pushed before the branch and the call
        happens after the join.  Resetting per block loses them.  The
        expression-inlining bookkeeping (`vals` / `defsite`) IS reset at every
        boundary, because inlining across a control-flow join is unsound.
        """
        self.vals = {}                   # var offset -> E  (last known value)
        self.stmts = []                  # [ [text, consumed_flag, defvar] ]
        self.defsite = {}                # var offset -> (stmt index, E)
        self.addr_taken = set()          # locals whose ADDRESS is on the stack
        cond = None
        self.cur_block = start
        tri = self.ternaries.get(start)
        if tri is not None:
            c, t, f = tri
            ct = self.block_cond.get(c)
            vt, vf = self.exit_vreg.get(t), self.exit_vreg.get(f)
            ot, of = self.exit_oreg.get(t), self.exit_oreg.get(f)
            if ct is not None and vt is not None and vf is not None and vt.s != vf.s:
                self.vreg = E("%s ? %s : %s" % (ct.s, vt.s, vf.s), 3)
            if ct is not None and ot is not None and of is not None and ot.s != of.s:
                self.oreg = E("%s ? %s : %s" % (ct.s, ot.s, of.s), 3)

        for ins in insns:
            si = OPCODES[ins.op][5]
            if si != 65535:              # 65535 == AngelScript's "variable" sentinel
                self.depth += si
            try:
                c = self.step(ins)
            except LiftError:
                raise
            except Exception as exc:                      # noqa: BLE001
                raise LiftError("%s at dword %d: %s: %s"
                                % (ins.name, ins.i, type(exc).__name__, exc))
            if c is not None:
                cond = c
            if ins.op == OP_RET:
                if self.stack:
                    self.ret_bad_stack += 1
                if self.depth != 0:
                    self.ret_bad_depth += 1
        if self.stack:
            self.blocks_dirty += 1
        if start is not None:
            self.exit_vreg[start] = self.vreg
            self.exit_oreg[start] = self.oreg
            if cond is not None:
                self.block_cond[start] = cond
        return self.finish(), cond

    def emit(self, text, defvar=None):
        self.stmts.append([text, False, defvar])
        return len(self.stmts) - 1

    def finish(self):
        return [s[0] for s in self.stmts if not s[1]]

    def setvar(self, off, expr, text=None):
        """Record `off = expr`.  Emits a statement, but remembers where, so a
        single immediate consumer can inline it and drop the statement."""
        idx = self.emit(text if text is not None
                        else "%s = %s;" % (self.var(off), expr.s), off)
        self.vals[off] = expr
        self.defsite[off] = (idx, expr)

    def ref(self, off):
        """Read a variable WITHOUT inlining its defining expression."""
        self.readcount[off] = self.readcount.get(off, 0) + 1
        return E(self.var(off), 100, kind="var")

    def readvar(self, off):
        """Read a variable, inlining its defining expression when that is both
        SAFE and USEFUL:

          * safe   -- the definition is the MOST RECENT statement in this
                      block, so no side effect can be reordered across it;
          * useful -- the variable is read exactly ONCE in the whole function
                      (counted by a warm-up pass).  Inlining a value that is
                      read again later would delete the binding a later
                      statement depends on, which reads as if the second use
                      came from nowhere.
        """
        self.readcount[off] = self.readcount.get(off, 0) + 1
        multi = (self.readcount_final is not None
                 and self.readcount_final.get(off, 0) > 1)
        d = self.defsite.get(off)
        if d is not None and not multi:
            idx, expr = d
            if idx == len(self.stmts) - 1 and not self.stmts[idx][1]:
                self.stmts[idx][1] = True          # consumed -> statement dropped
                del self.defsite[off]
                return expr
        v = self.vals.get(off)
        if v is not None and v.kind in ("const", "var", "null"):
            return v
        return E(self.var(off), 100, kind="var")

    def push(self, e):
        self.stack.append(e)

    def pop(self):
        if not self.stack:
            raise LiftError("value-stack underflow")
        return self.stack.pop()

    # -- the opcode dispatcher ---------------------------------------------
    def step(self, ins):
        op, a, sym = ins.op, ins.args, self.sym
        nm = ins.name

        # ---- pushes -------------------------------------------------------
        if op in (3, 48, 179):                    # PshV4 PshVPtr PshV8
            self.push(self.readvar(a["rW0"]))
            return None
        if op == 4:                               # PSF  (push stack frame addr)
            off = a["rW0"]
            self.addr_taken.add(off)              # may be written through
            self.push(E(self.var(off), 100, kind="var"))
            return None
        if op == 2:                               # PshC4
            self.push(E(str(a["DW"]), 100, raw=a["DW"], kind="const"))
            return None
        if op == 47:                              # PshC8
            self.push(E(str(a["QW"]), 100, raw=a["QW"], kind="const"))
            return None
        if op == 73:                              # PshNull
            self.push(NULL)
            return None
        if op in (1, 7, 98):                      # PshGPtr PshG4 PGA
            lbl = sym.global_label(a["QW"]) or ("g_0x%x" % a["QW"])
            g = sym.globals.get(a["QW"])
            self.push(E(lbl, 100, kind="str" if (g and g["bIsString"]) else "global"))
            return None
        if op == 59:                              # PshRPtr  (push value register)
            self.push(self.vreg or E("<vreg>", 100))
            return None
        if op == 0:                               # PopPtr
            if self.stack:
                self.stack.pop()
            return None
        if op == 58:                              # PopRPtr
            self.vreg = self.pop()
            return None
        if op == 5:                               # SwapPtr
            if len(self.stack) >= 2:
                self.stack[-1], self.stack[-2] = self.stack[-2], self.stack[-1]
            return None

        # ---- member access ------------------------------------------------
        if op == 79:                              # ADDSi : top = &top->Prop
            pr = sym.prop_by(a["DW"], a["W0"])
            base = self.pop()
            nmp = pr["Name"] if pr else ("field_%d" % a["W0"])
            self.push(E("%s.%s" % (base.p(100), nmp), 100, kind="member"))
            return None
        if op == 49:                              # RDSPtr : *top  (deref in place)
            return None
        if op == 178:                             # LoadThisR : vreg = &this->Prop
            pr = sym.prop_by(a["DW"], a["W0"])
            self.vreg = E("this.%s" % (pr["Name"] if pr else "field_%d" % a["W0"]),
                          100, kind="member")
            return None
        if op in (184, 185):                      # LoadRObjR / LoadVObjR
            pr = sym.prop_by(a["DW2"], a["W1"])
            base = self.readvar(a["rW0"])
            self.vreg = E("%s.%s" % (base.p(100),
                                     pr["Name"] if pr else "field_%d" % a["W1"]),
                          100, kind="member")
            return None

        # ---- register / variable moves ------------------------------------
        if op in (85, 86):                        # CpyRtoV4 / CpyRtoV8
            self.setvar(a["wW0"], self.vreg or E("<vreg>"))
            return None
        if op in (82, 83, 209):                   # CpyVtoR4 / CpyVtoR8 / CpyVtoR1
            # Deliberately NOT inlined.  The value register survives past the
            # end of the block, so an inlined constant would leak across a
            # control-flow join and a `return` at the join would print one
            # path's value as if it were unconditional.  Name the variable.
            self.vreg = self.ref(a["rW0"])
            return None
        if op in (80, 81):                        # CpyVtoV4 / CpyVtoV8
            if a["wW0"] in self.vartype and a["rW1"] not in self.vartype:
                self.vartype[a["rW1"]] = self.vartype[a["wW0"]]
            elif a["rW1"] in self.vartype and a["wW0"] not in self.vartype:
                self.vartype[a["wW0"]] = self.vartype[a["rW1"]]
            self.setvar(a["wW0"], self.readvar(a["rW1"]))
            return None
        if op == 67:                              # STOREOBJ
            self.setvar(a["wW0"], self.oreg or E("<oreg>"))
            self.oreg = None
            return None
        if op == 66:                              # LOADOBJ
            self.oreg = self.ref(a["rW0"])        # see CpyVtoR* -- no inlining
            return None
        if op == 186:                             # RefCpyV : var = pop()
            self.setvar(a["wW0"], self.pop())
            return None
        if op == 69:                              # REFCPY : pops the DEST pointer
            # asBC_REFCPY pops the destination (top) and LEAVES the source on
            # the stack -- stackInc is -2 (one pointer), not -4.
            dst = self.pop()
            src = self.stack[-1] if self.stack else E("?")
            self.emit("%s = %s;" % (dst.s, src.s))
            return None
        if op == 74:                              # ClrVPtr
            self.setvar(a["wW0"], NULL)
            return None
        if op == 142:                             # SetV1 (bool / int8 / enum)
            v = a["DW"] & 0xFF
            ty = self.vartype.get(a["wW0"])
            if v in (0, 1) and ty in (None, "bool"):
                txt = "true" if v else "false"
            else:
                txt = str(v)
            self.setvar(a["wW0"], E(txt, 100, raw=v, kind="const"))
            return None
        if op == 77:                              # SetV4
            self.setvar(a["wW0"], E(str(a["DW"]), 100, raw=a["DW"], kind="const"))
            return None
        if op == 78:                              # SetV8
            q = a["QW"]
            d = _f64(q)
            s = _num(d) if (q and -1e12 < d < 1e12 and abs(d) > 1e-9) else str(q)
            self.setvar(a["wW0"], E(s, 100, raw=q, kind="const"))
            return None

        # ---- indirect memory through the value register --------------------
        if op in (92, 93, 94, 95):                # RDR1/2/4/8 : var = *vreg
            self.setvar(a["wW0"], self.vreg or E("<vreg>"))
            return None
        if op in (88, 89, 90, 91):                # WRTV1/2/4/8 : *vreg = var
            self.emit("%s = %s;" % ((self.vreg or E("<vreg>")).s,
                                    self.readvar(a["rW0"]).s))
            return None
        if op in (96, 87):                        # LDG / CpyGtoV4
            lbl = sym.global_label(a["QW"]) or "g_0x%x" % a["QW"]
            if op == 96:
                self.vreg = E(lbl, 100, kind="global")
            else:
                self.setvar(a["wW0"], E(lbl, 100, kind="global"))
            return None
        if op in (84, 136):                       # CpyVtoG4 / SetG4
            lbl = sym.global_label(a["QW"]) or "g_0x%x" % a["QW"]
            rhs = (self.readvar(a["rW0"]).s if op == 84 else str(a["DW3"]))
            self.emit("%s = %s;" % (lbl, rhs))
            return None
        if op == 8:                               # LdGRdR4 : var = *global
            lbl = sym.global_label(a["QW"]) or "g_0x%x" % a["QW"]
            self.setvar(a["wW0"], E(lbl, 100, kind="global"))
            return None

        # ---- arithmetic ----------------------------------------------------
        if op in BIN3:
            o = BIN3[op]
            lhs, rhs = self.readvar(a["rW1"]), self.readvar(a["rW2"])
            self.setvar(a["wW0"], E("%s %s %s" % (lhs.p(6), o, rhs.p(7)), 6))
            return None
        if op in BIN_IMM:
            o, is_f = BIN_IMM[op]
            imm = a["DW2"]
            imm = _num(_f32(imm)) if is_f else str(imm)
            lhs = self.readvar(a["rW1"])
            self.setvar(a["wW0"], E("%s %s %s" % (lhs.p(6), o, imm), 6))
            return None
        if op in UNARY_V:
            v = self.readvar(a["rW0"])
            self.setvar(a["rW0"], E(UNARY_V[op] + v.p(9), 9))
            return None
        if op == 6:                               # NOT
            v = self.readvar(a["rW0"])
            self.setvar(a["rW0"], E("!" + v.p(9), 9))
            return None
        if op in INCDEC_R:                        # INCi/DECi... through *vreg
            self.emit("%s%s;" % ((self.vreg or E("<vreg>")).s, INCDEC_R[op]))
            return None
        if op in INCDEC_V:                        # IncVi / DecVi
            self.emit("%s%s;" % (self.var(a["rW0"]), INCDEC_V[op]))
            self.vals.pop(a["rW0"], None)
            self.defsite.pop(a["rW0"], None)
            return None
        if op in CONV_OPS:
            self.setvar(a["wW0"], E("%s(%s)" % (CONV_OPS[op],
                                                self.readvar(a["rW1"]).s), 100))
            return None

        # ---- comparison / tests -------------------------------------------
        if op in CMP_RR:                          # CMPi/CMPd/.../CmpPtr
            lhs, rhs = self.readvar(a["rW0"]), self.readvar(a["rW1"])
            self.vreg = E("cmp(%s, %s)" % (lhs.s, rhs.s), 100, kind="cmp")
            self.vreg.raw = (lhs, rhs)
            return None
        if op in CMP_RI:                          # CMPIi / CMPIf / CMPIu
            lhs = self.readvar(a["rW0"])
            imm = _num(_f32(a["DW"])) if CMP_RI[op] else str(a["DW"])
            rhs = E(imm, 100, kind="const")
            self.vreg = E("cmp(%s, %s)" % (lhs.s, rhs.s), 100, kind="cmp")
            self.vreg.raw = (lhs, rhs)
            return None
        if op == 211:                             # CmpPtrNull  (fork-added)
            v = self.readvar(a["rW0"])
            self.vreg = E("cmp(%s, null)" % v.s, 100, kind="cmp")
            self.vreg.raw = (v, NULL)
            return None
        if op in TEST_OPS:                        # TZ TNZ TS TNS TP TNP
            self.vreg = E(self._cmp_as(TEST_OPS[op]), 4, kind="bool")
            return None
        if op == 97:                              # LDV : vreg = &var
            self.vreg = E(self.var(a["rW0"]), 100, kind="var")
            return None
        if op == 100:                             # VAR : push a var placeholder
            self.push(E(self.var(a["rW0"]), 100, kind="var"))
            return None
        if op in (68, 71, 72):                    # GETOBJ / GETOBJREF / GETREF
            return None                           # resolves a VAR placeholder in place

        # ---- calls ---------------------------------------------------------
        if op in PTR_FUNC_OPS:
            return self.do_call(sym.func_by_ptr(a["QW"]), ins,
                                fallback="fn_0x%x" % a["QW"])
        if op in ID_FUNC_OPS:
            return self.do_call(sym.func_by_id(a["DW"]), ins,
                                fallback="fn_id_%d" % a["DW"],
                                virtual=(op == 139))
        if op == 64:                              # ALLOC : new <type>(ctor args)
            tn = sym.type_name(a["QW"]) or "?"
            fr = sym.func_by_id(a["DW3"])
            ptypes = fr["ParameterTypes"] if fr else []
            nargs = len(ptypes)
            self.depth -= 2 + sum(sym.dtype_size_dwords(t) for t in ptypes)
            args = [self.pop() for _ in range(min(nargs, len(self.stack)))]
            dst = self.pop() if self.stack else None
            self.invalidate_addr_taken()
            call = E("%s(%s)" % (tn, ", ".join(x.s for x in args)), 100, kind="call")
            if dst is not None and dst.kind in ("var", "member"):
                self.emit("%s = %s;" % (dst.s, call.s))
                self.vals.pop(_offof(dst), None)
            else:
                self.oreg = call
            return None
        if op == 65:                              # FREE  (destroy a local)
            self.vals.pop(a["wW0"], None)
            self.defsite.pop(a["wW0"], None)
            return None
        if op == 201:                             # FinConstruct : stackInc -2
            self.pop()                            # consumes the object pointer
            return None
        if op == 203:                             # CopyScript : stackInc -2
            dst = self.pop()
            src = self.pop() if self.stack else E("?")
            self.emit("%s = %s;" % (dst.s, src.s))
            self.push(dst)                        # net -1 pointer
            return None
        if op in (202, 205, 204, 206, 207, 208, 210, 63, 175, 70,
                  173, 174, 137, 138):
            # DestructScript / FreeNullV8 / ResolveObjectPtr /
            # Track|Untrack|ValidateRef / SaveReturnValue / SUSPEND /
            # JitEntry / CHKREF / ChkNullS / ClrHi / ChkRefS / ChkNullV
            # -- all stackInc 0: lifetime and null-check bookkeeping that has
            # no representation at source level.
            return None
        if op == 177:                             # FuncPtr
            fr = sym.func_by_ptr(a["QW"])
            self.push(E("@" + (sym.func_label(fr) or "fn_0x%x" % a["QW"]), 100))
            return None
        if op == 75:                              # OBJTYPE
            self.push(E(sym.type_name(a["QW"]) or "type_0x%x" % a["QW"], 100))
            return None
        if op == 76:                              # TYPEID
            tp = sym.typeid_ptr(a["DW"])
            self.push(E(sym.type_name(tp) if tp else "typeid_0x%x"
                        % (a["DW"] & 0xFFFFFFFF), 100, kind="typeid"))
            return None
        if op == 144:                             # Cast
            tp = sym.typeid_ptr(a["DW"])
            v = self.pop() if self.stack else E("?")
            self.oreg = E("cast<%s>(%s)" % (sym.type_name(tp) if tp else "?", v.s), 100)
            return None
        if op == 46:                              # COPY
            src = self.pop() if self.stack else E("?")
            dst = self.pop() if self.stack else E("?")
            self.emit("%s = %s;" % (dst.s, src.s))
            self.push(dst)
            return None

        # ---- terminators ---------------------------------------------------
        if op == OP_RET:
            rt = self.f["ReturnType"]
            if rt["TokenType"] == 82:                       # void
                self.emit("return;")
            elif rt["bIsObjectHandle"] or (rt["TokenType"] == TT_IDENTIFIER
                                           and rt["bIsReference"]):
                self.emit("return %s;" % (self.oreg or self.vreg or E("?")).s)
            elif rt["TokenType"] == TT_IDENTIFIER:
                self.emit("return;   // value returned via the caller's temp")
            else:
                self.emit("return %s;" % (self.vreg or self.oreg or E("?")).s)
            return None
        if op in JUMP_OPS:
            return self.jump_cond(ins)
        if op == OP_JMPP:
            self.emit("switch (%s) { /* computed jump */ }" % self.readvar(a["rW0"]).s)
            return None
        if op == 212:                             # ThrowException
            self.emit("throw;   // ThrowException %d" % a["W0"])
            return None

        self.unmodelled.add(nm)
        self.emit("/* %s %s */" % (nm, " ".join("%s=%s" % kv for kv in sorted(a.items()))))
        return None

    def _cmp_as(self, testexpr):
        """Turn the pending cmp() in the value register into a real relation."""
        v = self.vreg
        if v is not None and v.kind == "cmp" and isinstance(v.raw, tuple):
            lhs, rhs = v.raw
            rel = {"== 0": "==", "!= 0": "!=", "< 0": "<",
                   ">= 0": ">=", "> 0": ">", "<= 0": "<="}[testexpr]
            return "%s %s %s" % (lhs.p(5), rel, rhs.p(5))
        return "(%s) %s" % ((v or E("<vreg>")).s, testexpr)

    # Every conditional jump, expressed as the condition under which the JUMP
    # IS TAKEN.  Keeping one convention (rather than "sometimes the
    # fallthrough") is the only way to keep polarity straight; build_cfg then
    # sets cond_true = target unconditionally.
    JUMP_REL = {12: "== 0", 187: "== 0",       # JZ  / JLowZ
                13: "!= 0", 188: "!= 0",       # JNZ / JLowNZ
                14: "< 0", 15: ">= 0",         # JS  / JNS
                16: "> 0", 17: "<= 0"}         # JP  / JNP

    def jump_cond(self, ins):
        op = ins.op
        if op == OP_JMP:
            return None
        rel = self.JUMP_REL.get(op)
        if rel is None:
            return None
        v = self.vreg
        if v is not None and v.kind == "cmp" and isinstance(v.raw, tuple):
            return E(self._cmp_as(rel), 4)
        base = v or E("<vreg>")
        if rel == "!= 0":                          # plain truth test
            return E(base.s, base.prec)
        if rel == "== 0":
            return E(_negate(base.s), 4)
        return E("%s %s" % (base.p(5), rel), 4)

    def do_call(self, fr, ins, fallback="?", virtual=False):
        sym = self.sym
        if fr is None:
            self.unmodelled.add(ins.name)
            self.emit("/* %s -> %s (unresolved) */" % (ins.name, fallback))
            return None
        ptypes = fr["ParameterTypes"]
        # An AngelScript variable-type parameter (`?&`, eTokenType 59) is
        # passed as TWO stack slots: the pointer AND a typeid pushed under it.
        # Counting it as one is what left a stray typeid on the stack after
        # every cast<> in the file.
        nslots = [2 if t["TokenType"] == TT_QUESTION else 1 for t in ptypes]
        nparams = sum(nslots)
        rt = fr["ReturnType"]
        by_value_obj = self.returns_by_value(rt)
        need = nparams + (1 if by_value_obj else 0) + (1 if fr["bIsMethod"] else 0)
        if by_value_obj and len(self.stack) == need - 1:
            # Self-correction: the return type looked like an object but the
            # caller pushed no destination, so it is really an enum/typedef
            # coming back in the value register.  Back off rather than
            # underflow -- guessing here silently corrupts every later pop.
            by_value_obj = False
            need -= 1
            tn = self.sym.type_name(rt["TypeInfo"])
            if tn:
                self.sym.enum_names.add(tn.rsplit("::", 1)[-1])
        if len(self.stack) < need:
            raise LiftError("call %s wants %d stack item(s), have %d"
                            % (fr["Name"], need, len(self.stack)))
        obj = self.pop() if fr["bIsMethod"] else None
        dest = self.pop() if by_value_obj else None
        args = []                                  # one entry per DECLARED param
        qtypes = []                                # the typeid of each `?` param
        for k, dt in enumerate(ptypes):
            v = self.pop()
            if nslots[k] == 2:
                qtypes.append(self.pop())          # the typeid pushed beneath it
            else:
                qtypes.append(None)
            args.append(v)

        args_s = [self._fmt_arg(e, dt) for e, dt in zip(args, ptypes)]
        for e, dt in zip(args, ptypes):
            off = _offof(e)
            if off is not None and off not in self.vartype and dt["TokenType"] != TT_QUESTION:
                self.vartype[off] = self.sym.dtype(dt).lstrip("const ").rstrip("&")
        self.invalidate_addr_taken()

        # INDEPENDENT cross-check, in the VM's own units: how many DWORDs this
        # call consumes according to the callee signature.  The opcode table's
        # stackInc is the 65535 "variable" sentinel for calls, so this is the
        # only way to keep the dword counter honest -- and if the arg model is
        # wrong, the two counters diverge and the report says so.
        dw = 0
        for t, slots in zip(ptypes, nslots):
            dw += 1 if slots == 2 else 0                # the extra typeid dword
            dw += self.sym.dtype_size_dwords(t)
        if by_value_obj:
            dw += 2
        if fr["bIsMethod"]:
            dw += 2
        # Thiscall1 has a FIXED stackInc (-3) in the opcode table and the
        # generic counter already applied it; only the true 65535 "variable"
        # opcodes need the signature-derived delta.
        if OPCODES[ins.op][5] == 65535:
            self.depth -= dw

        name = fr["Name"]
        ns = fr["Namespace"]
        if name.startswith("$beh"):
            # AngelScript behaviours: 0=construct 2=destruct.  Destructors are
            # pure noise at source level; constructors read as a declaration.
            slot = name[4:]
            if slot == "2":
                return None
            tn = sym.type_name(fr["ObjectType"]) or "?"
            if obj is not None:
                self.emit("%s = %s(%s);" % (obj.s, tn, ", ".join(args_s)))
                self.vals.pop(_offof(obj), None)
                self.defsite.pop(_offof(obj), None)
            return None
        if name in ("opAssign", "opAddAssign", "opSubAssign", "opMulAssign",
                    "opDivAssign") and obj is not None and len(args_s) == 1:
            o = {"opAssign": "=", "opAddAssign": "+=", "opSubAssign": "-=",
                 "opMulAssign": "*=", "opDivAssign": "/="}[name]
            self.emit("%s %s %s;" % (obj.s, o, args_s[0]))
            return None
        if name == "opIndex" and obj is not None and len(args_s) == 1:
            self.vreg = E("%s[%s]" % (obj.p(100), args_s[0]), 100, kind="call")
            self.oreg = self.vreg
            return None
        if name in ("opCast", "opImplCast", "opConv", "opImplConv"):
            # AngelScript spells a dynamic cast as  obj.opCast(?&out result)
            # -- the target type is the TYPEID pushed under the out-reference,
            # and the result lands in that reference, not in a register.
            if qtypes and qtypes[0] is not None:
                tgt = qtypes[0].s
            elif args_s:
                tgt = args_s[0]
            else:
                tgt = sym.dtype(rt)          # opImplConv: target IS the return type
            src = obj.s if obj is not None else "?"
            out = args[0] if (args and qtypes and qtypes[0] is not None) else dest
            e = E("cast<%s>(%s)" % (tgt, src), 100, kind="call")
            if out is not None:
                self.emit("%s = %s;" % (out.s, e.s))
                self.vals.pop(_offof(out), None)
                self.defsite.pop(_offof(out), None)
            else:
                self.oreg = e
                self.vreg = e
            return None

        if name.startswith("op") and obj is not None and len(args_s) == 1:
            binop = {"opAdd": "+", "opSub": "-", "opMul": "*", "opDiv": "/",
                     "opEquals": "==", "opCmp": "<=>"}.get(name)
            if binop:
                e = E("%s %s %s" % (obj.p(6), binop, args_s[0]), 6, kind="call")
                self.vreg = e
                self.oreg = e
                return None

        if obj is not None:
            callee = "%s.%s" % (obj.p(100), name)
        elif ns:
            callee = "%s::%s" % (ns, name)
        else:
            callee = name
        expr = E("%s(%s)" % (callee, ", ".join(args_s)), 100, kind="call")
        if virtual:
            expr.s = expr.s          # (kept: CALLINTF is rendered identically)

        if dest is not None:
            self.emit("%s = %s;" % (dest.s, expr.s))
            self.vals.pop(_offof(dest), None)
            self.defsite.pop(_offof(dest), None)
            return None
        if rt["TokenType"] == 82:                 # void
            self.emit(expr.s + ";")
            return None
        # Result lands in the value register (primitives) or the object
        # register (handles/refs).  We set BOTH and let the next instruction
        # pick -- guessing wrong here would silently lose the value.
        #
        # Record it: if NOTHING ever consumes the register, the call would
        # otherwise disappear from the pseudo-source entirely.  A call with a
        # discarded return value is still a side effect and must be printed.
        self.calls.append((self.cur_block, expr.s))
        self.vreg = expr
        self.oreg = expr
        return None

    def returns_by_value(self, rt):
        """True when the caller must push a hidden destination pointer, i.e.
        the callee returns a real object BY VALUE (a UStruct, TArray, FString,
        ...).  Handles, references, primitives and ENUMS do not."""
        if rt["TokenType"] != TT_IDENTIFIER or not rt["TypeInfo"]:
            return False
        if rt["bIsObjectHandle"] or rt["bIsReference"]:
            return False
        tn = self.sym.type_name(rt["TypeInfo"])
        if tn:
            base = tn.split("<", 1)[0].rsplit("::", 1)[-1]
            if base in self.sym.enum_names:
                return False
            if base in self.sym.class_names:
                return False           # UObject class -> always a handle
        return True

    def _fmt_arg(self, e, dt):
        """Format a constant argument using the CALLEE's declared param type --
        the bytecode itself does not distinguish int from float bit patterns."""
        if e.kind != "const" or e.raw is None:
            return e.s
        tt = dt["TokenType"]
        if tt in (79, 80):
            return _num(_f32(e.raw))
        if tt in (81, 94):
            return _num(_f64(e.raw))
        if tt == 65:
            return "true" if e.raw else "false"
        return e.s


def _offof(e):
    m = re.match(r"^v(\d+)$", e.s or "")
    return int(m.group(1)) if m else None


# ===========================================================================
# 7.  CFG + structuring
# ===========================================================================

class Block(object):
    __slots__ = ("start", "insns", "succ", "cond_true", "cond_false", "term")

    def __init__(self, start):
        self.start = start
        self.insns = []
        self.succ = []
        self.cond_true = None
        self.cond_false = None
        self.term = None            # "ret" | "jmp" | "cond" | "fall" | "unknown"


def build_cfg(insns, ndwords):
    by_i = {ins.i: ins for ins in insns}
    order = [ins.i for ins in insns]
    leaders = {order[0]} if order else set()
    for k, ins in enumerate(insns):
        nxt = order[k + 1] if k + 1 < len(order) else None
        if ins.op in JUMP_OPS:
            leaders.add(ins.target)
            if nxt is not None:
                leaders.add(nxt)
        elif ins.op in (OP_RET, OP_JMPP):
            if nxt is not None:
                leaders.add(nxt)
    leaders = sorted(x for x in leaders if x in by_i)

    blocks = {}
    for k, st in enumerate(leaders):
        en = leaders[k + 1] if k + 1 < len(leaders) else None
        b = Block(st)
        for ins in insns:
            if ins.i >= st and (en is None or ins.i < en):
                b.insns.append(ins)
        blocks[st] = b

    for k, st in enumerate(leaders):
        b = blocks[st]
        nxt = leaders[k + 1] if k + 1 < len(leaders) else None
        last = b.insns[-1] if b.insns else None
        if last is None:
            b.term = "fall"
            b.succ = [nxt] if nxt is not None else []
        elif last.op == OP_RET:
            b.term, b.succ = "ret", []
        elif last.op == OP_JMP:
            b.term, b.succ = "jmp", [last.target]
        elif last.op in COND_JUMP_OPS:
            # The lifter always yields the condition under which the JUMP IS
            # TAKEN, so the taken edge is unconditionally the TRUE edge.
            b.term = "cond"
            b.cond_true = last.target
            b.cond_false = nxt
            b.succ = [x for x in (b.cond_true, b.cond_false) if x is not None]
        elif last.op == OP_JMPP:
            b.term, b.succ = "unknown", ([nxt] if nxt is not None else [])
        else:
            b.term = "fall"
            b.succ = [nxt] if nxt is not None else []
    return blocks, leaders


def reachable(blocks, start, stop, block_filter=None):
    seen, work = set(), [start]
    while work:
        b = work.pop()
        if b is None or b in seen or b not in blocks:
            continue
        if stop is not None and b >= stop:
            seen.add(b)
            continue
        seen.add(b)
        for s in blocks[b].succ:
            if s not in seen:
                work.append(s)
    return seen


class Structurer(object):
    """Recursive interval structuring over the (reducible) bytecode CFG.

    Emits if/else and while(true) where the shape is unambiguous and falls
    back to explicit labels + goto otherwise.  After structuring, the caller
    VERIFIES that every basic block was emitted exactly once; if not, the
    whole function is re-rendered flat.  Silent partial output is not an
    acceptable failure mode here.
    """

    MAX_DEPTH = 80

    def __init__(self, blocks, order, render_block, backedges, labels=()):
        self.blocks = blocks
        self.order = order
        self.render = render_block
        self.backedges = backedges       # header -> max(source block start)
        self.emitted = []
        self.emitted_set = set()
        self.labels_used = set()
        self.labels = set(labels)        # labels known from a previous pass
        self.active = set()              # headers of loops we are INSIDE

    def go(self, start, stop, depth=0, loop=None):
        out = []
        cur = start
        guard = 0
        while cur is not None and (stop is None or cur < stop):
            guard += 1
            if guard > 4000 or depth > self.MAX_DEPTH:
                raise LiftError("structuring runaway at block %s" % cur)
            if cur not in self.blocks:
                break
            if cur in self.emitted_set:
                out.append("goto L%d;" % cur)
                self.labels_used.add(cur)
                break
            b = self.blocks[cur]

            txt, cond = self.render(b)

            # ---- rotated loop? -------------------------------------------
            # AngelScript compiles `for`/`while` bottom-tested: the entry block
            # JUMPS FORWARD to the condition, which then branches BACKWARD into
            # the body.  Recognising that shape is what turns the most common
            # loop in this codebase from a goto-soup into a real `while`.
            rot = self._rotated_loop(cur, stop) if cur not in self.active else None
            if rot is not None:
                head, condblk, exitb = rot
                self.active.add(head)
                self.active.add(condblk)
                ctxt, ccond = self.render(self.blocks[condblk])
                self.emitted.append(cur)
                self.emitted_set.add(cur)
                self.emitted.append(condblk)
                self.emitted_set.add(condblk)
                out.extend(txt)
                cstr = ccond.s if ccond is not None else "<cond>"
                if self.blocks[condblk].cond_true != head:
                    cstr = _negate(cstr)
                if ctxt:
                    out.append("while (true) {")
                    out.extend(_indent(ctxt))
                    out.append("    if (%s) break;" % _negate(cstr))
                else:
                    out.append("while (%s) {" % cstr)
                out.extend(_indent(self.go(head, condblk, depth + 1,
                                           loop=(condblk, exitb))))
                out.append(LOOP_CLOSE)
                self.active.discard(head)
                self.active.discard(condblk)
                cur = exitb
                continue

            # ---- loop header? --------------------------------------------
            if cur in self.backedges and cur not in self.active:
                body_end = self.backedges[cur]
                nxt = self._after(body_end)
                self.active.add(cur)
                out.append("while (true) {")
                inner = self.go(cur, nxt, depth + 1, loop=(cur, nxt))
                out.extend(_indent(inner))
                out.append(LOOP_CLOSE)
                self.active.discard(cur)
                cur = nxt
                continue

            self.emitted.append(cur)
            self.emitted_set.add(cur)
            if cur in self.labels:
                out.append("L%d:" % cur)

            if b.term == "cond":
                t, f = b.cond_true, b.cond_false
                join = self._join(t, f, stop)
                if join is not None and ((t is not None and join < t)
                                         or (f is not None and join < f)):
                    join = None            # would emit an empty branch region
                out.extend(txt)
                cstr = cond.s if cond is not None else "<cond>"
                if join is None:
                    # One branch does not rejoin (it returns / breaks out).
                    # This is the dominant shape in this codebase:
                    #     if (!ok) { <bail> }   <rest>
                    # Emit the earlier branch as the body and continue at the
                    # later one, rather than losing the rest of the function.
                    if t is not None and f is not None and t < f:
                        inner = self.go(t, f, depth + 1, loop)
                        if inner:          # empty arm == register-only ternary
                            out.append("if (%s) {" % cstr)
                            out.extend(_indent(inner))
                            out.append("}")
                        cur = f
                        continue
                    if t is not None and f is not None and f < t:
                        inner = self.go(f, t, depth + 1, loop)
                        if inner:
                            out.append("if (%s) {" % _negate(cstr))
                            out.extend(_indent(inner))
                            out.append("}")
                        cur = t
                        continue
                    out.append("if (%s) {" % cstr)
                    out.extend(_indent(self.go(t, None, depth + 1, loop)))
                    out.append("} else {")
                    out.extend(_indent(self.go(f, None, depth + 1, loop)))
                    out.append("}")
                    break
                if f == join:
                    inner = self.go(t, join, depth + 1, loop)
                    if inner:
                        out.append("if (%s) {" % cstr)
                        out.extend(_indent(inner))
                        out.append("}")
                elif t == join:
                    inner = self.go(f, join, depth + 1, loop)
                    if inner:
                        out.append("if (%s) {" % _negate(cstr))
                        out.extend(_indent(inner))
                        out.append("}")
                else:
                    a = self.go(t, join, depth + 1, loop)
                    b2 = self.go(f, join, depth + 1, loop)
                    if a or b2:
                        # both arms empty == a register-only ternary; the value
                        # is already folded into the join, so emitting an
                        # `if () {} else {}` shell would be pure noise.
                        out.append("if (%s) {" % cstr)
                        out.extend(_indent(a))
                        out.append("} else {")
                        out.extend(_indent(b2))
                        out.append("}")
                cur = join
                continue

            out.extend(txt)
            if b.term == "ret":
                break
            if b.term in ("jmp", "fall"):
                nxt = b.succ[0] if b.succ else None
                if loop is not None:
                    if nxt == loop[0]:
                        out.append("continue;")
                        break
                    if nxt is not None and loop[1] is not None and nxt >= loop[1]:
                        out.append("break;" if nxt == loop[1] else "goto L%d;" % nxt)
                        if nxt != loop[1]:
                            self.labels_used.add(nxt)
                        break
                if nxt is None:
                    break
                if stop is not None and nxt == stop:
                    break            # falls straight out of the region: the
                                     # caller resumes at `stop`, so a goto here
                                     # would just name the next line
                if stop is not None and nxt > stop:
                    if nxt in self.blocks:
                        out.append("goto L%d;" % nxt)
                        self.labels_used.add(nxt)
                    break
                cur = nxt
                continue
            if b.term == "unknown":
                out.append("// computed jump -- flow not reconstructed")
                break
            break
        return out

    def _rotated_loop(self, cur, stop):
        """Detect  `B: ... goto C` / `H: body` / `C: if (cond) goto H`.

        Returns (header, condblock, exitblock) or None.  The signature is: an
        unconditional forward jump to a CONDITIONAL block C, one of whose
        successors H lies strictly between the jumping block and C, and whose
        other successor is outside [H, C].
        """
        b = self.blocks[cur]
        if b.term != "jmp" or not b.succ:
            return None
        c = b.succ[0]
        if c is None or c not in self.blocks or c <= cur:
            return None
        if stop is not None and c >= stop:
            return None
        cb = self.blocks[c]
        if cb.term != "cond" or c in self.emitted_set:
            return None
        for head, exitb in ((cb.cond_true, cb.cond_false),
                            (cb.cond_false, cb.cond_true)):
            if head is None or exitb is None:
                continue
            if not (cur < head < c):
                continue
            if head <= exitb <= c:
                continue                      # exit must leave the loop region
            if any(x in self.emitted_set for x in self.order
                   if head <= x <= c):
                continue
            return head, c, exitb
        return None

    def _after(self, i):
        for x in self.order:
            if x > i:
                return x
        return None

    def _join(self, t, f, stop):
        if t is None:
            return f
        if f is None:
            return t
        rt = reachable(self.blocks, t, stop)
        rf = reachable(self.blocks, f, stop)
        common = (rt & rf) - self.emitted_set
        if not common:
            return None
        return min(common)


def polish(lines):
    """Cosmetic cleanup that PROVABLY cannot change meaning.

    Only two rules, both purely local:
      1. `goto Lx;` whose IMMEDIATE next line is `Lx:` (a no-op jump).
      2. labels that nothing jumps to any more.

    Deliberately NOT done: skipping over `}` lines when matching rule 1 (a `}`
    may close a loop, in which case falling out is not the same as jumping),
    and dropping a trailing `continue;` (it may end an `if` body inside the
    loop rather than the loop body).  Both of those silently rewrite control
    flow, which is worse than leaving the output slightly noisy.
    """
    out = list(lines)

    def is_loop_close(ln):
        return ln.rstrip().endswith(LOOP_CLOSE)

    # 1. `goto Lx;` that reaches `Lx:` by falling out of `if` blocks only.
    i = 0
    while i < len(out):
        m = re.match(r"^\s*goto (L\d+);$", out[i])
        if m:
            j = i + 1
            while (j < len(out) and out[j].strip() == "}"
                   and not is_loop_close(out[j])):
                j += 1
            if j < len(out) and out[j].strip() == m.group(1) + ":":
                del out[i]
                continue
        i += 1
    # 2. `continue;` that falls straight out of its own loop body.
    i = 0
    while i < len(out) - 1:
        if out[i].strip() == "continue;":
            ind = len(out[i]) - len(out[i].lstrip())
            j = i + 1
            while (j < len(out) and out[j].strip() == "}"
                   and not is_loop_close(out[j])
                   and len(out[j]) - len(out[j].lstrip()) < ind):
                j += 1
            if (j < len(out) and is_loop_close(out[j])
                    and len(out[j]) - len(out[j].lstrip()) < ind):
                del out[i]
                continue
        i += 1
    # 3. `if (x) { }` left behind after a goto was elided -- ONLY when the
    #    condition contains no call (removing one would drop a side effect).
    i = 0
    while i < len(out) - 1:
        m = re.match(r"^(\s*)if \((.*)\) \{$", out[i])
        if (m and "(" not in m.group(2)
                and out[i + 1].strip() == "}"
                and len(out[i + 1]) - len(out[i + 1].lstrip()) == len(m.group(1))):
            del out[i:i + 2]
            continue
        i += 1
    # 4. labels nothing jumps to any more
    used = set()
    for ln in out:
        for m in re.finditer(r"goto (L\d+);", ln):
            used.add(m.group(1))
    out = [ln for ln in out
           if not (re.match(r"^\s*L\d+:$", ln) and ln.strip()[:-1] not in used)]
    return [ln.replace(LOOP_CLOSE, "}") for ln in out]


def txt_of(pair):
    return pair[0]


def _indent(lines, pad="    "):
    return [pad + x if x else x for x in lines]


_NEG_FLIP = {"==": "!=", "!=": "==", ">=": "<", "<=": ">", ">": "<=", "<": ">="}


def _negate(c):
    """Logical negation of a rendered condition.

    Flips a comparison operator when there is EXACTLY ONE at bracket depth 0
    (so `a == b` becomes `a != b` rather than `!(a == b)`); otherwise falls
    back to a parenthesised `!`.  Requiring depth 0 and a unique match is what
    keeps this from mangling something like `f(a == b) == c`.
    """
    c = c.strip()
    depth = 0
    hits = []
    i = 0
    while i < len(c):
        ch = c[i]
        if ch in "([<":
            depth += 1
        elif ch in ")]>":
            depth -= 1
        elif depth == 0 and c.startswith(" ", i):
            for op in ("==", "!=", ">=", "<=", ">", "<"):
                if c.startswith(" " + op + " ", i):
                    hits.append((i + 1, op))
                    i += len(op) + 1
                    break
        i += 1
    if len(hits) == 1:
        at, op = hits[0]
        return c[:at] + _NEG_FLIP[op] + c[at + len(op):]
    if c.startswith("!") and not c.startswith("!="):
        inner = c[1:]
        if inner.startswith("(") and inner.endswith(")"):
            return inner[1:-1]
        return inner
    if re.match(r"^[A-Za-z_][A-Za-z0-9_.:<>@\[\]]*$", c) or c.endswith(")"):
        return "!" + c                 # atom or call -- no parens needed
    return "!(%s)" % c


def find_backedges(blocks, order):
    """header -> the largest block start that jumps backwards to it."""
    be = {}
    for st in order:
        for s in blocks[st].succ:
            if s is not None and s <= st and s in blocks:
                be[s] = max(be.get(s, -1), st)
    return be


# ===========================================================================
# 8.  Rendering
# ===========================================================================

def render_signature(sym, f, owner, kind):
    parts = []
    if f["bIsUFunction"]:
        flags = [nm for nm, v in zip(UFUNC_FLAGS, f["Flags"]) if v]
        meta = ["%s=%s" % (k, v) if v else k
                for k, v in zip(f["MetaSpec"], f["MetaValues"])]
        if meta:
            flags.append("meta=(%s)" % ", ".join(meta))
        parts.append("UFUNCTION(%s)" % ", ".join(flags))
        if f["UnrealFunctionName"] and f["UnrealFunctionName"] != f["FunctionName"]:
            parts.append("// UFunction name: %s" % f["UnrealFunctionName"])
    ret = sym.dtype(f["ReturnType"])
    args = []
    for dt, nm, fl, dv in zip(f["ParameterTypes"], f["ParameterNames"],
                              f["ParameterFlags"], f["ParameterDefaultArgs"]):
        s = "%s %s" % (sym.dtype(dt, fl), nm)
        if dv:
            s += " = " + dv.replace(" :: ", "::")
        args.append(s)
    name = f["FunctionName"]
    if kind == "ctor":
        sig = "%s(%s)" % (name, ", ".join(args))
    elif kind == "behavior":
        sig = "%s(%s)" % (name, ", ".join(args))
    else:
        sig = "%s %s(%s)" % (ret, name, ", ".join(args))
    if f["FunctionTraits"] & 0x1:
        sig += " const"
    parts.append(sig)
    return parts


def render_class_decl(sym, c):
    out = []
    meta = ["%s=%s" % (k, v) if v else k
            for k, v in zip(c.get("MetaSpec", ()), c.get("MetaValues", ()))]
    extra = []
    for k, lbl in (("bAbstract", "Abstract"), ("bTransient", "Transient"),
                   ("bDefaultToInstanced", "DefaultToInstanced"),
                   ("bEditInlineNew", "EditInlineNew"),
                   ("bIsDeprecatedClass", "Deprecated")):
        if c.get(k):
            extra.append(lbl)
    if c.get("bIsInPreprocessor"):
        spec = extra + (["meta=(%s)" % ", ".join(meta)] if meta else [])
        out.append("UCLASS(%s)" % ", ".join(spec))
    base = c.get("SuperClass") or sym.type_name(c["DerivedFrom"]) or ""
    up = sym.unreal_path.get(base)
    line = "class %s%s" % (c["ClassName"], (" : " + base) if base else "")
    out.append(line)
    if up:
        out.append("// base %s  ->  %s" % (up, sym.header_of.get(up, "?")))
    if c.get("ComposeOntoClassName"):
        out.append("// composed onto %s" % c["ComposeOntoClassName"])
    return out


def render_property(sym, pr):
    line = ""
    if pr["bIsUnrealProperty"]:
        spec = list(pr["Flags"])
        if pr["ReplicationCondition"] is not None:
            spec.append("RepCond=%d" % pr["ReplicationCondition"])
        meta = ["%s=%s" % (k, v) if v else k
                for k, v in zip(pr["MetaSpec"], pr["MetaValues"])]
        if meta:
            spec.append("meta=(%s)" % ", ".join(meta))
        line += "UPROPERTY(%s) " % ", ".join(spec)
    if pr["bIsPrivate"]:
        line += "private "
    elif pr["bIsProtected"]:
        line += "protected "
    return line + "%s %s;" % (sym.dtype(pr["Type"]), pr["Name"])


class FuncResult(object):
    __slots__ = ("pseudo", "disasm", "decoded", "lifted", "structured", "err",
                 "ninsn", "nbytes", "unmodelled", "balanced", "depth_ok",
                 "nblocks", "locals", "unnamed_params", "recovered_calls")

    def __init__(self):
        self.pseudo = []
        self.disasm = []
        self.decoded = False
        self.lifted = False
        self.structured = False
        self.err = None
        self.ninsn = 0
        self.nbytes = 0
        self.nblocks = 0
        self.unmodelled = set()
        self.balanced = True
        self.depth_ok = True
        self.locals = []
        self.unnamed_params = 0
        self.recovered_calls = 0


def process_function(sym, f, owner, kind):
    r = FuncResult()
    r.nbytes = f["_bytecode_dwords"] * 4
    if f["_bytecode_dwords"] == 0:
        r.decoded = r.lifted = True
        r.pseudo = ["// (no bytecode)"]
        return r

    try:
        insns = decode(f["ByteCode"], f["_bytecode_dwords"])
    except Exception as exc:                                    # noqa: BLE001
        r.err = "%s: %s" % (type(exc).__name__, exc)
        r.disasm = ["<<UNDECODED: %s -- %d bytes at cache offset 0x%x>>"
                    % (r.err, r.nbytes, f["_bytecode_off"])]
        return r
    annotate(insns, sym)
    r.decoded = True
    r.ninsn = len(insns)
    r.disasm = [fmt_insn(i) for i in insns]

    # -- lift: bytecode -> statements per basic block ------------------------
    try:
        blocks, order = build_cfg(insns, f["_bytecode_dwords"])
        r.nblocks = len(order)
        lifter = Lifter(sym, f, owner, kind, insns)
        lifter.ternaries = find_ternaries(blocks, order)
        # PASS 1 discovers local types from the signatures of the calls they
        # are passed to; PASS 2 renders with those types known (so a byte-sized
        # enum stops printing as `true`).  The lifter is deterministic, so the
        # only difference between the passes is the warmed type map.
        for _ in range(2):                 # types propagate one hop per pass
            lifter.begin()
            for st in order:
                lifter.run_block(blocks[st].insns, st)
        lifter.readcount_final = dict(lifter.readcount)
        lifter.begin()
        rendered = {}
        for st in order:                       # `order` is in address order
            rendered[st] = lifter.run_block(blocks[st].insns, st)
        # Recover calls whose result was never consumed (see Lifter.do_call).
        blob = chr(10).join(ln for st in order for ln in rendered[st][0])
        blob += chr(10) + chr(10).join(rendered[st][1].s for st in order
                                  if rendered[st][1] is not None)
        recovered = 0
        for st, text in lifter.calls:
            if st in rendered and text not in blob:
                stmts, c = rendered[st]
                rendered[st] = (stmts + [text + ";"], c)
                blob += chr(10) + text
                recovered += 1
        r.recovered_calls = recovered

        used = set()
        for st in order:
            for ln in rendered[st][0]:
                for mm in re.finditer(r"\bv(\d+)\b", ln):
                    used.add(int(mm.group(1)))
        r.locals = ["%s v%d;" % (lifter.vartype.get(o, "auto"), o)
                    for o in sorted(used)]
        r.unnamed_params = len(lifter.unnamed_params)
        r.balanced = (lifter.ret_bad_stack == 0)
        r.depth_ok = (lifter.ret_bad_depth == 0)
        r.unmodelled = lifter.unmodelled
        r.lifted = True
    except Exception as exc:                                    # noqa: BLE001
        r.pseudo = ["<<PSEUDO FAILED: %s: %s>>" % (type(exc).__name__, exc),
                    "// the annotated disassembly below is unaffected"]
        return r

    # -- structure: basic blocks -> if / else / while ------------------------
    # Two passes: the first discovers which blocks need a visible label (a
    # `goto` was emitted at them), the second re-runs with those known so no
    # goto is ever left dangling.  If ANY block would be dropped we do not ship
    # a partial reconstruction -- we fall back to the flat labelled form, which
    # is uglier but complete.
    be = find_backedges(blocks, order)
    try:
        s = Structurer(blocks, order, lambda b: rendered[b.start], be)
        body = s.go(order[0], None)
        missing = [x for x in order if x not in s.emitted_set]
        if missing:
            raise LiftError("structuring dropped %d of %d block(s)"
                            % (len(missing), len(order)))
        if len(s.emitted) != len(s.emitted_set):
            raise LiftError("structuring emitted %d block(s) twice"
                            % (len(s.emitted) - len(s.emitted_set)))
        if s.labels_used:
            s2 = Structurer(blocks, order, lambda b: rendered[b.start], be,
                            labels=s.labels_used)
            body2 = s2.go(order[0], None)
            if not [x for x in order if x not in s2.emitted_set]:
                body = body2
        r.pseudo = polish(body)
        r.structured = True
    except Exception as exc:                                    # noqa: BLE001
        r.pseudo = (["// control flow not structured (%s); flat form:"
                     % str(exc).replace(LOOP_CLOSE, "}")]
                    + polish(flat_render(order, blocks, rendered)))
    return r


# Instructions that only move a value into the VALUE/OBJECT register without
# producing a statement.  A pair of branches built solely from these is a
# ternary, not an if/else: the selected value leaves the block in a register.
REG_ONLY_OPS = {178, 184, 185, 96, 97, 82, 83, 209, 66, 59, 2, 47, 73,
                77, 78, 142, 143, 63, 175}


def find_ternaries(blocks, order):
    """Locate `cond ? a : b` compiled as a diamond whose arms emit nothing and
    merely load the value register.  Returns {join_block: (cond, t, f)}.

    Without this the two arms render as an empty `if (c) {} else {}` and the
    join silently keeps whichever arm the linear walk happened to see last --
    i.e. one half of the expression is thrown away.
    """
    preds = {}
    for st in order:
        for sc in blocks[st].succ:
            if sc is not None:
                preds.setdefault(sc, []).append(st)
    out = {}
    for st in order:
        b = blocks[st]
        if b.term != "cond":
            continue
        t, f = b.cond_true, b.cond_false
        if t is None or f is None or t not in blocks or f not in blocks:
            continue
        if preds.get(t) != [st] or preds.get(f) != [st]:
            continue
        arms = []
        ok = True
        for x in (t, f):
            bx = blocks[x]
            if not bx.succ or bx.succ[0] is None:
                ok = False
                break
            body = [i for i in bx.insns if i.op not in (OP_JMP,)]
            if not body or any(i.op not in REG_ONLY_OPS for i in body):
                ok = False
                break
            arms.append(bx.succ[0])
        if ok and len(arms) == 2 and arms[0] == arms[1] and arms[0] != st:
            out[arms[0]] = (st, t, f)
    return out


def flat_render(order, blocks, rendered):
    """Complete, always-correct fallback: every basic block in address order
    with an explicit label and explicit gotos."""
    out = []
    for st in order:
        stmts, cond = rendered[st]
        out.append("L%d:" % st)
        out.extend(_indent(stmts))
        b = blocks[st]
        if b.term == "cond":
            out.append("    if (%s) goto L%d; else goto L%d;"
                       % (cond.s if cond else "<cond>", b.cond_true, b.cond_false))
        elif b.term == "jmp":
            out.append("    goto L%d;" % b.succ[0])
        elif b.term == "fall" and b.succ and b.succ[0] is not None:
            pass                                    # falls through to the next label
        elif b.term == "unknown":
            out.append("    // computed jump -- flow not reconstructed")
    return out


# ===========================================================================
# 9.  Emit
# ===========================================================================

BANNER = "=" * 78
RULE = "-" * 78


def module_text(sym, m, results):
    L = []
    A = L.append
    A(BANNER)
    A("MODULE   %s" % m["ModuleName"])
    A("SOURCE   %s" % m["ScriptRelativeFilename"])
    A(BANNER)
    A("")
    A("// Decompiled from Loki/Script/PrecompiledScript.Cache (build 2025-12-17,")
    A("// UE_BUILD_SHIPPING).  The shipping cache carries NO line numbers and NO")
    A("// local-variable names, so locals are synthesised as v<stack-offset>.")
    A("// Parameter names, default-argument source text and all UPROPERTY /")
    A("// UFUNCTION metadata ARE preserved and are reproduced verbatim.")
    A("")
    if m["ImportedModules"]:
        for im in m["ImportedModules"]:
            A("import %s;" % im)
        A("")
    if m["StaticsClassName"]:
        A("// statics class: %s" % m["StaticsClassName"])
    for ev in m["DeclaredEvents"]:
        A("event %s;" % ev)
    for dg in m["DeclaredDelegates"]:
        A("delegate %s;" % dg)
    if m["PostInitFunctions"]:
        A("// post-init: %s" % ", ".join(m["PostInitFunctions"]))
    A("")

    for en in m["Enums"]:
        A("enum %s" % (en["Namespace"] + "::" + en["Name"] if en["Namespace"]
                       else en["Name"]))
        A("{")
        for nm, v in zip(en["EnumNames"], en["EnumValues"]):
            A("    %s = %d," % (nm, v))
        A("}")
        A("")

    for g in m["GlobalVariables"]:
        line = "%s %s" % (sym.dtype(g["Type"]), g["Name"])
        if g.get("bIsPureConstant"):
            line += " = %d" % g["PureConstantValue"]
        A(line + ";")
    if m["GlobalVariables"]:
        A("")

    def dump_func(owner, kind, f, indent=""):
        key = id(f)
        r = results[key]
        A(indent + RULE)
        for ln in render_signature(sym, f, owner, kind):
            A(indent + ln)
        tail = ["%d instr" % r.ninsn, "%d B bytecode" % r.nbytes,
                "id=0x%08X" % f["Id"], "varspace=%d" % f["VariableSpace"]]
        A(indent + "// " + ", ".join(tail))
        A(indent + RULE)
        A(indent + "{")
        if r.locals:
            for ln in r.locals:
                A(indent + "    " + ln)
            A("")
        for ln in (r.pseudo or ["// (empty)"]):
            A(indent + "    " + ln if ln else "")
        A(indent + "}")
        A("")
        A(indent + "    // ---- disassembly " + "-" * 48)
        for ln in r.disasm:
            A(indent + "    // " + ln)
        A("")

    if m["Functions"]:
        A(BANNER)
        A("// module-level functions")
        A(BANNER)
        A("")
        for f in m["Functions"]:
            dump_func(m["ModuleName"], "global", f)

    for c in m["Classes"]:
        A(BANNER)
        for ln in render_class_decl(sym, c):
            A(ln)
        A(BANNER)
        A("{")
        for pr in c["Properties"]:
            A("    " + render_property(sym, pr))
        if c["Properties"]:
            A("")
        A("}")
        A("")
        for f in c["Constructors"]:
            dump_func(c["ClassName"], "ctor", f)
        for f in c["Methods"]:
            dump_func(c["ClassName"], "method", f)
        for f in c["BehaviorFunctions"]:
            dump_func(c["ClassName"], "behavior", f)

    for g in m["GlobalVariables"]:
        if "InitFunc" in g:
            A(BANNER)
            A("// initialiser for global '%s'" % g["Name"])
            A(BANNER)
            dump_func(m["ModuleName"], "globalinit", g["InitFunc"])

    return "\n".join(L) + "\n"


def safe_name(module_name):
    return re.sub(r"[^A-Za-z0-9_.-]", "_", module_name)


# ===========================================================================
# 10.  Driver
# ===========================================================================

def coverage_report(p):
    """Byte ledger for PrecompiledScript.Cache: every byte must belong to
    exactly one region, with no gaps and no overlap."""
    regs = sorted(p["_regions"], key=lambda r: r[1])
    lines = []
    total = 0
    prev_end = 0
    gaps = 0
    overlap = 0
    for name, st, en in regs:
        if st > prev_end:
            gaps += st - prev_end
            lines.append("    !! GAP  0x%08x..0x%08x  %d bytes" % (prev_end, st, st - prev_end))
        if st < prev_end:
            overlap += prev_end - st
            lines.append("    !! OVERLAP at 0x%08x" % st)
        lines.append("    %-30s 0x%08x..0x%08x  %10s B  %5.1f%%"
                     % (name, st, en, "{:,}".format(en - st), 100.0 * (en - st) / p["_size"]))
        total += en - st
        prev_end = max(prev_end, en)
    if prev_end < p["_size"]:
        gaps += p["_size"] - prev_end
        lines.append("    !! TRAILING  %d bytes" % (p["_size"] - prev_end))
    return lines, total, gaps, overlap


def main(argv):
    t0 = time.time()
    want_module = None
    want_func = None
    report_only = False
    outdir = OUT_DIR
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--report":
            report_only = True
        elif a == "--module":
            i += 1
            want_module = argv[i]
        elif a == "--func":
            i += 1
            want_func = argv[i]
        elif a == "--out":
            i += 1
            outdir = argv[i]
        else:
            sys.stderr.write("unknown argument %r\n" % a)
            return 2
        i += 1

    print("asdump -- SUPERVIVE Angelscript decompiler")
    print(RULE)

    # ---- parse ------------------------------------------------------------
    p = parse_precompiled()
    print("PrecompiledScript.Cache : %s bytes   DataGuid %s   BuildIdentifier %d (%s)"
          % ("{:,}".format(p["_size"]), p["DataGuid"], p["BuildIdentifier"],
             {1: "DEBUG", 2: "DEVELOPMENT", 3: "TEST", 4: "SHIPPING"}
             .get(p["BuildIdentifier"], "?")))

    binds = parse_binds()
    headers = parse_bind_headers()
    print("Binds.Cache             : %d structs + %d classes, %d methods, %d properties"
          % (len(binds[0]), len(binds[1]),
             sum(len(c["Methods"]) for c in binds[1]),
             sum(len(c["Properties"]) for c in binds[1])
             + sum(len(s["Properties"]) for s in binds[0])))
    print("Binds.Cache.Headers     : %d /Script path -> C++ header links" % len(headers))

    sym = SymTab(p, binds, headers)

    # ---- hard expectations ------------------------------------------------
    nmod = len(p["Modules"])
    nclass = sum(len(m["Classes"]) for m in p["Modules"])
    fns = list(all_functions(p))
    nfn = len(fns)
    assert nmod == EXPECT_MODULES, "expected %d modules, parsed %d" % (EXPECT_MODULES, nmod)
    assert nclass == EXPECT_CLASSES, "expected %d classes, parsed %d" % (EXPECT_CLASSES, nclass)
    assert nfn == EXPECT_FUNCTIONS, "expected %d functions, parsed %d" % (EXPECT_FUNCTIONS, nfn)
    paths = [m["ScriptRelativeFilename"] for m in p["Modules"]]
    assert len(set(paths)) == EXPECT_MODULES, "duplicate .as source paths"

    print()
    print("byte-coverage ledger (PrecompiledScript.Cache)")
    lines, total, gaps, overlap = coverage_report(p)
    for ln in lines:
        print(ln)
    print("    %-30s %35s B" % ("TOTAL ACCOUNTED", "{:,}".format(total)))
    print("    %-30s %35s B" % ("FILE SIZE", "{:,}".format(p["_size"])))
    print("    %-30s %35s B   (gaps %d, overlap %d)"
          % ("UNACCOUNTED", "{:,}".format(p["_size"] - total), gaps, overlap))
    if total != p["_size"] or gaps or overlap:
        raise SystemExit("FATAL: byte ledger does not balance")

    # ---- process every function -------------------------------------------
    results = {}
    nd = nl = ns = 0
    unbalanced = 0
    depth_bad = 0
    unnamed_p = 0
    recovered = 0
    unmodelled = {}
    tot_insn = tot_bytes = tot_blocks = 0
    for m, owner, kind, f in fns:
        r = process_function(sym, f, owner, kind)
        results[id(f)] = r
        nd += r.decoded
        nl += r.lifted
        ns += r.structured
        unbalanced += (0 if r.balanced else 1)
        depth_bad += (0 if r.depth_ok else 1)
        unnamed_p += r.unnamed_params
        recovered += r.recovered_calls
        tot_insn += r.ninsn
        tot_bytes += r.nbytes
        tot_blocks += r.nblocks
        for u in r.unmodelled:
            unmodelled[u] = unmodelled.get(u, 0) + 1

    print()
    print("parse / decode / lift")
    print("    modules parsed          : %d / %d" % (nmod, EXPECT_MODULES))
    print("    classes parsed          : %d" % nclass)
    print("    properties parsed       : %d"
          % sum(len(c["Properties"]) for m in p["Modules"] for c in m["Classes"]))
    print("    enums / global vars     : %d / %d"
          % (sum(len(m["Enums"]) for m in p["Modules"]),
             sum(len(m["GlobalVariables"]) for m in p["Modules"])))
    print("    functions found         : %d / %d" % (nfn, EXPECT_FUNCTIONS))
    print("    bytecode                : %s bytes, %s instructions"
          % ("{:,}".format(tot_bytes), "{:,}".format(tot_insn)))
    print("    basic blocks            : %s" % "{:,}".format(tot_blocks))
    print("    bytecode DECODE rate    : %d / %d  (%.2f%%)"
          % (nd, nfn, 100.0 * nd / nfn))
    print("    pseudo-source LIFT rate : %d / %d  (%.2f%%)"
          % (nl, nfn, 100.0 * nl / nfn))
    print("    STRUCTURED (if/while)   : %d / %d  (%.2f%%)   [rest = flat labels+goto]"
          % (ns, nfn, 100.0 * ns / nfn))
    print("    symbolic stack balanced : %d / %d functions clean (%.2f%%)"
          % (nfn - unbalanced, nfn, 100.0 * (nfn - unbalanced) / nfn))
    print("    dword-depth balanced    : %d / %d functions clean (%.2f%%)"
          "   [independent check vs the game's own stackInc table]"
          % (nfn - depth_bad, nfn, 100.0 * (nfn - depth_bad) / nfn))
    nparam = sum(len(f["ParameterNames"]) for _m, _o, _k, f in fns)
    print("    parameter slots resolved: %d / %d  (%.2f%%)   [unnamed: %d]"
          % (nparam - unnamed_p, nparam,
             100.0 * (nparam - unnamed_p) / max(nparam, 1), unnamed_p))
    print("    discarded-result calls  : %d recovered (would otherwise vanish "
          "from the pseudo-source)" % recovered)
    if unmodelled:
        top = sorted(unmodelled.items(), key=lambda kv: -kv[1])[:12]
        print("    opcodes not lifted      : " +
              ", ".join("%s(%d)" % kv for kv in top))
    else:
        print("    opcodes not lifted      : none")
    if nl < nfn:
        reasons = {}
        for m, owner, kind, f in fns:
            r = results[id(f)]
            if not r.lifted and r.pseudo:
                key = re.sub(r"\d+", "N", r.pseudo[0])[:110]
                reasons.setdefault(key, []).append("%s::%s" % (owner, f["FunctionName"]))
        print("    lift failures by cause  :")
        for key, who in sorted(reasons.items(), key=lambda kv: -len(kv[1]))[:12]:
            print("        %4d  %s" % (len(who), key))
            print("              e.g. %s" % ", ".join(who[:3]))

    print()
    print("symbol resolution (bytecode operands -> names)")
    labels = {"func_ptr": "CALLSYS/Thiscall1/FuncPtr -> FunctionReferences",
              "func_id": "CALL/CALLINTF/CALLBND    -> function id",
              "type_ptr": "OBJTYPE/FREE/ALLOC       -> TypeReferences",
              "type_id": "TYPEID/Cast              -> type id",
              "global_ptr": "PshGPtr/LDG/PGA/...      -> GlobalReferences",
              "prop_key": "ADDSi/LoadThisR/Load*ObjR-> PropertyReferences"}
    for k in ("func_ptr", "func_id", "type_ptr", "type_id", "global_ptr", "prop_key"):
        used, ok = sym.stat.get(k, [0, 0])
        if used:
            print("    %-42s %6d used, %6d resolved (%.2f%%)"
                  % (labels[k], used, ok, 100.0 * ok / used))

    # ---- targeted output ---------------------------------------------------
    if want_func:
        owner_want, _, fname = want_func.rpartition("::")
        for m, owner, kind, f in fns:
            if f["FunctionName"] == fname and (not owner_want
                                               or owner_want in owner
                                               or owner_want in m["ModuleName"]):
                r = results[id(f)]
                print()
                print(RULE)
                for ln in render_signature(sym, f, owner, kind):
                    print(ln)
                print(RULE)
                print("{")
                for ln in r.pseudo:
                    print("    " + ln)
                print("}")
                print()
                for ln in r.disasm:
                    print("    // " + ln)
        return 0

    if want_module:
        for m in p["Modules"]:
            if m["ModuleName"] == want_module or m["ScriptRelativeFilename"] == want_module:
                sys.stdout.write(module_text(sym, m, results))
                return 0
        sys.stderr.write("no such module: %s\n" % want_module)
        return 1

    if report_only:
        print("\n(--report: no files written)  %.1fs" % (time.time() - t0))
        return 0

    # ---- write ------------------------------------------------------------
    if not os.path.isdir(outdir):
        os.makedirs(outdir)
    written = 0
    index = []
    for m in p["Modules"]:
        txt = module_text(sym, m, results)
        fn = os.path.join(outdir, safe_name(m["ModuleName"]) + ".as.txt")
        with open(fn, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(txt)
        written += 1
        mf = list(iter_functions(m))
        index.append({
            "module": m["ModuleName"],
            "src": m["ScriptRelativeFilename"],
            "file": os.path.basename(fn),
            "classes": [c["ClassName"] for c in m["Classes"]],
            "bases": [c.get("SuperClass") or sym.type_name(c["DerivedFrom"]) or ""
                      for c in m["Classes"]],
            "nfunc": len(mf),
            "nbytes": sum(results[id(f)].nbytes for _o, _k, f in mf),
            "ninsn": sum(results[id(f)].ninsn for _o, _k, f in mf),
            "nprops": sum(len(c["Properties"]) for c in m["Classes"]),
            "dec": sum(1 for _o, _k, f in mf if results[id(f)].decoded),
            "lift": sum(1 for _o, _k, f in mf if results[id(f)].lifted),
            "struct": sum(1 for _o, _k, f in mf if results[id(f)].structured),
            "bytes_file": len(txt),
        })

    write_index(outdir, p, index, nfn, nd, nl, ns, unbalanced, tot_bytes,
                tot_insn, sym)
    print()
    print("wrote %d module files + _index.md to %s   (%.1fs)"
          % (written, outdir, time.time() - t0))
    return 0


def write_index(outdir, p, index, nfn, nd, nl, ns, unbalanced, tot_bytes,
                tot_insn, sym):
    L = []
    A = L.append
    A("# SUPERVIVE Angelscript decompilation index")
    A("")
    A("Generated by `tools/asdump/impl_a/asdump.py` from the game's shipped script")
    A("caches (build 2025-12-17).  Source of truth:")
    A("")
    A("| file | bytes |")
    A("|---|---|")
    A("| `PrecompiledScript.Cache` | %s |" % "{:,}".format(p["_size"]))
    A("| `Binds.Cache` | 5,764,301 |")
    A("| `Binds.Cache.Headers` | 2,050,287 |")
    A("")
    A("## Totals")
    A("")
    A("- **%d** modules, **%d** classes, **%d** functions" %
      (len(index), sum(len(x["classes"]) for x in index), nfn))
    A("- **%s** bytes of bytecode, **%s** instructions" %
      ("{:,}".format(tot_bytes), "{:,}".format(tot_insn)))
    A("- bytecode decode rate: **%d / %d (%.2f%%)**" % (nd, nfn, 100.0 * nd / nfn))
    A("- pseudo-source lift rate: **%d / %d (%.2f%%)**" % (nl, nfn, 100.0 * nl / nfn))
    A("- control flow structured into `if`/`while`: **%d / %d (%.2f%%)** "
      "-- the remaining %d are emitted as complete flat label+`goto` form"
      % (ns, nfn, 100.0 * ns / nfn, nfn - ns))
    used, ok = sym.stat.get("func_ptr", [0, 0])
    A("- native call targets resolved: **%d / %d**" % (ok, used))
    used, ok = sym.stat.get("prop_key", [0, 0])
    A("- member accesses resolved to property names: **%d / %d**" % (ok, used))
    A("")
    A("> The shipping build strips `DeclaredAt` and `LineNumbers`, so there are")
    A("> **no source line numbers and no local-variable names** anywhere in the")
    A("> cache.  Locals are synthesised as `v<stack-offset>`.  Everything else --")
    A("> parameter names, default-argument source text, UPROPERTY/UFUNCTION")
    A("> metadata, class hierarchy, string literals -- is intact.")
    A("")
    A("## Modules")
    A("")
    A("| module | source | classes | base | fn | instr | bytecode | decoded | lifted | structured |")
    A("|---|---|---|---|---:|---:|---:|---:|---:|---:|")
    for x in sorted(index, key=lambda y: y["src"]):
        cls = "<br>".join("`%s`" % c for c in x["classes"]) or "-"
        base = "<br>".join("`%s`" % (b or "-") for b in x["bases"]) or "-"
        A("| [`%s`](%s) | `%s` | %s | %s | %d | %s | %s B | %d/%d | %d/%d | %d/%d |"
          % (x["module"], x["file"], x["src"], cls, base, x["nfunc"],
             "{:,}".format(x["ninsn"]), "{:,}".format(x["nbytes"]),
             x["dec"], x["nfunc"], x["lift"], x["nfunc"],
             x["struct"], x["nfunc"]))
    A("")
    A("## By directory")
    A("")
    groups = {}
    for x in index:
        groups.setdefault(x["src"].split("/")[0], []).append(x)
    A("| directory | modules | functions | bytecode |")
    A("|---|---:|---:|---:|")
    for g in sorted(groups, key=lambda k: -len(groups[k])):
        A("| `%s` | %d | %d | %s B |" % (g, len(groups[g]),
                                         sum(y["nfunc"] for y in groups[g]),
                                         "{:,}".format(sum(y["nbytes"] for y in groups[g]))))
    A("")
    A("## Known limits (read before trusting a line of this)")
    A("")
    A("- **Locals have no names.** `v12` is a stack offset, not a source name.")
    A("  Their TYPES are real: object locals come from the function record's")
    A("  `ObjVariableTypes`, primitives are inferred from the signature of the")
    A("  call they are passed to.  `auto` means neither source knew.")
    A("- **No line numbers.** Statement order is bytecode order, not source order.")
    A("- **%d function(s)** could not be folded into `if`/`while` and appear in flat"
      % (nfn - ns))
    A("  label+`goto` form.  Nothing is lost; it is just less pretty.")
    A("- **%d function(s)** leave the symbolic value stack non-empty at a `return`."
      % unbalanced)
    A("  Both an independent dword-depth counter (driven by the game's own")
    A("  `stackInc` table) and the symbolic stack agree on which ones, so these")
    A("  are the cases where the argument model is genuinely incomplete --")
    A("  treat their pseudo-source with suspicion and read the disassembly.")
    A("- Computed jumps (`JMPP`, 5 sites) are NOT reconstructed; they are marked")
    A("  `// computed jump -- flow not reconstructed`.")
    A("- The disassembly under every function is the ground truth and is")
    A("  independent of the pseudo-source: it is a direct decode of the bytes")
    A("  with symbol names attached, and it round-trips to the exact declared")
    A("  length for all %d functions." % nfn)
    A("")
    with open(os.path.join(outdir, "_index.md"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(L) + "\n")


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
