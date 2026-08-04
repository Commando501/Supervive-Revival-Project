"""Locate AngelScript bytecode regions in PrecompiledScript.Cache.

Tries both plausible serialized forms and reports the longest self-consistent
linear decodes. Stdlib only.

  RAW  : in-memory form -- instruction = TYPE_SIZE[type] dwords, opcode = low byte.
  VARINT: asCWriter form -- 1 opcode byte + WriteEncodedInt64-packed args.
"""
import sys, os, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from opcodes import OPCODES, MAXBYTECODE

CACHE = r'G:\git\GAME BACKUPS FOR REVERSE ENGINEERING\SUPERVIVE\Loki\Script\PrecompiledScript.Cache'


def decode_raw(d, off, limit=10**9):
    """Linear decode assuming in-memory dword form. Returns list of (off, op, size)."""
    out = []
    n = len(d)
    while off + 4 <= n and len(out) < limit:
        op = d[off]
        if op >= MAXBYTECODE:
            break
        sz = OPCODES[op][3]
        if off + sz * 4 > n:
            break
        out.append((off, op, sz))
        off += sz * 4
    return out


def read_varint(d, p):
    """AngelScript ReadEncodedUInt64. Returns (value, newpos) or (None, p) on overrun."""
    n = len(d)
    if p >= n:
        return None, p
    b = d[p]; p += 1
    neg = bool(b & 0x80); b &= 0x7F
    def take(k):
        nonlocal p
        if p + k > n: raise IndexError
        v = d[p:p+k]; p += k; return v
    try:
        if (b & 0x7F) == 0x7F:   i = int.from_bytes(take(8), 'big')
        elif (b & 0x7E) == 0x7E: i = ((b & 0x01) << 48) + int.from_bytes(take(6), 'big')
        elif (b & 0x7C) == 0x7C: i = ((b & 0x03) << 40) + int.from_bytes(take(5), 'big')
        elif (b & 0x78) == 0x78: i = ((b & 0x07) << 32) + int.from_bytes(take(4), 'big')
        elif (b & 0x70) == 0x70: i = ((b & 0x0F) << 24) + int.from_bytes(take(3), 'big')
        elif (b & 0x60) == 0x60: i = ((b & 0x1F) << 16) + int.from_bytes(take(2), 'big')
        elif (b & 0x40) == 0x40: i = ((b & 0x3F) << 8)  + int.from_bytes(take(1), 'big')
        else:                    i = b
    except IndexError:
        return None, p
    return (-i if neg else i), p


# how many varints each type writes (from asCWriter::WriteByteCode)
VARINT_ARGS = {
    'INFO': 0, 'NO_ARG': 0, 'W_ARG': 1, 'wW_ARG': 1, 'rW_ARG': 1,
    'rW_DW_ARG': 2, 'wW_DW_ARG': 2, 'W_DW_ARG': 2, 'W_DW_ARG21': 2,
    'DW_ARG': 1, 'DW_DW_ARG': 2, 'wW_rW_rW_ARG': 3, 'wW_rW_ARG': 2,
    'rW_rW_ARG': 2, 'wW_W_ARG': 2, 'wW_rW_DW_ARG': 3, 'rW_W_DW_ARG': 3,
    'QW_ARG': 1, 'QW_DW_ARG': 2, 'wW_QW_ARG': 2, 'rW_QW_ARG': 2,
    'rW_DW_DW_ARG': 3,
}


def decode_varint(d, off, limit=10**9):
    out = []
    n = len(d)
    while off < n and len(out) < limit:
        op = d[off]
        if op >= MAXBYTECODE:
            break
        tn = OPCODES[op][2]
        p = off + 1
        ok = True
        for _ in range(VARINT_ARGS[tn]):
            v, p = read_varint(d, p)
            if v is None:
                ok = False; break
        if not ok:
            break
        out.append((off, op, p - off))
        off = p
    return out


def scan(d, fn, label, topn=15):
    n = len(d)
    best = []
    off = 0
    covered = {}
    step = 1 if fn is decode_varint else 4
    for off in range(0, n - 8, step):
        ins = fn(d, off, limit=100000)
        if len(ins) >= 60:
            end = ins[-1][0] + ins[-1][2] if fn is decode_varint else ins[-1][0] + ins[-1][2]*4
            best.append((len(ins), off, end))
    best.sort(reverse=True)
    print('=== %s : runs >=60 instructions: %d ===' % (label, len(best)))
    for cnt, o, e in best[:topn]:
        print('   %6d instrs  0x%06x .. 0x%06x  (%d bytes)' % (cnt, o, e, e - o))
    return best


if __name__ == '__main__':
    d = open(CACHE, 'rb').read()
    print('file %d bytes' % len(d))
    scan(d, decode_raw, 'RAW dword form')
    print()
    scan(d, decode_varint, 'VARINT (asCWriter) form')
