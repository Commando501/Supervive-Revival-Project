#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
uereflect.py -- recover UE5 reflection symbols from the cold image, OFFLINE.

Discovered while validating the project's recorded addresses (S102).  UE's code
generator emits two arrays of {pointer,pointer} pairs per class, and both survive
the packer intact in `.rdata` (which is 99.64% readable -- see FK-3):

    FClassFunctionLinkInfo { UFunction*(*CreateFuncPtr)();  const char* FuncNameUTF8; }
        -> a run of qwords alternating TEXT,STR  starting with TEXT
        -> name -> Z_Construct_UFunction_<Class>_<Name>() stub

    FNameNativePtrPair     { const char* NameUTF8;  FNativeFuncPtr Pointer; }
        -> a run alternating STR,TEXT starting with STR
        -> name -> exec<Name> thunk

Both look identical locally; only the PHASE of the run distinguishes them, so the
run's start and end must both be found.  Getting this wrong silently shifts every
symbol by one entry -- the first version of this scan did exactly that.

VERIFIED, three independent ways, on ULokiAbilitySystemComponent:
  * the run at 0x0886D800..0x0886DC50 is 138 qwords = 69 entries; docs/session-100
    -gas-api-dump.txt (captured LIVE, months earlier, by a different tool) records
    exactly "69 UFunctions" for that class;
  * the stub at the paired address disassembles to the textbook Z_Construct body
    (sub rsp,28 / mov rax,[rip+cache] / test / lea rdx,&Params / lea rcx,&cache /
     call ConstructUFunction / mov rax,[rip+cache] / add rsp,28 / ret);
  * the FFunctionParams struct that stub points at carries FunctionFlags
    0x54020401 for AbilityClassIsLMB -- byte-identical to the flags the live GAS
    dump recorded for that same function.

