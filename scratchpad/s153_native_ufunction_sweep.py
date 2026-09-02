"""S153 offline extension of the S152 batch hunt: enumerate ALL native UFunctions
via UHT class-registration arrays (fk13natreg), grade each thunk against
dumps/merged14.dump.exe.

The S152 hunt (scratchpad/move4_fk1_batch_hunt.py) walked GUObjectArray on a LIVE
process and matched names against `Auth*|Server*|Grant*|Kick*|Ban*|Force*|
Debug*|Broadcast*|Init*|*Cheat*`. That's:
  - live-only (needs a running game with target classes loaded)
  - pattern-filtered (missed anything not matching the regex)

This tool is COMPLEMENTARY: purely offline, all names, no pattern filter.
Uses fk13natreg.natives() per class to enumerate {name, thunk_rva} pairs from
StaticRegisterNatives<Class> arrays in .data, which are populated at startup
and preserved in dumps/tutorial-hero (the fk13img default seed).

Grades each thunk against merged14's .text bytes with the S153 JMP-trampoline
chase (chases up to 3 levels of E9 <rel32> before believing a verdict).

Two mandatory positive controls before any verdict emits:
  - ULokiAbilitySystemComponent::AdjustHealth (S153 wrapper 0x5294270 must be REAL
    via tail-call to 0x5516610 which is a real MSVC prologue on a lit page)
  - ULokiCharacter::AuthCheatSetHealth (S152 5th FK-1 entry, thunk 0x52FD620 must
    grade FOLDED-STUB via tail-call to 0x0F7EC20)

Output:
  - stdout: aggregate stats + progress
  - scratchpad/s153_native_ufunction_sweep.csv: (class, name, thunk_rva, verdict, note)
  - scratchpad/s153_native_ufunction_sweep_stripped.txt: focused FOLDED-STUB list
"""
import sys, time, struct, os

sys.path.insert(0, "tools/re")
import fk13uht as U
import fk13natreg as NR

# Capstone for proper instruction-boundary walking. The byte-scan heuristic
# misclassified two ways: (a) an early E9 inside another instruction's data
# broke the loop and stole `last_call` (ULokiCharacterMovementComponent::
# AuthBeginGlideDiveFromDropPod false REAL); (b) removing the mid-body E9
# branch then broke thunks like 0x5254180 whose tail dispatch IS `jmp fold`
# with no `call` at all (92-way ICF-shared thunk of AuthSetSpawnTeamLeader
# et al.). Capstone walks instructions properly and both cases resolve.
from capstone import Cs, CS_ARCH_X86, CS_MODE_64
from capstone.x86 import X86_OP_IMM
_MD = Cs(CS_ARCH_X86, CS_MODE_64)
_MD.detail = True

