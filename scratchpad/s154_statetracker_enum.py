"""S154 state-tracker offset enumeration.

Enumerate readers/writers of the state-tracker bytes discovered in the S153
WALL P auto-fire hunt (docs/wall-p-autofire-mechanism-s153.md).

Bytes to enumerate: 0xC0D (propagated bManuallyCallSpellCompleteEvent), 0xBFC,
0xBEC, 0xBF4, 0xC0C, 0xC04 (state-active flags cleared by auto-fire family),
0xBF8, 0xBF0 (timing floats read into auto-fire callee args).

For each offset:
  - Find all instructions accessing [reg + offset] in .text
  - Classify each as READ / WRITE / CMP (branch)
  - Get the enclosing function via pdata_union.csv
  - Note the accessing instruction + width (byte/dword/etc.)

Output: scratchpad/s154_statetracker_access_map.md (human-readable) +
scratchpad/s154_statetracker_access_map.csv (machine-readable).
"""
import struct, csv
from collections import defaultdict
from capstone import Cs, CS_ARCH_X86, CS_MODE_64
from capstone.x86 import X86_OP_MEM

md = Cs(CS_ARCH_X86, CS_MODE_64); md.detail=True

# Load merged14
DUMP = "dumps/merged14.dump.exe"
with open(DUMP, 'rb') as f:
    d = f.read()
pe = struct.unpack_from('<I', d, 0x3C)[0]
for i in range(struct.unpack_from('<H', d, pe+6)[0]):
    s = d[pe+0x108+i*0x28:pe+0x108+(i+1)*0x28]
    if s[:8].rstrip(b'\0') == b'.text':
        tv, tr, ts = struct.unpack_from('<I', s, 0x0C)[0], struct.unpack_from('<I', s, 0x14)[0], struct.unpack_from('<I', s, 0x10)[0]
        break

tb = d[tr:tr+ts]

# Load pdata for enclosing-function lookup
funcs = []
with open('tools/strxref/index/pdata_union.csv') as f:
    r = csv.reader(f); next(r)
    for row in r:
        try:
            start = int(row[0], 16); end = int(row[1], 16)
            funcs.append((start, end))
        except: continue
funcs.sort()

def enclosing_func(rva):
    """Binary search for the enclosing function."""
    lo, hi = 0, len(funcs) - 1
    while lo <= hi:
        mid = (lo + hi) // 2
        st, en = funcs[mid]
        if rva < st: hi = mid - 1
        elif rva >= en: lo = mid + 1
        else: return (st, en)
    return None

OFFSETS = [0xC0D, 0xBFC, 0xBEC, 0xBF4, 0xC0C, 0xC04, 0xBF8, 0xBF0]

results = defaultdict(list)  # offset -> [(rva, mnemonic, op_str, kind, size)]

for offset in OFFSETS:
    # Encode as little-endian 4-byte disp32 for MOD=10 [reg+disp32] pattern
    disp = struct.pack('<I', offset)
    # Also 1-byte disp8 form: offset must fit in signed byte, which 0xC0D+ don't (>127) — skip disp8
    positions = []
    start = 0
    while True:
        idx = tb.find(disp, start)
        if idx < 0: break
        positions.append(idx)
        start = idx + 1

    for p in positions:
        # Try backup 2..8 to catch varying opcode encodings
        for backup in range(2, 9):
            if p - backup < 0: continue
            rva = tv + p - backup
            try:
                it = md.disasm(tb[p-backup:p-backup+16], rva)
                insn = next(it)
            except StopIteration: continue
            if not insn.operands: continue
            # Must have a memory operand at this exact displacement
            hit = False
            for op in insn.operands:
                if op.type == X86_OP_MEM and op.mem.disp == offset:
                    # Classify: WRITE if memory operand is destination (index 0 for most ops), READ/CMP otherwise
                    kind = 'CMP' if insn.mnemonic == 'cmp' else (
                           'TEST' if insn.mnemonic == 'test' else (
                           'WRITE' if op == insn.operands[0] and insn.mnemonic in ('mov', 'add', 'sub', 'and', 'or', 'xor', 'inc', 'dec', 'movsd', 'movss', 'movups') else 'READ'))
                    size = op.size
                    results[offset].append((rva, insn.mnemonic, insn.op_str, kind, size))
                    hit = True
                    break
            if hit: break