Emits index/uesymbols.json:  {rva: {"name":..., "class":..., "kind":...}}
"""

import array
import json
import os
import re
import struct
import sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import strxref                                                 # noqa: E402

OUT = os.path.join(HERE, "index", "uesymbols.json")

LEA_RDX = re.compile(rb"\x48\x8d\x15(....)", re.S)
LEA_RCX = re.compile(rb"\x48\x8d\x0d(....)", re.S)


def main():
    idx = strxref.Index.load(strxref.INDEX_PATH)
    d = idx._dump()
    IB = idx.imagebase
    SZIMG = max(s[1] + s[2] for s in idx.sections)
    TLO, THI = idx.text_va, idx.text_end
    sec = {s[0]: (s[1], s[1] + s[2]) for s in idx.sections}
    s_at = {r: k for k, r in enumerate(idx.s_rva)}

    def klass(v):
        """Classify a qword: 'T'=code ptr, 'S'=ASCII-string ptr, else '.'."""
        if not (IB <= v < IB + SZIMG):
            return "."
        r = v - IB
        if TLO <= r < THI:
            return "T"
        k = s_at.get(r)
        if k is not None and idx.s_enc[k] == ord("A"):
            return "S"
        return "."

    def rva(v):
        return v - IB if IB <= v < IB + SZIMG else -1

    # ---- classify every qword in .rdata and .data ------------------------
    tags = {}
    for name in (".rdata", ".data"):
        lo, hi = sec[name]
        q = array.array("Q")
        q.frombytes(d[lo:lo + ((hi - lo) // 8) * 8])
        tags[name] = (lo, [klass(v) for v in q], q)

    link_info = []      # (name, zconstruct_rva)
    native_pair = []    # (name, exec_rva)
    runs = Counter()

    for name, (lo, tg, q) in tags.items():
        n = len(tg)
        i = 0
        while i < n - 1:
            if {tg[i], tg[i + 1]} != {"T", "S"}:
                i += 1
                continue
            j = i
            while j + 1 < n and {tg[j], tg[j + 1]} == {"T", "S"}:
                j += 1
            ln = j - i + 1                       # qwords in the run
            if ln >= 4:
                phase = tg[i]
                nent = ln // 2
                runs[(name, phase, ln % 2 == 0)] += 1
                for k in range(nent):
                    a, b = q[i + 2 * k], q[i + 2 * k + 1]
                    if phase == "T":
                        fn, nm = rva(a), rva(b)
                        tgt = link_info
                    else:
                        nm, fn = rva(a), rva(b)
                        tgt = native_pair
                    si = s_at.get(nm)
                    if si is None or not (TLO <= fn < THI):
                        continue
                    tgt.append((idx.text_of(si, d), fn))
            i = j + 1

    print("runs found: %s" % dict(runs))
    print("FClassFunctionLinkInfo entries : %d" % len(link_info))
    print("FNameNativePtrPair     entries : %d" % len(native_pair))

    # ---- decode each Z_Construct_UFunction stub -> FFunctionParams -------
    dlo, dhi = sec[".data"]
    rlo, rhi = sec[".rdata"]

    def stub_params(fn):
        """lea rdx,[rip+d] inside the stub -> the UECodeGen params struct."""
        body = d[fn:fn + 0x40]
        for m in LEA_RDX.finditer(body):
            disp = struct.unpack("<i", m.group(1))[0]
            t = fn + m.end() + disp
            if dlo <= t < dhi or rlo <= t < rhi:
                return t
        return -1

    # FFunctionParams layout (UECodeGen_Private, UE5.4):
    #   +0x00 UObject*(*OuterFunc)()     <- the OWNING CLASS's Z_Construct stub
    #   +0x08 UFunction*(*SuperFunc)()
    #   +0x10 const char* NameUTF8       <- verified against the link-info name
    OUTER, NAMEP = 0x00, 0x10

    fn_class, fn_flags, fn_params = {}, {}, {}
    verified = mismatch = noparams = 0
    for nm, fn in link_info:
        p = stub_params(fn)
        if p < 0:
            noparams += 1
            continue
        try:
            outer = rva(struct.unpack_from("<Q", d, p + OUTER)[0])
            namep = rva(struct.unpack_from("<Q", d, p + NAMEP)[0])
            flags = struct.unpack_from("<I", d, p + 0x38)[0]   # FunctionFlags
        except struct.error:
            noparams += 1
            continue
        si = s_at.get(namep)
        if si is not None and idx.text_of(si, d) == nm:
            verified += 1
            fn_params[fn], fn_flags[fn] = p, flags
            if TLO <= outer < THI:
                fn_class[fn] = outer
        else:
            mismatch += 1
    print("params struct resolved+name-VERIFIED : %d" % verified)
    print("params struct name MISMATCH          : %d   <-- must stay ~0" % mismatch)
    print("no params struct decoded             : %d" % noparams)

    # ---- resolve each owning-class stub to a class NAME ------------------
    # FClassParams carries NO class name.  The name lives in
    #   FClassRegisterCompiledInInfo { OuterRegister, InnerRegister, UClass** ,
    #                                  FClassRegistrationInfo*, const TCHAR* Name, ... }
    # and it is a TCHAR -- i.e. UTF-16 -- which is exactly why the first pass
    # (ASCII-only) resolved barely half of them.  Same encoding trap as FK-4.
    # So: reverse-map every absolute pointer, find the slots that point AT the
    # class's Z_Construct_UClass stub, and take the nearest UTF-16 name.
    CLSNAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{2,}$")
    ptr_slots = defaultdict(list)
    for name in (".rdata", ".data"):
        lo, hi = sec[name]
        q = array.array("Q")
        q.frombytes(d[lo:lo + ((hi - lo) // 8) * 8])
        for k, v in enumerate(q):
            if IB <= v < IB + SZIMG:
                ptr_slots[v - IB].append(lo + k * 8)

    # EXACT structural rule, measured on ULokiAbilitySystemComponent at .rdata
    # 0x0886E430 -- NOT a "nearest string" guess (that first version invented
    # 'ELegendPosition' for APawn and 'Engine' for AActor):
    #     +0x00 UClass*(*OuterRegister)()   == the class's Z_Construct stub
    #     +0x08 UClass*(*InnerRegister)()   -- must ALSO be a code pointer
    #     +0x10 const TCHAR* Name           -- UTF-16, the class name
    def class_name_at(cstub):
        for slot in ptr_slots.get(cstub, ()):
            try:
                inner = rva(struct.unpack_from("<Q", d, slot + 0x08)[0])
                namep = rva(struct.unpack_from("<Q", d, slot + 0x10)[0])
            except struct.error:
                continue
            if not (TLO <= inner < THI):
                continue
            si = s_at.get(namep)
            if si is None or idx.s_enc[si] != ord("U"):
                continue
            t = idx.text_of(si, d)
            if CLSNAME.match(t):
                return t
        return ""

    cstubs = set(fn_class.values())
    class_name = {}
    for cstub in cstubs:
        t = class_name_at(cstub)
        if t:
            class_name[cstub] = t
    print("classes with a recovered name        : %d / %d  (exact +0x10 rule)"
          % (len(class_name), len(cstubs)))

    # ---- emit ------------------------------------------------------------
    syms = {}

    def put(r, nm, cls, kind, **kw):
        e = syms.setdefault(r, {"names": [], "class": "", "kind": kind})
        if nm not in e["names"]:
            e["names"].append(nm)
        if cls and not e["class"]:
            e["class"] = cls
        e.update(kw)

    for nm, fn in link_info:
        c = class_name.get(fn_class.get(fn, -1), "")
        extra = {}
        if fn in fn_flags:
            extra = {"flags": "0x%08X" % fn_flags[fn], "params": "0x%08X" % fn_params[fn]}
        put(fn, nm, c, "Z_Construct_UFunction", **extra)

    # ---- .data native-registration table: name -> EXEC THUNK ---------------
    # Layout, measured (stride 0x48, entries at .data 0x09BA1540+):
    #     +0x00 const char* Name      +0x08 exec thunk      +0x10 secondary fn
    # This is the table the project actually cares about: the exec thunk is the
    # value `UFunction.Func @ +0xE0` holds, i.e. exactly what the game-thread
    # native-call primitive invokes.
    #
    # VALIDATED against docs/session-100-gas-api-dump.txt, captured LIVE months
    # ago by usmapdump: 1,404 of its `thunk=` values resolve, 0 mismatch, under a
    # SINGLE 64K-aligned module base 0x7FF6E7D30000 recovered from the data
    # itself.  That base was never recorded anywhere, so it is also the key that
    # converts every absolute address in that dump into an RVA.
    #
    # The +0x10 pointer is NOT reliably the C++ implementation: measured, the exec
    # thunk calls it in only 33.8% of 2,621 sampled entries, so it is emitted as
    # "secondary" and nothing is claimed about it.
    dlo, dhi2 = sec[".data"]
    qd = array.array("Q")
    qd.frombytes(d[dlo:dlo + ((dhi2 - dlo) // 8) * 8])
    native_exec = []
    for k in range(len(qd) - 2):
        a, b, c = rva(qd[k]), rva(qd[k + 1]), rva(qd[k + 2])
        if a < 0 or b < 0 or c < 0:
            continue
        si = s_at.get(a)
        if si is None or idx.s_enc[si] != ord("A"):
            continue
        if TLO <= b < THI and TLO <= c < THI:
            native_exec.append((idx.text_of(si, d), b, c))
    print("native exec-thunk entries (.data)    : %d  (%d distinct names)"
          % (len(native_exec), len({n for n, _b, _c in native_exec})))

    # Join the class in from the link-info side: a UFunction name that belongs to
    # exactly ONE class there names the exec thunk's class unambiguously.  Names
    # shared across classes (Tick, IsValid, GetName...) are left blank rather than
    # guessed.
    name_cls = defaultdict(set)
    for nm, fn in link_info:
        c = class_name.get(fn_class.get(fn, -1), "")
        if c:
            name_cls[nm].add(c)
    joined = 0
    impl = {}
    for nm, ex, second in native_exec:
        cs = name_cls.get(nm, ())
        c = next(iter(cs)) if len(cs) == 1 else ""
        if c:
            joined += 1
        put(ex, nm, c, "exec_thunk", secondary="0x%07X" % second)
    print("exec thunks with an unambiguous class: %d / %d" % (joined, len(native_exec)))

    out = {"%#09x" % r: v for r, v in sorted(syms.items())}
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump({"symbols": out,
                   "native_exec_count": len(native_exec),
                   "stats": {"link_info": len(link_info), "native_pair": len(native_pair),
                             "verified": verified, "mismatch": mismatch,
                             "classes": len(class_name), "distinct_rvas": len(syms)}},
                  f, indent=1)
    print("distinct code RVAs named             : %d" % len(syms))
    
    print("-> %s" % OUT)


if __name__ == "__main__":
    main()
