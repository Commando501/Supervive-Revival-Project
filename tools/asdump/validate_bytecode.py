"""Validate the extracted opcode table against every bytecode blob in the cache.

Bytecode blobs are stored in RAW IN-MEMORY DWORD FORM, prefixed by a u32 giving
the blob length in DWORDs:

    u32 dwordCount
    dwordCount * u32   <- AngelScript instructions, opcode in low byte of dword 0

A blob is accepted only if a linear decode consumes EXACTLY dwordCount dwords
(landing on the boundary, never over/under) and the final instruction is RET.
That is an extremely tight test: a wrong size for any opcode desynchronizes and
the run fails to land.
"""
import sys, os, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from opcodes import OPCODES, MAXBYTECODE

CACHE = r'G:\git\GAME BACKUPS FOR REVERSE ENGINEERING\SUPERVIVE\Loki\Script\PrecompiledScript.Cache'
RET = 10

SIZE = [OPCODES[i][3] if i < MAXBYTECODE else 0 for i in range(256)]


def try_blob(d, start, ndw):
    """Decode exactly ndw dwords from `start`. Return list of (off,op) or None."""
    off = start
    end = start + ndw * 4
    ins = []
    while off < end:
        op = d[off]
        if op >= MAXBYTECODE:
            return None
        sz = SIZE[op]
        if off + sz * 4 > end:      # would overshoot the declared length
            return None
        ins.append((off, op))
        off += sz * 4
    if off != end or not ins or ins[-1][1] != RET:
        return None
    return ins


def find_blobs(d, min_dw=3, max_dw=200000):
    out = []
    n = len(d)
    for x in range(0, n - 8, 4):
        c = struct.unpack_from('<I', d, x)[0]
        if c < min_dw or c > max_dw or x + 4 + c * 4 > n:
            continue
        ins = try_blob(d, x + 4, c)
        if ins is not None:
            out.append((x, c, ins))
    return out


def check_jumps(d, ins, start, ndw):
    """Every relative jump must land on a decoded instruction boundary."""
    JUMPS = {11, 12, 13, 14, 15, 16, 17, 187, 188}   # JMP JZ JNZ JS JNS JP JNP JLowZ JLowNZ
    bounds = {o for o, _ in ins}
    end = start + ndw * 4
    good = bad = 0
    for o, op in ins:
        if op in JUMPS:
            rel = struct.unpack_from('<i', d, o + 4)[0]
            tgt = o + 8 + rel * 4          # relative to the NEXT instruction, in dwords
            if tgt in bounds or tgt == end:
                good += 1
            else:
                bad += 1
    return good, bad


if __name__ == '__main__':
    d = open(CACHE, 'rb').read()
    blobs = find_blobs(d)
    tot_ins = sum(len(b[2]) for b in blobs)
    tot_dw = sum(b[1] for b in blobs)
    print('cache: %d bytes' % len(d))
    print('validated blobs (exact landing + RET): %d' % len(blobs))
    print('total instructions decoded          : %d' % tot_ins)
    print('total dwords covered                : %d  (%.1f%% of file)'
          % (tot_dw, 100.0 * tot_dw * 4 / len(d)))
    g = b = 0
    for x, c, ins in blobs:
        gg, bb = check_jumps(d, ins, x + 4, c)
        g += gg; b += bb
    print('relative jumps landing on boundary  : %d good / %d bad' % (g, b))
    from collections import Counter
    cnt = Counter(op for _, _, ins in blobs for _, op in ins)
    print('\ndistinct opcodes seen: %d' % len(cnt))
    print('top 25 opcodes:')
    for op, k in cnt.most_common(25):
        print('   %-16s %d' % (OPCODES[op][0], k))
    fork = [op for op in cnt if op >= 201]
    print('\nfork-only opcodes (201..212) observed:')
    for op in sorted(fork):
        print('   %3d %-16s %d' % (op, OPCODES[op][0], cnt[op]))
    print('\nlargest blobs:')
    for x, c, ins in sorted(blobs, key=lambda t: -t[1])[:8]:
        print('   0x%06x  %6d dwords  %5d instrs' % (x, c, len(ins)))