# Dedupe per (offset, rva)
for offset in list(results.keys()):
    seen = set(); uniq = []
    for row in results[offset]:
        if row[0] in seen: continue
        seen.add(row[0]); uniq.append(row)
    results[offset] = uniq

# Add enclosing-function info
enriched = defaultdict(list)
for offset, rows in results.items():
    for rva, mn, ops, kind, sz in rows:
        fn = enclosing_func(rva)
        fn_str = f'0x{fn[0]:X}..0x{fn[1]:X}' if fn else 'NO_PDATA'
        enriched[offset].append((rva, mn, ops, kind, sz, fn))

# Write CSV
with open('scratchpad/s154_statetracker_access_map.csv', 'w', encoding='ascii') as f:
    f.write('offset,access_rva,fn_start,fn_end,mnemonic,size,kind,op_str\n')
    for offset in OFFSETS:
        for rva, mn, ops, kind, sz, fn in enriched[offset]:
            fs = f'0x{fn[0]:X}' if fn else ''
            fe = f'0x{fn[1]:X}' if fn else ''
            ops_csv = ops.replace(',', ';')
            f.write(f'0x{offset:X},0x{rva:X},{fs},{fe},{mn},{sz},{kind},{ops_csv}\n')

# Write markdown
with open('scratchpad/s154_statetracker_access_map.md', 'w', encoding='ascii') as f:
    f.write(f'# S154 state-tracker offset access map (offline, merged14)\n\n')
    f.write(f'Enumeration of readers/writers for the 8 state-tracker offsets discovered\n')
    f.write(f'in the S153 WALL P auto-fire hunt (docs/wall-p-autofire-mechanism-s153.md).\n\n')
    for offset in OFFSETS:
        rows = enriched[offset]
        f.write(f'## `[reg + 0x{offset:X}]` -- {len(rows)} unique accesses\n\n')
        # Group by enclosing function
        by_fn = defaultdict(list)
        for r in rows:
            key = f'0x{r[5][0]:X}..0x{r[5][1]:X} ({r[5][1]-r[5][0]:#x} B)' if r[5] else 'NO_PDATA'
            by_fn[key].append(r)
        for fn_key, fn_rows in sorted(by_fn.items(), key=lambda kv: kv[0]):
            f.write(f'### fn {fn_key}\n\n')
            for rva, mn, ops, kind, sz, _ in fn_rows:
                f.write(f'  - `0x{rva:X}` **{kind}** ({sz}B): `{mn} {ops}`\n')
            f.write('\n')
    # Cross-tab: functions that access multiple offsets = strongest evidence of a single class
    f.write('## Functions accessing multiple state-tracker offsets\n\n')
    fn_touched = defaultdict(set)
    for offset in OFFSETS:
        for rva, mn, ops, kind, sz, fn in enriched[offset]:
            if fn:
                fn_touched[fn].add(offset)
    multi = sorted([(fn, offsets) for fn, offsets in fn_touched.items() if len(offsets) >= 2],
                   key=lambda x: (-len(x[1]), x[0][0]))
    for fn, offsets in multi[:30]:
        offs_str = ', '.join(f'0x{o:X}' for o in sorted(offsets))
        f.write(f'  - fn `0x{fn[0]:X}..0x{fn[1]:X}` ({fn[1]-fn[0]:#x} B) touches {len(offsets)} offsets: {offs_str}\n')

    f.write(f'\n\n**Summary:** enumerated across {sum(len(v) for v in enriched.values())} accesses; ')
    f.write(f'{len(fn_touched)} distinct functions touch these offsets; ')
    f.write(f'{len(multi)} touch multiple.\n')

# Also stdout summary
print(f'=== S154 state-tracker access enumeration ===')
print(f'Wrote scratchpad/s154_statetracker_access_map.csv and .md')
print()
for offset in OFFSETS:
    print(f'  [reg + 0x{offset:X}]  {len(enriched[offset]):3d} accesses')
print()
print(f'Distinct enclosing functions touching >=1 of these offsets: {len(fn_touched)}')
print(f'Distinct functions touching MULTIPLE of these offsets: {len(multi)}')
print()
print('Top 5 multi-offset functions (strongest evidence of single-class body):')
for fn, offsets in multi[:5]:
    offs_str = ', '.join(f'0x{o:X}' for o in sorted(offsets))
    print(f'  0x{fn[0]:X}..0x{fn[1]:X} ({fn[1]-fn[0]:#x} B): touches {len(offsets)} offsets - {offs_str}')
