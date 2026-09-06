#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""asdump -- decompile SUPERVIVE's Angelscript layer.

SUPERVIVE (Theorycraft, UE5.4 fork, internal codename "Loki") embeds
UE-Angelscript (Hazelight's UnrealEngine-Angelscript plugin), and a large part
of its gameplay logic lives in Angelscript rather than C++ or Blueprint.  The
shipping game carries the whole compiled script layer in three plaintext files:

    Loki/Script/PrecompiledScript.Cache    declarations + bytecode  (1,184,817 B)
    Loki/Script/Binds.Cache                engine<->script bind table (5,764,301 B)
    Loki/Script/Binds.Cache.Headers        /Script/Mod.Class -> C++ header (2,050,287 B)

This tool parses all three and reconstructs, per module, a readable `.as`
source file: exact declarations plus decompiled function bodies, each with a
fully symbol-resolved disassembly appendix.

    python asdump.py                    # parse everything -> ../out/modules + _index.md
    python asdump.py --validate         # self-check + census only, write nothing
    python asdump.py --module DropShip  # just the modules matching a substring
    python asdump.py --no-asm           # omit the disassembly appendix

WHAT IS EXACT vs WHAT IS RECONSTRUCTED
  Exact (stored verbatim in the cache, not inferred): module names and source
  paths, class names and bases, every property with its type and full UPROPERTY
  metadata, every function name, return type, parameter types AND NAMES,
  default-argument source text, UFUNCTION metadata and flags, script enums with
  their members, and the bytecode itself.
  Reconstructed (decompiled, best effort): function bodies.
  ABSENT from a SHIPPING cache, therefore NOT recoverable at any effort:
  local-variable names (locals render as `vN`, N = the stack slot) and line
  numbers -- `DeclaredAt == 0` and `LineNumbers` is empty for all 1,463
  functions, because the plugin guards both with `#if !UE_BUILD_SHIPPING`.

PROVENANCE
  The opcode table is not copied from upstream AngelScript.  It is extracted
  byte-exact from the GAME BINARY's own `asBCInfo[256]` and `asBCTypeSize[22]`
  (see FORMAT.md); the fork differs from stock in ways that matter, notably the
  extra `asBCTYPE_W_rW_ARG` operand class and the appended `ThrowException`
  opcode.  Every operand layout was re-derived from those tables and checked
  against the real instruction stream.

DESIGN RULES (deliberate -- do not "fix" these)
  * FAIL LOUDLY.  The container walk raises on the first desynchronised byte,
    with an offset.  It never guesses and never resynchronises.  ~250k 4-byte
    bool canaries, every string's NUL, and the module-key == module-name
    identity are all checked.
  * DEGRADE PER FUNCTION.  A decode or lift failure is contained to the one
    function and printed as an explicit `<<UNDECODED>>` / `<<STRUCTURING
    FAILED>>` marker.  Nothing is ever silently dropped.
  * NEVER WRITE INSIDE THE GAME INSTALL.  Every game file is opened 'rb'.

Stdlib only.  Optionally reads a `mappings.usmap` (if one is found) purely to
name enum members; everything works without it.
"""

import argparse
import os
import struct
import sys
import time

_TOOL_DOC = __doc__

# ==========================================================================
# ---- section: opcode_table.py -----------------------------------------
# ==========================================================================

# Decodable opcodes are 0..MAXBYTECODE-1. asBC_MAXBYTECODE in the fork's own
# header reads 212 (from the dummy slots), and slot 212 is a real entry, so the
# fork appended an opcode without bumping the constant. We trust the table.
MAXBYTECODE = 213
PSEUDO_OPS = [251, 252, 253, 254, 255]  # never present in a serialized stream

TYPE_NAMES = ['INFO', 'NO_ARG', 'W_ARG', 'wW_ARG', 'DW_ARG', 'rW_DW_ARG', 'QW_ARG', 'DW_DW_ARG', 'wW_rW_rW_ARG', 'wW_QW_ARG', 'wW_rW_ARG', 'rW_ARG', 'wW_DW_ARG', 'wW_rW_DW_ARG', 'rW_rW_ARG', 'wW_W_ARG', 'QW_DW_ARG', 'rW_QW_ARG', 'W_DW_ARG', 'rW_W_DW_ARG', 'rW_DW_DW_ARG', 'W_rW_ARG']
TYPE_SIZE = [0, 1, 1, 1, 2, 2, 3, 3, 2, 3, 2, 1, 2, 3, 2, 2, 4, 3, 2, 3, 3, 2]

# type_id -> [(field_name, byte_offset_within_instruction, kind)]
TYPE_LAYOUT = {
     0: [],   # INFO
     1: [],   # NO_ARG
     2: [('W0', 2, 's16')],   # W_ARG
     3: [('wW0', 2, 's16')],   # wW_ARG
     4: [('DW', 4, 'i32')],   # DW_ARG
     5: [('rW0', 2, 's16'), ('DW', 4, 'i32')],   # rW_DW_ARG
     6: [('QW', 4, 'u64')],   # QW_ARG
     7: [('DW', 4, 'i32'), ('DW1', 8, 'i32')],   # DW_DW_ARG
     8: [('wW0', 2, 's16'), ('rW1', 4, 's16'), ('rW2', 6, 's16')],   # wW_rW_rW_ARG
     9: [('wW0', 2, 's16'), ('QW', 4, 'u64')],   # wW_QW_ARG
    10: [('wW0', 2, 's16'), ('rW1', 4, 's16')],   # wW_rW_ARG
    11: [('rW0', 2, 's16')],   # rW_ARG
    12: [('wW0', 2, 's16'), ('DW', 4, 'i32')],   # wW_DW_ARG
    13: [('wW0', 2, 's16'), ('rW1', 4, 's16'), ('DW', 8, 'i32')],   # wW_rW_DW_ARG
    14: [('rW0', 2, 's16'), ('rW1', 4, 's16')],   # rW_rW_ARG
    15: [('wW0', 2, 's16'), ('W1', 4, 's16')],   # wW_W_ARG
    16: [('QW', 4, 'u64'), ('DW', 12, 'i32')],   # QW_DW_ARG
    17: [('rW0', 2, 's16'), ('QW', 4, 'u64')],   # rW_QW_ARG
    18: [('W0', 2, 's16'), ('DW', 4, 'i32')],   # W_DW_ARG
    19: [('rW0', 2, 's16'), ('W1', 4, 's16'), ('DW', 8, 'i32')],   # rW_W_DW_ARG
    20: [('rW0', 2, 's16'), ('DW', 4, 'i32'), ('DW1', 8, 'i32')],   # rW_DW_DW_ARG
    21: [('W0', 2, 's16'), ('rW1', 4, 's16')],   # W_rW_ARG
}

# opcode -> (name, type_id, size_dwords, stack_inc)
# stack_inc 0xFFFF is AngelScript's 'variable stack effect' sentinel.
OPCODES = {
      0: ('PopPtr'          ,  1, 1,     -2),
      1: ('PshGPtr'         ,  6, 3,      2),
      2: ('PshC4'           ,  4, 2,      1),
      3: ('PshV4'           , 11, 1,      1),
      4: ('PSF'             , 11, 1,      2),
      5: ('SwapPtr'         ,  1, 1,      0),
      6: ('NOT'             , 11, 1,      0),
      7: ('PshG4'           ,  6, 3,      1),
      8: ('LdGRdR4'         ,  9, 3,      0),
      9: ('CALL'            ,  4, 2,  65535),
     10: ('RET'             ,  2, 1,  65535),
     11: ('JMP'             ,  4, 2,      0),
     12: ('JZ'              ,  4, 2,      0),
     13: ('JNZ'             ,  4, 2,      0),
     14: ('JS'              ,  4, 2,      0),
     15: ('JNS'             ,  4, 2,      0),
     16: ('JP'              ,  4, 2,      0),
     17: ('JNP'             ,  4, 2,      0),
     18: ('TZ'              ,  1, 1,      0),
     19: ('TNZ'             ,  1, 1,      0),
     20: ('TS'              ,  1, 1,      0),
     21: ('TNS'             ,  1, 1,      0),
     22: ('TP'              ,  1, 1,      0),
     23: ('TNP'             ,  1, 1,      0),
     24: ('NEGi'            , 11, 1,      0),
     25: ('NEGf'            , 11, 1,      0),
     26: ('NEGd'            , 11, 1,      0),
     27: ('INCi16'          ,  1, 1,      0),
     28: ('INCi8'           ,  1, 1,      0),
     29: ('DECi16'          ,  1, 1,      0),
     30: ('DECi8'           ,  1, 1,      0),
     31: ('INCi'            ,  1, 1,      0),
     32: ('DECi'            ,  1, 1,      0),
     33: ('INCf'            ,  1, 1,      0),
     34: ('DECf'            ,  1, 1,      0),
     35: ('INCd'            ,  1, 1,      0),
     36: ('DECd'            ,  1, 1,      0),
     37: ('IncVi'           , 11, 1,      0),
     38: ('DecVi'           , 11, 1,      0),
     39: ('BNOT'            , 11, 1,      0),
     40: ('BAND'            ,  8, 2,      0),
     41: ('BOR'             ,  8, 2,      0),
     42: ('BXOR'            ,  8, 2,      0),
     43: ('BSLL'            ,  8, 2,      0),
     44: ('BSRL'            ,  8, 2,      0),
     45: ('BSRA'            ,  8, 2,      0),
     46: ('COPY'            , 18, 2,     -2),
     47: ('PshC8'           ,  6, 3,      2),
     48: ('PshVPtr'         , 11, 1,      2),
     49: ('RDSPtr'          ,  1, 1,      0),
     50: ('CMPd'            , 14, 2,      0),
     51: ('CMPu'            , 14, 2,      0),
     52: ('CMPf'            , 14, 2,      0),
     53: ('CMPi'            , 14, 2,      0),
     54: ('CMPIi'           ,  5, 2,      0),
     55: ('CMPIf'           ,  5, 2,      0),
     56: ('CMPIu'           ,  5, 2,      0),
     57: ('JMPP'            ,  5, 2,      0),
     58: ('PopRPtr'         ,  1, 1,     -2),
     59: ('PshRPtr'         ,  1, 1,      2),
     60: ('STR'             ,  2, 1,      3),
     61: ('CALLSYS'         ,  6, 3,  65535),
     62: ('CALLBND'         ,  4, 2,  65535),
     63: ('SUSPEND'         ,  1, 1,      0),
     64: ('ALLOC'           , 16, 4,  65535),
     65: ('FREE'            ,  9, 3,      0),
     66: ('LOADOBJ'         , 11, 1,      0),
     67: ('STOREOBJ'        ,  3, 1,      0),
     68: ('GETOBJ'          , 21, 2,      0),
     69: ('REFCPY'          ,  1, 1,     -2),
     70: ('CHKREF'          ,  1, 1,      0),
     71: ('GETOBJREF'       , 21, 2,      0),
     72: ('GETREF'          , 21, 2,      0),
     73: ('PshNull'         ,  1, 1,      2),
     74: ('ClrVPtr'         ,  3, 1,      0),
     75: ('OBJTYPE'         ,  6, 3,      2),
     76: ('TYPEID'          ,  4, 2,      1),
     77: ('SetV4'           , 12, 2,      0),
     78: ('SetV8'           ,  9, 3,      0),
     79: ('ADDSi'           , 18, 2,      0),
     80: ('CpyVtoV4'        , 10, 2,      0),
     81: ('CpyVtoV8'        , 10, 2,      0),
     82: ('CpyVtoR4'        , 11, 1,      0),
     83: ('CpyVtoR8'        , 11, 1,      0),
     84: ('CpyVtoG4'        , 17, 3,      0),
     85: ('CpyRtoV4'        ,  3, 1,      0),
     86: ('CpyRtoV8'        ,  3, 1,      0),
     87: ('CpyGtoV4'        ,  9, 3,      0),
     88: ('WRTV1'           , 11, 1,      0),
     89: ('WRTV2'           , 11, 1,      0),
     90: ('WRTV4'           , 11, 1,      0),
     91: ('WRTV8'           , 11, 1,      0),
     92: ('RDR1'            ,  3, 1,      0),
     93: ('RDR2'            ,  3, 1,      0),
     94: ('RDR4'            ,  3, 1,      0),
     95: ('RDR8'            ,  3, 1,      0),
     96: ('LDG'             ,  6, 3,      0),
     97: ('LDV'             , 11, 1,      0),
     98: ('PGA'             ,  6, 3,      2),
     99: ('CmpPtr'          , 14, 2,      0),
    100: ('VAR'             , 11, 1,      2),
    101: ('iTOf'            , 10, 2,      0),
    102: ('fTOi'            , 10, 2,      0),
    103: ('uTOf'            , 10, 2,      0),
    104: ('fTOu'            , 10, 2,      0),
    105: ('sbTOi'           , 10, 2,      0),
    106: ('swTOi'           , 10, 2,      0),
    107: ('ubTOi'           , 10, 2,      0),
    108: ('uwTOi'           , 10, 2,      0),
    109: ('dTOi'            , 10, 2,      0),
    110: ('dTOu'            , 10, 2,      0),
    111: ('dTOf'            , 10, 2,      0),
    112: ('iTOd'            , 10, 2,      0),
    113: ('uTOd'            , 10, 2,      0),
    114: ('fTOd'            , 10, 2,      0),
    115: ('ADDi'            ,  8, 2,      0),
    116: ('SUBi'            ,  8, 2,      0),
    117: ('MULi'            ,  8, 2,      0),
    118: ('DIVi'            ,  8, 2,      0),
    119: ('MODi'            ,  8, 2,      0),
    120: ('ADDf'            ,  8, 2,      0),
    121: ('SUBf'            ,  8, 2,      0),
    122: ('MULf'            ,  8, 2,      0),
    123: ('DIVf'            ,  8, 2,      0),
    124: ('MODf'            ,  8, 2,      0),
    125: ('ADDd'            ,  8, 2,      0),
    126: ('SUBd'            ,  8, 2,      0),
    127: ('MULd'            ,  8, 2,      0),
    128: ('DIVd'            ,  8, 2,      0),
    129: ('MODd'            ,  8, 2,      0),
    130: ('ADDIi'           , 13, 3,      0),
    131: ('SUBIi'           , 13, 3,      0),
    132: ('MULIi'           , 13, 3,      0),
    133: ('ADDIf'           , 13, 3,      0),
    134: ('SUBIf'           , 13, 3,      0),
    135: ('MULIf'           , 13, 3,      0),
    136: ('SetG4'           , 16, 4,      0),
    137: ('ChkRefS'         ,  1, 1,      0),
    138: ('ChkNullV'        , 11, 1,      0),
    139: ('CALLINTF'        ,  4, 2,  65535),
    140: ('iTOb'            , 10, 2,      0),
    141: ('iTOw'            , 10, 2,      0),
    142: ('SetV1'           , 12, 2,      0),
    143: ('SetV2'           , 12, 2,      0),
    144: ('Cast'            ,  4, 2,     -2),
    145: ('i64TOi'          , 10, 2,      0),
    146: ('uTOi64'          , 10, 2,      0),
    147: ('iTOi64'          , 10, 2,      0),
    148: ('fTOi64'          , 10, 2,      0),
    149: ('dTOi64'          , 10, 2,      0),
    150: ('fTOu64'          , 10, 2,      0),
    151: ('dTOu64'          , 10, 2,      0),
    152: ('i64TOf'          , 10, 2,      0),
    153: ('u64TOf'          , 10, 2,      0),
    154: ('i64TOd'          , 10, 2,      0),
    155: ('u64TOd'          , 10, 2,      0),
    156: ('NEGi64'          , 11, 1,      0),
    157: ('INCi64'          ,  1, 1,      0),
    158: ('DECi64'          ,  1, 1,      0),
    159: ('BNOT64'          , 11, 1,      0),
    160: ('ADDi64'          ,  8, 2,      0),
    161: ('SUBi64'          ,  8, 2,      0),
    162: ('MULi64'          ,  8, 2,      0),
    163: ('DIVi64'          ,  8, 2,      0),
    164: ('MODi64'          ,  8, 2,      0),
    165: ('BAND64'          ,  8, 2,      0),
    166: ('BOR64'           ,  8, 2,      0),
    167: ('BXOR64'          ,  8, 2,      0),
    168: ('BSLL64'          ,  8, 2,      0),
    169: ('BSRL64'          ,  8, 2,      0),
    170: ('BSRA64'          ,  8, 2,      0),
    171: ('CMPi64'          , 14, 2,      0),
    172: ('CMPu64'          , 14, 2,      0),
    173: ('ChkNullS'        ,  2, 1,      0),
    174: ('ClrHi'           ,  1, 1,      0),
    175: ('JitEntry'        ,  6, 3,      0),
    176: ('CallPtr'         , 11, 1,  65535),
    177: ('FuncPtr'         ,  6, 3,      2),
    178: ('LoadThisR'       , 18, 2,      0),
    179: ('PshV8'           , 11, 1,      2),
    180: ('DIVu'            ,  8, 2,      0),
    181: ('MODu'            ,  8, 2,      0),
    182: ('DIVu64'          ,  8, 2,      0),
    183: ('MODu64'          ,  8, 2,      0),
    184: ('LoadRObjR'       , 19, 3,      0),
    185: ('LoadVObjR'       , 19, 3,      0),
    186: ('RefCpyV'         ,  3, 1,     -2),
    187: ('JLowZ'           ,  4, 2,      0),
    188: ('JLowNZ'          ,  4, 2,      0),
    189: ('AllocMem'        , 12, 2,      0),
    190: ('SetListSize'     , 20, 3,      0),
    191: ('PshListElmnt'    ,  5, 2,      2),
    192: ('SetListType'     , 20, 3,      0),
    193: ('POWi'            ,  8, 2,      0),
    194: ('POWu'            ,  8, 2,      0),
    195: ('POWf'            ,  8, 2,      0),
    196: ('POWd'            ,  8, 2,      0),
    197: ('POWdi'           ,  8, 2,      0),
    198: ('POWi64'          ,  8, 2,      0),
    199: ('POWu64'          ,  8, 2,      0),
    200: ('Thiscall1'       ,  6, 3,     -3),
    201: ('FinConstruct'    ,  6, 3,     -2),
    202: ('DestructScript'  , 17, 3,      0),
    203: ('CopyScript'      ,  6, 3,     -2),
    204: ('ResolveObjectPtr',  1, 1,      0),
    205: ('FreeNullV8'      ,  3, 1,      0),
    206: ('TrackRef'        , 11, 1,      0),
    207: ('UntrackRef'      , 11, 1,      0),
    208: ('ValidateRef'     , 11, 1,      0),
    209: ('CpyVtoR1'        , 11, 1,      0),
    210: ('SaveReturnValue' ,  1, 1,      0),
    211: ('CmpPtrNull'      , 11, 1,      0),
    212: ('ThrowException'  ,  2, 1,      0),
    251: ('VarDecl'         ,  2, 1,      0),
    252: ('Block'           ,  0, 0,      0),
    253: ('ObjInfo'         ,  5, 2,      0),
    254: ('LINE'            ,  0, 0,      0),
    255: ('LABEL'           ,  0, 0,      0),
}

NAME_TO_OP = {v[0]: k for k, v in OPCODES.items()}


# ==========================================================================
# ---- section: ascache.py ----------------------------------------------
# ==========================================================================

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
        # A script-declared type is a VALUE type (asOBJ_VALUE) when it
        # registers a `construct` behaviour and NO `factory`.  The 7
        # BehaviorRefs slots are, in order:
        #   0 factory 1 listFactory 2 copyfactory 3 construct
        #   4 copyconstruct 5 destruct 6 copy
        # 34 of the 110 script types classify this way (every F-struct and
        # every script delegate); they DO return on the stack, so the
        # hidden return pointer occupies a slot and every parameter after
        # it shifts.  Independent dword-depth audit: 99.04% -> 99.66%.
        self.script_value_types = set(
            c.name for _, c in self.classes
            if len(c.behavior_refs) == 7 and c.behavior_refs[3]
            and not c.behavior_refs[0])
        # Script-declared enums carry EXPLICIT values in the cache, so this map
        # is exact (unlike the usmap's positional fallback).
        self.script_enum_values = {}
        for m in self.modules:
            for e in m.enums:
                self.script_enum_values[e.name] = dict(zip(e.values, e.names))

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


def load_cache(path):
    return PrecompiledCache(path)


# ==========================================================================
# ---- section: asbinds.py ----------------------------------------------
# ==========================================================================

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


def load_binds(binds_path, headers_path=None):
    return BindDatabase(binds_path, headers_path)


# ==========================================================================
# ---- .usmap enum table (OPTIONAL) ---------------------------------------
# ==========================================================================
#
# Neither cache file carries the members of a C++ UENUM, so on their own an
# enum comparison can only ever decompile to `int(v25) == 1`.  Unreal's
# `.usmap` mapping file DOES carry them, and this project already generates one
# (tools/usmapdump).  Reading just its enum table is ~30 lines, so if a usmap
# is present we use it to turn `1` into `ELokiAssetLookupExecPins::LookupFailed`.
#
# Format (version 0, uncompressed -- verified against our own mappings.usmap):
#     u16 magic = 0x30C4 | u8 version | u8 compression | u32 csize | u32 dsize
#     u32 nameCount, then nameCount * (u8 len, len bytes)
#     u32 enumCount, then enumCount * (u32 nameIdx, u8 numValues,
#                                      numValues * u32 nameIdx)
#     u32 structCount ... (not read -- we only want enums)
#
# CAVEAT, and it is load-bearing: usmap v0 stores enum members POSITIONALLY,
# with no explicit values.  Mapping index -> value is therefore only correct for
# enums that do not override values (`A = 3`), which is the overwhelming
# majority but not all.  The disassembly appendix always keeps the raw integer,
# so any name printed here is checkable.  Pass --no-usmap to switch it off.

USMAP_MAGIC = 0x30C4


class UsmapEnums(object):
    """name -> [member, ...] in ordinal order.  Empty if no usmap was found."""

    def __init__(self, by_name=None, path=None):
        self.by_name = by_name or {}
        self.path = path

    def member(self, enum_name, value):
        """Member name for a value, or None when it cannot be named safely."""
        vals = self.by_name.get(enum_name)
        if not vals or not (0 <= value < len(vals)):
            return None
        m = vals[value]
        # usmap spells members fully qualified ("EFoo::Bar") about half the
        # time; normalise so the caller always gets a bare member.
        if "::" in m:
            m = m.rsplit("::", 1)[1]
        if m.endswith("_MAX"):
            return None
        return "%s::%s" % (enum_name, m)

    def __len__(self):
        return len(self.by_name)


def load_usmap(path):
    if not path or not os.path.exists(path):
        return UsmapEnums()
    with open(path, "rb") as fh:
        d = fh.read()
    if len(d) < 12:
        return UsmapEnums()
    magic, ver, comp = struct.unpack_from("<HBB", d, 0)
    if magic != USMAP_MAGIC or comp != 0:
        return UsmapEnums()          # compressed (Oodle/Brotli) -- out of scope
    o = 12
    try:
        n = struct.unpack_from("<I", d, o)[0]
        o += 4
        names = []
        for _ in range(n):
            ln = d[o]
            o += 1
            names.append(d[o:o + ln].decode("utf-8", "replace"))
            o += ln
        ne = struct.unpack_from("<I", d, o)[0]
        o += 4
        out = {}
        for _ in range(ne):
            ni = struct.unpack_from("<I", d, o)[0]
            o += 4
            nv = d[o]
            o += 1
            vals = []
            for _ in range(nv):
                vi = struct.unpack_from("<I", d, o)[0]
                o += 4
                vals.append(names[vi])
            out[names[ni]] = vals
    except (IndexError, struct.error):
        return UsmapEnums()          # unexpected shape -> degrade to no enums
    return UsmapEnums(out, path)


def find_usmap(explicit=None):
    """Look for a usmap next to the tool / in the project, else give up."""
    if explicit:
        return explicit if os.path.exists(explicit) else None
    here = os.path.dirname(os.path.abspath(__file__))
    root = os.path.abspath(os.path.join(here, "..", ".."))
    for c in (os.path.join(here, "mappings.usmap"),
              os.path.join(root, "mappings.usmap"),
              os.path.join(root, "tools", "usmapdump", "mappings.usmap"),
              os.path.join(root, "tools", "extractor", "mappings.usmap")):
        if os.path.exists(c):
            return c
    return None



# ==========================================================================
# ---- section: aslift.py -----------------------------------------------
# ==========================================================================

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
        info = OPCODES.get(op)
        if info is None or op >= MAXBYTECODE:
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
        for fld, boff, kind in TYPE_LAYOUT[ty]:
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
# Numeric literals.  asBC_SetV8 carries a raw 64-bit immediate that is EITHER an
# int64 or an IEEE-754 double, and the bytecode does not say which.  Printing it
# as an unsigned integer makes every tuning constant in the gameplay layer
# unreadable ("v10 = 4641240890982006784" is really "v10 = 200.0").
#
# The two interpretations are separable by exponent, not by taste.  A bit
# pattern only decodes to a NORMAL double (|d| >= 1e-300) once the raw u64 is
# above ~1.2e17; every int64 literal below that -- which is every count, index,
# id and timestamp a game script writes -- lands in the denormal/tiny band and
# is left as an integer.  Measured over this corpus: 77 distinct 64-bit
# immediates, 76 decode to clean game numbers (1.0, 0.8, 500.0, 1e-8, DBL_MAX),
# 1 is zero (identical either way), 0 are misclassified.  The disassembly
# appendix always keeps the raw immediate, so any call is checkable.
FLOAT_MIN_MAG = 1e-300         # smallest normal double, rounded up
FLOAT32_MIN_MAG = 1e-38        # smallest normal float32, rounded up


def _fmt_float(x):
    """Shortest exact decimal for a float, always visibly a float."""
    s = repr(float(x))
    if s.endswith(".0"):
        return s
    if "e" in s or "." in s:
        return s
    return s + ".0"


def qw_literal(v):
    """Render an asBC_SetV8 immediate: double when the bit pattern is one."""
    d = struct.unpack("<d", struct.pack("<Q", v & 0xFFFFFFFFFFFFFFFF))[0]
    # v == 0 is 0.0 and 0 at once -- the text is the same, so leave it as "0".
    if v != 0 and d == d and abs(d) != float("inf") and abs(d) >= FLOAT_MIN_MAG:
        return _fmt_float(d)
    if v >= 1 << 63:
        return str(v - (1 << 63) * 2)   # print as signed int64
    return str(v)


def dw_literal(v):
    """Render an asBC_SetV4 immediate: float32 only when it cannot be an int.

    Requires |int| > 1e6 so no plausible small integer is ever reinterpreted.
    Rare in this corpus (a single site across the whole gameplay layer), but
    when it happens the integer form is pure noise.
    """
    if abs(v) > 1000000:
        f = struct.unpack("<f", struct.pack("<i", v))[0]
        if f == f and abs(f) != float("inf") and abs(f) >= FLOAT32_MIN_MAG:
            return _fmt_float(f)
    return str(v)


WIDE_TOKENS = frozenset([71, 78, 81, 94])   # int64, uint64, float64, double


def is_enum_type(cache, binds, dt):
    """True when `dt` names an enum (asOBJ_ENUM), not an object.

    An enum HAS type info, so the naive "has type info => it is an object =>
    2 dwords" rule misclassifies it.  Script enums are known outright; engine
    enums are absent from Binds.Cache as types, so anything left that is
    neither a bound UStruct nor a bound UCLASS and carries the E<Upper> shape
    is an enum.  This is the same classification returns_on_stack() needs.
    """
    if cache is None or not dt.type_info or dt.handle or dt.is_ref:
        return False
    tr = cache.type_refs.get(dt.type_info)
    if tr is None or tr.subtypes:
        return False
    n = tr.name
    if n in cache.script_enums:
        return True
    if n in cache.script_classes:
        return False
    if binds is not None and (n in binds.struct_names or n in binds.class_names):
        return False
    return len(n) > 1 and n[0] == "E" and n[1].isupper()


def stack_width(dt, cache=None, binds=None):
    """asCDataType::GetSizeOnStackDWords, x64 (AS_PTR_SIZE == 2).

    An ENUM is ONE dword, not two.  It has type info, so the obvious
    "type_info => pointer => 2" rule is wrong for it, and getting this wrong
    shifts the offset of every parameter that FOLLOWS an enum -- which
    mis-attributes parameter names in 19 functions in this corpus (measured).
    """
    if dt.is_ref:
        return 2
    if dt.type_info:
        return 1 if is_enum_type(cache, binds, dt) else 2
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
    if n in cache.script_enums:
        return False
    # 34 of the 110 script-declared types are AngelScript VALUE types
    # (asOBJ_VALUE) -- every F-struct and every script delegate.  They return
    # on the stack; the remaining script types are reference types and cannot.
    if n in getattr(cache, "script_value_types", ()):
        return True
    if n in cache.script_classes:
        return False
    if binds is not None:
        if n in binds.struct_names:
            return True
        if n in binds.class_names:
            return False
    # Engine enums are not in Binds.Cache as types; every remaining unclassified
    # name in this corpus is either E<Upper>... (an enum) or an F-struct/T-template.
    return not (len(n) > 1 and n[0] == "E" and n[1].isupper())


def param_offsets(param_types, is_method, cache=None, binds=None,
                  ret_type=None):
    """asCCompiler's parameter slot assignment.

    `this` (methods only) sits at variable offset 0; parameters march NEGATIVE,
    each starting where the previous left off:
        off[0] = -AS_PTR_SIZE if method else 0
        off[i] = off[i-1] - width(param[i-1])
    Verified against ALokiAirship_AS::Spawn: 5 params land on 0,-2,-4,-6,-7 with
    widths 2,2,2,1,2 -- exactly the offsets its bytecode references.  Passing
    the cache lets enum parameters be sized correctly (1 dword); without it
    they fall back to 2 and any parameter after an enum shifts.

    ⚠ The HIDDEN BY-VALUE RETURN POINTER occupies a slot too.  The full frame
    shape (see FORMAT.md §3) is

        [this] [hidden by-value return ptr] [param0] [param1] ...

    so a method that returns a VALUE type (asCScriptFunction::DoesReturnOnStack)
    pushes every declared parameter two dwords further down.  Omitting this
    labels the hidden pointer with param0's NAME and leaves the real param0 as
    an anonymous `arg_mN` -- e.g. ULokiRespawnComponent::GetValidPlayerStart,
    whose `PS` was attached to the FTransform return temp, and
    LokiScriptUtility::LinearColorToVector, which read `arg_m2.B` instead of
    `Color.B`.  Measured over this corpus: 34 script functions return a value
    type on the stack and 20 of those take parameters, so 20 functions had every
    parameter name shifted by one slot.  `ret_type` must be passed for the
    correction to apply; callers that omit it keep the old behaviour.
    """
    pos = -2 if is_method else 0
    if ret_type is not None and cache is not None \
            and returns_on_stack(cache, binds, ret_type):
        pos -= 2
    out = []
    for dt in param_types:
        out.append(pos)
        pos -= stack_width(dt, cache, binds)
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

    def __init__(self, cache, binds, func, owner_class=None, usmap=None):
        self.c, self.b, self.f = cache, binds, func
        self.usmap = usmap if (usmap and len(usmap)) else None
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
        self.enum_slot = {}            # slot -> enum type name (whole function)
        self.enums_named = 0
        self.last_call_ret = None      # return type of the most recent call
        self.slots_used = set()        # every variable slot the bytecode touches
        self.const_slot = {}           # slot -> (literal text, index in self.out)
        offs = param_offsets(func.param_types, self.is_method, cache, binds,
                             func.ret)
        # Name the hidden by-value return temp, so a by-value return renders as
        # `__ret = FVector(v56)` instead of an anonymous `arg_m2 = ...`.
        if returns_on_stack(cache, binds, func.ret):
            hid = -2 if self.is_method else 0
            self.varname[hid] = "__ret"
            self.vartype[hid] = cache.type_name(func.ret)
        for i, o in enumerate(offs):
            nm = func.param_names[i] if i < len(func.param_names) else ""
            self.varname[o] = nm or ("arg%d" % i)
            self.vartype[o] = cache.type_name(func.param_types[i])
            # Seed enum knowledge from the signature, so `int(NewDetachState)
            # == 3` can become `== ELokiCrewPodDetachState::Detaching`.
            en = self.enum_name_of(func.param_types[i], allow_ref=True)
            if en is not None:
                self.enum_slot[o] = en
        if self.is_method:
            self.varname[0] = "this"
            self.vartype[0] = owner_class.name
        for pos, tp in zip(func.obj_var_pos, func.obj_var_types):
            tr = cache.type_refs.get(tp)
            if tr and pos not in self.vartype:
                # Keep the template arguments: `TSubclassOf<ALokiDropPod@>`,
                # not a bare `TSubclassOf`.
                nm = tr.name
                if tr.subtypes:
                    nm += "<%s>" % ", ".join(cache.type_name(s)
                                             for s in tr.subtypes)
                self.vartype[pos] = nm

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

    # ---- enums ------------------------------------------------------------
    def enum_name_of(self, dt, allow_ref=False):
        """The enum type named by `dt`, or None when `dt` is not an enum.

        An enum has type info (so it is not a bare primitive) but is not a
        handle and is not a bound UCLASS/UStruct.  Script enums and anything
        the usmap knows are positive identifications; the E<Upper> shape is the
        last-resort rule and is the same one returns_on_stack() already relies
        on.  `allow_ref` admits `&out` enum parameters, which cannot carry a
        literal but do pin down the type of the caller's slot.
        """
        if not dt.type_info or dt.handle or (dt.is_ref and not allow_ref):
            return None
        tr = self.c.type_refs.get(dt.type_info)
        if tr is None or tr.subtypes:
            return None
        n = tr.name
        if n in self.c.script_enums:
            return n
        if self.usmap is not None and n in self.usmap.by_name:
            return n
        if self.b is not None and (n in self.b.struct_names or n in self.b.class_names):
            return None
        return n if (len(n) > 1 and n[0] == "E" and n[1].isupper()) else None

    def enum_member(self, enum_name, value):
        """`EType::Member` for a value, or None if it cannot be named safely."""
        exact = self.c.script_enum_values.get(enum_name)
        if exact is not None:
            m = exact.get(value)
            return ("%s::%s" % (enum_name, m)) if m else None
        if self.usmap is not None:
            return self.usmap.member(enum_name, value)
        return None

    def _fix_enum_args(self, fr, args):
        """Re-render integer/bool literals that are really enum members.

        Skipped entirely when the call has `?&` parameters, because those
        occupy two stack slots and break the 1:1 arg-index -> param-index
        mapping this relies on.  Anything that cannot be named is left as a
        plain integer -- which is still strictly better than `true`/`false`.
        """
        if not args or len(args) != len(fr.param_types):
            return args
        out = list(args)
        for k, pt in enumerate(fr.param_types):
            en = self.enum_name_of(pt, allow_ref=True)
            if en is None:
                continue
            a = out[k]
            # Whatever else happens, we now KNOW this slot's type -- including
            # for an `&out` enum, which is how the asset-lookup exec pins and
            # most other status enums come back.
            if a.startswith("v") and a[1:].isdigit():
                self.enum_slot[int(a[1:])] = en
                self.vartype.setdefault(int(a[1:]), en)
            if pt.is_ref:
                continue          # a reference argument is never a literal
            slot = None
            if a.startswith("v") and a[1:].isdigit():
                # The literal reached the call through a slot:
                #     SetV1 v34, 0 ; ... ; PshV4 v34 ; CALLSYS f(..., EFoo)
                # Follow it, but only when the recorded statement is still the
                # last write to that slot in this block -- otherwise the value
                # is not provably the one we remembered.
                slot = int(a[1:])
                rec = self.const_slot.get(slot)
                if rec is None:
                    continue
                lit, idx = rec
                if idx >= len(self.out) or self.out[idx] != "%s = %s;" % (a, lit):
                    continue
                if any(l.startswith(a + " = ") for l in self.out[idx + 1:]):
                    continue
                a = lit
            if a == "true":
                v = 1
            elif a == "false":
                v = 0
            elif a.lstrip("-").isdigit():
                v = int(a)
            else:
                continue
            named = self.enum_member(en, v) or str(v)
            if "::" in named:
                self.enums_named += 1
            if slot is None:
                out[k] = named
            else:
                # Rewrite the assignment in place so the variable and the call
                # site agree; the argument keeps referring to the slot.
                self.out[self.const_slot[slot][1]] = "%s = %s;" % (out[k], named)
                self.vartype.setdefault(slot, en)   # and the slot is that enum
        return out

    def _type_args(self, fr, args):
        """Type a local from the parameter slot it is passed into.

        The cache never names a local, but it does name every PARAMETER of
        every callee, so `f(v25)` tells us v25's type exactly.  This is where
        most non-object locals (bools, ints, enums) get their type; without it
        they can only be declared `auto`.  Only fills slots nothing else has
        claimed, and only when the arg list lines up 1:1 with the signature.
        """
        if len(args) != len(fr.param_types):
            return
        for k, pt in enumerate(fr.param_types):
            a = args[k]
            if not (a.startswith("v") and a[1:].isdigit()):
                continue
            t = self.c.type_name(pt)
            # A reference parameter says nothing about the storage class of
            # the caller's slot, only about its type.
            t = t.rstrip("&").replace("const ", "")
            if t and t != "?":
                self.vartype.setdefault(int(a[1:]), t)

    # ---- local declarations (grafted from impl_a) -------------------------
    def declarations(self):
        """`Type vN;` for every local the body actually references.

        The cache has no local NAMES, but it does have ObjVariableTypes /
        ObjVariablePos, which types every object local exactly; call-return
        inference fills in most of the rest.  Anything still unknown is
        declared `auto` rather than guessed.
        """
        out = []
        for off in sorted(self.slots_used):
            if off <= 0 or off in self.varname:
                continue               # parameters, `this`, and the temp area
            t = self.vartype.get(off)
            out.append("%s v%d;" % (t if t else "auto", off))
        return out

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
        # const_slot indexes into self.out, so it must not outlive the block.
        self.const_slot = {}
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
        # Record every slot the instruction stream actually touches, so the
        # declaration block can list exactly the locals that appear in the
        # body -- no more, no fewer.  Only wW/rW operand classes are variable
        # slots; a plain W is a count or a byte offset, never a slot.
        for k in ("wW0", "rW0", "rW1", "rW2"):
            if k in a:
                self.slots_used.add(a[k])
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
            # An enum widened to int is still that enum for naming purposes.
            if src in self.enum_slot:
                self.enum_slot[dst] = self.enum_slot[src]
            # A conversion names its destination type exactly.
            self.vartype.setdefault(dst, self.CONVERT[n])
            self.emit("%s = %s(%s);" % (self.v(dst), self.CONVERT[n], self.v(src)))
            return
        if n in self.CMP:
            self.cond = (self.v(a["rW0"]), self.v(a["rW1"]))
            return
        if n in self.CMP_IMM:
            k = self.CMP_IMM[n]
            imm = _fmt_f(_f32(a["DW"])) if k == "f" else str(a["DW"])
            # `if (int(v25) == 1)` reads as nothing at all; when the slot is
            # known to hold an enum, name the constant instead.
            en = self.enum_slot.get(a["rW0"])
            if en is not None and k in ("i", "u"):
                nm = self.enum_member(en, a["DW"])
                if nm:
                    imm = nm
                    self.enums_named += 1
            self.cond = (self.v(a["rW0"]), imm)
            return
        self.note(n)
        self.flush_pending()
        self.emit("asm(%s)" % self.raw(ins))

    # ---- pushes -----------------------------------------------------------
    def op_PshC4(self, i, a):
        self.push(E(dw_literal(a["DW"])))

    def op_PshC8(self, i, a):
        self.push(E(qw_literal(a["QW"])))

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
        if val is None:
            # VOID return: ret_value() bails before it ever looks at `pending`,
            # so a call still parked there is a real statement that executes
            # BEFORE the return.  run_block() only flushes at end-of-block, which
            # put the flushed call AFTER `return;` -- e.g. AFFAGameMode::ResetArmor
            # rendered `return;` immediately followed by its TryAddToInventory
            # call, which the disassembly shows running before the RET.
            # 2 sites in this corpus; both fixed by flushing here.
            self.flush_pending()
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

    def _load_ref(self, expr):
        """asBC_LoadThisR / LoadRObjR / LoadVObjR / LDV / LDG.

        All five write the ADDRESS of their operand into the VM's **value
        register** (`*(asPWORD*)&m_regs.valueRegister = ...`), which is exactly
        what `asBC_PshRPtr` later pushes.  Recording it only in `refreg` and
        leaving a stale `pending` / `valreg` behind lets `PshRPtr` push the
        wrong thing -- in ALokiAimingLaserSpreadLines::Tick that printed
        `Math::Lerp(1.0, n"Final Opacity", v52)` where the bytecode passes
        `this.LaserOpacityMultWhenSpread`.  Mirroring the VM (the load clobbers
        the value register) fixes every by-reference member argument.

        `pending` is FLUSHED rather than discarded: a call whose by-value result
        went to a temp slot is still a statement that has to appear, and simply
        dropping it would silently lose `this.DoLaserTrace();` from
        ALokiAimingLaser::Tick.
        """
        self.flush_pending()
        self.refreg = self.valreg = expr

    def op_LoadThisR(self, i, a):
        nm = self.prop_name(a["DW"], a["W0"])
        self._load_ref("this.%s" % (nm or "field_%d" % a["W0"]))

    def op_LoadRObjR(self, i, a):
        nm = self.prop_name(a["DW"], a["W1"])
        self._load_ref("%s.%s" % (self.v(a["rW0"]), nm or "field_%d" % a["W1"]))

    op_LoadVObjR = op_LoadRObjR

    def op_LDV(self, i, a):
        self._load_ref(self.v(a["rW0"]))

    def op_LDG(self, i, a):
        self._load_ref(self.gname(a["QW"]) or "global_%x" % a["QW"])

    # ---- moves ------------------------------------------------------------
    def _setv(self, a, val):
        self.emit("%s = %s;" % (self.v(a["wW0"]), val))
        # Remember literal-into-slot so a later enum-typed argument can be
        # named.  Records WHERE the statement landed so the rewrite can verify
        # the line is still the one it thinks it is.
        self.const_slot[a["wW0"]] = (val, len(self.out) - 1)

    def op_SetV1(self, i, a):
        d = a["DW"] & 0xFF
        self._setv(a, "true" if d == 1 else ("false" if d == 0 else str(d)))

    def op_SetV2(self, i, a):
        self._setv(a, str(a["DW"] & 0xFFFF))

    def op_SetV4(self, i, a):
        self._setv(a, dw_literal(a["DW"]))

    def op_SetV8(self, i, a):
        self._setv(a, qw_literal(a["QW"]))

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
        # Local typing (grafted from impl_a): the object register was last
        # written by a call, so the destination slot has that call's return
        # type.  Only fills slots ObjVariableTypes did not already cover.
        if self.last_call_ret is not None and a["wW0"] not in self.vartype:
            self.vartype[a["wW0"]] = self.last_call_ret
        self.emit("%s = %s;" % (dst, src))
        self.objreg = self.valreg = dst

    def op_REFCPY(self, i, a):
        # asBC_REFCPY is `*dst = src` with refcounting.  In the VM the
        # DESTINATION pointer is the TOP of the stack and the source sits
        # below it:
        #
        #     asDWORD **d = (asDWORD**)*(asPWORD*)l_sp;   // top  -> destination
        #     l_sp += AS_PTR_SIZE;
        #     asDWORD  *s = (asDWORD*) *(asPWORD*)l_sp;   // next -> source
        #     *d = s;
        #
        # and the compiler emits it as
        #     PshVPtr <src> ; PshVPtr this ; ADDSi .<member> ; REFCPY ; PopPtr
        # (the trailing PopPtr discards the source REFCPY left behind).
        #
        # Reading the first pop as the right-hand side inverts every handle
        # assignment -- it printed `HeroOwner = this.OwnerHero` for the body of
        # ALokiAimingLaser::UpdateOwner, which actually assigns OwnerHero.
        # Verified against four independent sites whose intent is unambiguous
        # (UpdateOwner, MyCharacter caching, ShadowDecalComponent/MID caching,
        # OwnerAimingVisComponent back-link).
        lhs = self.pop()        # destination pointer (pushed last)
        rhs = self.pop()        # source handle
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
        # asBC_COPY has the SAME stack shape as asBC_REFCPY: the DESTINATION is
        # the pointer pushed LAST, and it is what stays on the stack afterwards.
        #     void *d = (void*)*(asPWORD*)l_sp;  l_sp += AS_PTR_SIZE;
        #     void *s = (void*)*(asPWORD*)l_sp;  memcpy(d, s, n);
        # Ground truth: ULokiInteractionPlayerComponent::ProcessInteractionSelection
        #     PshVPtr this ; ADDSi .HoveredUsable
        #     PshVPtr this ; ADDSi .SelectedUsable
        #     COPY 24 (FLokiUsableData)
        # is `SelectedUsable = HoveredUsable` -- SelectedUsable was Clear()ed two
        # instructions earlier, so the other reading is impossible.
        lhs = self.pop()        # destination struct (pushed last)
        rhs = self.pop()        # source struct
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
            # The by-value destination temp has the callee's return type,
            # exactly.
            if byval_dest.startswith("v") and byval_dest[1:].isdigit():
                self.vartype.setdefault(int(byval_dest[1:]),
                                        self.c.type_name(fr.ret))
        nargs = len(fr.param_types)
        extra = sum(1 for p in fr.param_types if not p.type_info and p.token == 59)
        args = [str(self.pop()) for _ in range(nargs + extra)]
        # Enum-typed arguments.  An enum occupies ONE dword and is pushed with
        # PshV4, exactly like a bool, so a literal 0/1 that reached us as
        # "false"/"true" is wrong whenever the parameter is really an enum --
        # BOTH source implementations mis-rendered
        #   SpawnPoolableActorFromClassDeferred(..., false, true)
        # for (ESpawnActorCollisionHandlingMethod, ESpawnActorScaleMethod).
        # The callee's own parameter type settles it; the usmap (when present)
        # then supplies the member name.
        args = self._fix_enum_args(fr, args)
        self._type_args(fr, args)
        owner = ""
        owner_full = ""
        if fr.object_type:
            tr = self.c.type_refs.get(fr.object_type)
            owner = tr.name if tr else ""
            owner_full = owner
            if tr is not None and tr.subtypes:
                owner_full += "<%s>" % ", ".join(self.c.type_name(s)
                                                 for s in tr.subtypes)
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
            self.emit("%s = %s(%s);"
                      % (this, owner_full or owner or "ctor", ", ".join(args)))
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
        # Remember the return type so a following STOREOBJ can type its slot.
        self.last_call_ret = None if is_void else self.c.type_name(fr.ret)
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
def lift_function(cache, binds, func, owner_class=None, want_pseudo=True,
                  usmap=None):
    res = {"insns": [], "asm": [], "pseudo": [], "error": None, "decls": [],
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
    lf = Lifter(cache, binds, func, owner_class, usmap)
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
            res["decls"] = lf.declarations()
        except Exception as e:
            res["structure_error"] = "%s: %s" % (type(e).__name__, e)
            res["pseudo"] = []
    res["unhandled"] = dict(lf.unhandled)
    res["stack_warnings"] = lf.stack_warnings
    res["enums_named"] = lf.enums_named
    return res


def func_decl(cache, fr):
    """`ret Owner::Name(paramtypes) const` -- the full callee signature.

    Grafted from impl_a: a bare callee NAME leaves you guessing about arity and
    which overload was taken, and the disassembly is exactly where that matters.
    """
    ow = cache.type_refs.get(fr.object_type)
    if ow is not None:
        on = ow.name
        if ow.subtypes:
            on += "<%s>" % ", ".join(cache.type_name(s) for s in ow.subtypes)
        qual = "%s::" % on
    else:
        qual = ("%s::" % fr.namespace) if fr.namespace else ""
    return "%s %s%s(%s)%s" % (cache.type_name(fr.ret), qual, fr.name,
                              ", ".join(cache.type_name(p) for p in fr.param_types),
                              " const" if fr.is_const else "")


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
                extra = "  ; %s" % func_decl(lf.c, fr)
        elif i.name in ("CALLSYS", "Thiscall1", "CallPtr"):
            fr = lf.c.func_refs.get(i.args.get("QW"))
            if fr:
                extra = "  ; %s" % func_decl(lf.c, fr)
        elif i.name == "ALLOC":
            tr = lf.c.type_refs.get(i.args.get("QW"))
            fr = lf.c.func_of_id(i.args.get("DW"))
            extra = "  ; new %s%s" % (tr.name if tr else "?",
                                      ("  ctor=%s" % func_decl(lf.c, fr)) if fr else "")
        if i.target is not None:
            extra = "  -> L%04X" % i.target
        lines.append("    %04X  %-13s %-44s%s" % (i.off, i.name, " ".join(parts), extra))
    return lines


# ==========================================================================
# ---- section: asdump.py -----------------------------------------------
# ==========================================================================

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


DEFAULT_SCRIPT_DIR = (r"G:\git\GAME BACKUPS FOR REVERSE ENGINEERING\SUPERVIVE"
                      r"\Loki\Script")
DEFAULT_OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "out", "modules")

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
    def __init__(self, cache, binds, want_asm=True, usmap=None):
        self.c = cache
        self.b = binds
        self.usmap = usmap
        self.want_asm = want_asm
        self.stats = {
            "functions": 0, "with_bytecode": 0, "decoded": 0, "structured": 0,
            "decode_errors": [], "structure_errors": [], "unhandled": {},
            "stack_warnings": 0, "asm_lines": 0, "pseudo_lines": 0,
            "bytecode_bytes": 0, "instructions": 0,
            "locals_typed": 0, "locals_auto": 0, "enums_named": 0,
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
        r = lift_function(self.c, self.b, f, owner, usmap=self.usmap)
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
        st["enums_named"] += r.get("enums_named", 0)
        lines = [indent + "{"]
        if r["structure_error"]:
            st["structure_errors"].append((owner.name if owner else "", f.name,
                                           r["structure_error"]))
            lines.append(indent + "    <<STRUCTURING FAILED: %s -- body available "
                                  "as disassembly below>>" % r["structure_error"])
        else:
            st["structured"] += 1
            # Typed local declarations (grafted from impl_a).  The cache has no
            # local NAMES, but ObjVariableTypes types every object local
            # exactly, so `ULokiRideableComponent v42;` beats a bare `v42`.
            for l in r["decls"]:
                lines.append(indent + "    " + l)
                if "auto " not in l:
                    st["locals_typed"] += 1
                else:
                    st["locals_auto"] += 1
            if r["decls"]:
                lines.append("")
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
        A("//  Reconstructed by tools/asdump/asdump.py from")
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
def stack_depth_audit(cache, binds):
    """INDEPENDENT check of the calling-convention model (from impl_a).

    Walks every bytecode stream accumulating the GAME'S OWN `asBCInfo.stackInc`
    per opcode.  For the opcodes whose table entry is AngelScript's 0xFFFF
    "variable" sentinel -- the calls -- the delta is derived from the callee
    signature instead: every parameter's width, plus 2 dwords for `this`, plus
    2 more for the hidden destination pointer of a by-value return.

    At `RET` the depth must be back to zero.  This shares no code with the
    lifter's symbolic stack, so when the two disagree about which functions are
    unbalanced, the argument model is wrong somewhere; when they agree, the
    convention is corroborated by the engine's own table.

    Returns (functions_checked, unbalanced, [(class, func, depth), ...]).
    """
    checked = 0
    bad = []
    for _mod, f in cache.functions:
        if f.bc_dwords == 0:
            continue
        try:
            insns = decode(f.bytecode, f.name)
        except LiftError:
            continue
        checked += 1
        depth = 0
        for ins in insns:
            info = OPCODES.get(ins.op)
            si = info[3]
            if si != 65535:
                depth += si
            elif ins.name == "ALLOC":
                # asBC_ALLOC: QW is the TYPE, DW the constructor's function id.
                # It consumes the destination pointer plus the ctor arguments.
                depth -= 2
                fr = cache.func_of_id(ins.args.get("DW"))
                if fr is not None:
                    depth -= sum(stack_width(p, cache, binds)
                                 for p in fr.param_types)
            else:
                fr = None
                if "QW" in ins.args:
                    fr = cache.func_refs.get(ins.args["QW"])
                elif ins.name in ("CALL", "CALLINTF", "CALLBND"):
                    fr = cache.func_of_id(ins.args.get("DW"))
                if fr is not None:
                    dw = sum(stack_width(p, cache, binds)
                             for p in fr.param_types)
                    # A `?&` (asTYPEID / variable-type) parameter is pushed as
                    # the reference PLUS a typeid dword, so it costs one more
                    # than its declared width -- the same correction the lifter
                    # applies as `extra`.
                    dw += sum(1 for p in fr.param_types
                              if not p.type_info and p.token == 59)
                    if fr.is_method and fr.object_type:
                        dw += 2
                    if returns_on_stack(cache, binds, fr.ret):
                        dw += 2
                    depth -= dw
            if ins.name == "RET" and depth != 0:
                bad.append((f.name, depth))
    return checked, len(bad), bad


def validate(cache, binds, log=print, usmap=None):
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


def bytecode_census(cache, log=print, binds=None):
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
            insns = decode(f.bytecode, "%s::%s" % (m.name, f.name))
        except LiftError as e:
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

    nchk, nbad, worst = stack_depth_audit(cache, binds)
    log("")
    log("CALLING CONVENTION (independent dword-depth audit vs the game's own "
        "stackInc table)")
    log("  balanced at RET           %d / %d  (%.2f%%)"
        % (nchk - nbad, nchk, 100.0 * (nchk - nbad) / max(nchk, 1)))
    if worst:
        log("  unbalanced: %s"
            % ", ".join("%s(%+d)" % w for w in worst[:8]))
    return ok, bad


def write_index(path, cache, emitter, files, elapsed, log=print, usmap=None,
                module_dir="modules"):
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
    A("Generated by `tools/asdump/asdump.py` in %.1fs. "
      "Module sources are under `%s/`." % (elapsed, module_dir))
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
    nl = st["locals_typed"] + st["locals_auto"]
    A("- local declarations emitted: **%d**, of which typed **%d (%.1f%%)** "
      "and `auto` %d" % (nl, st["locals_typed"],
                         100.0 * st["locals_typed"] / max(nl, 1),
                         st["locals_auto"]))
    if usmap is not None and len(usmap):
        A("- enum member names resolved from `%s` (**%d** enums)"
          % (os.path.basename(usmap.path or "?"), len(usmap)))
    else:
        A("- no usmap in use: enum members print as plain integers")
    A("")
    A("## Modules")
    A("")
    A("| source | module | class(es) | funcs | bytecode |")
    A("|---|---|---|---:|---:|")
    for name, src, cls, nf, bc, rel in rows:
        rel = ("%s/%s" % (module_dir, rel.replace("\\", "/"))) if rel else ""
        link = "[`%s`](%s)" % (src, rel) if rel else "`%s`" % src
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
    ap = argparse.ArgumentParser(description=_TOOL_DOC,
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
    ap.add_argument("--usmap", default=None,
                    help="path to a mappings.usmap (enum member names); "
                         "auto-detected in the project tree when omitted")
    ap.add_argument("--no-usmap", action="store_true",
                    help="do not name enum members even if a usmap is available")
    args = ap.parse_args(argv)

    pcs = os.path.join(args.script_dir, "PrecompiledScript.Cache")
    bc = os.path.join(args.script_dir, "Binds.Cache")
    bh = os.path.join(args.script_dir, "Binds.Cache.Headers")
    for p in (pcs,):
        if not os.path.exists(p):
            sys.exit("missing required file: %s" % p)

    t0 = time.time()
    cache = load_cache(pcs)
    binds = None
    if not args.no_binds and os.path.exists(bc):
        binds = load_binds(bc, bh if os.path.exists(bh) else None)

    usmap = UsmapEnums()
    if not args.no_usmap:
        usmap = load_usmap(find_usmap(args.usmap))

    validate(cache, binds, usmap=usmap)
    bytecode_census(cache, binds=binds)

    if args.validate:
        print("\nvalidate-only: nothing written. %.1fs" % (time.time() - t0))
        return 0

    em = Emitter(cache, binds, want_asm=not args.no_asm, usmap=usmap)
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
            fh.write("\n".join(l.rstrip() for l in lines) + "\n")
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
    nl = st["locals_typed"] + st["locals_auto"]
    print("  local decls emitted       %d  (typed %d = %.1f%%, auto %d)"
          % (nl, st["locals_typed"], 100.0 * st["locals_typed"] / max(nl, 1),
             st["locals_auto"]))
    if len(usmap):
        print("  enum members named        %d  (from %s, %d enums)"
              % (st["enums_named"], os.path.basename(usmap.path or "?"),
                 len(usmap)))
    else:
        print("  enum members named        0  (no usmap; enums print as integers)")
    if st["decode_errors"]:
        print("  DECODE ERRORS             %d" % len(st["decode_errors"]))
        for e in st["decode_errors"][:10]:
            print("     %s::%s  %s" % e)
    if st["structure_errors"]:
        print("  STRUCTURE ERRORS          %d" % len(st["structure_errors"]))
        for e in st["structure_errors"][:10]:
            print("     %s::%s  %s" % e)

    if not args.module:
        # The index lives one level ABOVE the module tree so `out/` reads as
        # "here is the index, here are the modules".
        write_index(os.path.join(os.path.dirname(outdir), "_index.md"),
                    cache, em, files, time.time() - t0, usmap=usmap,
                    module_dir=os.path.basename(outdir))
    print("done in %.1fs" % (time.time() - t0))
    return 0


if __name__ == "__main__":
    sys.exit(main())
