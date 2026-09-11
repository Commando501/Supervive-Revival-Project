#!/usr/bin/env python
"""q7_validated_returns.py -- turn the noisy stack scan of q6 into a VALIDATED set of
protector call-site RVAs.

runtime.dll is NOT packed (FK-10 [M]): 46-64 MB of plaintext x86-64 on disk.  So a candidate
return address rva can be CHECKED: the bytes immediately before it must decode as a call.
Ambient data that merely happens to fall inside the mapping will not pass.

VALIDATOR (conservative, opcode-only, no disassembler needed):
    rva-5  : E8 rel32                        (call near rel32)
    rva-6  : FF /2 with modrm 15             (call qword [rip+disp32])
    rva-7  : REX FF /2 rip-relative
    rva-2  : FF D0..D7 / FF 10..17           (call reg / call [reg])
    rva-3  : FF 50..57 xx  (call [reg+disp8]) / 41 FF Dx
    rva-6/7: FF 90..97 disp32 (call [reg+disp32]) with optional REX
And, decisively, for E8 rel32 the TARGET must land inside an EXECUTABLE section of
runtime.dll -- a second, independent condition that random data almost never satisfies.

CONTROLS
  P1 POSITIVE: the same validator is run on the game module's own stack qwords using
     dumps/merged6.dump.exe as the byte source.  A healthy UE call stack must yield a high
     pass rate; if it does not, the validator is broken.
  N1 NEGATIVE: the validator is run against the SAME COUNT of uniformly random RVAs inside
     runtime.dll's executable sections.  That is the false-positive floor.

usage: python q7_validated_returns.py [--n N]
"""
import collections
import csv
import os
import random
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from md_streams import Dump                                    # noqa: E402
from md_sweep import fast_meminfo                              # noqa: E402
from q5_killstack import memranges                             # noqa: E402

RT = "G:/git/GAME BACKUPS FOR REVERSE ENGINEERING/SUPERVIVE/Loki/Binaries/Win64/runtime.dll"
MERGED = "dumps/merged6.dump.exe"


def load_runtime():
    with open(RT, 'rb') as f:
        data = f.read()
    e = struct.unpack_from('<I', data, 0x3C)[0]
    nsec = struct.unpack_from('<H', data, e + 6)[0]
    optsz = struct.unpack_from('<H', data, e + 20)[0]
    st = e + 24 + optsz
    secs = []
    for i in range(nsec):
        s = st + i * 40
        nm = data[s:s + 8].rstrip(b'\0').decode('latin1')
        vsz, va, rsz, rp = struct.unpack_from('<IIII', data, s + 8)
        ch = struct.unpack_from('<I', data, s + 36)[0]
        secs.append((nm, va, vsz, rp, rsz, ch))
    return data, secs


DATA, SECS = load_runtime()
EXEC_RANGES = [(va, va + vsz) for nm, va, vsz, rp, rsz, ch in SECS if ch & 0x20000000]


def rt_bytes(rva, n):
    for nm, va, vsz, rp, rsz, ch in SECS:
        if va <= rva and rva + n <= va + max(vsz, rsz):
            off = rp + (rva - va)
            if off + n <= len(DATA):
                return DATA[off:off + n]
    return None


def is_exec(rva):
    return any(a <= rva < b for a, b in EXEC_RANGES)


def valid_return(rva):
    """-> reason string if the bytes before rva decode as a call, else None."""
    b = rt_bytes(rva - 8, 8)
    if b is None:
        return None
    # E8 rel32 at rva-5
    if b[3] == 0xE8:
        rel = struct.unpack_from('<i', b, 4)[0]
        tgt = (rva + rel) & 0xFFFFFFFF
        if is_exec(tgt):
            return "E8->0x%X" % tgt
        return None
    # FF /2 forms
    if b[2] == 0xFF and (b[3] & 0x38) == 0x10 and (b[3] & 0xC7) == 0x15:
        return "call[rip]"                       # rva-6: FF 15 disp32
    if b[1] == 0xFF and (b[2] & 0x38) == 0x10 and (b[2] & 0xC7) == 0x15 and 0x40 <= b[0] <= 0x4F:
        return "REX call[rip]"
    if b[6] == 0xFF and 0xD0 <= b[7] <= 0xD7:
        return "call reg"
    if b[6] == 0xFF and 0x10 <= b[7] <= 0x17 and (b[7] & 7) != 4 and (b[7] & 7) != 5:
        return "call [reg]"
    if b[5] == 0x41 and b[6] == 0xFF and 0xD0 <= b[7] <= 0xD7:
        return "call r8-r15"
    if b[5] == 0xFF and 0x50 <= b[6] <= 0x57 and (b[6] & 7) != 4:
        return "call [reg+d8]"
    if b[2] == 0xFF and 0x90 <= b[3] <= 0x97 and (b[3] & 7) != 4:
        return "call [reg+d32]"
    return None


# ---- N1 negative control -------------------------------------------------
random.seed(1)
tot_exec = sum(b - a for a, b in EXEC_RANGES)
NEG = 20000
neg_pass = 0
for _ in range(NEG):
    k = random.randrange(tot_exec)
    for a, b in EXEC_RANGES:
        if k < b - a:
            rva = a + k
            break
        k -= b - a
    if valid_return(rva):
        neg_pass += 1
print("=" * 100)
print("Q7  VALIDATED PROTECTOR RETURN ADDRESSES")
print("=" * 100)
print("runtime.dll executable bytes: %d over %d sections %s"
      % (tot_exec, len(EXEC_RANGES), [(hex(a), hex(b)) for a, b in EXEC_RANGES]))
