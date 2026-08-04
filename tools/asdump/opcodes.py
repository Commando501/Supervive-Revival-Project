"""AngelScript opcode table for SUPERVIVE (UE-Angelscript fork), build 2025-12-17.

EXTRACTED BYTE-EXACT from the game binary's own asBCInfo[256] table
(dumps/merged.dump.exe, RVA 0x84a22c0, ImageBase 0x7ff6af000000, 24-byte
asSBCInfo entries {asEBCInstr bc; asEBCType type; int stackInc; const char* name;}).
Sizes come from the binary's own asBCTypeSize[22] (RVA 0x84b45a0 / 0x84ea4a0).

NOT copied from upstream AngelScript -- the fork differs (see FORK_DIFFS).

OPCODES[n] = (name, type_id, type_name, size_in_dwords, operand_layout, stack_inc)
  size_in_dwords : length of the instruction in the IN-MEMORY dword form.
  stack_inc      : 0xFFFF (65535) is AngelScript's "variable, computed at runtime" sentinel.

Operand accessors (in-memory form, bc = pointer to first dword):
  opcode   = byte 0 of dword 0
  W0/wW0/rW0 = int16 at byte offset 2   (asBC_SWORDARG0)
  W1/rW1     = int16 at byte offset 4   (asBC_SWORDARG1)
  rW2        = int16 at byte offset 6   (asBC_SWORDARG2)
  DW         = int32 at dword index 1   (asBC_DWORDARG)
  DW2        = int32 at dword index 2
  DW3        = int32 at dword index 3   (only QW_DW_ARG)
  QW         = int64 at dword index 1   (asBC_QWORDARG / asBC_PTRARG)
"""

MAXBYTECODE = 213          # EXCLUSIVE bound: opcodes 0..212 are real and decodable.
                           # 213..250 are unused dummy slots ("BC_213"...), 251..255 pseudo.
                           # NOTE: the binary's dummy entries carry bc==212, which would imply
                           # asBC_MAXBYTECODE==212, yet slot 212 (ThrowException) has a real
                           # name+type+size. Treat 0..212 as valid; the fork appears to have
                           # not bumped MAXBYTECODE when ThrowException was appended.
FIRST_PSEUDO = 251         # VarDecl/Block/ObjInfo/LINE/LABEL - never in final bytecode
                           # (upstream 2.38 has TryBlock at 250; this fork does NOT -- dummy)

# asEBCType id -> size in dwords (the fork's asBCTypeSize[22]; upstream has only 21)
TYPE_SIZE = [0,1,1,1,2,2,3,3,2,3,2,1,2,3,2,2,4,3,2,3,3,2]

