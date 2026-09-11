#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""AngelScript bytecode: decode -> symbolic lift -> structured pseudo-source.

The stream stored in PrecompiledScript.Cache is the RAW IN-MEMORY asDWORD array
straight out of asCScriptFunction::scriptData->byteCode. It is NOT AngelScript's
portable asCWriter form: there are no varints and no "used function/type/string"
index tables. Pointer operands are the save-time heap addresses -- useless as
addresses, exact as identity keys into the cache's own trailer tables.

Three layers:
  decode()     -- strict linear decode; raises LiftError with a byte offset
  Lifter       -- symbolic execution of the stack machine, per basic block
  structure()  -- interval-based if/else + loop recovery, source order preserved

CALLING CONVENTION (established from the bytes, not assumed):
    args are pushed LAST-parameter-first, and the object pointer is pushed LAST,
    so at the call the stack reads  top -> [this][param0][param1]...[paramN-1].
    Proof: UFFABotSpawnerComponent::BeginPlay does
        PSF v4 ; PshVPtr this ; ADDSi .AvailableBots ; CALLSYS TArray::Add
    i.e. `this.AvailableBots` is on top and `v4` (the value being added) is below,
    which is `this.AvailableBots.Add(v4)`.

DEGRADE-GRACEFULLY POLICY: decode() is strict (a desync must be loud); the lifter
never aborts a function -- an unmodelled opcode emits a visible `asm(...)` line.
"""
import struct

import opcode_table as T

__all__ = ["LiftError", "decode", "Ins", "Lifter", "lift_function", "render_asm"]


class LiftError(Exception):
    pass


JUMP_OPS = frozenset(["JMP", "JZ", "JNZ", "JS", "JNS", "JP", "JNP",
                      "JLowZ", "JLowNZ"])
COND_JUMPS = JUMP_OPS - {"JMP"}
TERMINATORS = JUMP_OPS | {"RET", "JMPP"}


class Ins(object):
    __slots__ = ("off", "op", "name", "size", "args", "target")

    def __init__(self, off, op, name, size, args):
        self.off, self.op, self.name, self.size, self.args = off, op, name, size, args
        self.target = None

    def __repr__(self):
        return "<%04x %s %r>" % (self.off, self.name, self.args)


def decode(bc, where=""):
    out = []
    off, end = 0, len(bc)
    if end % 4:
        raise LiftError("%s: bytecode length %d is not a multiple of 4" % (where, end))
    while off < end:
        op = bc[off]
        info = T.OPCODES.get(op)
        if info is None or op >= T.MAXBYTECODE:
            raise LiftError("%s: invalid opcode %d (0x%02x) at byte 0x%x of %d"
                            % (where, op, op, off, end))
        name, ty, size, _stk = info
        if size == 0:
            raise LiftError("%s: pseudo-instruction %s at 0x%x cannot appear in a "
                            "serialized stream" % (where, name, off))
        if off + size * 4 > end:
            raise LiftError("%s: %s at 0x%x (%d dwords) overruns blob end %d"
                            % (where, name, off, size, end))
        args = {}
        for fld, boff, kind in T.TYPE_LAYOUT[ty]:
            if kind == "s16":
                args[fld] = struct.unpack_from("<h", bc, off + boff)[0]
            elif kind == "i32":
                args[fld] = struct.unpack_from("<i", bc, off + boff)[0]
            else:
                args[fld] = struct.unpack_from("<Q", bc, off + boff)[0]
        ins = Ins(off, op, name, size, args)
        if name in JUMP_OPS:
            ins.target = off + 8 + args["DW"] * 4     # dword-relative to NEXT insn
            if ins.target < 0 or ins.target > end or ins.target % 4:
                raise LiftError("%s: %s at 0x%x targets 0x%x, outside [0,%d]"
                                % (where, name, off, ins.target, end))
        out.append(ins)
        off += size * 4
    if off != end:
        raise LiftError("%s: decode landed at %d, expected %d" % (where, off, end))
    starts = set(i.off for i in out)
    starts.add(end)
    for i in out:
        if i.target is not None and i.target not in starts:
            raise LiftError("%s: %s at 0x%x targets 0x%x, not an instruction boundary"
                            % (where, i.name, i.off, i.target))
    return out


# ---------------------------------------------------------------------------
WIDE_TOKENS = frozenset([71, 78, 81, 94])   # int64, uint64, float64, double


def stack_width(dt):
    """asCDataType::GetSizeOnStackDWords, x64 (AS_PTR_SIZE == 2)."""
    if dt.is_ref or dt.type_info:
        return 2
    return 2 if dt.token in WIDE_TOKENS else 1


def returns_on_stack(cache, binds, dt):
    """asCScriptFunction::DoesReturnOnStack(): true only for a VALUE type
    returned neither by reference nor as a handle. Such a call takes a hidden
    pointer to a caller-allocated temp.

    ENUMS have type info in AngelScript but are asOBJ_ENUM, not asOBJ_VALUE, so
    they do NOT return on the stack -- getting this wrong eats an argument and
    silently shifts the whole call. Reference types (script classes, engine
    UCLASSes) can only be returned as handles, so they are excluded too.
    """
    if not dt.type_info or dt.handle or dt.is_ref:
        return False
    tr = cache.type_refs.get(dt.type_info)
    if tr is None:
        return False
    n = tr.name
    if n in cache.script_enums or n in cache.script_classes:
        return False
    if binds is not None:
        if n in binds.struct_names:
            return True
        if n in binds.class_names:
            return False
    # Engine enums are not in Binds.Cache as types; every remaining unclassified
    # name in this corpus is either E<Upper>... (an enum) or an F-struct/T-template.
    return not (len(n) > 1 and n[0] == "E" and n[1].isupper())


def param_offsets(param_types, is_method):
    """asCCompiler's parameter slot assignment.

    `this` (methods only) sits at variable offset 0; parameters march NEGATIVE,
    each starting where the previous left off:
        off[0] = -AS_PTR_SIZE if method else 0
        off[i] = off[i-1] - width(param[i-1])
    Verified against ALokiAirship_AS::Spawn: 5 params land on 0,-2,-4,-6,-7 with
    widths 2,2,2,1,2 -- exactly the offsets its bytecode references.
    """
    pos = -2 if is_method else 0
    out = []
    for dt in param_types:
        out.append(pos)
        pos -= stack_width(dt)
    return out


class E(object):
    __slots__ = ("s", "prec")

    def __init__(self, s, prec=100):
        self.s, self.prec = s, prec

    def p(self, need):
        return "(%s)" % self.s if self.prec < need else self.s

    def __str__(self):
        return self.s


UNKNOWN = "<?>"


def _f32(bits):
    return struct.unpack("<f", struct.pack("<I", bits & 0xFFFFFFFF))[0]


def _fmt_f(v):
    if v == int(v) and abs(v) < 1e15:
        return "%.1f" % v
    return "%g" % v


# AngelScript behaviour ids -> the "$behN" internal names it registers.
BEHAVIOUR = {0: "construct", 1: "list_construct", 2: "destruct", 3: "factory",
             4: "list_factory", 5: "addref", 6: "release", 7: "get_weakref",
             8: "template_callback", 9: "first_gc", 10: "getrefcount"}
SILENT_BEHAVIOURS = frozenset(["$beh2", "$beh5", "$beh6"])   # destruct/addref/release
CTOR_BEHAVIOURS = frozenset(["$beh0", "$beh1", "$beh3", "$beh4"])

BINARY_OPS = {"opAdd": "+", "opSub": "-", "opMul": "*", "opDiv": "/",
              "opMod": "%", "opAnd": "&", "opOr": "|", "opXor": "^",
              "opShl": "<<", "opShr": ">>", "opPow": "**",
              "opAdd_r": "+", "opSub_r": "-", "opMul_r": "*", "opDiv_r": "/"}
ASSIGN_OPS = {"opAssign": "=", "opAddAssign": "+=", "opSubAssign": "-=",
              "opMulAssign": "*=", "opDivAssign": "/=", "opModAssign": "%=",
              "opAndAssign": "&=", "opOrAssign": "|=", "opXorAssign": "^="}


class Lifter(object):
    BINOP = {
        "ADDi": "+", "SUBi": "-", "MULi": "*", "DIVi": "/", "MODi": "%",
        "ADDu": "+", "SUBu": "-", "MULu": "*", "DIVu": "/", "MODu": "%",
        "ADDf": "+", "SUBf": "-", "MULf": "*", "DIVf": "/", "MODf": "%",
        "ADDd": "+", "SUBd": "-", "MULd": "*", "DIVd": "/", "MODd": "%",
        "ADDi64": "+", "SUBi64": "-", "MULi64": "*", "DIVi64": "/", "MODi64": "%",
        "DIVu64": "/", "MODu64": "%", "ADDu64": "+", "SUBu64": "-", "MULu64": "*",
        "BAND": "&", "BOR": "|", "BXOR": "^", "BSLL": "<<", "BSRL": ">>",
        "BSRA": ">>", "BAND64": "&", "BOR64": "|", "BXOR64": "^",
        "BSLL64": "<<", "BSRL64": ">>", "BSRA64": ">>",
        "POWi": "**", "POWu": "**", "POWf": "**", "POWd": "**",
        "POWi64": "**", "POWu64": "**", "POWdi": "**",
    }
    BINOP_IMM = {"ADDIi": ("+", "i"), "SUBIi": ("-", "i"), "MULIi": ("*", "i"),
                 "ADDIf": ("+", "f"), "SUBIf": ("-", "f"), "MULIf": ("*", "f")}
    UNOP = {"NEGi": "-", "NEGf": "-", "NEGd": "-", "NEGi64": "-",
            "BNOT": "~", "BNOT64": "~"}
    CONVERT = {
        "iTOf": "float32", "fTOi": "int", "uTOf": "float32", "fTOu": "uint",
        "sbTOi": "int", "swTOi": "int", "ubTOi": "int", "uwTOi": "int",
        "iTOb": "int8", "iTOw": "int16", "i64TOi": "int", "uTOi64": "int64",
        "iTOi64": "int64", "fTOd": "float64", "dTOf": "float32",
        "dTOi": "int", "dTOu": "uint", "dTOi64": "int64", "dTOu64": "uint64",
        "i64TOf": "float32", "u64TOf": "float32", "i64TOd": "float64",
        "iTOd": "float64", "uTOd": "float64",
        "u64TOd": "float64", "fTOi64": "int64", "fTOu64": "uint64",
    }
    CMP = {"CMPi", "CMPu", "CMPf", "CMPd", "CMPi64", "CMPu64"}
    CMP_IMM = {"CMPIi": "i", "CMPIu": "u", "CMPIf": "f"}

    def __init__(self, cache, binds, func, owner_class=None):
        self.c, self.b, self.f = cache, binds, func
        self.owner = owner_class
        self.is_method = bool(owner_class) and func.kind in ("method", "ctor",
                                                             "behavior")
        self.unhandled = {}
        self.stack_warnings = 0
        # VM registers persist for the whole function, not per block
        self.cond = None
        self.valreg = self.objreg = self.refreg = None
        self.pending = None
        self.pending_pure = False
        self.out = []
        self.stk = []
        self.varname, self.vartype = {}, {}
        offs = param_offsets(func.param_types, self.is_method)
        for i, o in enumerate(offs):
            nm = func.param_names[i] if i < len(func.param_names) else ""
            self.varname[o] = nm or ("arg%d" % i)
            self.vartype[o] = cache.type_name(func.param_types[i])
        if self.is_method:
            self.varname[0] = "this"
            self.vartype[0] = owner_class.name
        for pos, tp in zip(func.obj_var_pos, func.obj_var_types):
            tr = cache.type_refs.get(tp)
            if tr and pos not in self.vartype:
                self.vartype[pos] = tr.name

    # ---- naming -----------------------------------------------------------
    def v(self, off):
        if off in self.varname:
            return self.varname[off]
        return "v%d" % off if off >= 0 else "arg_m%d" % (-off)

    def gname(self, ptr):
        g = self.c.global_refs.get(ptr)
        if g is None:
            return None
        if g.is_string:
            return '"%s"' % g.name.replace("\\", "\\\\").replace('"', '\\"')
        if g.namespace:
            return "%s::%s" % (g.namespace, g.name)
        return g.name

    def tname(self, ptr):
        tr = self.c.type_refs.get(ptr)
        return tr.name if tr else "type@%x" % (ptr & 0xFFFFFFFFFFFF)

    def tid_name(self, tid):
        tr = self.c.type_of_id(tid)
        if tr:
            return tr.name
        for mask in (0x60000000, 0x40000000, 0x20000000):
            tr = self.c.type_of_id(tid & ~mask)
            if tr:
                return tr.name + ("@" if tid & 0x40000000 else "")
        return "typeid_0x%08x" % (tid & 0xFFFFFFFF)

    def prop_name(self, type_id, offset):
        pr = self.c.prop_of(type_id, offset)
        return pr.name if pr else None

    # ---- emission ---------------------------------------------------------
    def emit(self, text):
        self.out.append(text)

    def flush_pending(self):
        if self.pending is not None:
            if not self.pending_pure:
                self.emit(self.pending + ";")
            self.pending = None
        self.pending_pure = False

    def push(self, e):
        self.stk.append(e if isinstance(e, E) else E(str(e)))

    def pop(self):
        if not self.stk:
            self.stack_warnings += 1
            return E(UNKNOWN)
        return self.stk.pop()

    def note(self, name):
        self.unhandled[name] = self.unhandled.get(name, 0) + 1

    # ---- driver -----------------------------------------------------------
    def run_block(self, insns, carry_cond=None, carry_stack=None):
        self.out = []
        self.stk = list(carry_stack) if carry_stack else []
        self.pending = None
        self.pending_pure = False
        if carry_cond is not None:
            self.cond = carry_cond
        for ins in insns:
            try:
                self.step(ins)
            except Exception as ex:
                self.note(ins.name)
                self.flush_pending()
                self.emit("asm(%s)  /* lifter: %s */" % (self.raw(ins), ex))
        # A trailing call whose ONLY consumer is this block's conditional jump
        # must not also be emitted as a statement -- it would read as if the call
        # happened twice.
        if self.pending is not None and self.cond is not None \
                and self.cond[0] == self.pending and insns[-1].name in COND_JUMPS:
            self.pending = None
        self.flush_pending()
        return self.out, self.cond, list(self.stk), self.ret_value()

    def raw(self, ins):
        parts = []
        for k, val in ins.args.items():
            if k == "QW":
                nm = self.gname(val)
                if nm is None and val in self.c.func_refs:
                    nm = self.c.func_refs[val].name
                if nm is None and val in self.c.type_refs:
                    nm = self.c.type_refs[val].name
                parts.append("%s=%s" % (k, nm if nm else "0x%x" % val))
            else:
                parts.append("%s=%d" % (k, val))
        return "%s %s" % (ins.name, " ".join(parts))

    def step(self, ins):
        n, a = ins.name, ins.args
        h = getattr(self, "op_" + n, None)
        if h is not None:
            return h(ins, a)
        if n in self.BINOP:
            self.emit("%s = %s %s %s;" % (self.v(a["wW0"]), self.v(a["rW1"]),
                                          self.BINOP[n], self.v(a["rW2"])))
            return
        if n in self.BINOP_IMM:
            o, kind = self.BINOP_IMM[n]
            imm = _fmt_f(_f32(a["DW"])) if kind == "f" else str(a["DW"])
            self.emit("%s = %s %s %s;" % (self.v(a["wW0"]), self.v(a["rW1"]), o, imm))
            return
        if n in self.UNOP:
            dst = a.get("wW0", a.get("rW0"))
            src = a.get("rW1", a.get("rW0"))
            self.emit("%s = %s%s;" % (self.v(dst), self.UNOP[n], self.v(src)))
            return
        if n in self.CONVERT:
            dst = a.get("wW0", a.get("rW0"))
            src = a.get("rW1", a.get("rW0"))
            self.emit("%s = %s(%s);" % (self.v(dst), self.CONVERT[n], self.v(src)))
            return
        if n in self.CMP:
            self.cond = (self.v(a["rW0"]), self.v(a["rW1"]))
            return
        if n in self.CMP_IMM:
            k = self.CMP_IMM[n]
            imm = _fmt_f(_f32(a["DW"])) if k == "f" else str(a["DW"])
            self.cond = (self.v(a["rW0"]), imm)
            return
        self.note(n)
        self.flush_pending()
        self.emit("asm(%s)" % self.raw(ins))

    # ---- pushes -----------------------------------------------------------
    def op_PshC4(self, i, a):
        self.push(E(str(a["DW"])))

    def op_PshC8(self, i, a):
        self.push(E(str(a["QW"])))

    def op_PshV4(self, i, a):
        self.push(E(self.v(a["rW0"])))

    op_PshV8 = op_PshVPtr = op_PSF = op_VAR = op_PshV4

    def op_PshNull(self, i, a):
        self.push(E("nullptr"))

    def op_PshGPtr(self, i, a):
        self.push(E(self.gname(a["QW"]) or "global_%x" % a["QW"]))

    op_PshG4 = op_PGA = op_PshGPtr

    def op_PshRPtr(self, i, a):
        self.push(E(self.pending or self.valreg or self.refreg or "valueReg"))

    def op_OBJTYPE(self, i, a):
        self.push(E(self.tname(a["QW"])))

    def op_TYPEID(self, i, a):
        self.push(E("typeid(%s)" % self.tid_name(a["DW"])))

    def op_FuncPtr(self, i, a):
        fr = self.c.func_refs.get(a["QW"])
        self.push(E("&%s" % (fr.name if fr else "func_%x" % a["QW"])))

    def op_PopPtr(self, i, a):
        if self.stk:
            self.stk.pop()

    def op_SwapPtr(self, i, a):
        if len(self.stk) >= 2:
            self.stk[-1], self.stk[-2] = self.stk[-2], self.stk[-1]

    def op_PopRPtr(self, i, a):
        self.refreg = str(self.pop())

    def _nop(self, i, a):
        pass

    op_ClrHi = op_SUSPEND = op_CHKREF = op_ChkNullV = op_ChkNullS = _nop
    op_ResolveObjectPtr = op_SaveReturnValue = op_JitEntry = _nop
    op_TrackRef = op_UntrackRef = op_ValidateRef = _nop
    op_FREE = op_FreeNullV8 = op_DestructScript = op_FinConstruct = _nop
    op_CopyScript = op_GETOBJ = op_GETOBJREF = op_GETREF = _nop
    op_JMP = op_JZ = op_JNZ = op_JS = op_JNS = _nop
    op_JP = op_JNP = op_JLowZ = op_JLowNZ = _nop

    def ret_value(self, consume=False):
        """What this function would return right now: the value register for
        primitives, the object register for handles. A by-value object return was
        written straight into the caller-supplied temp, so there is nothing to
        name. Returns None for a void function."""
        rt = self.f.ret
        if rt.token == 82 and not rt.type_info:
            return None
        if self.pending is not None:
            val = self.pending
            if consume:
                self.pending = None
            return val
        if returns_on_stack(self.c, self.b, rt):
            return ""            # written into the hidden destination temp
        if rt.type_info and (rt.handle or rt.is_ref):
            return self.objreg or self.valreg
        return self.valreg or self.objreg

    def op_RET(self, i, a):
        val = self.ret_value(consume=True)
        self.emit("return %s;" % val if val else "return;")

    def op_ClrVPtr(self, i, a):
        self.emit("%s = nullptr;" % self.v(a["wW0"]))

    def op_RDSPtr(self, i, a):
        self.push(self.pop())          # dereference; reads the same in source

    # ---- member access ----------------------------------------------------
    def op_ADDSi(self, i, a):
        top = self.pop()
        nm = self.prop_name(a["DW"], a["W0"])
        self.push(E("%s.%s" % (top.p(90), nm or "field_%d" % a["W0"]), 90))

    def op_LoadThisR(self, i, a):
        nm = self.prop_name(a["DW"], a["W0"])
        self.refreg = "this.%s" % (nm or "field_%d" % a["W0"])

    def op_LoadRObjR(self, i, a):
        nm = self.prop_name(a["DW"], a["W1"])
        self.refreg = "%s.%s" % (self.v(a["rW0"]), nm or "field_%d" % a["W1"])

    op_LoadVObjR = op_LoadRObjR

    def op_LDV(self, i, a):
        self.refreg = self.v(a["rW0"])

    def op_LDG(self, i, a):
        self.refreg = self.gname(a["QW"]) or "global_%x" % a["QW"]

    # ---- moves ------------------------------------------------------------
    def _setv(self, a, val):
        self.emit("%s = %s;" % (self.v(a["wW0"]), val))

    def op_SetV1(self, i, a):
        d = a["DW"] & 0xFF
        self._setv(a, "true" if d == 1 else ("false" if d == 0 else str(d)))

    def op_SetV2(self, i, a):
        self._setv(a, str(a["DW"] & 0xFFFF))

    def op_SetV4(self, i, a):
        self._setv(a, str(a["DW"]))

    def op_SetV8(self, i, a):
        self._setv(a, str(a["QW"]))

    def op_SetVPtr(self, i, a):
        self._setv(a, "nullptr")

    def op_CpyVtoV4(self, i, a):
        self._setv(a, self.v(a["rW1"]))

    op_CpyVtoV8 = op_CpyVtoV4

    def op_CpyVtoR1(self, i, a):
        self.valreg = self.v(a["rW0"])
        self.cond = (self.valreg, None)

    op_CpyVtoR4 = op_CpyVtoR8 = op_CpyVtoR1

    def op_CpyRtoV4(self, i, a):
        src = self.pending if self.pending is not None else (self.valreg or "valueReg")
        self.pending = None
        dst = self.v(a["wW0"])
        self.emit("%s = %s;" % (dst, src))
        # the value now LIVES in dst -- a later reader must name the variable, not
        # re-print the call expression (that reads as if the call happened twice)
        self.valreg = self.objreg = dst

    op_CpyRtoV8 = op_CpyRtoV4

    def op_CpyVtoG4(self, i, a):
        self.emit("%s = %s;" % (self.gname(a["QW"]) or "global", self.v(a["rW0"])))

    def op_CpyGtoV4(self, i, a):
        self._setv(a, self.gname(a["QW"]) or "global")

    def op_SetG4(self, i, a):
        self.emit("%s = %d;" % (self.gname(a["QW"]) or "global", a["DW"]))

    def op_LdGRdR4(self, i, a):
        self._setv(a, self.gname(a["QW"]) or "global")

    def op_LOADOBJ(self, i, a):
        self.objreg = self.v(a["rW0"])

    def op_STOREOBJ(self, i, a):
        src = self.pending if self.pending is not None else (self.objreg or "objReg")
        self.pending = None
        dst = self.v(a["wW0"])
        self.emit("%s = %s;" % (dst, src))
        self.objreg = self.valreg = dst

    def op_REFCPY(self, i, a):
        rhs = self.pop()
        lhs = self.pop()
        self.emit("%s = %s;" % (lhs, rhs))

    def op_RefCpyV(self, i, a):
        # RefCpyV pops a pointer off the stack and stores it with refcounting, so
        # the stack is the authoritative source when it has anything.
        if self.stk:
            src = str(self.pop())
        elif self.pending is not None:
            src, self.pending = self.pending, None
        else:
            src = self.objreg or "objReg"
        dst = self.v(a["wW0"])
        self.emit("%s = %s;" % (dst, src))
        self.objreg = self.valreg = dst

    def op_RDR1(self, i, a):
        self._setv(a, self.refreg or "*refReg")

    op_RDR2 = op_RDR4 = op_RDR8 = op_RDR1

    def op_WRTV1(self, i, a):
        self.emit("%s = %s;" % (self.refreg or "*refReg", self.v(a["rW0"])))

    op_WRTV2 = op_WRTV4 = op_WRTV8 = op_WRTV1

    def op_IncVi(self, i, a):
        self.emit("%s++;" % self.v(a["rW0"]))

    def op_DecVi(self, i, a):
        self.emit("%s--;" % self.v(a["rW0"]))

    op_IncVf = op_IncVi
    op_DecVf = op_DecVi

    def op_NOT(self, i, a):
        off = a.get("rW0", a.get("wW0"))
        self.emit("%s = !%s;" % (self.v(off), self.v(off)))
        self.cond = (self.v(off), None)

    # T-ops fold the three-way compare result in the value register down to a
    # 0/1 boolean, i.e. they are what turns `a < b` into an rvalue.
    def _test(self, op):
        lhs, rhs = self.cond if self.cond else ("cond", None)
        expr = ("%s %s %s" % (lhs, op, rhs)) if rhs is not None else \
               ("%s%s" % ("!" if op == "==" else "", lhs))
        self.valreg = expr
        self.cond = (expr, None)

    def op_TZ(self, i, a):
        self._test("==")

    def op_TNZ(self, i, a):
        self._test("!=")

    def op_TS(self, i, a):
        self._test("<")

    def op_TNS(self, i, a):
        self._test(">=")

    def op_TP(self, i, a):
        self._test(">")

    def op_TNP(self, i, a):
        self._test("<=")

    # INCx/DECx operate on the value POINTED TO by the value register.
    def _incdec(self, delta):
        self.emit("%s%s;" % (self.refreg or "*valueReg", "++" if delta > 0 else "--"))

    def op_INCi(self, i, a):
        self._incdec(1)

    op_INCi8 = op_INCi16 = op_INCi64 = op_INCf = op_INCd = op_INCi

    def op_DECi(self, i, a):
        self._incdec(-1)

    op_DECi8 = op_DECi16 = op_DECi64 = op_DECf = op_DECd = op_DECi

    def op_CmpPtr(self, i, a):
        self.cond = (self.v(a["rW0"]), self.v(a["rW1"]))

    def op_CmpPtrNull(self, i, a):
        self.cond = (self.v(a["rW0"]), "nullptr")

    def op_Cast(self, i, a):
        top = self.pop()
        e = "cast<%s>(%s)" % (self.tid_name(a["DW"]), top)
        self.push(E(e, 90))
        self.objreg = e

    def op_COPY(self, i, a):
        rhs = self.pop()
        lhs = self.pop()
        self.emit("%s = %s;" % (lhs, rhs))
        self.push(lhs)

    def op_ThrowException(self, i, a):
        self.emit("throw;  /* code %d */" % a["W0"])

    def op_JMPP(self, i, a):
        # The jump TABLE is the run of single-JMP blocks that follows; the
        # structurer turns them into real case labels.
        self.emit("switch (%s)" % self.v(a["rW0"]))

    # ---- allocation -------------------------------------------------------
    def op_ALLOC(self, i, a):
        tn = self.tname(a["QW"])
        fr = self.c.func_of_id(a["DW"])
        nargs = len(fr.param_types) if fr else 0
        args = [str(self.pop()) for _ in range(nargs)]
        dest = self.pop() if self.stk else E(UNKNOWN)
        self.emit("%s = %s(%s);" % (dest, tn, ", ".join(args)))
        self.objreg = str(dest)

    # ---- calls ------------------------------------------------------------
    def _do_call(self, fr, fallback):
        if fr is None:
            self.flush_pending()
            self.note("unresolved-call")
            self.emit("%s;" % fallback)
            return
        # top of stack is `this` (pushed last), then param0, param1, ...
        this = str(self.pop()) if (fr.is_method and fr.object_type) else None
        # A function returning an OBJECT BY VALUE (not a handle, not a reference)
        # takes a hidden pointer to the destination temp. asCCompiler pushes it
        # AFTER the arguments and then SwapPtr's it under the object pointer, so
        # it sits below `this` and above every real argument:
        #     PSF v18 ; PSF v8 ; CALLSYS TArray::Iterator          -> v18 = v8.Iterator()
        #     PshV4 TeamIndex ; PshGPtr __WorldContext ; PSF v8 ;
        #       CALLSYS GetPlayerStatesOnTeam   -> v8 = GetPlayerStatesOnTeam(__WorldContext, TeamIndex)
        byval_dest = None
        if returns_on_stack(self.c, self.b, fr.ret):
            byval_dest = str(self.pop())
        nargs = len(fr.param_types)
        extra = sum(1 for p in fr.param_types if not p.type_info and p.token == 59)
        args = [str(self.pop()) for _ in range(nargs + extra)]
        owner = ""
        if fr.object_type:
            tr = self.c.type_refs.get(fr.object_type)
            owner = tr.name if tr else ""
        name = fr.name
        is_void = (fr.ret.token == 82 and not fr.ret.type_info)

        # -- behaviours and operators read far better as syntax -------------
        if name == "__STATIC_NAME" and len(args) == 1 and args[0].lstrip("-").isdigit():
            idx = int(args[0])
            names = self.c.static_names
            lit = ('n"%s"' % names[idx]) if 0 <= idx < len(names)                 else "__STATIC_NAME(%d)" % idx
            self.flush_pending()
            self.pending = lit
            self.pending_pure = True       # a name literal is not a statement
            self.objreg = self.valreg = lit
            return
        if name in SILENT_BEHAVIOURS:
            return                                   # destruct/addref/release noise
        if name in CTOR_BEHAVIOURS and this is not None:
            self.flush_pending()
            self.emit("%s = %s(%s);" % (this, owner or "ctor", ", ".join(args)))
            return
        if name in ASSIGN_OPS and this is not None and len(args) == 1:
            self.flush_pending()
            self.emit("%s %s %s;" % (this, ASSIGN_OPS[name], args[0]))
            self.pending = None
            self.objreg = this
            return
        if name in BINARY_OPS and this is not None and len(args) == 1:
            call = "%s %s %s" % (this, BINARY_OPS[name], args[0])
        elif name == "opIndex" and this is not None and len(args) == 1:
            call = "%s[%s]" % (this, args[0])
        elif name == "opEquals" and this is not None and len(args) == 1:
            call = "%s == %s" % (this, args[0])
        elif name == "opNeg" and this is not None:
            call = "-%s" % this
        elif name in ("opCast", "opImplCast") and this is not None \
                and len(args) == 2 and args[1].startswith("typeid("):
            # opCast(?&out) -- the destination and the target typeid are both on
            # the stack, so this reconstructs to a real named cast.
            self.flush_pending()
            self.emit("%s = cast<%s>(%s);" % (args[0], args[1][7:-1], this))
            self.objreg = args[0]
            return
        elif name in ("opConv", "opImplConv", "opCast", "opImplCast") and this:
            call = "%s(%s)" % (self.c.type_name(fr.ret), this)
        else:
            alias = ""
            if owner and self.b is not None:
                u = self.b.ufunction_name(owner, name)
                if u and u != name:
                    alias = "  /* UFunction %s */" % u
            if this is not None:
                call = "%s.%s(%s)%s" % (this, name, ", ".join(args), alias)
            elif owner:
                call = "%s::%s(%s)%s" % (owner, name, ", ".join(args), alias)
            else:
                ns = (fr.namespace + "::") if fr.namespace else ""
                call = "%s%s(%s)%s" % (ns, name, ", ".join(args), alias)
        pure = name in ("opIndex", "opEquals") or name in BINARY_OPS
        self.flush_pending()
        if byval_dest is not None:
            self.emit("%s = %s;" % (byval_dest, call))
            self.objreg = byval_dest
        elif is_void:
            self.emit(call + ";")
        else:
            self.pending = call
            self.pending_pure = pure
            self.objreg = self.valreg = call
            self.cond = (call, None)

    def op_CALLSYS(self, i, a):
        self._do_call(self.c.func_refs.get(a["QW"]), "sysfunc_%x()" % a["QW"])

    op_Thiscall1 = op_CALLSYS

    def op_CALL(self, i, a):
        self._do_call(self.c.func_of_id(a["DW"]), "script_func_%d()" % a["DW"])

    op_CALLINTF = op_CALLBND = op_CALL


# ---------------------------------------------------------------------------
# control flow
# ---------------------------------------------------------------------------
COND_TEXT = {
    "JZ":     ("%s == %s", "%s != %s"),
    "JNZ":    ("%s != %s", "%s == %s"),
    "JS":     ("%s < %s",  "%s >= %s"),
    "JNS":    ("%s >= %s", "%s < %s"),
    "JP":     ("%s > %s",  "%s <= %s"),
    "JNP":    ("%s <= %s", "%s > %s"),
    "JLowZ":  ("!%s", "%s"),
    "JLowNZ": ("%s", "!%s"),
}


def render_cond(jump_name, cond, taken):
    """Condition text. taken=True renders 'the branch is taken'."""
    pair = COND_TEXT.get(jump_name)
    if pair is None:
        return "cond"
    fmt = pair[0] if taken else pair[1]
    lhs, rhs = (cond if cond else ("cond", None))
    if rhs is None:
        one = fmt.replace("%s == %s", "!%s").replace("%s != %s", "%s")
        if one.count("%s") == 1:
            return one % lhs
        return ("%s" if taken else "!%s") % lhs
    if fmt.count("%s") == 1:
        return fmt % lhs
    return fmt % (lhs, rhs)


class Block(object):
    __slots__ = ("start", "insns", "succ", "stmts", "cond", "term", "label",
                 "ret_expr")

    def __init__(self, start):
        self.start = start
        self.insns, self.succ, self.stmts = [], [], []
        self.cond = self.term = self.ret_expr = None
        self.label = "L%04X" % start


def build_blocks(insns, end):
    leaders = {0}
    for idx, i in enumerate(insns):
        if i.target is not None:
            leaders.add(i.target)
        if i.name in TERMINATORS and idx + 1 < len(insns):
            leaders.add(insns[idx + 1].off)
    leaders = sorted(x for x in leaders if x < end)
    blocks = dict((s, Block(s)) for s in leaders)
    order = [blocks[s] for s in leaders]
    nxt = dict((leaders[k], leaders[k + 1] if k + 1 < len(leaders) else end)
               for k in range(len(leaders)))
    cur = None
    for i in insns:
        if i.off in blocks:
            cur = blocks[i.off]
        cur.insns.append(i)
    for b in order:
        last = b.insns[-1]
        b.term = last.name
        fall = nxt[b.start]
        if last.name == "RET" or last.name == "JMPP":
            b.succ = []
        elif last.name == "JMP":
            b.succ = [last.target]
        elif last.name in COND_JUMPS:
            b.succ = [fall, last.target]        # [fallthrough, taken]
        elif fall < end:
            b.succ = [fall]
    return order, blocks


class Structurer(object):
    """Interval-based structurer.

    Emits blocks in LAYOUT ORDER -- which for an AngelScript-compiled function is
    source order -- and recognises three shapes: natural loops, if-then, and
    if-then-else. Anything that does not fit becomes an explicit labelled goto
    rather than being reordered or dropped. That trade favours never lying about
    control flow over always producing pretty braces.
    """

    def __init__(self, order, blocks, indent="    "):
        self.order = order
        self.blocks = blocks
        self.idx = dict((b.start, k) for k, b in enumerate(order))
        self.indent = indent
        self.lines = []
        self.label_at = {}     # block start -> index into self.lines
        self.referenced = set()
        self.loopstack = []    # (header_start, exit_index)

    def run(self, depth=1):
        self.emit_range(0, len(self.order), depth)
        # insert labels only where a goto actually points
        for start in sorted(self.referenced, reverse=True,
                            key=lambda s: self.label_at.get(s, -1)):
            pos = self.label_at.get(start)
            if pos is None:
                continue
            self.lines.insert(pos, "%s:" % self.blocks[start].label)
        return self.lines

    def out(self, depth, text):
        self.lines.append(self.indent * depth + text)

    def goto(self, depth, start, kw="goto"):
        for hdr, exit_i in reversed(self.loopstack):
            if start == hdr:
                self.out(depth, "continue;")
                return
            if exit_i is not None and exit_i < len(self.order) \
                    and self.order[exit_i].start == start:
                self.out(depth, "break;")
                return
        self.referenced.add(start)
        self.out(depth, "%s %s;" % (kw, self.blocks[start].label))

    def emit_range(self, lo, hi, depth, exit_target=None):
        i = lo
        guard = 0
        while i < hi and guard < 20000:
            guard += 1
            b = self.order[i]
            self.label_at.setdefault(b.start, len(self.lines))

            latch = self._find_latch(i, hi)
            if latch is not None:
                self._emit_loop(i, latch, hi, depth)
                i = latch + 1
                continue

            for s in b.stmts:
                self.out(depth, s)

            if b.term == "RET":
                i += 1          # the lifter already emitted `return ...;`
                continue
            if b.term == "JMPP":
                # AngelScript lays a computed switch out as JMPP followed by a
                # dense table of single-JMP blocks, one per case value.
                j = i + 1
                cases = []
                while j < hi and len(self.order[j].insns) == 1                         and self.order[j].term == "JMP":
                    cases.append(self.order[j].succ[0])
                    self.order[j].stmts = []
                    j += 1
                if cases:
                    self.out(depth, "{")
                    for n, tgt in enumerate(cases):
                        self.out(depth + 1, "case %d: goto %s;"
                                 % (n, self.blocks[tgt].label))
                        self.referenced.add(tgt)
                    self.out(depth, "}")
                    i = j
                    continue
                i += 1
                continue
            if b.term == "JMP":
                t = self.idx.get(b.succ[0])
                # PRE-TEST LOOP: an unconditional jump forward to the test block,
                # which conditionally jumps back to the instruction right after
                # this one. That is how AngelScript compiles `while`/`foreach`:
                #     JMP test ; body: ... ; test: <cond> ; Jcc body
                # Rendering it as do-while would be WRONG (do-while always runs
                # the body once), so emit the exact shape instead.
                if t is not None and i + 1 < t < hi:
                    latch = self._find_backedge(t, hi, self.order[i + 1].start)
                    if latch is not None:
                        self._emit_pretest_loop(i, t, latch, depth)
                        i = latch + 1
                        continue
                tb = self.blocks.get(b.succ[0])
                if tb is not None and tb.term == "RET" and self._ret_only(tb):
                    # `LOADOBJ x ; JMP ret_block` -- the return VALUE differs per
                    # path, so inline it rather than emit a goto that would show
                    # some other path's value.
                    self.out(depth, "return %s;" % b.ret_expr
                             if b.ret_expr else "return;")
                    i += 1
                    continue
                if t == i + 1 or (t is not None and t == hi)                         or b.succ[0] == exit_target:
                    i += 1
                    continue
                self.goto(depth, b.succ[0])
                i += 1
                continue
            if b.term in COND_JUMPS:
                i = self._emit_cond(i, hi, depth)
                continue
            i += 1

    def _is_last_overall(self, i):
        return i == len(self.order) - 1

    @staticmethod
    def _ret_only(b):
        real = [x for x in b.stmts if not x.startswith("return")]
        return not real

    def _find_latch(self, i, hi):
        hdr = self.order[i].start
        for k in range(hi - 1, i - 1, -1):
            if hdr in self.order[k].succ:
                return k
        return None

    def _find_backedge(self, lo, hi, target_start):
        for k in range(hi - 1, lo - 1, -1):
            if target_start in self.order[k].succ:
                return k
        return None

    def _emit_pretest_loop(self, i, t, latch, depth):
        """while (cond) { body }, compiled as JMP test / body / test / Jcc body.

        Rendered as an exact `while (true) { <test>; if (!cond) break; <body> }`
        rather than a prettier `while (cond)` -- the test statements are real
        code (e.g. `v21 = it.CanProceed;`) and must not be duplicated or dropped.
        """
        lb = self.order[latch]
        self.loopstack.append((self.order[t].start, latch + 1))
        self.out(depth, "while (true) {")
        self.emit_range(t, latch, depth + 1)
        self.label_at.setdefault(lb.start, len(self.lines))
        for s in lb.stmts:
            self.out(depth + 1, s)
        if lb.term in COND_JUMPS:
            self.out(depth + 1, "if (%s) break;" % render_cond(lb.term, lb.cond, False))
        self.emit_range(i + 1, t, depth + 1)
        self.out(depth, "}")
        self.loopstack.pop()

    def _emit_loop(self, i, latch, hi, depth):
        hdr = self.order[i]
        exit_i = latch + 1
        # while (cond) { body }  -- header is a 2-way whose taken edge leaves
        if hdr.term in COND_JUMPS and self.idx.get(hdr.succ[1]) == exit_i \
                and not hdr.stmts[:0]:
            self.loopstack.append((hdr.start, exit_i))
            for s in hdr.stmts:
                self.out(depth, s)
            self.out(depth, "while (%s) {" % render_cond(hdr.term, hdr.cond, False))
            self.emit_range(i + 1, latch + 1, depth + 1)
            self.out(depth, "}")
            self.loopstack.pop()
            return
        # do { body } while (cond)  -- latch is the 2-way that jumps back
        lb = self.order[latch]
        if lb.term in COND_JUMPS and lb.succ[1] == hdr.start:
            self.loopstack.append((hdr.start, exit_i))
            self.out(depth, "do {")
            self.emit_range(i, latch, depth + 1)
            self.label_at.setdefault(lb.start, len(self.lines))
            for s in lb.stmts:
                self.out(depth + 1, s)
            self.out(depth, "} while (%s);" % render_cond(lb.term, lb.cond, True))
            self.loopstack.pop()
            return
        self.loopstack.append((hdr.start, exit_i))
        self.out(depth, "while (true) {")
        self.emit_range(i, latch + 1, depth + 1)
        self.out(depth, "}")
        self.loopstack.pop()

    def _emit_cond(self, i, hi, depth):
        b = self.order[i]
        t = self.idx.get(b.succ[1])
        if t is None or t <= i or t > hi:
            self.out(depth, "if (%s)" % render_cond(b.term, b.cond, True))
            self.goto(depth + 1, b.succ[1])
            return i + 1
        # then-region is [i+1, t); look for a trailing JMP that skips an else
        else_end = None
        if t - 1 > i:
            last = self.order[t - 1]
            if last.term == "JMP":
                e = self.idx.get(last.succ[0])
                if e is not None and t < e <= hi:
                    else_end = e
        if t == i + 1:
            # empty then-branch: invert and use the taken side as the body
            self.out(depth, "if (%s) {" % render_cond(b.term, b.cond, True))
            self.emit_range(t, else_end if else_end else hi, depth + 1,
                            self.order[else_end].start if else_end else None)
            self.out(depth, "}")
            return else_end if else_end else hi
        head = len(self.lines)
        self.out(depth, "if (%s) {" % render_cond(b.term, b.cond, False))
        self.emit_range(i + 1, t, depth + 1,
                        self.order[else_end].start if else_end is not None else None)
        if else_end is not None:
            if len(self.lines) == head + 1:
                # the then-branch collapsed to nothing (its only content was a
                # jump to the join). Invert instead of emitting `if (c) {} else`.
                self.lines[head] = (self.indent * depth + "if (%s) {"
                                    % render_cond(b.term, b.cond, True))
                self.emit_range(t, else_end, depth + 1)
                self.out(depth, "}")
                return else_end
            self.out(depth, "} else {")
            self.emit_range(t, else_end, depth + 1)
            self.out(depth, "}")
            return else_end
        if len(self.lines) == head + 1:
            self.lines.pop()          # `if (c) { }` with no else is pure noise
            return t
        self.out(depth, "}")
        return t


def structure(order, blocks, indent="    "):
    return Structurer(order, blocks, indent).run()


# ---------------------------------------------------------------------------
def lift_function(cache, binds, func, owner_class=None, want_pseudo=True):
    res = {"insns": [], "asm": [], "pseudo": [], "error": None,
           "unhandled": {}, "stack_warnings": 0, "structure_error": None}
    if func.bc_dwords == 0:
        return res
    where = "%s::%s" % (owner_class.name if owner_class else "", func.name)
    try:
        insns = decode(func.bytecode, where)
    except LiftError as e:
        res["error"] = str(e)
        return res
    res["insns"] = insns
    lf = Lifter(cache, binds, func, owner_class)
    res["asm"] = render_asm(insns, lf)
    if want_pseudo:
        try:
            order, blocks = build_blocks(insns, len(func.bytecode))
            # A value can be pushed in one block and consumed in the next (the
            # short-circuit && / || shapes do this). Carry the symbolic stack
            # forward ONLY across an unambiguous fallthrough -- one predecessor,
            # and it is the immediately preceding block in layout order.
            preds = {}
            for b in order:
                for s in b.succ:
                    preds.setdefault(s, []).append(b.start)
            carry_stack = None
            prev = None
            for b in order:
                p = preds.get(b.start, [])
                if not (prev is not None and p == [prev.start]
                        and b.start in prev.succ):
                    carry_stack = None
                b.stmts, b.cond, carry_stack, b.ret_expr =                     lf.run_block(b.insns, None, carry_stack)
                prev = b
            res["pseudo"] = structure(order, blocks)
        except Exception as e:
            res["structure_error"] = "%s: %s" % (type(e).__name__, e)
            res["pseudo"] = []
    res["unhandled"] = dict(lf.unhandled)
    res["stack_warnings"] = lf.stack_warnings
    return res


def render_asm(insns, lf):
    lines = []
    targets = set(i.target for i in insns if i.target is not None)
    for i in insns:
        if i.off in targets:
            lines.append("  L%04X:" % i.off)
        parts = []
        for k in ("wW0", "rW0", "W0", "rW1", "W1", "rW2", "DW", "DW1", "QW"):
            if k not in i.args:
                continue
            val = i.args[k]
            if k == "QW":
                nm = lf.gname(val)
                if nm is None and val in lf.c.func_refs:
                    fr = lf.c.func_refs[val]
                    ow = lf.c.type_refs.get(fr.object_type)
                    nm = ("%s::%s" % (ow.name, fr.name)) if ow else fr.name
                if nm is None and val in lf.c.type_refs:
                    nm = lf.c.type_refs[val].name
                parts.append(nm if nm else "0x%x" % val)
            elif k in ("wW0", "rW0", "rW1", "rW2"):
                parts.append(lf.v(val))
            else:
                parts.append(str(val))
        extra = ""
        if i.name == "ADDSi":
            p = lf.prop_name(i.args["DW"], i.args["W0"])
            extra = "  ; .%s" % p if p else ""
        elif i.name == "LoadThisR":
            p = lf.prop_name(i.args["DW"], i.args["W0"])
            extra = "  ; this.%s" % p if p else ""
        elif i.name in ("LoadRObjR", "LoadVObjR"):
            p = lf.prop_name(i.args["DW"], i.args["W1"])
            extra = "  ; .%s" % p if p else ""
        elif i.name in ("TYPEID", "Cast", "COPY"):
            extra = "  ; %s" % lf.tid_name(i.args["DW"])
        elif i.name in ("CALL", "CALLINTF", "CALLBND"):
            fr = lf.c.func_of_id(i.args["DW"])
            if fr:
                ow = lf.c.type_refs.get(fr.object_type)
                extra = "  ; %s" % (("%s::%s" % (ow.name, fr.name)) if ow else fr.name)
        if i.target is not None:
            extra = "  -> L%04X" % i.target
        lines.append("    %04X  %-13s %-44s%s" % (i.off, i.name, " ".join(parts), extra))
    return lines
