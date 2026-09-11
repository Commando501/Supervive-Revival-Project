#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Binds.Cache / Binds.Cache.Headers reader -- the engine<->script binding table.

Binds.Cache is FAngelscriptBindDatabase::Serialize output:  Archive << Structs;
Archive << Classes;  -- two TArrays back to back, no header/magic/version.

Note the string convention here is DIFFERENT from PrecompiledScript.Cache's
FStringInArchive: these are plain UE FStrings, so length INCLUDES the trailing NUL
and an empty string is a bare int32 0 with no payload.
"""
import struct

__all__ = ["BindsError", "BindDatabase", "load"]


class BindsError(Exception):
    pass


class R(object):
    def __init__(self, data, path=""):
        self.d = data
        self.o = 0
        self.n = len(data)
        self.path = path

    def fail(self, msg, off=None):
        off = self.o if off is None else off
        raise BindsError("%s at 0x%x (%d/%d) in %s\n  context: %s"
                         % (msg, off, off, self.n, self.path,
                            self.d[max(0, off - 16):off + 32].hex()))

    def i32(self):
        if self.o + 4 > self.n:
            self.fail("int32 read overruns EOF")
        v = struct.unpack_from("<i", self.d, self.o)[0]
        self.o += 4
        return v

    def i8(self):
        if self.o + 1 > self.n:
            self.fail("int8 read overruns EOF")
        v = struct.unpack_from("<b", self.d, self.o)[0]
        self.o += 1
        return v

    def b(self):
        at = self.o
        v = self.i32()
        if v not in (0, 1):
            self.fail("bool desync: read %d, expected 0 or 1" % v, at)
        return v == 1

    def s(self):
        at = self.o
        n = self.i32()
        if n == 0:
            return ""
        if n < 0:
            k = -n * 2
            if self.o + k > self.n:
                self.fail("FString(UTF16) overruns EOF", at)
            raw = self.d[self.o:self.o + k]
            self.o += k
            return raw[:-2].decode("utf-16-le")
        if n > 0x100000 or self.o + n > self.n:
            self.fail("FString length %d implausible" % n, at)
        raw = self.d[self.o:self.o + n]
        self.o += n
        if raw[-1] != 0:
            self.fail("FString len=%d not NUL-terminated" % n, at)
        return raw[:-1].decode("latin1")

    def arr(self, fn, what="array"):
        at = self.o
        n = self.i32()
        if n < 0 or self.o + n > self.n:
            self.fail("%s count %d implausible" % (what, n), at)
        return [fn() for _ in range(n)]


def _prop(r):
    return {"decl": r.s(), "name": r.s(), "can_write": r.b(), "can_read": r.b(),
            "can_edit": r.b(), "gen_getter": r.b(), "gen_setter": r.b(),
            "gen_name": r.s(), "gen_handle": r.b(), "gen_unresolved": r.b()}


def _meth(r):
    m = {"decl": r.s(), "ufunc": r.s(), "static_unreal": r.b(),
         "static_script": r.b(), "global_scope": r.b(), "not_as_property": r.b(),
         "trivial": r.b(), "world_ctx": r.i8(), "determines_output": r.i8(),
         "as_class": r.s(), "script_name": r.s()}
    return m


class BindDatabase(object):
    def __init__(self, binds_path, headers_path=None):
        with open(binds_path, "rb") as fh:
            r = R(fh.read(), binds_path)
        self.structs = r.arr(
            lambda: {"type": r.s(), "path": r.s(),
                     "props": r.arr(lambda: _prop(r), "struct props")}, "Structs")
        self.classes = r.arr(
            lambda: {"type": r.s(), "path": r.s(),
                     "methods": r.arr(lambda: _meth(r), "methods"),
                     "props": r.arr(lambda: _prop(r), "class props")}, "Classes")
        if r.o != r.n:
            r.fail("Binds.Cache walk left %d trailing bytes (expected 0)" % (r.n - r.o))
        self.consumed, self.size = r.o, r.n

        self.headers = {}
        self.headers_consumed = self.headers_size = 0
        if headers_path:
            with open(headers_path, "rb") as fh:
                r2 = R(fh.read(), headers_path)
            pairs = r2.arr(lambda: (r2.s(), r2.s()), "Headers")
            if r2.o != r2.n:
                r2.fail("Binds.Cache.Headers left %d trailing bytes" % (r2.n - r2.o))
            self.headers = dict(pairs)
            self.headers_consumed, self.headers_size = r2.o, r2.n

        self._index()

    def _index(self):
        # AS type name -> record (classes win over structs on a name clash; there
        # are none in this file but be explicit rather than lucky)
        self.by_type = {}
        for s in self.structs:
            self.by_type.setdefault(s["type"], s)
        for c in self.classes:
            self.by_type[c["type"]] = c
        self.struct_names = set(s["type"] for s in self.structs)
        self.class_names = set(c["type"] for c in self.classes)
        self.by_path = {}
        for rec in list(self.structs) + list(self.classes):
            self.by_path.setdefault(rec["path"], rec)
        # (AS owner type, AS function name) -> method bind
        self.method_index = {}
        # bare AS function name -> [method binds]  (for global/mixin resolution)
        self.method_by_name = {}
        for c in self.classes:
            for m in c["methods"]:
                nm = m["script_name"] or as_decl_name(m["decl"])
                if nm:
                    self.method_index.setdefault((c["type"], nm), m)
                    self.method_by_name.setdefault(nm, []).append((c, m))
        self.prop_index = {}
        for rec in list(self.structs) + list(self.classes):
            for p in rec["props"]:
                nm = as_decl_name(p["decl"], is_prop=True) or p["name"]
                if nm:
                    self.prop_index.setdefault((rec["type"], nm), p)

    # -- queries ------------------------------------------------------------
    def unreal_path(self, as_type):
        rec = self.by_type.get(as_type)
        return rec["path"] if rec else None

    def header_for(self, as_type):
        p = self.unreal_path(as_type)
        return self.headers.get(p) if p else None

    def method(self, as_type, as_func):
        return self.method_index.get((as_type, as_func))

    def ufunction_name(self, as_type, as_func):
        """The UFunction name, which DIFFERS from the AS name for 662 methods
        (e.g. AS LokiBeginPlay <-> UFunction BP_LokiBeginPlay). A native shim
        needs the UFunction name; decompiled script shows the AS name."""
        m = self.method(as_type, as_func)
        if not m:
            return None
        return m["ufunc"] or None


def as_decl_name(decl, is_prop=False):
    """Pull the identifier out of an AngelScript declaration string.

    method: 'void AddPlayerToPlane(ALokiPlayerState PlayerState)' -> AddPlayerToPlane
    prop:   'TArray<FMissionProgress> FinalMissionProgress'       -> FinalMissionProgress
    Template args and pointer/ref decorations must not confuse the split, so we
    scan from the '(' (or end) backwards over the identifier.
    """
    if not decl:
        return ""
    end = decl.find("(") if not is_prop else -1
    if end < 0:
        end = len(decl)
    i = end - 1
    while i >= 0 and decl[i] == " ":
        i -= 1
    j = i
    while j >= 0 and (decl[j].isalnum() or decl[j] == "_"):
        j -= 1
    return decl[j + 1:i + 1]


def load(binds_path, headers_path=None):
    return BindDatabase(binds_path, headers_path)


if __name__ == "__main__":
    import sys
    base = r"G:\git\GAME BACKUPS FOR REVERSE ENGINEERING\SUPERVIVE\Loki\Script"
    db = load(base + r"\Binds.Cache", base + r"\Binds.Cache.Headers")
    print("structs=%d classes=%d methods=%d props=%d headers=%d"
          % (len(db.structs), len(db.classes),
             sum(len(c["methods"]) for c in db.classes),
             sum(len(c["props"]) for c in db.classes)
             + sum(len(s["props"]) for s in db.structs),
             len(db.headers)))
    print("Binds.Cache        consumed %d / %d" % (db.consumed, db.size))
    print("Binds.Cache.Headers consumed %d / %d" % (db.headers_consumed, db.headers_size))
    print()
    print("ALokiDropPlane ->", db.unreal_path("ALokiDropPlane"))
    print("  header:", db.header_for("ALokiDropPlane"))
    rec = db.by_type.get("ALokiDropPlane")
    for m in rec["methods"][:6]:
        print("   ", m["decl"], "   [UFunction %s]" % m["ufunc"])