# name, type_id, type_name, size_dwords, operand_layout, stack_inc
OPCODES = {
      0: ('PopPtr',            1, 'NO_ARG',        1, (),                                -2),
      1: ('PshGPtr',           6, 'QW_ARG',        3, ('QW',),                            2),
      2: ('PshC4',             4, 'DW_ARG',        2, ('DW',),                            1),
      3: ('PshV4',            11, 'rW_ARG',        1, ('rW0',),                           1),
      4: ('PSF',              11, 'rW_ARG',        1, ('rW0',),                           2),
      5: ('SwapPtr',           1, 'NO_ARG',        1, (),                                 0),
      6: ('NOT',              11, 'rW_ARG',        1, ('rW0',),                           0),
      7: ('PshG4',             6, 'QW_ARG',        3, ('QW',),                            1),
      8: ('LdGRdR4',           9, 'wW_QW_ARG',     3, ('wW0', 'QW'),                      0),
      9: ('CALL',              4, 'DW_ARG',        2, ('DW',),                        65535),
     10: ('RET',               2, 'W_ARG',         1, ('W0',),                        65535),
     11: ('JMP',               4, 'DW_ARG',        2, ('DW',),                            0),
     12: ('JZ',                4, 'DW_ARG',        2, ('DW',),                            0),
     13: ('JNZ',               4, 'DW_ARG',        2, ('DW',),                            0),
     14: ('JS',                4, 'DW_ARG',        2, ('DW',),                            0),
     15: ('JNS',               4, 'DW_ARG',        2, ('DW',),                            0),
     16: ('JP',                4, 'DW_ARG',        2, ('DW',),                            0),
     17: ('JNP',               4, 'DW_ARG',        2, ('DW',),                            0),
     18: ('TZ',                1, 'NO_ARG',        1, (),                                 0),
     19: ('TNZ',               1, 'NO_ARG',        1, (),                                 0),
     20: ('TS',                1, 'NO_ARG',        1, (),                                 0),
     21: ('TNS',               1, 'NO_ARG',        1, (),                                 0),
     22: ('TP',                1, 'NO_ARG',        1, (),                                 0),
     23: ('TNP',               1, 'NO_ARG',        1, (),                                 0),
     24: ('NEGi',             11, 'rW_ARG',        1, ('rW0',),                           0),
     25: ('NEGf',             11, 'rW_ARG',        1, ('rW0',),                           0),
     26: ('NEGd',             11, 'rW_ARG',        1, ('rW0',),                           0),
     27: ('INCi16',            1, 'NO_ARG',        1, (),                                 0),
     28: ('INCi8',             1, 'NO_ARG',        1, (),                                 0),
     29: ('DECi16',            1, 'NO_ARG',        1, (),                                 0),
     30: ('DECi8',             1, 'NO_ARG',        1, (),                                 0),
     31: ('INCi',              1, 'NO_ARG',        1, (),                                 0),
     32: ('DECi',              1, 'NO_ARG',        1, (),                                 0),
     33: ('INCf',              1, 'NO_ARG',        1, (),                                 0),
     34: ('DECf',              1, 'NO_ARG',        1, (),                                 0),
     35: ('INCd',              1, 'NO_ARG',        1, (),                                 0),
     36: ('DECd',              1, 'NO_ARG',        1, (),                                 0),
     37: ('IncVi',            11, 'rW_ARG',        1, ('rW0',),                           0),
     38: ('DecVi',            11, 'rW_ARG',        1, ('rW0',),                           0),
     39: ('BNOT',             11, 'rW_ARG',        1, ('rW0',),                           0),
     40: ('BAND',              8, 'wW_rW_rW_ARG',  2, ('wW0', 'rW1', 'rW2'),              0),
     41: ('BOR',               8, 'wW_rW_rW_ARG',  2, ('wW0', 'rW1', 'rW2'),              0),
     42: ('BXOR',              8, 'wW_rW_rW_ARG',  2, ('wW0', 'rW1', 'rW2'),              0),
     43: ('BSLL',              8, 'wW_rW_rW_ARG',  2, ('wW0', 'rW1', 'rW2'),              0),
     44: ('BSRL',              8, 'wW_rW_rW_ARG',  2, ('wW0', 'rW1', 'rW2'),              0),
     45: ('BSRA',              8, 'wW_rW_rW_ARG',  2, ('wW0', 'rW1', 'rW2'),              0),
     46: ('COPY',             18, 'W_DW_ARG',      2, ('W0', 'DW'),                      -2),
     47: ('PshC8',             6, 'QW_ARG',        3, ('QW',),                            2),
     48: ('PshVPtr',          11, 'rW_ARG',        1, ('rW0',),                           2),
     49: ('RDSPtr',            1, 'NO_ARG',        1, (),                                 0),
     50: ('CMPd',             14, 'rW_rW_ARG',     2, ('rW0', 'rW1'),                     0),
     51: ('CMPu',             14, 'rW_rW_ARG',     2, ('rW0', 'rW1'),                     0),
     52: ('CMPf',             14, 'rW_rW_ARG',     2, ('rW0', 'rW1'),                     0),
     53: ('CMPi',             14, 'rW_rW_ARG',     2, ('rW0', 'rW1'),                     0),
     54: ('CMPIi',             5, 'rW_DW_ARG',     2, ('rW0', 'DW'),                      0),
     55: ('CMPIf',             5, 'rW_DW_ARG',     2, ('rW0', 'DW'),                      0),
     56: ('CMPIu',             5, 'rW_DW_ARG',     2, ('rW0', 'DW'),                      0),
     57: ('JMPP',              5, 'rW_DW_ARG',     2, ('rW0', 'DW'),                      0),
     58: ('PopRPtr',           1, 'NO_ARG',        1, (),                                -2),
     59: ('PshRPtr',           1, 'NO_ARG',        1, (),                                 2),
     60: ('STR',               2, 'W_ARG',         1, ('W0',),                            3),
     61: ('CALLSYS',           6, 'QW_ARG',        3, ('QW',),                        65535),
     62: ('CALLBND',           4, 'DW_ARG',        2, ('DW',),                        65535),
     63: ('SUSPEND',           1, 'NO_ARG',        1, (),                                 0),
     64: ('ALLOC',            16, 'QW_DW_ARG',     4, ('QW', 'DW3'),                  65535),
     65: ('FREE',              9, 'wW_QW_ARG',     3, ('wW0', 'QW'),                      0),
     66: ('LOADOBJ',          11, 'rW_ARG',        1, ('rW0',),                           0),
     67: ('STOREOBJ',          3, 'wW_ARG',        1, ('wW0',),                           0),
     68: ('GETOBJ',           21, 'W_DW_ARG21',    2, ('W0', 'DW'),                       0),
     69: ('REFCPY',            1, 'NO_ARG',        1, (),                                -2),
     70: ('CHKREF',            1, 'NO_ARG',        1, (),                                 0),
     71: ('GETOBJREF',        21, 'W_DW_ARG21',    2, ('W0', 'DW'),                       0),
     72: ('GETREF',           21, 'W_DW_ARG21',    2, ('W0', 'DW'),                       0),
     73: ('PshNull',           1, 'NO_ARG',        1, (),                                 2),
     74: ('ClrVPtr',           3, 'wW_ARG',        1, ('wW0',),                           0),
     75: ('OBJTYPE',           6, 'QW_ARG',        3, ('QW',),                            2),
     76: ('TYPEID',            4, 'DW_ARG',        2, ('DW',),                            1),
     77: ('SetV4',            12, 'wW_DW_ARG',     2, ('wW0', 'DW'),                      0),
     78: ('SetV8',             9, 'wW_QW_ARG',     3, ('wW0', 'QW'),                      0),
     79: ('ADDSi',            18, 'W_DW_ARG',      2, ('W0', 'DW'),                       0),
     80: ('CpyVtoV4',         10, 'wW_rW_ARG',     2, ('wW0', 'rW1'),                     0),
     81: ('CpyVtoV8',         10, 'wW_rW_ARG',     2, ('wW0', 'rW1'),                     0),
     82: ('CpyVtoR4',         11, 'rW_ARG',        1, ('rW0',),                           0),
     83: ('CpyVtoR8',         11, 'rW_ARG',        1, ('rW0',),                           0),
     84: ('CpyVtoG4',         17, 'rW_QW_ARG',     3, ('rW0', 'QW'),                      0),
     85: ('CpyRtoV4',          3, 'wW_ARG',        1, ('wW0',),                           0),
     86: ('CpyRtoV8',          3, 'wW_ARG',        1, ('wW0',),                           0),
     87: ('CpyGtoV4',          9, 'wW_QW_ARG',     3, ('wW0', 'QW'),                      0),
     88: ('WRTV1',            11, 'rW_ARG',        1, ('rW0',),                           0),
     89: ('WRTV2',            11, 'rW_ARG',        1, ('rW0',),                           0),
     90: ('WRTV4',            11, 'rW_ARG',        1, ('rW0',),                           0),
     91: ('WRTV8',            11, 'rW_ARG',        1, ('rW0',),                           0),
     92: ('RDR1',              3, 'wW_ARG',        1, ('wW0',),                           0),
     93: ('RDR2',              3, 'wW_ARG',        1, ('wW0',),                           0),
     94: ('RDR4',              3, 'wW_ARG',        1, ('wW0',),                           0),
     95: ('RDR8',              3, 'wW_ARG',        1, ('wW0',),                           0),
     96: ('LDG',               6, 'QW_ARG',        3, ('QW',),                            0),
     97: ('LDV',              11, 'rW_ARG',        1, ('rW0',),                           0),
     98: ('PGA',               6, 'QW_ARG',        3, ('QW',),                            2),
     99: ('CmpPtr',           14, 'rW_rW_ARG',     2, ('rW0', 'rW1'),                     0),
    100: ('VAR',              11, 'rW_ARG',        1, ('rW0',),                           2),
    101: ('iTOf',             10, 'wW_rW_ARG',     2, ('wW0', 'rW1'),                     0),
    102: ('fTOi',             10, 'wW_rW_ARG',     2, ('wW0', 'rW1'),                     0),
    103: ('uTOf',             10, 'wW_rW_ARG',     2, ('wW0', 'rW1'),                     0),
    104: ('fTOu',             10, 'wW_rW_ARG',     2, ('wW0', 'rW1'),                     0),
    105: ('sbTOi',            10, 'wW_rW_ARG',     2, ('wW0', 'rW1'),                     0),
    106: ('swTOi',            10, 'wW_rW_ARG',     2, ('wW0', 'rW1'),                     0),
    107: ('ubTOi',            10, 'wW_rW_ARG',     2, ('wW0', 'rW1'),                     0),
    108: ('uwTOi',            10, 'wW_rW_ARG',     2, ('wW0', 'rW1'),                     0),
    109: ('dTOi',             10, 'wW_rW_ARG',     2, ('wW0', 'rW1'),                     0),
    110: ('dTOu',             10, 'wW_rW_ARG',     2, ('wW0', 'rW1'),                     0),
    111: ('dTOf',             10, 'wW_rW_ARG',     2, ('wW0', 'rW1'),                     0),
    112: ('iTOd',             10, 'wW_rW_ARG',     2, ('wW0', 'rW1'),                     0),
    113: ('uTOd',             10, 'wW_rW_ARG',     2, ('wW0', 'rW1'),                     0),
    114: ('fTOd',             10, 'wW_rW_ARG',     2, ('wW0', 'rW1'),                     0),
    115: ('ADDi',              8, 'wW_rW_rW_ARG',  2, ('wW0', 'rW1', 'rW2'),              0),
    116: ('SUBi',              8, 'wW_rW_rW_ARG',  2, ('wW0', 'rW1', 'rW2'),              0),
    117: ('MULi',              8, 'wW_rW_rW_ARG',  2, ('wW0', 'rW1', 'rW2'),              0),
    118: ('DIVi',              8, 'wW_rW_rW_ARG',  2, ('wW0', 'rW1', 'rW2'),              0),
    119: ('MODi',              8, 'wW_rW_rW_ARG',  2, ('wW0', 'rW1', 'rW2'),              0),
    120: ('ADDf',              8, 'wW_rW_rW_ARG',  2, ('wW0', 'rW1', 'rW2'),              0),
    121: ('SUBf',              8, 'wW_rW_rW_ARG',  2, ('wW0', 'rW1', 'rW2'),              0),
    122: ('MULf',              8, 'wW_rW_rW_ARG',  2, ('wW0', 'rW1', 'rW2'),              0),
    123: ('DIVf',              8, 'wW_rW_rW_ARG',  2, ('wW0', 'rW1', 'rW2'),              0),
    124: ('MODf',              8, 'wW_rW_rW_ARG',  2, ('wW0', 'rW1', 'rW2'),              0),
    125: ('ADDd',              8, 'wW_rW_rW_ARG',  2, ('wW0', 'rW1', 'rW2'),              0),
    126: ('SUBd',              8, 'wW_rW_rW_ARG',  2, ('wW0', 'rW1', 'rW2'),              0),
    127: ('MULd',              8, 'wW_rW_rW_ARG',  2, ('wW0', 'rW1', 'rW2'),              0),
    128: ('DIVd',              8, 'wW_rW_rW_ARG',  2, ('wW0', 'rW1', 'rW2'),              0),
    129: ('MODd',              8, 'wW_rW_rW_ARG',  2, ('wW0', 'rW1', 'rW2'),              0),
    130: ('ADDIi',            13, 'wW_rW_DW_ARG',  3, ('wW0', 'rW1', 'DW2'),              0),
    131: ('SUBIi',            13, 'wW_rW_DW_ARG',  3, ('wW0', 'rW1', 'DW2'),              0),
    132: ('MULIi',            13, 'wW_rW_DW_ARG',  3, ('wW0', 'rW1', 'DW2'),              0),
    133: ('ADDIf',            13, 'wW_rW_DW_ARG',  3, ('wW0', 'rW1', 'DW2'),              0),
    134: ('SUBIf',            13, 'wW_rW_DW_ARG',  3, ('wW0', 'rW1', 'DW2'),              0),
    135: ('MULIf',            13, 'wW_rW_DW_ARG',  3, ('wW0', 'rW1', 'DW2'),              0),
    136: ('SetG4',            16, 'QW_DW_ARG',     4, ('QW', 'DW3'),                      0),
    137: ('ChkRefS',           1, 'NO_ARG',        1, (),                                 0),
    138: ('ChkNullV',         11, 'rW_ARG',        1, ('rW0',),                           0),
    139: ('CALLINTF',          4, 'DW_ARG',        2, ('DW',),                        65535),
    140: ('iTOb',             10, 'wW_rW_ARG',     2, ('wW0', 'rW1'),                     0),
    141: ('iTOw',             10, 'wW_rW_ARG',     2, ('wW0', 'rW1'),                     0),
    142: ('SetV1',            12, 'wW_DW_ARG',     2, ('wW0', 'DW'),                      0),
    143: ('SetV2',            12, 'wW_DW_ARG',     2, ('wW0', 'DW'),                      0),
    144: ('Cast',              4, 'DW_ARG',        2, ('DW',),                           -2),
    145: ('i64TOi',           10, 'wW_rW_ARG',     2, ('wW0', 'rW1'),                     0),
    146: ('uTOi64',           10, 'wW_rW_ARG',     2, ('wW0', 'rW1'),                     0),
    147: ('iTOi64',           10, 'wW_rW_ARG',     2, ('wW0', 'rW1'),                     0),
    148: ('fTOi64',           10, 'wW_rW_ARG',     2, ('wW0', 'rW1'),                     0),
    149: ('dTOi64',           10, 'wW_rW_ARG',     2, ('wW0', 'rW1'),                     0),
    150: ('fTOu64',           10, 'wW_rW_ARG',     2, ('wW0', 'rW1'),                     0),
    151: ('dTOu64',           10, 'wW_rW_ARG',     2, ('wW0', 'rW1'),                     0),
    152: ('i64TOf',           10, 'wW_rW_ARG',     2, ('wW0', 'rW1'),                     0),
    153: ('u64TOf',           10, 'wW_rW_ARG',     2, ('wW0', 'rW1'),                     0),
    154: ('i64TOd',           10, 'wW_rW_ARG',     2, ('wW0', 'rW1'),                     0),
    155: ('u64TOd',           10, 'wW_rW_ARG',     2, ('wW0', 'rW1'),                     0),
    156: ('NEGi64',           11, 'rW_ARG',        1, ('rW0',),                           0),
    157: ('INCi64',            1, 'NO_ARG',        1, (),                                 0),
    158: ('DECi64',            1, 'NO_ARG',        1, (),                                 0),
    159: ('BNOT64',           11, 'rW_ARG',        1, ('rW0',),                           0),
    160: ('ADDi64',            8, 'wW_rW_rW_ARG',  2, ('wW0', 'rW1', 'rW2'),              0),
    161: ('SUBi64',            8, 'wW_rW_rW_ARG',  2, ('wW0', 'rW1', 'rW2'),              0),
    162: ('MULi64',            8, 'wW_rW_rW_ARG',  2, ('wW0', 'rW1', 'rW2'),              0),
    163: ('DIVi64',            8, 'wW_rW_rW_ARG',  2, ('wW0', 'rW1', 'rW2'),              0),
    164: ('MODi64',            8, 'wW_rW_rW_ARG',  2, ('wW0', 'rW1', 'rW2'),              0),
    165: ('BAND64',            8, 'wW_rW_rW_ARG',  2, ('wW0', 'rW1', 'rW2'),              0),
    166: ('BOR64',             8, 'wW_rW_rW_ARG',  2, ('wW0', 'rW1', 'rW2'),              0),
    167: ('BXOR64',            8, 'wW_rW_rW_ARG',  2, ('wW0', 'rW1', 'rW2'),              0),
    168: ('BSLL64',            8, 'wW_rW_rW_ARG',  2, ('wW0', 'rW1', 'rW2'),              0),
    169: ('BSRL64',            8, 'wW_rW_rW_ARG',  2, ('wW0', 'rW1', 'rW2'),              0),
    170: ('BSRA64',            8, 'wW_rW_rW_ARG',  2, ('wW0', 'rW1', 'rW2'),              0),
    171: ('CMPi64',           14, 'rW_rW_ARG',     2, ('rW0', 'rW1'),                     0),
    172: ('CMPu64',           14, 'rW_rW_ARG',     2, ('rW0', 'rW1'),                     0),
    173: ('ChkNullS',          2, 'W_ARG',         1, ('W0',),                            0),
    174: ('ClrHi',             1, 'NO_ARG',        1, (),                                 0),
    175: ('JitEntry',          6, 'QW_ARG',        3, ('QW',),                            0),
    176: ('CallPtr',          11, 'rW_ARG',        1, ('rW0',),                       65535),
    177: ('FuncPtr',           6, 'QW_ARG',        3, ('QW',),                            2),
    178: ('LoadThisR',        18, 'W_DW_ARG',      2, ('W0', 'DW'),                       0),
    179: ('PshV8',            11, 'rW_ARG',        1, ('rW0',),                           2),
    180: ('DIVu',              8, 'wW_rW_rW_ARG',  2, ('wW0', 'rW1', 'rW2'),              0),
    181: ('MODu',              8, 'wW_rW_rW_ARG',  2, ('wW0', 'rW1', 'rW2'),              0),
    182: ('DIVu64',            8, 'wW_rW_rW_ARG',  2, ('wW0', 'rW1', 'rW2'),              0),
    183: ('MODu64',            8, 'wW_rW_rW_ARG',  2, ('wW0', 'rW1', 'rW2'),              0),
    184: ('LoadRObjR',        19, 'rW_W_DW_ARG',   3, ('rW0', 'W1', 'DW2'),               0),
    185: ('LoadVObjR',        19, 'rW_W_DW_ARG',   3, ('rW0', 'W1', 'DW2'),               0),
    186: ('RefCpyV',           3, 'wW_ARG',        1, ('wW0',),                          -2),
    187: ('JLowZ',             4, 'DW_ARG',        2, ('DW',),                            0),
    188: ('JLowNZ',            4, 'DW_ARG',        2, ('DW',),                            0),
    189: ('AllocMem',         12, 'wW_DW_ARG',     2, ('wW0', 'DW'),                      0),
    190: ('SetListSize',      20, 'rW_DW_DW_ARG',  3, ('rW0', 'DW', 'DW2'),               0),
    191: ('PshListElmnt',      5, 'rW_DW_ARG',     2, ('rW0', 'DW'),                      2),
    192: ('SetListType',      20, 'rW_DW_DW_ARG',  3, ('rW0', 'DW', 'DW2'),               0),
    193: ('POWi',              8, 'wW_rW_rW_ARG',  2, ('wW0', 'rW1', 'rW2'),              0),
    194: ('POWu',              8, 'wW_rW_rW_ARG',  2, ('wW0', 'rW1', 'rW2'),              0),
    195: ('POWf',              8, 'wW_rW_rW_ARG',  2, ('wW0', 'rW1', 'rW2'),              0),
    196: ('POWd',              8, 'wW_rW_rW_ARG',  2, ('wW0', 'rW1', 'rW2'),              0),
    197: ('POWdi',             8, 'wW_rW_rW_ARG',  2, ('wW0', 'rW1', 'rW2'),              0),
    198: ('POWi64',            8, 'wW_rW_rW_ARG',  2, ('wW0', 'rW1', 'rW2'),              0),
    199: ('POWu64',            8, 'wW_rW_rW_ARG',  2, ('wW0', 'rW1', 'rW2'),              0),
    200: ('Thiscall1',         6, 'QW_ARG',        3, ('QW',),                           -3),
    201: ('FinConstruct',      6, 'QW_ARG',        3, ('QW',),                           -2),
    202: ('DestructScript',   17, 'rW_QW_ARG',     3, ('rW0', 'QW'),                      0),
    203: ('CopyScript',        6, 'QW_ARG',        3, ('QW',),                           -2),
    204: ('ResolveObjectPtr',  1, 'NO_ARG',        1, (),                                 0),
    205: ('FreeNullV8',        3, 'wW_ARG',        1, ('wW0',),                           0),
    206: ('TrackRef',         11, 'rW_ARG',        1, ('rW0',),                           0),
    207: ('UntrackRef',       11, 'rW_ARG',        1, ('rW0',),                           0),
    208: ('ValidateRef',      11, 'rW_ARG',        1, ('rW0',),                           0),
    209: ('CpyVtoR1',         11, 'rW_ARG',        1, ('rW0',),                           0),
    210: ('SaveReturnValue',   1, 'NO_ARG',        1, (),                                 0),
    211: ('CmpPtrNull',       11, 'rW_ARG',        1, ('rW0',),                           0),
    212: ('ThrowException',    2, 'W_ARG',         1, ('W0',),                            0),
    213: ('BC_213',            0, 'INFO',          0, (),                                 0),
    214: ('BC_214',            0, 'INFO',          0, (),                                 0),
    215: ('BC_215',            0, 'INFO',          0, (),                                 0),
    216: ('BC_216',            0, 'INFO',          0, (),                                 0),
    217: ('BC_217',            0, 'INFO',          0, (),                                 0),
    218: ('BC_218',            0, 'INFO',          0, (),                                 0),
    219: ('BC_219',            0, 'INFO',          0, (),                                 0),
    220: ('BC_220',            0, 'INFO',          0, (),                                 0),
    221: ('BC_221',            0, 'INFO',          0, (),                                 0),
    222: ('BC_222',            0, 'INFO',          0, (),                                 0),
    223: ('BC_223',            0, 'INFO',          0, (),                                 0),
    224: ('BC_224',            0, 'INFO',          0, (),                                 0),
    225: ('BC_225',            0, 'INFO',          0, (),                                 0),
    226: ('BC_226',            0, 'INFO',          0, (),                                 0),
    227: ('BC_227',            0, 'INFO',          0, (),                                 0),
    228: ('BC_228',            0, 'INFO',          0, (),                                 0),
    229: ('BC_229',            0, 'INFO',          0, (),                                 0),
    230: ('BC_230',            0, 'INFO',          0, (),                                 0),
    231: ('BC_231',            0, 'INFO',          0, (),                                 0),
    232: ('BC_232',            0, 'INFO',          0, (),                                 0),
    233: ('BC_233',            0, 'INFO',          0, (),                                 0),
    234: ('BC_234',            0, 'INFO',          0, (),                                 0),
    235: ('BC_235',            0, 'INFO',          0, (),                                 0),
    236: ('BC_236',            0, 'INFO',          0, (),                                 0),
    237: ('BC_237',            0, 'INFO',          0, (),                                 0),
    238: ('BC_238',            0, 'INFO',          0, (),                                 0),
    239: ('BC_239',            0, 'INFO',          0, (),                                 0),
    240: ('BC_240',            0, 'INFO',          0, (),                                 0),
    241: ('BC_241',            0, 'INFO',          0, (),                                 0),
    242: ('BC_242',            0, 'INFO',          0, (),                                 0),
    243: ('BC_243',            0, 'INFO',          0, (),                                 0),
    244: ('BC_244',            0, 'INFO',          0, (),                                 0),
    245: ('BC_245',            0, 'INFO',          0, (),                                 0),
    246: ('BC_246',            0, 'INFO',          0, (),                                 0),
    247: ('BC_247',            0, 'INFO',          0, (),                                 0),
    248: ('BC_248',            0, 'INFO',          0, (),                                 0),
    249: ('BC_249',            0, 'INFO',          0, (),                                 0),
    250: ('BC_250',            0, 'INFO',          0, (),                                 0),
    251: ('VarDecl',           2, 'W_ARG',         1, ('W0',),                            0),
    252: ('Block',             0, 'INFO',          0, (),                                 0),
    253: ('ObjInfo',           5, 'rW_DW_ARG',     2, ('rW0', 'DW'),                      0),
    254: ('LINE',              0, 'INFO',          0, (),                                 0),
    255: ('LABEL',             0, 'INFO',          0, (),                                 0),
}

