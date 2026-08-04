#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""asdump -- decompile SUPERVIVE's Angelscript layer.

Reads the three plaintext caches the game ships:
    Loki/Script/PrecompiledScript.Cache    compiled script: declarations + bytecode
    Loki/Script/Binds.Cache                engine<->script binding table (symbols)
    Loki/Script/Binds.Cache.Headers        /Script/Module.Class -> C++ header

and writes, per module, a reconstructed .as source file plus an index.

    python asdump.py                       # defaults, writes to ../out/b
    python asdump.py --out DIR --no-asm    # skip the disassembly appendix
    python asdump.py --module LokiDropShip # only modules matching a substring
    python asdump.py --validate            # self-check only, write nothing

WHAT IS EXACT vs WHAT IS RECONSTRUCTED
  Exact (stored verbatim in the cache): module names, source paths, class names
  and bases, every property with its type and UPROPERTY metadata, every function
  name, return type, parameter types AND NAMES, default-argument source text,
  UFUNCTION metadata and flags, enums, and the bytecode itself.
  Reconstructed (decompiled, best effort): function bodies.
  ABSENT from a SHIPPING cache and therefore NOT recoverable: local variable
  names (locals render as vN) and line numbers (DeclaredAt==0, LineNumbers empty
  for all 1463 functions -- InitFrom() guards them with #if !UE_BUILD_SHIPPING).

Stdlib only. Opens every game file 'rb'; never writes inside the game install.
"""
import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import ascache
import asbinds
import aslift
import opcode_table as T

DEFAULT_SCRIPT_DIR = (r"G:\git\GAME BACKUPS FOR REVERSE ENGINEERING\SUPERVIVE"
                      r"\Loki\Script")
DEFAULT_OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "..", "out", "b")

EXPECTED_MODULES = 78

# Verified by correlation against the data (see README notes):
#   bit0 -> only ctors (130/130), bit1 -> only behaviours (68/68),
#   bit2 -> only methods AND agrees with FunctionReference.is_const 401/401,
#   bit3/bit4 -> only methods. Bits 5/13/18 are set too broadly to be the stock
#   FINAL/OVERRIDE/SHARED meanings, so they are reported raw rather than guessed.
TRAIT_BITS = [(0, "constructor"), (1, "destructor"), (2, "const"),
              (3, "private"), (4, "protected")]
TRAIT_KNOWN_MASK = 0b11111


def traits_text(traits):
    named = [nm for bit, nm in TRAIT_BITS if traits & (1 << bit)]
    return named


# ---------------------------------------------------------------------------
class Emitter(object):
    def __init__(self, cache, binds, want_asm=True):
        self.c = cache
        self.b = binds
        self.want_asm = want_asm
        self.stats = {
            "functions": 0, "with_bytecode": 0, "decoded": 0, "structured": 0,
            "decode_errors": [], "structure_errors": [], "unhandled": {},
            "stack_warnings": 0, "asm_lines": 0, "pseudo_lines": 0,
            "bytecode_bytes": 0, "instructions": 0,
        }

    # -- declarations -------------------------------------------------------
    def sig(self, f, owner=None):
        ret = self.c.type_name(f.ret)
        ps = []
        for i, pt in enumerate(f.param_types):
            nm = f.param_names[i] if i < len(f.param_names) else ""
            d = f.param_defaults[i] if i < len(f.param_defaults) else ""
            flag = f.param_flags[i] if i < len(f.param_flags) else 0
            t = self.c.type_name(pt)
            # asETypeModifiers: 1=asTM_INREF 2=asTM_OUTREF 3=asTM_INOUTREF.
            # UE-Angelscript's own bind declarations spell a const reference as a
            # bare `&` (6428/6428 in Binds.Cache), so match that; keep the
            # out/inout suffix where it is load-bearing.
            if pt.is_ref and flag in (1, 2, 3):
                suffix = {1: "&in", 2: "&out", 3: "&" if pt.obj_const else "&inout"}
                t = t[:-1] + suffix[flag]
            ps.append("%s %s%s" % (t, nm or "arg%d" % i,
                                   (" = " + d) if d else ""))
        tr = traits_text(f.traits)
        const = " const" if "const" in tr else ""
        pre = ""
        if "private" in tr:
            pre = "private "
        elif "protected" in tr:
            pre = "protected "
        if f.kind == "ctor" or (owner and f.name == owner.name):
            return "%s%s(%s)" % (pre, f.name, ", ".join(ps))
        ns = (f.namespace + "::") if f.namespace else ""
        return "%s%s %s%s(%s)%s" % (pre, ret, ns, f.name, ", ".join(ps), const)

    def ufunction_line(self, f):
        if not f.is_ufunction:
            return None
        bits = [k for k, v in f.uflags.items() if v]
        for k, v in f.meta:
            bits.append("meta.%s=%s" % (k, v) if v else "meta.%s" % k)
        if f.unreal_name and f.unreal_name != f.name:
            bits.insert(0, "UnrealName=%s" % f.unreal_name)
        return "UFUNCTION(%s)" % ", ".join(bits)

    def uproperty_line(self, p):
        if not p.is_uproperty:
            return None
        bits = [k for k, v in p.flags.items() if v]
        if p.rep_condition is not None:
            bits.append("ReplicationCondition=%d" % p.rep_condition)
        if p.rep_notify:
            bits.append("RepNotify")
        for k, v in p.meta:
            bits.append("meta.%s=%s" % (k, v) if v else "meta.%s" % k)
        return "UPROPERTY(%s)" % ", ".join(bits)

    # -- bodies -------------------------------------------------------------
    def body(self, f, owner, indent):
        st = self.stats
        st["functions"] += 1
        if f.bc_dwords == 0:
            return [indent + "{", indent + "}"], []
        st["with_bytecode"] += 1
        st["bytecode_bytes"] += len(f.bytecode)
        r = aslift.lift_function(self.c, self.b, f, owner)
        if r["error"]:
            st["decode_errors"].append((owner.name if owner else "", f.name,
                                        r["error"]))
            return ([indent + "{",
                     indent + "    <<UNDECODED: %s>>" % r["error"].replace("\n", " "),
                     indent + "    <<%d bytes of bytecode at cache offset 0x%x>>"
                     % (len(f.bytecode), f.bc_off),
                     indent + "}"], [])
        st["decoded"] += 1
        st["instructions"] += len(r["insns"])
        for k, v in r["unhandled"].items():
            st["unhandled"][k] = st["unhandled"].get(k, 0) + v
        st["stack_warnings"] += r["stack_warnings"]
        lines = [indent + "{"]
        if r["structure_error"]:
            st["structure_errors"].append((owner.name if owner else "", f.name,
                                           r["structure_error"]))
            lines.append(indent + "    <<STRUCTURING FAILED: %s -- body available "
                                  "as disassembly below>>" % r["structure_error"])
        else:
            st["structured"] += 1
            for l in r["pseudo"]:
                lines.append(indent + l)
            st["pseudo_lines"] += len(r["pseudo"])
        lines.append(indent + "}")
        asm = []
        if self.want_asm and r["asm"]:
            asm.append(indent + "/* ---- %s: %d dwords / %d instructions "
                                "(cache offset 0x%x) ----"
                       % (f.name, f.bc_dwords, len(r["insns"]), f.bc_off))
            for l in r["asm"]:
                asm.append(indent + l)
            asm.append(indent + "*/")
            st["asm_lines"] += len(r["asm"])
        return lines, asm

    def function(self, f, owner, indent):
        out = []
        uf = self.ufunction_line(f)
        if uf:
            out.append(indent + uf)
        extra = f.traits & ~TRAIT_KNOWN_MASK
        note = "   // traits=0x%x" % f.traits if extra else ""
        out.append(indent + self.sig(f, owner) + note)
        body, asm = self.body(f, owner, indent)
        out.extend(body)
        out.extend(asm)
        out.append("")
        return out

    # -- module -------------------------------------------------------------
    def module(self, m):
        L = []
        A = L.append
        nfun = len(m.all_functions())
        bcb = sum(len(f.bytecode) for f in m.all_functions())
        A("// " + "=" * 76)
        A("//  MODULE   %s" % m.name)
        A("//  SOURCE   %s" % m.source_path)
        A("//  CONTENT  %d class(es), %d function(s), %d enum(s), %d global(s), "
          "%d bytes of bytecode" % (len(m.classes), nfun, len(m.enums),
                                    len(m.globals), bcb))
        A("// " + "=" * 76)
        A("//  Reconstructed by tools/asdump/impl_b/asdump.py from")
        A("//  Loki/Script/PrecompiledScript.Cache (SHIPPING build).")
        A("//  DECLARATIONS are exact (stored verbatim). BODIES are decompiled:")
        A("//  a shipping cache carries NO local-variable names and NO line")
        A("//  numbers, so locals render as vN and there is no source mapping.")
        A("// " + "=" * 76)
        A("")
        if m.imported_modules:
            for i in m.imported_modules:
                A("import %s;" % i)
            A("")
        if m.statics_class:
            A("// statics class: %s" % m.statics_class)
        if m.declared_events:
            for e in m.declared_events:
                A("event %s;" % e)
        if m.declared_delegates:
            for d in m.declared_delegates:
                A("delegate %s;" % d)
        if m.post_init:
            A("// post-init functions: %s" % ", ".join(m.post_init))
        if m.declared_events or m.declared_delegates or m.statics_class \
                or m.post_init:
            A("")

        for e in m.enums:
            A("enum %s" % e.name)
            A("{")
            for nm, val in zip(e.names, e.values):
                A("    %s = %d," % (nm, val))
            A("}")
            A("")

        for g in m.globals:
            t = self.c.type_name(g.type)
            if g.pure_constant:
                A("const %s %s = %d;" % (t, g.name, g.value))
            elif g.init_func is not None:
                A("%s %s = /* initialiser */" % (t, g.name))
                body, asm = self.body(g.init_func, None, "")
                L.extend(body)
                L.extend(asm)
            else:
                A("%s %s;" % (t, g.name))
        if m.globals:
            A("")

        for f in m.functions:
            L.extend(self.function(f, None, ""))

        for k in m.classes:
            L.extend(self.klass(k))
        return L

    def klass(self, k):
        L = []
        A = L.append
        base = k.super_class or (self.c.type_refs.get(k.derived_from).name
                                 if self.c.type_refs.get(k.derived_from) else "")
        A("// " + "-" * 76)
        if k.in_preprocessor:
            meta = [kk for kk, vv in k.cflags.items() if vv]
            if k.placeable:
                meta.append("Placeable")
            for kk, vv in k.meta:
                meta.append("meta.%s=%s" % (kk, vv) if vv else "meta.%s" % kk)
            if k.config_name:
                meta.append("Config=%s" % k.config_name)
            if k.compose_onto:
                meta.append("ComposeOnto=%s" % k.compose_onto)
            A("UCLASS(%s)" % ", ".join(meta))
        A("class %s%s" % (k.name, (" : " + base) if base else ""))
        up = self.b.unreal_path(base) if (self.b and base) else None
        if up:
            A("// unreal base : %s" % up)
            hdr = self.b.headers.get(up)
            if hdr:
                A("// C++ header  : %s" % hdr)
        if k.static_class_global:
            A("// static class global: %s" % k.static_class_global)
        A("{")
        for p in k.properties:
            u = self.uproperty_line(p)
            if u:
                A("    " + u)
            vis = "private " if p.is_private else ("protected " if p.is_protected
                                                   else "")
            A("    %s%s %s;" % (vis, self.c.type_name(p.type), p.name))
        if k.properties:
            A("")
        for f in k.constructors:
            L.extend(self.function(f, k, "    "))
        for f in k.methods:
            L.extend(self.function(f, k, "    "))
        for f, bt in zip(k.behavior_functions, k.behavior_types):
            L.extend(self.function(f, k, "    "))
        A("}")
        A("")
        return L


# ---------------------------------------------------------------------------
def validate(cache, binds, log=print):
    """Self-validation. Raises AssertionError on anything structural."""
    log("=" * 78)
    log("SELF-VALIDATION")
    log("=" * 78)
    log("PrecompiledScript.Cache  %s" % cache.path)
    log("  GUID (per-save random, NOT a format id) : %s"
        % "-".join("%08X" % g for g in cache.guid))
    log("  BuildIdentifier                         : %d (%s)"
        % (cache.build_identifier,
           {1: "DEBUG", 2: "DEVELOPMENT", 3: "TEST", 4: "SHIPPING"}
           .get(cache.build_identifier, "?")))
    log("  byte accounting:")
    total = 0
    for a, b, label in cache.regions:
        total += b - a
        log("    0x%08X..0x%08X %10d B  %6.2f%%  %s"
            % (a, b, b - a, 100.0 * (b - a) / cache.size, label))
    log("    %s" % ("-" * 62))
    log("    parsed %d / %d bytes = %.4f%%, UNACCOUNTED %d"
        % (cache.consumed, cache.size, 100.0 * cache.consumed / cache.size,
           cache.size - cache.consumed))
    assert cache.consumed == cache.size, "cache walk did not reach EOF"
    assert total == cache.size, "region ledger does not tile the file"
    assert len(cache.modules) == EXPECTED_MODULES, \
        "expected %d modules, parsed %d" % (EXPECTED_MODULES, len(cache.modules))
    log("  modules parsed  : %d  (asserted == %d)" % (len(cache.modules),
                                                      EXPECTED_MODULES))
    log("  classes         : %d" % len(cache.classes))
    log("  functions       : %d" % len(cache.functions))
    log("  properties      : %d"
        % sum(len(k.properties) for _, k in cache.classes))
    log("  source paths    : %d distinct .as files"
        % len(set(m.source_path for m in cache.modules)))
    assert len(set(m.source_path for m in cache.modules)) == EXPECTED_MODULES

    if binds:
        log("")
        log("Binds.Cache")
        log("  parsed %d / %d bytes, UNACCOUNTED %d"
            % (binds.consumed, binds.size, binds.size - binds.consumed))
        log("  structs=%d classes=%d methods=%d props=%d"
            % (len(binds.structs), len(binds.classes),
               sum(len(c["methods"]) for c in binds.classes),
               sum(len(c["props"]) for c in binds.classes)
               + sum(len(s["props"]) for s in binds.structs)))
        log("Binds.Cache.Headers")
        log("  parsed %d / %d bytes, UNACCOUNTED %d"
            % (binds.headers_consumed, binds.headers_size,
               binds.headers_size - binds.headers_consumed))
        log("  header links=%d" % len(binds.headers))
        assert binds.consumed == binds.size
        assert binds.headers_consumed == binds.headers_size

    # --- symbol resolution census -----------------------------------------
    log("")
    log("SYMBOL RESOLUTION (measured over every reference in the file)")
    tot = miss = 0
    for m, f in cache.functions:
        for dt in [f.ret] + list(f.param_types):
            if dt.type_info:
                tot += 1
                miss += dt.type_info not in cache.type_refs
        for t in f.obj_var_types:
            if t:
                tot += 1
                miss += t not in cache.type_refs
    for m, k in cache.classes:
        for p in k.properties:
            if p.type.type_info:
                tot += 1
                miss += p.type.type_info not in cache.type_refs
        for t in (k.derived_from, k.shadow_type):
            if t:
                tot += 1
                miss += t not in cache.type_refs
    log("  type pointers          %6d resolved, %d unresolved" % (tot - miss, miss))
    ftot = fmiss = 0
    for m, k in cache.classes:
        for fid in list(k.factory_refs) + list(k.behavior_refs):
            if fid:
                ftot += 1
                fmiss += cache.func_of_id(fid) is None
    log("  factory/behaviour ids  %6d resolved, %d unresolved"
        % (ftot - fmiss, fmiss))
    return True


def bytecode_census(cache, log=print):
    """Decode every stream and resolve every operand; report the real rates."""
    ptr_ops = {"PshGPtr", "PshG4", "LdGRdR4", "CALLSYS", "ALLOC", "FREE",
               "OBJTYPE", "CpyVtoG4", "CpyGtoV4", "LDG", "PGA", "SetG4",
               "JitEntry", "FuncPtr", "Thiscall1", "FinConstruct",
               "DestructScript", "CopyScript"}
    id_ops = {"CALL", "CALLBND", "CALLINTF"}
    mem_ops = {"ADDSi": "W0", "LoadThisR": "W0", "LoadRObjR": "W1",
               "LoadVObjR": "W1"}
    ok = bad = ins_n = rets = 0
    op_hist = {}
    pt = pr = it = ir = mt = mr = 0
    fails = []
    for m, f in cache.functions:
        if f.bc_dwords == 0:
            continue
        try:
            insns = aslift.decode(f.bytecode, "%s::%s" % (m.name, f.name))
        except aslift.LiftError as e:
            bad += 1
            fails.append(str(e))
            continue
        ok += 1
        ins_n += len(insns)
        for i in insns:
            op_hist[i.name] = op_hist.get(i.name, 0) + 1
            if i.name == "RET":
                rets += 1
            if i.name in ptr_ops and "QW" in i.args:
                q = i.args["QW"]
                pt += 1
                pr += (q in cache.func_refs or q in cache.type_refs
                       or q in cache.global_refs)
            if i.name in id_ops:
                it += 1
                ir += cache.func_of_id(i.args["DW"]) is not None
            if i.name in mem_ops:
                mt += 1
                mr += cache.prop_of(i.args["DW"], i.args[mem_ops[i.name]]) is not None
    log("")
    log("BYTECODE")
    log("  streams decoded exactly   %d / %d  (%.2f%%)"
        % (ok, ok + bad, 100.0 * ok / max(ok + bad, 1)))
    log("  instructions              %d, distinct opcodes %d, RET count %d"
        % (ins_n, len(op_hist), rets))
    log("  RET == function count?    %s (%d streams)"
        % ("YES" if rets == ok else "NO", ok))
    log("  call/global ptr operands  %d / %d resolved to a name (%.2f%%)"
        % (pr, pt, 100.0 * pr / max(pt, 1)))
    log("  script-call id operands   %d / %d resolved (%.2f%%)"
        % (ir, it, 100.0 * ir / max(it, 1)))
    log("  member accesses           %d / %d resolved to a property NAME (%.2f%%)"
        % (mr, mt, 100.0 * mr / max(mt, 1)))
    for fl in fails[:5]:
        log("  DECODE FAILURE: %s" % fl)
    return ok, bad


def write_index(path, cache, emitter, files, elapsed, log=print):
    rows = []
    for m in cache.modules:
        fns = m.all_functions()
        rows.append((m.name, m.source_path,
                     ", ".join(k.name for k in m.classes) or "-",
                     len(fns), sum(len(f.bytecode) for f in fns),
                     files.get(m.name, "")))
    rows.sort(key=lambda r: r[1].lower())
    st = emitter.stats
    L = []
    A = L.append
    A("# SUPERVIVE Angelscript -- decompiled module index")
    A("")
    A("Generated by `tools/asdump/impl_b/asdump.py` in %.1fs." % elapsed)
    A("")
    A("Source caches (read-only, never modified):")
    A("")
    A("| file | bytes | parsed | unaccounted |")
    A("|---|---:|---:|---:|")
    A("| `PrecompiledScript.Cache` | %d | %d | %d |"
      % (cache.size, cache.consumed, cache.size - cache.consumed))
    if emitter.b:
        A("| `Binds.Cache` | %d | %d | %d |"
          % (emitter.b.size, emitter.b.consumed,
             emitter.b.size - emitter.b.consumed))
        A("| `Binds.Cache.Headers` | %d | %d | %d |"
          % (emitter.b.headers_size, emitter.b.headers_consumed,
             emitter.b.headers_size - emitter.b.headers_consumed))
    A("")
    A("## Totals")
    A("")
    A("- modules: **%d**" % len(cache.modules))
    A("- classes: **%d**, properties: **%d**"
      % (len(cache.classes), sum(len(k.properties) for _, k in cache.classes)))
    A("- functions: **%d** (%d carry bytecode)"
      % (st["functions"], st["with_bytecode"]))
    A("- bytecode decoded: **%d / %d = %.2f%%**"
      % (st["decoded"], st["with_bytecode"],
         100.0 * st["decoded"] / max(st["with_bytecode"], 1)))
    A("- bodies structured to pseudo-source: **%d / %d = %.2f%%**"
      % (st["structured"], st["with_bytecode"],
         100.0 * st["structured"] / max(st["with_bytecode"], 1)))
    A("- instructions: %d over %d bytes of bytecode"
      % (st["instructions"], st["bytecode_bytes"]))
    if st["unhandled"]:
        A("- UNMODELLED OPCODES: %s" % st["unhandled"])
    else:
        A("- unmodelled opcodes: **none**")
    A("- stack-underflow markers (`<?>`) emitted: %d" % st["stack_warnings"])
    A("")
    A("## Modules")
    A("")
    A("| source | module | class(es) | funcs | bytecode |")
    A("|---|---|---|---:|---:|")
    for name, src, cls, nf, bc, rel in rows:
        link = "[`%s`](%s)" % (src, rel.replace("\\", "/")) if rel else "`%s`" % src
        A("| %s | `%s` | %s | %d | %d |" % (link, name, cls, nf, bc))
    A("")
    A("## Notes")
    A("")
    A("Declarations are exact -- names, types, parameter names, default-argument")
    A("source text and UPROPERTY/UFUNCTION metadata are all stored verbatim in the")
    A("cache. Function bodies are decompiled from bytecode. A SHIPPING cache")
    A("carries no local-variable names and no line numbers (`DeclaredAt == 0` and")
    A("`LineNumbers` empty for all %d functions), so locals appear as `vN` and"
      % st["functions"])
    A("there is no mapping back to source lines.")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(L) + "\n")
    log("wrote %s" % path)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--script-dir", default=DEFAULT_SCRIPT_DIR,
                    help="directory holding the three .Cache files")
    ap.add_argument("--out", default=DEFAULT_OUT, help="output directory")
    ap.add_argument("--no-asm", action="store_true",
                    help="omit the per-function disassembly appendix")
    ap.add_argument("--no-binds", action="store_true",
                    help="skip Binds.Cache (faster; loses UFunction aliases)")
    ap.add_argument("--module", default=None,
                    help="only emit modules whose name/path contains this")
    ap.add_argument("--validate", action="store_true",
                    help="run self-validation and the bytecode census, write nothing")
    args = ap.parse_args(argv)

    pcs = os.path.join(args.script_dir, "PrecompiledScript.Cache")
    bc = os.path.join(args.script_dir, "Binds.Cache")
    bh = os.path.join(args.script_dir, "Binds.Cache.Headers")
    for p in (pcs,):
        if not os.path.exists(p):
            sys.exit("missing required file: %s" % p)

    t0 = time.time()
    cache = ascache.load(pcs)
    binds = None
    if not args.no_binds and os.path.exists(bc):
        binds = asbinds.load(bc, bh if os.path.exists(bh) else None)

    validate(cache, binds)
    bytecode_census(cache)

    if args.validate:
        print("\nvalidate-only: nothing written. %.1fs" % (time.time() - t0))
        return 0

    em = Emitter(cache, binds, want_asm=not args.no_asm)
    outdir = os.path.abspath(args.out)
    files = {}
    n = 0
    for m in cache.modules:
        if args.module and args.module.lower() not in (m.name + m.source_path).lower():
            continue
        rel = m.source_path.replace("/", os.sep) + ".txt"
        dst = os.path.join(outdir, rel)
        d = os.path.dirname(dst)
        if not os.path.isdir(d):
            os.makedirs(d)
        lines = em.module(m)
        with open(dst, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")
        files[m.name] = rel
        n += 1

    st = em.stats
    print("")
    print("=" * 78)
    print("EMIT")
    print("=" * 78)
    print("  modules written           %d -> %s" % (n, outdir))
    print("  functions emitted         %d" % st["functions"])
    print("  with bytecode             %d" % st["with_bytecode"])
    print("  decoded                   %d  (%.2f%%)"
          % (st["decoded"], 100.0 * st["decoded"] / max(st["with_bytecode"], 1)))
    print("  structured to pseudo      %d  (%.2f%%)"
          % (st["structured"], 100.0 * st["structured"] / max(st["with_bytecode"], 1)))
    print("  pseudo-source lines       %d" % st["pseudo_lines"])
    print("  disassembly lines         %d" % st["asm_lines"])
    print("  unmodelled opcodes        %s" % (st["unhandled"] or "none"))
    print("  stack-underflow markers   %d" % st["stack_warnings"])
    if st["decode_errors"]:
        print("  DECODE ERRORS             %d" % len(st["decode_errors"]))
        for e in st["decode_errors"][:10]:
            print("     %s::%s  %s" % e)
    if st["structure_errors"]:
        print("  STRUCTURE ERRORS          %d" % len(st["structure_errors"]))
        for e in st["structure_errors"][:10]:
            print("     %s::%s  %s" % e)

    if not args.module:
        write_index(os.path.join(outdir, "_index.md"), cache, em, files,
                    time.time() - t0)
    print("done in %.1fs" % (time.time() - t0))
    return 0


if __name__ == "__main__":
    sys.exit(main())