# --- merged14 loader (for grading .text bytes) ---
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
    """Return (verdict, note). Verdicts: STRIPPED / REAL / DARK / OOR.
    Chases JMP trampolines up to 3 levels. Also chases the tail call inside a
    UHT exec wrapper (E8 <rel32> at Func+small_offset) if the wrapper's own
    prologue doesn't match a fold — this catches the S152 wrapper-hides-stub
    pattern (real MSVC prologue whose ultimate impl is a fold).
    """
    if trail is None:
        trail = [rva]
    if rva < TEXT_VA or rva >= TEXT_VA + TEXT_SIZE:
        return ("OOR", f"RVA 0x{rva:X} not in .text")
    if not page_readable(rva):
        return ("DARK", f"page 0x{rva & ~0xFFF:X} all-zero")
    # NOTE: window must be big enough to reach the tail call in a UHT exec wrapper.
    # Empirical failure at 0x80 (128 B): ALokiDropPlane::OverridePlaneLocations's tail
    # call sits at wrapper+0xD8 = 216 B and was misclassified REAL. 0x400 (1 KiB) is
    # comfortably above every UHT wrapper size seen in this project.
    body = bytes_at(rva, 0x400)
    # Fold match on the entry bytes
    for fold_rva, sig in FOLD_BYTES.items():
        if body.startswith(sig):
            return ("STRIPPED", f"tail-call {' -> '.join(f'0x{a:X}' for a in trail)} -> fold: {FOLDS[fold_rva]}")
    # JMP trampoline (E9 rel32)
    if follow_jmp and depth < 3 and body[0] == 0xE9:
        rel = struct.unpack_from("<i", body, 1)[0]
        tgt = rva + 5 + rel
        if tgt in trail:
            return ("REAL", f"jmp cycle at 0x{rva:X} -> 0x{tgt:X}")
        return classify(tgt, follow_jmp=True, depth=depth + 1, trail=trail + [tgt])
    # S152 wrapper-hides-stub: walk instructions properly with capstone, track
    # the last call/jmp before the function terminator (ret or unconditional
    # tail-jmp to a non-adjacent target). Both patterns are legitimate UHT
    # wrappers:
    #   pattern A (with-args, e.g. AuthCheatSetHealth 0x52FD620):
    #     ...FFrame arg unpacking with E8 property helpers...
    #     E8 <fold_rel32>      ; call fold
    #     ...epilogue...
    #     C3                   ; ret
    #   pattern B (zero-arg, e.g. 0x5254180 = 92-way ICF-shared thunk):
    #     48 8b 42 20          ; mov rax, [rdx+0x20]  ; step FFrame::Code
    #     45 33 c0 ...         ; misc scratch
    #     E9 <fold_rel32>      ; jmp fold  (tail-jmp, replaces call+ret)
    last_call = None
    body_end_va = rva + len(body)
    for insn in _MD.disasm(body, rva):
        if insn.address - rva > len(body) - 16:
            break
        if insn.mnemonic == "ret":
            break
        # Extract immediate operand target, if any
        target = None
        for op in insn.operands:
            if op.type == X86_OP_IMM:
                target = op.imm
                break
        if insn.mnemonic == "call" and target is not None:
            last_call = target
        elif insn.mnemonic == "jmp" and target is not None:
            # Tail-jmp iff target is OUTSIDE the wrapper's byte range. A jmp
            # to a target inside [rva, body_end_va) is an internal branch
            # (AuthCheatSetHealth's `jmp 0x52FD673` at +0x35 is the classic
            # example) and MUST NOT terminate the walk. Real UHT tail-jmp
            # examples: 0x5254180 (92-way ICF-shared thunk of AuthSetSpawn-
            # TeamLeader et al.) jumps to fold 0xF7EC20 at +0x15.
            if target < rva or target >= body_end_va:
                last_call = target
                break
            # else: internal branch, continue walking past it
    if last_call is not None:
        # Classify the tail-call target. If it's a fold, this is a wrapper-hides-stub.
        tgt_page = last_call & ~0xFFF
        if not page_readable(last_call):
            return ("REAL", f"tail-call target 0x{last_call:X} on dark page 0x{tgt_page:X}; wrapper's own prologue looked real")
        tgt_bytes = bytes_at(last_call, 16)
        for fold_rva, sig in FOLD_BYTES.items():
            if tgt_bytes.startswith(sig):
                return ("STRIPPED", f"wrapper-hides-stub 0x{rva:X} -> tail-call 0x{last_call:X} -> fold: {FOLDS[fold_rva]}")
    return ("REAL", f"impl 0x{rva:X}: {body[:16].hex()}")

# --- Positive controls ---
CTRL_ADJUST = 0x5294270  # ULokiAbilitySystemComponent::AdjustHealth wrapper -> impl at 0x5516610 which is real
CTRL_CHEAT_SET_HEALTH = 0x52FD620  # ULokiCharacter::AuthCheatSetHealth wrapper -> tail-call to fold
v1, n1 = classify(CTRL_ADJUST)
v2, n2 = classify(CTRL_CHEAT_SET_HEALTH)
print(f"CONTROL AdjustHealth       @ 0x{CTRL_ADJUST:X}: {v1}  --  {n1}")
print(f"CONTROL AuthCheatSetHealth @ 0x{CTRL_CHEAT_SET_HEALTH:X}: {v2}  --  {n2}")
# NOTE: AdjustHealth's impl page 0x5516000 is PAGE_NOACCESS in merged14 (never executed),
# so the wrapper-hides-stub scan sees an unreadable tail-call target and returns REAL.
# That's the correct verdict — the wrapper IS real and the impl (if it ever runs) IS real.
if v1 != "REAL":
    print(f"!! CONTROL 1 FAILED — instrument broken, aborting")
    sys.exit(1)
if v2 != "STRIPPED":
    print(f"!! CONTROL 2 FAILED — expected STRIPPED for AuthCheatSetHealth wrapper via tail-call to fold")
    sys.exit(1)
print("  ==> both controls passed, proceeding\n")

# --- Enumerate ---
t0 = time.time()
uht = U.UHT()
recs = uht.scan_class_registrations()
print(f"UHT enumerated {len(recs)} class/struct/enum/function registrations in {time.time()-t0:.1f}s\n")

