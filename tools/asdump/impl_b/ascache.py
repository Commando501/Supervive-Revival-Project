#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""PrecompiledScript.Cache reader.

The file is a raw FMemoryWriter dump of UE-Angelscript's FAngelscriptPrecompiledData:
no magic, no chunk table, no offsets, no alignment. It can only be read by replaying
the exact operator<< order. Everything is little-endian and byte-packed at whatever
offset the cursor happens to be at.

Two string types are in play and they are NOT interchangeable:
  FString           -- len INCLUDES the trailing NUL. Used for exactly one field in
                       the whole file: the Modules TMap key.
  FStringInArchive  -- len EXCLUDES the NUL, len+1 bytes follow; len==0 writes
                       NOTHING (not even the NUL). Used for every other string.

Every C++ bool is a 4-byte legacy UBOOL (this fork predates Hazelight's bitpacking
commit 661ba173). That makes bools a superb desync canary and we assert on all of
them.

FAIL-LOUD POLICY: every anomaly raises CacheError carrying the byte offset. This
module never guesses and never skips.
"""
import struct

__all__ = ["CacheError", "PrecompiledCache", "load"]


class CacheError(Exception):
    pass


# ---------------------------------------------------------------------------
# eTokenType ordinals (as_tokendef.h). Only the ones that can appear as a
# DataType.TokenType for a primitive (TypeInfo == 0) matter.
# ---------------------------------------------------------------------------
TOKEN_PRIMITIVE = {
    5:  None,        # ttIdentifier -- an object type; name comes from TypeInfo
    59: "?",         # ttQuestion   -- the variable-argument type
    65: "bool",
    68: "int",
    69: "int8",
    70: "int16",
    71: "int64",
    75: "uint",
    76: "uint8",
    77: "uint16",
    78: "uint64",
    79: "float",
    80: "float32",     # verified against Binds.Cache declaration strings
    81: "float64",     # verified against Binds.Cache declaration strings
    82: "void",
    94: "double",
    110: "auto",
}


class Reader(object):
    """Sequential FArchive reader. Never seeks backwards during a walk."""

    def __init__(self, data, path=""):
        self.d = data
        self.o = 0
        self.n = len(data)
        self.path = path

    # -- failure ------------------------------------------------------------
    def fail(self, msg, off=None):
        off = self.o if off is None else off
        ctx = self.d[max(0, off - 16):off + 32]
        raise CacheError("%s at 0x%x (%d/%d)\n  context: %s" %
                         (msg, off, off, self.n, ctx.hex()))

    def need(self, k):
        if self.o + k > self.n:
            self.fail("read of %d bytes overruns EOF" % k)

    # -- primitives ---------------------------------------------------------
    def u32(self):
        self.need(4)
        v = struct.unpack_from("<I", self.d, self.o)[0]
        self.o += 4
        return v

    def i32(self):
        self.need(4)
        v = struct.unpack_from("<i", self.d, self.o)[0]
        self.o += 4
        return v

    def i64(self):
        self.need(8)
        v = struct.unpack_from("<q", self.d, self.o)[0]
        self.o += 8
        return v

    def u64(self):
        self.need(8)
        v = struct.unpack_from("<Q", self.d, self.o)[0]
        self.o += 8
        return v

    def boolean(self):
        """C++ bool == 4-byte legacy UBOOL. THE canary: must be exactly 0 or 1."""
        at = self.o
        v = self.u32()
        if v > 1:
            self.fail("bool desync: UBOOL read %d (0x%x), expected 0 or 1" % (v, v), at)
        return v == 1

    def raw(self, k):
        self.need(k)
        v = self.d[self.o:self.o + k]
        self.o += k
        return v

    # -- strings ------------------------------------------------------------
    def fstring(self):
        """UE FString. len INCLUDES the NUL. Negative len == UTF-16LE."""
        at = self.o
        n = self.i32()
        if n == 0:
            return ""
        if n < 0:
            k = -n * 2
            self.need(k)
            b = self.raw(k)
            if b[-2:] != b"\x00\x00":
                self.fail("FString(UTF16) not NUL-terminated", at)
            return b[:-2].decode("utf-16-le")
        if n > 0x100000:
            self.fail("FString length %d is implausible" % n, at)
        b = self.raw(n)
        if b[-1] != 0:
            self.fail("FString len=%d not NUL-terminated (got %r)" % (n, b[-4:]), at)
        return b[:-1].decode("latin1")

    def sia(self):
        """FStringInArchive. len EXCLUDES the NUL; len+1 bytes follow.
        len == 0 writes NOTHING -- not even the NUL. That asymmetry is the whole
        source of the 'inconsistent NUL handling' folklore; it is not heuristic."""
        at = self.o
        n = self.i32()
        if n == 0:
            return ""
        if n < 0 or n > 0x100000:
            self.fail("FStringInArchive length %d is implausible" % n, at)
        b = self.raw(n + 1)
        if b[-1] != 0:
            self.fail("FStringInArchive len=%d not NUL-terminated (got %r)"
                      % (n, b[-4:]), at)
        return b[:-1].decode("latin1")

    # -- containers ---------------------------------------------------------
    def count(self, min_elem_bytes=0, what="array"):
        at = self.o
        n = self.i32()
        if n < 0:
            self.fail("%s has negative count %d" % (what, n), at)
        if min_elem_bytes and self.o + n * min_elem_bytes > self.n:
            self.fail("%s count %d needs >= %d bytes, only %d remain"
                      % (what, n, n * min_elem_bytes, self.n - self.o), at)
        return n

    def arr(self, fn, min_elem_bytes=0, what="array"):
        return [fn() for _ in range(self.count(min_elem_bytes, what))]

    def arr_i32(self):
        n = self.count(4, "TArray<int32>")
        self.need(4 * n)
        v = list(struct.unpack_from("<%di" % n, self.d, self.o)) if n else []
        self.o += 4 * n
        return v

    def arr_i64(self):
        n = self.count(8, "TArray<int64>")
        self.need(8 * n)
        v = list(struct.unpack_from("<%dq" % n, self.d, self.o)) if n else []
        self.o += 8 * n
        return v


# ---------------------------------------------------------------------------
# record types
# ---------------------------------------------------------------------------
class DataType(object):
    """FAngelscriptPrecompiledDataType -- 36 bytes flat (6 UBOOLs + int64 + int32)."""
    __slots__ = ("is_ref", "obj_const", "handle", "const_handle", "is_auto",
                 "if_handle_then_const", "type_info", "token")

    def __init__(self, r):
        self.is_ref = r.boolean()
        self.obj_const = r.boolean()
        self.handle = r.boolean()
        self.const_handle = r.boolean()
        self.is_auto = r.boolean()
        self.if_handle_then_const = r.boolean()
        self.type_info = r.i64()
        self.token = r.i32()


class Function(object):
    __slots__ = ("off", "size", "name", "namespace", "ret", "param_types",
                 "param_names", "param_flags", "param_defaults", "traits",
                 "bc_off", "bc_dwords", "bytecode", "var_space", "obj_var_types",
                 "obj_var_pos", "obj_vars_on_heap", "vi_pos", "vi_off", "vi_opt",
                 "stack_needed", "id", "declared_at", "line_numbers",
                 "is_ufunction", "unreal_name", "meta", "uflags", "owner", "kind")

    def __init__(self, r):
        self.off = r.o
        self.name = r.sia()
        self.namespace = r.sia()
        self.ret = DataType(r)
        self.param_types = r.arr(lambda: DataType(r), 36, "ParameterTypes")
        self.param_names = r.arr(r.sia, 4, "ParameterNames")
        self.param_flags = r.arr_i32()
        self.param_defaults = r.arr(r.sia, 4, "ParameterDefaultArgs")
        self.traits = r.i32()
        n = r.count(4, "ByteCode")
        self.bc_off = r.o
        self.bc_dwords = n
        self.bytecode = r.raw(4 * n)
        bcrefs = r.arr_i32()
        if bcrefs:
            # declared in the struct but never written by InitFrom(); a non-empty
            # one means our field order is wrong, not that the data is exotic.
            r.fail("ByteCodeReferences is non-empty (%d) -- field order desync"
                   % len(bcrefs), self.off)
        self.var_space = r.i32()
        self.obj_var_types = r.arr_i64()
        self.obj_var_pos = r.arr_i32()
        self.obj_vars_on_heap = r.i32()
        self.vi_pos = r.arr_i32()
        self.vi_off = r.arr_i32()
        self.vi_opt = r.arr_i32()
        self.stack_needed = r.i32()
        self.id = r.u32()
        self.declared_at = r.i32()
        self.line_numbers = r.arr_i32()
        self.is_ufunction = r.boolean()
        self.unreal_name = ""
        self.meta = []
        self.uflags = {}
        if self.is_ufunction:
            self.unreal_name = r.sia()
            spec = r.arr(r.sia, 4, "MetaSpec")
            vals = r.arr(r.sia, 4, "MetaValues")
            if len(spec) != len(vals):
                r.fail("UFUNCTION MetaSpec/MetaValues length mismatch (%d vs %d)"
                       % (len(spec), len(vals)), self.off)
            self.meta = list(zip(spec, vals))
            self.uflags = dict(zip(UFUNC_FLAGS, [r.boolean() for _ in UFUNC_FLAGS]))
        # structural invariants -- these are free and catch a desync instantly
        if not (len(self.param_types) == len(self.param_names)
                == len(self.param_flags) == len(self.param_defaults)):
            r.fail("parameter arrays not parallel: types=%d names=%d flags=%d defs=%d"
                   % (len(self.param_types), len(self.param_names),
                      len(self.param_flags), len(self.param_defaults)), self.off)
        if len(self.obj_var_types) != len(self.obj_var_pos):
            r.fail("ObjVariableTypes/ObjVariablePos length mismatch", self.off)
        if not (len(self.vi_pos) == len(self.vi_off) == len(self.vi_opt)):
            r.fail("VariableInfo arrays not parallel", self.off)
        self.size = r.o - self.off
        self.owner = None
        self.kind = "global"


UFUNC_FLAGS = ("BlueprintCallable", "BlueprintOverride", "BlueprintEvent",
               "BlueprintPure", "NetFunction", "NetMulticast", "NetClient",
               "NetServer", "NetValidate", "Unreliable", "BlueprintAuthorityOnly",
               "Exec", "CanOverrideEvent", "DevFunction", "Static", "ConstMethod",
               "ThreadSafe", "NoOp")

UPROP_FLAGS = ("BlueprintReadable", "BlueprintWritable", "EditConst",
               "EditableOnDefaults", "EditableOnInstance", "InstancedReference",
               "PersistentInstance", "AdvancedDisplay", "Transient", "Replicated",
               "SkipReplication", "SkipSerialization", "SaveGame")


class Property(object):
    __slots__ = ("name", "type", "is_private", "is_protected", "is_uproperty",
                 "meta", "flags", "rep_condition", "rep_notify")

    def __init__(self, r):
        at = r.o
        self.name = r.sia()
        self.type = DataType(r)
        self.is_private = r.boolean()
        self.is_protected = r.boolean()
        self.is_uproperty = r.boolean()
        self.meta = []
        self.flags = {}
        self.rep_condition = None
        self.rep_notify = False
        if self.is_uproperty:
            spec = r.arr(r.sia, 4, "MetaSpec")
            vals = r.arr(r.sia, 4, "MetaValues")
            if len(spec) != len(vals):
                r.fail("UPROPERTY MetaSpec/MetaValues mismatch", at)
            self.meta = list(zip(spec, vals))
            vals13 = [r.boolean() for _ in UPROP_FLAGS]
            self.flags = dict(zip(UPROP_FLAGS, vals13))
            if self.flags["Replicated"]:
                self.rep_condition = r.i32()
                self.rep_notify = r.boolean()
            self.flags["Config"] = r.boolean()
            self.flags["Interp"] = r.boolean()
            self.flags["AssetRegistrySearchable"] = r.boolean()


class Enum(object):
    __slots__ = ("name", "namespace", "names", "values")

    def __init__(self, r):
        at = r.o
        self.name = r.sia()
        self.namespace = r.sia()
        self.names = r.arr(r.sia, 4, "EnumNames")
        self.values = r.arr_i32()
        if len(self.names) != len(self.values):
            r.fail("enum name/value arrays not parallel", at)


class GlobalVar(object):
    __slots__ = ("name", "namespace", "type", "default_init", "pure_constant",
                 "value", "has_init", "init_func")

    def __init__(self, r):
        self.name = r.sia()
        self.namespace = r.sia()
        self.type = DataType(r)
        self.default_init = r.boolean()
        self.pure_constant = False
        self.value = None
        self.has_init = False
        self.init_func = None
        if not self.default_init:
            self.pure_constant = r.boolean()
            if self.pure_constant:
                self.value = r.u64()
            else:
                self.has_init = r.boolean()
                self.init_func = Function(r)


class Klass(object):
    __slots__ = ("off", "size", "name", "namespace", "flags", "properties",
                 "methods", "method_table", "derived_from", "shadow_type",
                 "constructors", "factory_refs", "behavior_refs",
                 "behavior_functions", "behavior_types", "in_preprocessor",
                 "super_class", "code_super_class", "cflags", "config_name",
                 "static_class_global", "placeable", "meta", "compose_onto")

    def __init__(self, r):
        self.off = r.o
        self.name = r.sia()
        self.namespace = r.sia()
        self.flags = r.i32()
        self.properties = r.arr(lambda: Property(r), 4, "Properties")
        self.methods = r.arr(lambda: Function(r), 4, "Methods")
        self.method_table = r.arr_i32()
        self.derived_from = r.i64()
        self.shadow_type = r.i64()
        self.constructors = r.arr(lambda: Function(r), 4, "Constructors")
        self.factory_refs = r.arr_i64()
        self.behavior_refs = r.arr_i64()
        self.behavior_functions = r.arr(lambda: Function(r), 4, "BehaviorFunctions")
        self.behavior_types = r.arr_i32()
        if len(self.behavior_refs) not in (0, 7):
            r.fail("BehaviorRefs has %d entries, expected 0 or 7"
                   % len(self.behavior_refs), self.off)
        if len(self.behavior_functions) != len(self.behavior_types):
            r.fail("BehaviorFunctions/BehaviorFunctionTypes mismatch", self.off)
        self.in_preprocessor = r.boolean()
        self.super_class = ""
        self.code_super_class = ""
        self.cflags = {}
        self.config_name = ""
        self.static_class_global = ""
        self.placeable = False
        self.meta = []
        self.compose_onto = ""
        if self.in_preprocessor:
            self.super_class = r.sia()
            self.code_super_class = r.sia()
            for k in ("SuperIsCodeClass", "Abstract", "Transient", "HideDropdown",
                      "DefaultToInstanced", "EditInlineNew", "DeprecatedClass"):
                self.cflags[k] = r.boolean()
            self.config_name = r.sia()
            self.static_class_global = r.sia()
            self.placeable = r.boolean()
            spec = r.arr(r.sia, 4, "MetaSpec")
            vals = r.arr(r.sia, 4, "MetaValues")
            if len(spec) != len(vals):
                r.fail("UCLASS MetaSpec/MetaValues mismatch", self.off)
            self.meta = list(zip(spec, vals))
            self.compose_onto = r.sia()
        self.size = r.o - self.off
        for f in self.methods:
            f.owner, f.kind = self, "method"
        for f in self.constructors:
            f.owner, f.kind = self, "ctor"
        for f in self.behavior_functions:
            f.owner, f.kind = self, "behavior"

    def all_functions(self):
        return self.methods + self.constructors + self.behavior_functions


class Module(object):
    __slots__ = ("off", "size", "key", "name", "functions", "classes", "enums",
                 "globals", "function_imports", "code_hash", "imported_modules",
                 "statics_class", "declared_events", "declared_delegates",
                 "source_path", "post_init")

    def __init__(self, r, key):
        self.off = r.o
        self.key = key
        self.name = r.sia()
        self.functions = r.arr(lambda: Function(r), 4, "Functions")
        self.classes = r.arr(lambda: Klass(r), 4, "Classes")
        self.enums = r.arr(lambda: Enum(r), 4, "Enums")
        self.globals = r.arr(lambda: GlobalVar(r), 4, "GlobalVariables")
        self.function_imports = r.arr(lambda: _func_import(r), 4, "FunctionImports")
        self.code_hash = r.i64()
        self.imported_modules = r.arr(r.sia, 4, "ImportedModules")
        self.statics_class = r.sia()
        self.declared_events = r.arr(r.sia, 4, "DeclaredEvents")
        self.declared_delegates = r.arr(r.sia, 4, "DeclaredDelegates")
        self.source_path = r.sia()
        self.post_init = r.arr(r.sia, 4, "PostInitFunctions")
        self.size = r.o - self.off
        if self.name != key:
            # the TMap key and the struct's own ModuleName have matched on every
            # record in this file; a mismatch is a strong desync signal.
            r.fail("module key %r != ModuleName %r" % (key, self.name), self.off)

    def all_functions(self):
        out = list(self.functions)
        for c in self.classes:
            out.extend(c.all_functions())
        for g in self.globals:
            if g.init_func is not None:
                out.append(g.init_func)
        return out


def _func_import(r):
    frm = r.sia()
    sig = {"name": r.sia(), "namespace": r.sia(),
           "param_types": r.arr(lambda: DataType(r), 36, "ParameterTypes"),
           "param_flags": r.arr_i32(),
           "param_defaults": r.arr(r.sia, 4, "ParameterDefaultArgs")}
    sig["ret"] = DataType(r)
    return (frm, sig)


# ---------------------------------------------------------------------------
# trailer reference tables
# ---------------------------------------------------------------------------
class TypeRef(object):
    __slots__ = ("name", "module", "namespace", "subtypes")

    def __init__(self, r):
        self.name = r.sia()
        self.module = r.sia()
        self.namespace = r.sia()
        self.subtypes = r.arr(lambda: DataType(r), 36, "SubTypes")


class FuncRef(object):
    __slots__ = ("name", "module", "namespace", "is_const", "is_imported_decl",
                 "is_method", "object_type", "param_types", "ret")

    def __init__(self, r):
        self.name = r.sia()
        self.module = r.sia()
        self.namespace = r.sia()
        self.is_const = r.boolean()
        self.is_imported_decl = r.boolean()
        self.is_method = r.boolean()
        self.object_type = r.i64()
        self.param_types = r.arr(lambda: DataType(r), 36, "ParameterTypes")
        self.ret = DataType(r)


class GlobalRef(object):
    __slots__ = ("name", "module", "namespace", "is_string")

    def __init__(self, r):
        self.name = r.sia()
        self.module = r.sia()
        self.namespace = r.sia()
        self.is_string = r.boolean()


class PropRef(object):
    __slots__ = ("name", "type_id")

    def __init__(self, r):
        self.name = r.sia()
        self.type_id = r.i32()


# ---------------------------------------------------------------------------
class PrecompiledCache(object):
    def __init__(self, path):
        with open(path, "rb") as fh:
            data = fh.read()
        self.path = path
        self.size = len(data)
        r = Reader(data, path)
        self.regions = []          # [(start, end, label)]

        def mark(label, start):
            self.regions.append((start, r.o, label))

        s = r.o
        self.guid = tuple(r.u32() for _ in range(4))
        self.build_identifier = r.i32()
        mark("header (FGuid + BuildIdentifier)", s)
        if self.build_identifier not in (1, 2, 3, 4):
            r.fail("BuildIdentifier %d not in 1..4 (DEBUG/DEVELOPMENT/TEST/SHIPPING)"
                   % self.build_identifier, s + 16)

        s = r.o
        nmod = r.count(4, "Modules TMap")
        self.modules = []
        for _ in range(nmod):
            key = r.fstring()
            self.modules.append(Module(r, key))
        mark("Modules TMap (%d)" % nmod, s)
        self.modules_end = r.o

        s = r.o
        self.type_refs = dict(
            (r.i64(), TypeRef(r)) for _ in range(r.count(8, "TypeReferences")))
        mark("TypeReferences (%d)" % len(self.type_refs), s)

        s = r.o
        self.typeid_to_ptr = dict(
            (r.i32(), r.i64()) for _ in range(r.count(12, "TypeIdReferenceToPointer")))
        mark("TypeIdReferenceToPointer (%d)" % len(self.typeid_to_ptr), s)

        s = r.o
        self.func_refs = dict(
            (r.i64(), FuncRef(r)) for _ in range(r.count(8, "FunctionReferences")))
        mark("FunctionReferences (%d)" % len(self.func_refs), s)

        s = r.o
        self.funcid_to_ptr = dict(
            (r.i32(), r.i64()) for _ in range(r.count(12, "FunctionIdReferenceToPointer")))
        mark("FunctionIdReferenceToPointer (%d)" % len(self.funcid_to_ptr), s)

        s = r.o
        self.global_refs = dict(
            (r.i64(), GlobalRef(r)) for _ in range(r.count(8, "GlobalReferences")))
        mark("GlobalReferences (%d)" % len(self.global_refs), s)

        s = r.o
        self.static_names = r.arr(r.sia, 4, "StaticNames")
        mark("StaticNames (%d)" % len(self.static_names), s)

        s = r.o
        self.prop_refs = dict(
            (r.i64(), PropRef(r)) for _ in range(r.count(8, "PropertyReferences")))
        mark("PropertyReferences (%d)" % len(self.prop_refs), s)

        if r.o != r.n:
            r.fail("walk finished with %d bytes of slack (expected exactly 0)"
                   % (r.n - r.o))
        self.consumed = r.o
        self._check_regions()
        self._index()

    # -- validation ---------------------------------------------------------
    def _check_regions(self):
        cur = 0
        for a, b, label in self.regions:
            if a != cur:
                raise CacheError("region gap/overlap before %r: expected 0x%x, got 0x%x"
                                 % (label, cur, a))
            if b < a:
                raise CacheError("region %r ends before it starts" % label)
            cur = b
        if cur != self.size:
            raise CacheError("regions cover 0x%x of 0x%x bytes" % (cur, self.size))

    def _index(self):
        self.functions = []
        for m in self.modules:
            for f in m.all_functions():
                f_mod = m
                self.functions.append((m, f))
        ids = {}
        for m, f in self.functions:
            if f.id in ids:
                raise CacheError("duplicate function Id 0x%08x: %s and %s"
                                 % (f.id, ids[f.id].name, f.name))
            ids[f.id] = f
        self.by_id = ids
        self.classes = [(m, c) for m in self.modules for c in m.classes]
        self.script_enums = set(e.name for m in self.modules for e in m.enums)
        self.script_classes = set(c.name for _, c in self.classes)

    # -- symbol resolution --------------------------------------------------
    def type_of_ptr(self, ptr):
        return self.type_refs.get(ptr)

    def type_of_id(self, tid):
        p = self.typeid_to_ptr.get(tid)
        return self.type_refs.get(p) if p is not None else None

    def func_of_ptr(self, ptr):
        return self.func_refs.get(ptr)

    def func_of_id(self, fid):
        p = self.funcid_to_ptr.get(fid)
        return self.func_refs.get(p) if p is not None else None

    def prop_of(self, type_id, offset):
        """PropertyReferences uses a COMPOSITE key, not a pointer:
              key = (TypeId << 1) | (Offset << 33) | 1
        where TypeId is the member-access instruction's INTARG (rewritten at save
        time to the OWNING object type's typeid) and Offset is its SWORDARG."""
        key = ((type_id & 0xFFFFFFFF) << 1) | (offset << 33) | 1
        # int64 wrap
        if key >= (1 << 63):
            key -= (1 << 64)
        return self.prop_refs.get(key)

    # -- pretty type names --------------------------------------------------
    def type_name(self, dt, _depth=0):
        if _depth > 6:
            return "?"
        if dt.type_info:
            tr = self.type_refs.get(dt.type_info)
            if tr is None:
                base = "UNRESOLVED_TYPE_0x%x" % (dt.type_info & 0xFFFFFFFFFFFF)
            else:
                base = tr.name
                if tr.subtypes:
                    base += "<%s>" % ", ".join(
                        self.type_name(s, _depth + 1) for s in tr.subtypes)
        else:
            base = TOKEN_PRIMITIVE.get(dt.token)
            if base is None:
                base = "void" if dt.token == 5 else "tok%d" % dt.token
        if dt.obj_const:
            base = "const " + base
        if dt.handle:
            base += "@"
            if dt.const_handle:
                base += " const"
        if dt.is_ref:
            base += "&"
        return base


def load(path):
    return PrecompiledCache(path)


if __name__ == "__main__":
    import sys
    p = sys.argv[1] if len(sys.argv) > 1 else (
        r"G:\git\GAME BACKUPS FOR REVERSE ENGINEERING\SUPERVIVE\Loki\Script"
        r"\PrecompiledScript.Cache")
    c = load(p)
    print("guid=%s build=%d" % ("-".join("%08X" % g for g in c.guid),
                                c.build_identifier))
    print("modules=%d classes=%d functions=%d"
          % (len(c.modules), len(c.classes), len(c.functions)))
    print("trailer: types=%d typeids=%d funcs=%d funcids=%d globals=%d "
          "statics=%d props=%d"
          % (len(c.type_refs), len(c.typeid_to_ptr), len(c.func_refs),
             len(c.funcid_to_ptr), len(c.global_refs), len(c.static_names),
             len(c.prop_refs)))
    for a, b, label in c.regions:
        print("  0x%08x..0x%08x %9d B  %5.1f%%  %s"
              % (a, b, b - a, 100.0 * (b - a) / c.size, label))
    print("consumed %d / %d, slack %d" % (c.consumed, c.size, c.size - c.consumed))
