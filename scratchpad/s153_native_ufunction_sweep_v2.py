"""S153 native UFunction sweep v2 — closes the fk13natreg instrument gap.

v1 (scratchpad/s153_native_ufunction_sweep.py) used tools/re/fk13natreg.py's
per-class StaticRegisterNatives walker (needs a valid <Class>::GetPrivateStaticClass
pattern for each class; ALokiGameMode's shape didn't match and 5 FK-1 register
entries' worth of coverage were silently lost — 15,129 natives enumerated).

v2 replaces the enumerator with tools/re/exec_chain_grade.py's DATA-DIRECTED
FNameNativePtrPair scanner (walks .data/.rdata for consecutive {name*, thunk*}
pairs at 8-byte stride, groups into constant-stride runs, assigns to classes
via name-set overlap against uht_funcflags_tuthero.csv). That scanner finds
17,892 pairs and assigns 16,490 (class, func) keys — 1,361 more than v1, and
INCLUDES ALokiGameMode::SpawnPlayer.

Classifier is unchanged from v1 — capstone-based instruction walker chasing
JMP trampolines up to 3 levels, distinguishing internal branches from tail
jmps (target-outside-wrapper), plus the wrapper-hides-stub pattern.

Same two mandatory positive controls as v1: AdjustHealth REAL, AuthCheatSet
Health STRIPPED.

Delta vs v1: writes only the NEW rows (16,490 - 15,129 = ~1,361 entries) plus
a per-class breakdown of what fk13natreg missed. Full census is in the CSV.
"""
import sys, time, struct, os

sys.path.insert(0, "tools/re")

# Capstone-based classifier: shared with v1
from capstone import Cs, CS_ARCH_X86, CS_MODE_64
from capstone.x86 import X86_OP_IMM
_MD = Cs(CS_ARCH_X86, CS_MODE_64)
_MD.detail = True

DUMP = "dumps/merged14.dump.exe"
with open(DUMP, "rb") as f:
    D = f.read()
PE = struct.unpack_from("<I", D, 0x3C)[0]
NSEC = struct.unpack_from("<H", D, PE + 6)[0]
for i in range(NSEC):
    s = D[PE + 0x108 + i * 0x28 : PE + 0x108 + (i + 1) * 0x28]
    if s[:8].rstrip(b"\0") == b".text":
        TEXT_VA = struct.unpack_from("<I", s, 0x0C)[0]
        TEXT_RAW = struct.unpack_from("<I", s, 0x14)[0]
        TEXT_SIZE = struct.unpack_from("<I", s, 0x10)[0]
        break

FOLDS = {
    0x0F7EC20: "void_ret (c2 00 00)",
    0x0F7EB50: "xor eax,eax; ret (false/nullptr)",
    0x0F7EB60: "xor al,al; ret (LokiIsServer FALSE)",
    0x0B9E1F0: "mov al,1; ret (LokiIsClient TRUE)",
    0x0FC6CF0: "xorps xmm0,xmm0; ret (0.0f)",
}
FOLD_BYTES = {
    0x0F7EC20: b"\xc2\x00\x00",
    0x0F7EB50: b"\x33\xc0\xc3",
    0x0F7EB60: b"\x32\xc0\xc3",
    0x0B9E1F0: b"\xb0\x01\xc3",
    0x0FC6CF0: b"\x0f\x57\xc0\xc3",
}

def bytes_at(rva, n):
    off = TEXT_RAW + (rva - TEXT_VA)
    if off < 0 or off + n > len(D):
        return None
    return D[off : off + n]

def page_readable(rva):
    pb = bytes_at(rva & ~0xFFF, 0x1000)
    if pb is None:
        return False
    return any(b != 0 for b in pb)

