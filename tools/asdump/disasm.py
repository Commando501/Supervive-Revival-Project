"""AngelScript bytecode disassembler for SUPERVIVE's PrecompiledScript.Cache.

Bytecode is stored in RAW IN-MEMORY DWORD FORM (NOT AngelScript's asCWriter
varint form), framed as:

    u16  stackNeeded?      (commonly 32 / 33 / 34 / 48)
    u16  flags?            (commonly 0 or 4)
    u32  dwordCount        <-- length of the bytecode in DWORDs
    u32 * dwordCount       <-- the instructions

Each instruction: opcode in the LOW BYTE of its first dword; total length is
TYPE_SIZE[type] dwords. Operand accessors (bc = byte offset of instruction):
    W0/wW0/rW0 : int16 at bc+2      W1/rW1 : int16 at bc+4     rW2 : int16 at bc+6
    DW  : int32 at bc+4             DW2 : int32 at bc+8        DW3 : int32 at bc+12
    QW  : int64 at bc+4

Relative jumps (JMP/JZ/JNZ/JS/JNS/JP/JNP/JLowZ/JLowNZ) store a DWORD-count
offset relative to the START OF THE NEXT INSTRUCTION:
    target_byte_offset = insn_offset + 8 + DW*4
(Note: in AngelScript's own *serialized* form these are instruction counts;
here they are dword counts, i.e. the raw in-memory form.)
"""
import os, struct, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from opcodes import OPCODES, MAXBYTECODE

RET = 10
JUMPS = {11, 12, 13, 14, 15, 16, 17, 187, 188}


def decode(buf, start, ndwords):
    """Linear-decode ndwords DWORDs of bytecode at byte offset `start`.

    Yields dicts: {off, op, name, size, args:{...}, target (for jumps)}.
    Raises ValueError if the stream desynchronizes.
    """
    off, end = start, start + ndwords * 4
    while off < end:
        op = buf[off]
        if op >= MAXBYTECODE:
            raise ValueError('invalid opcode %d at 0x%x' % (op, off))
        name, tid, tname, size, layout, stackinc = OPCODES[op]
        if off + size * 4 > end:
            raise ValueError('instruction at 0x%x overruns blob end' % off)
        a = {}
        for f in layout:
            if f in ('W0', 'wW0', 'rW0'): a[f] = struct.unpack_from('<h', buf, off + 2)[0]
            elif f in ('W1', 'rW1'):      a[f] = struct.unpack_from('<h', buf, off + 4)[0]
            elif f == 'rW2':              a[f] = struct.unpack_from('<h', buf, off + 6)[0]
            elif f == 'DW':               a[f] = struct.unpack_from('<i', buf, off + 4)[0]
            elif f == 'DW2':              a[f] = struct.unpack_from('<i', buf, off + 8)[0]
            elif f == 'DW3':              a[f] = struct.unpack_from('<i', buf, off + 12)[0]
            elif f == 'QW':               a[f] = struct.unpack_from('<Q', buf, off + 4)[0]
        ins = {'off': off, 'op': op, 'name': name, 'size': size,
               'type': tname, 'args': a, 'stackinc': stackinc}
        if op in JUMPS:
            ins['target'] = off + 8 + a['DW'] * 4
        yield ins
        off += size * 4
    if off != end:
        raise ValueError('blob did not land on its declared end')


def format_ins(ins):
    a = ins['args']
    parts = []
    for k in ('W0', 'wW0', 'rW0', 'W1', 'rW1', 'rW2'):
        if k in a: parts.append('%s=%d' % (k, a[k]))
    if 'DW' in a:
        parts.append('->0x%06x' % ins['target'] if 'target' in ins else 'DW=%d' % a['DW'])
    for k in ('DW2', 'DW3'):
        if k in a: parts.append('%s=%d' % (k, a[k]))
    if 'QW' in a: parts.append('QW=0x%x' % a['QW'])
    return '%06x  %-16s %s' % (ins['off'], ins['name'], ' '.join(parts))


def disassemble_blob(buf, count_off):
    """count_off = byte offset of the u32 dwordCount. Returns (ndwords, [ins])."""
    n = struct.unpack_from('<I', buf, count_off)[0]
    return n, list(decode(buf, count_off + 4, n))


if __name__ == '__main__':
    CACHE = r'G:\git\GAME BACKUPS FOR REVERSE ENGINEERING\SUPERVIVE\Loki\Script\PrecompiledScript.Cache'
    buf = open(CACHE, 'rb').read()
    off = int(sys.argv[1], 0) if len(sys.argv) > 1 else 0x37c
    n, ins = disassemble_blob(buf, off)
    print('blob at 0x%x : %d dwords, %d instructions' % (off, n, len(ins)))
    for i in ins:
        print('  ' + format_ins(i))