t0 = time.time()
CSV_PATH = "scratchpad/s153_native_ufunction_sweep.csv"
STRIPPED_PATH = "scratchpad/s153_native_ufunction_sweep_stripped.txt"

per_class = {}
tallies = {"STRIPPED": 0, "REAL": 0, "DARK": 0, "OOR": 0}
distinct_stripped_thunks = set()
total_natives = 0

with open(CSV_PATH, "w", encoding="ascii") as fcsv:
    fcsv.write("class,name,thunk_rva,verdict,note\n")
    for i, (cls, r) in enumerate(recs.items()):
        if i % 500 == 0 and i > 0:
            elapsed = time.time() - t0
            rate = i / elapsed if elapsed > 0 else 0
            eta = (len(recs) - i) / rate if rate > 0 else 0
            print(f"  progress {i}/{len(recs)} ({100 * i / len(recs):.1f}%) "
                  f"rate={rate:.0f} cls/s eta={eta:.0f}s "
                  f"natives={total_natives} stripped={tallies['STRIPPED']} dark={tallies['DARK']}", flush=True)
        try:
            natives, meta = NR.natives(cls, uht)
        except Exception as e:
            continue
        if not natives:
            continue
        per_class_counts = {"STRIPPED": 0, "REAL": 0, "DARK": 0}
        for name, thunk in natives.items():
            if not isinstance(thunk, int):
                continue
            total_natives += 1
            v, note = classify(thunk)
            tallies[v] = tallies.get(v, 0) + 1
            per_class_counts[v] = per_class_counts.get(v, 0) + 1
            if v == "STRIPPED":
                distinct_stripped_thunks.add(thunk)
            # Escape commas in note for CSV
            note_csv = note.replace(",", ";")
            fcsv.write(f"{cls},{name},0x{thunk:X},{v},{note_csv}\n")
        per_class[cls] = (len(natives), per_class_counts)

# --- Report ---
elapsed = time.time() - t0
print(f"\n=== S153 native UFunction sweep — SUMMARY ===")
print(f"scan time:           {elapsed:.1f}s")
print(f"registrations:       {len(recs)}")
print(f"classes with natives:{len(per_class)}")
print(f"native UFunctions:   {total_natives}")
print(f"verdict counts:")
for v in ("STRIPPED", "REAL", "DARK", "OOR"):
    n = tallies.get(v, 0)
    print(f"  {v:10s}  {n:>6d}  ({100*n/max(total_natives,1):.2f}%)")
print(f"distinct STRIPPED thunk RVAs: {len(distinct_stripped_thunks)}")
print(f"  (many UFunctions ICF-fold onto the same thunk — this is the count of unique bodies)")
print(f"\nStripped-per-class top 30:")
top = sorted(per_class.items(), key=lambda kv: kv[1][1].get("STRIPPED", 0), reverse=True)[:30]
for cls, (total, counts) in top:
    if counts.get("STRIPPED", 0) == 0:
        break
    print(f"  {cls:60s} {counts['STRIPPED']:>4d} stripped / {total:>4d} natives "
          f"(REAL={counts['REAL']}, DARK={counts['DARK']})")

# Write focused stripped list
with open(STRIPPED_PATH, "w", encoding="ascii") as fs:
    fs.write(f"# S153 native UFunction sweep - {tallies.get('STRIPPED',0)} FOLDED-STUB verdicts\n")
    fs.write(f"# {total_natives} native UFunctions enumerated across {len(per_class)} classes\n")
    fs.write(f"# {len(distinct_stripped_thunks)} distinct stripped thunk RVAs\n\n")
    for cls, (total, counts) in sorted(per_class.items()):
        if counts.get("STRIPPED", 0) == 0:
            continue
        fs.write(f"=== {cls}  ({counts['STRIPPED']}/{total} stripped)\n")
        # Read the CSV back to get names, or just rescan
        # (rescanning is faster than parsing CSV back)
        try:
            natives, _ = NR.natives(cls, uht)
        except Exception:
            continue
        for name, thunk in sorted(natives.items()):
            if not isinstance(thunk, int):
                continue
            v, note = classify(thunk)
            if v == "STRIPPED":
                fs.write(f"  {name:50s}  thunk=0x{thunk:X}  {note}\n")

print(f"\nCSV output: {CSV_PATH}")
print(f"Stripped list: {STRIPPED_PATH}")