print("N1 NEGATIVE CONTROL: %d uniformly random exec RVAs -> %d pass the validator (%.3f%%)"
      % (NEG, neg_pass, 100.0 * neg_pass / NEG))

# ---- P1 positive control: game-module return addresses -------------------
MG = None
if os.path.exists(MERGED):
    MG = open(MERGED, 'rb')


def game_valid(rva):
    if MG is None:
        return None
    MG.seek(max(0, rva - 8))
    b = MG.read(8)
    if len(b) != 8 or b.count(0) == 8:
        return None
    if b[3] == 0xE8:
        return "E8"
    if b[2] == 0xFF and (b[3] & 0xC7) == 0x15 and (b[3] & 0x38) == 0x10:
        return "call[rip]"
    if b[6] == 0xFF and 0xD0 <= b[7] <= 0xD7:
        return "call reg"
    if b[5] == 0x41 and b[6] == 0xFF and 0xD0 <= b[7] <= 0xD7:
        return "call r8-15"
    if b[5] == 0xFF and 0x50 <= b[6] <= 0x57:
        return "call [reg+d8]"
    return None


N = 6
if '--n' in sys.argv:
    N = int(sys.argv[sys.argv.index('--n') + 1])
rows = list(csv.DictReader(open('scratchpad/s133/evidence/md_sweep.tsv', encoding='utf-8'),
                           delimiter='\t'))
rows.sort(key=lambda r: int(r['create_time'] or 0))
fam = [r for r in rows if r['kill_shape'] == 'AV+EXEC+PLUS1']
ctr = [r for r in rows if r['exc_addr'] and int(r['exc_addr'], 16) & 0xFFFF == 0x205D]


def sweep(rs_rows, label, nmax):
    validated = collections.Counter()
    raw = collections.Counter()
    gp = gt = 0
    for r in rs_rows[:nmax]:
        d = Dump(r['first_path'])
        mi = fast_meminfo(r['first_path'], d.streams)
        groups = collections.defaultdict(int)
        for x in mi:
            if x[6] == 0x1000000:
                groups[x[1]] += x[3]
        hb = [(a, s) for a, s in groups.items() if not d.modof(a) and s == 0x4066000]
        gb = int(r['game_base'], 16)
        gsz = 0xA9E1000
        rs = memranges(d)
        seen_rva = set()
        for t in d.threads:
            lo, sz = t['stack'], t['stacksize']
            if not sz:
                continue
            for sa, ssz, sr in rs:
                if not (sa < lo + sz and sa + ssz > lo):
                    continue
                blob = d._at(sr, ssz)
                for i in range(0, len(blob) - 7, 8):
                    q = struct.unpack_from('<Q', blob, i)[0]
                    if q < 0x10000:
                        continue
                    if gb <= q < gb + gsz:
                        gt += 1
                        if game_valid(q - gb):
                            gp += 1
                        continue
                    for ab, span in hb:
                        if ab <= q < ab + span:
                            rva = q - ab
                            raw[rva] += 1
                            if rva not in seen_rva:
                                seen_rva.add(rva)
                                v = valid_return(rva)
                                if v:
                                    validated[(rva, v)] += 1
                            break
    print("\n%s  reports=%d" % (label, min(nmax, len(rs_rows))))
    print("   raw distinct runtime.dll RVAs on stacks : %d" % len(raw))
    print("   VALIDATED as return-after-call          : %d" % len(validated))
    print("   P1 POSITIVE CONTROL (game module qwords): %d of %d pass (%.1f%%)"
          % (gp, gt, 100.0 * gp / max(1, gt)))
    return validated, raw


vf, rf = sweep(fam, "FK-31 family", N)
vc, rc = sweep(ctr, "0x205d contrast family", min(N, len(ctr)))

print("\n--- VALIDATED protector call-site RVAs, FK-31 family, by report-count (top 50) ---")
byrva = collections.Counter()
for (rva, v), n in vf.items():
    byrva[(rva, v)] += n
for (rva, v), n in byrva.most_common(50):
    sec = [nm for nm, va, vsz, rp, rsz, ch in SECS if va <= rva < va + max(vsz, rsz)]
    print("   runtime.dll+0x%08X  %-14s %-9s in %d reports" % (rva, v, sec[0] if sec else '?', n))

only_fk31 = set(k[0] for k in vf) - set(k[0] for k in vc)
only_ctr = set(k[0] for k in vc) - set(k[0] for k in vf)
print("\n   validated RVAs in FK-31 only : %d" % len(only_fk31))
print("   validated RVAs in contrast only: %d" % len(only_ctr))
print("   shared                        : %d" % len(set(k[0] for k in vf) & set(k[0] for k in vc)))

out = 'scratchpad/s133/evidence/runtime_dll_live_callsites.txt'
with open(out, 'w') as fh:
    fh.write("# runtime.dll RVAs found on LIVE thread stacks in crashpad minidumps AND\n")
    fh.write("# validated as return-after-call against the plaintext on-disk runtime.dll.\n")
    fh.write("# false-positive floor (N1, uniform random exec RVAs): %.3f%%\n"
             % (100.0 * neg_pass / NEG))
    fh.write("# columns: RVA  call-form  section  reports(FK-31)  reports(0x205d-contrast)\n")
    cc = collections.Counter()
    for (rva, v), n in vc.items():
        cc[rva] += n
    for (rva, v), n in sorted(byrva.items()):
        sec = [nm for nm, va, vsz, rp, rsz, ch in SECS if va <= rva < va + max(vsz, rsz)]
        fh.write("0x%08X\t%s\t%s\t%d\t%d\n" % (rva, v, sec[0] if sec else '?', n, cc.get(rva, 0)))
print("\n-> %s (%d rows)" % (out, len(byrva)))