# Opcodes whose arg layout the fork CHANGED vs upstream AngelScript 2.38.0.
# (verified by diffing the binary's table against upstream angelscript.h)
FORK_DIFFS = {
     57: ('JMPP',      'rW_ARG'      , 'rW_DW_ARG'),
     61: ('CALLSYS',   'DW_ARG'      , 'QW_ARG'),      # now an inline 64-bit pointer
     68: ('GETOBJ',    'W_ARG'       , 'type21(size2)'),
     69: ('REFCPY',    'PTR_ARG'     , 'NO_ARG'),
     71: ('GETOBJREF', 'W_ARG'       , 'type21(size2)'),
     72: ('GETREF',    'W_ARG'       , 'type21(size2)'),
    101: ('iTOf',      'rW_ARG'      , 'wW_rW_ARG'),   # + 12 more conversions, see below
    186: ('RefCpyV',   'wW_PTR_ARG'  , 'wW_ARG'),
    200: ('Thiscall1', 'DW_ARG'      , 'QW_ARG'),      # now an inline 64-bit pointer
}
# conversions changed rW_ARG -> wW_rW_ARG (separate dest reg):
CONV_CHANGED = [101,102,103,104,105,106,107,108,140,141,149,151,154,155]

# Opcodes 201..212 do not exist upstream at all - added by the UE-Angelscript fork:
FORK_ADDED = list(range(201, 213))


def size_of(op):
    """Instruction size in dwords for an opcode byte (in-memory form)."""
    return OPCODES[op][3]


def name_of(op):
    return OPCODES[op][0]


def is_real(op):
    """True if op is a real executable opcode (not a dummy/pseudo slot)."""
    return 0 <= op < MAXBYTECODE