def classify(rva, follow_jmp=True, depth=0, trail=None):
    if trail is None:
        trail = [rva]
    if rva < TEXT_VA or rva >= TEXT_VA + TEXT_SIZE:
        return ("OOR", f"RVA 0x{rva:X} not in .text")
    if not page_readable(rva):
        return ("DARK", f"page 0x{rva & ~0xFFF:X} all-zero")
    body = bytes_at(rva, 0x400)
    for fold_rva, sig in FOLD_BYTES.items():
        if body.startswith(sig):
            return ("STRIPPED", f"tail-call {' -> '.join(f'0x{a:X}' for a in trail)} -> fold: {FOLDS[fold_rva]}")
    if follow_jmp and depth < 3 and body[0] == 0xE9:
        rel = struct.unpack_from("<i", body, 1)[0]
        tgt = rva + 5 + rel
        if tgt in trail:
            return ("REAL", f"jmp cycle at 0x{rva:X} -> 0x{tgt:X}")
        return classify(tgt, follow_jmp=True, depth=depth + 1, trail=trail + [tgt])
    # wrapper-hides-stub: capstone instruction walker.
    #
    # SpawnPlayer's wrapper at 0x534C070 revealed a real subtlety: MSVC emits
    # `call __security_check_cookie` just before `ret` when the function has a
    # stack cookie, so the naive "last call before ret" heuristic picks the
    # cookie check and misses the fold call ~19 bytes earlier. The fix is
    # NOT "any fold call wins" (that false-positives on real functions that
    # legitimately consume fold results, e.g. `if (LokiIsClient()) ...`) but
    # to specifically IGNORE the cookie-check callee when picking `last_call`.
    # __security_check_cookie is at RVA 0x751DEB0 in this build (verified:
    # `cmp rcx, [__security_cookie]; jne fail; rol rcx, 0x10; test cx, 0xffff;
    # jne fail; ret` — canonical MSVC helper).
    IGNORED_TAIL_TARGETS = {0x751DEB0}  # __security_check_cookie
    last_call = None
    body_end_va = rva + len(body)
    tail_jmp_hit = False
    for insn in _MD.disasm(body, rva):
        if insn.address - rva > len(body) - 16:
            break
        if insn.mnemonic == "ret":
            break
        target = None
        for op in insn.operands:
            if op.type == X86_OP_IMM:
                target = op.imm
                break
        if insn.mnemonic == "call" and target is not None:
            if target in IGNORED_TAIL_TARGETS:
                continue  # skip compiler-inserted epilogue helper
            last_call = target
        elif insn.mnemonic == "jmp" and target is not None:
            # tail-jmp iff outside wrapper's byte range
            if target < rva or target >= body_end_va:
                if target in IGNORED_TAIL_TARGETS:
                    continue
                last_call = target
                tail_jmp_hit = True
                break
    if last_call is not None:
        # Direct fold match?
        if last_call in FOLD_BYTES:
            return ("STRIPPED", f"wrapper-hides-stub 0x{rva:X} -> {'tail-jmp' if tail_jmp_hit else 'call'} 0x{last_call:X} -> fold: {FOLDS[last_call]}")
        # Follow one level (jmp-trampoline case)
        tgt_page = last_call & ~0xFFF
        if not page_readable(last_call):
            return ("REAL", f"tail-call target 0x{last_call:X} on dark page 0x{tgt_page:X}; wrapper's own prologue looked real")
        tgt_bytes = bytes_at(last_call, 16)
        for fold_rva, sig in FOLD_BYTES.items():
            if tgt_bytes.startswith(sig):
                return ("STRIPPED", f"wrapper-hides-stub 0x{rva:X} -> tail-call 0x{last_call:X} -> fold: {FOLDS[fold_rva]}")
    return ("REAL", f"impl 0x{rva:X}: {body[:16].hex()}")

# --- Load the superior enumerator ---
os.chdir("tools/re")
import exec_chain_grade as ECG
im = ECG.Img(ECG.TUTHERO)
t0 = time.time()
funcs, byclass, meta = ECG.load_funcs()
tmap, runinfo, runs = ECG.build_thunk_map(im, byclass)
os.chdir("../..")
print(f"exec_chain_grade enumerated {sum(len(v) for v in byclass.values())} UHT UFunctions across {len(byclass)} owners")
print(f"scan_native_pairs found {sum(len(items) for _, items in runs)} raw pairs, assigned {len(tmap)} (class,func) -> thunk keys")
print(f"enumeration time: {time.time()-t0:.1f}s\n")

# --- Positive controls ---
CTRL_ADJUST = 0x5294270
CTRL_CHEAT_SET_HEALTH = 0x52FD620
v1c, n1c = classify(CTRL_ADJUST)
v2c, n2c = classify(CTRL_CHEAT_SET_HEALTH)
print(f"CONTROL AdjustHealth       @ 0x{CTRL_ADJUST:X}: {v1c}")
print(f"CONTROL AuthCheatSetHealth @ 0x{CTRL_CHEAT_SET_HEALTH:X}: {v2c}")
if v1c != "REAL" or v2c != "STRIPPED":
    print("!! CONTROL FAILED, aborting")
    sys.exit(1)
print("  ==> both controls passed\n")

# --- Load v1's CSV for delta comparison ---
V1_CSV = "scratchpad/s153_native_ufunction_sweep.csv"
v1_keys = set()  # (class, name)
if os.path.exists(V1_CSV):
    import csv
    with open(V1_CSV, encoding="ascii") as f:
        for row in csv.DictReader(f):
            v1_keys.add((row["class"], row["name"]))
    print(f"v1 CSV loaded: {len(v1_keys)} (class,name) keys\n")

# --- Sweep ---
t0 = time.time()
CSV_PATH = "scratchpad/s153_native_ufunction_sweep_v2.csv"
DELTA_PATH = "scratchpad/s153_native_ufunction_sweep_v2_delta.txt"

tallies = {"STRIPPED": 0, "REAL": 0, "DARK": 0, "OOR": 0}
per_class = {}
delta_stripped = []
delta_real = []
delta_dark = []
all_rows = []

for (cls, name), thunk in tmap.items():
    v, note = classify(thunk)
    tallies[v] = tallies.get(v, 0) + 1
    key = (cls, name)
    is_new = key not in v1_keys
    all_rows.append((cls, name, thunk, v, note, is_new))
    if cls not in per_class:
        per_class[cls] = {"total": 0, "STRIPPED": 0, "REAL": 0, "DARK": 0, "new": 0, "new_stripped": 0}
    per_class[cls]["total"] += 1
    per_class[cls][v] = per_class[cls].get(v, 0) + 1
    if is_new:
        per_class[cls]["new"] += 1
        if v == "STRIPPED":
            per_class[cls]["new_stripped"] += 1
            delta_stripped.append((cls, name, thunk, note))
        elif v == "REAL":
            delta_real.append((cls, name, thunk))
        elif v == "DARK":
            delta_dark.append((cls, name, thunk))

# Write CSV
with open(CSV_PATH, "w", encoding="ascii") as f:
    f.write("class,name,thunk_rva,verdict,new_vs_v1,note\n")
    for cls, name, thunk, v, note, is_new in all_rows:
        note_csv = note.replace(",", ";")
        f.write(f"{cls},{name},0x{thunk:X},{v},{'YES' if is_new else 'no'},{note_csv}\n")

# --- Report ---
elapsed = time.time() - t0
total = sum(tallies.values())
new_total = sum(pc["new"] for pc in per_class.values())
new_stripped = sum(pc["new_stripped"] for pc in per_class.values())
print(f"=== S153 v2 sweep — SUMMARY ===")
print(f"scan time:                     {elapsed:.1f}s")
print(f"total UFunctions enumerated:   {total}")
print(f"delta vs v1 (fk13natreg):      +{new_total} newly enumerated")
print()
print(f"Verdicts:")
for v in ("STRIPPED", "REAL", "DARK", "OOR"):
    n = tallies.get(v, 0)
    print(f"  {v:10s}  {n:>6d}  ({100*n/max(total,1):.2f}%)")
print()
print(f"NEW-in-v2 entries: {new_total}")
print(f"  NEW STRIPPED: {new_stripped}")
print(f"  NEW REAL:     {len(delta_real)}")
print(f"  NEW DARK:     {len(delta_dark)}")

# Top-20 classes with the most NEW entries
print()
print(f"=== Top 20 classes with most fk13natreg-missed UFunctions ===")
top_new = sorted(per_class.items(), key=lambda kv: kv[1]["new"], reverse=True)[:20]
for cls, pc in top_new:
    if pc["new"] == 0: break
    print(f"  {cls:60s}  new={pc['new']:>4d}  new_stripped={pc['new_stripped']:>3d}  (total this class: {pc['total']})")

# Delta STRIPPED list
if delta_stripped:
    print()
    print(f"=== NEW STRIPPED entries (fk13natreg missed these; v2 finds them) ===")
    for cls, name, thunk, note in delta_stripped[:60]:
        print(f"  {cls}::{name}  thunk=0x{thunk:X}  {note[:80]}")
    if len(delta_stripped) > 60:
        print(f"  ... and {len(delta_stripped)-60} more (see {CSV_PATH})")

# Also: which CLASSES did fk13natreg miss ENTIRELY?
classes_v1 = set(k[0] for k in v1_keys)
classes_v2 = set(per_class.keys())
missed_classes = classes_v2 - classes_v1
if missed_classes:
    print()
    print(f"=== Classes fk13natreg missed ENTIRELY (v2 enumerates them from scratch): {len(missed_classes)} ===")
    for cls in sorted(missed_classes)[:40]:
        pc = per_class[cls]
        marker = "  <-- FK-1 CANDIDATES" if pc['STRIPPED'] > 0 else ""
        print(f"  {cls:60s}  total={pc['total']:>4d}  stripped={pc['STRIPPED']:>3d}  dark={pc['DARK']:>3d}{marker}")
    if len(missed_classes) > 40:
        print(f"  ... and {len(missed_classes)-40} more classes")

# Save delta detail
with open(DELTA_PATH, "w", encoding="ascii") as f:
    f.write(f"# v2 - v1 delta: {new_total} NEW UFunctions ({new_stripped} STRIPPED)\n\n")
    f.write(f"=== Classes missed entirely by fk13natreg ({len(missed_classes)}) ===\n")
    for cls in sorted(missed_classes):
        pc = per_class[cls]
        f.write(f"  {cls:60s} total={pc['total']} stripped={pc['STRIPPED']} dark={pc['DARK']}\n")
    f.write(f"\n=== NEW STRIPPED entries ({len(delta_stripped)}) ===\n")
    for cls, name, thunk, note in delta_stripped:
        f.write(f"  {cls}::{name}  thunk=0x{thunk:X}\n    {note}\n")

print(f"\nCSV: {CSV_PATH}")
print(f"Delta detail: {DELTA_PATH}")
