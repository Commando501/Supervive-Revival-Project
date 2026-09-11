"""S153 coverage re-grade: check whether the 18 COVERAGE-BLOCKED FUNC_Exec entries
from tools/re/out/exec_chain_grade.txt (S114, based on dumps/tutorial-hero/...) are
now readable in dumps/merged14.dump.exe.

Purely offline: reads bytes only, no live process.

For each entry:
  - If thunk RVA was dark:
      - Check thunk page in merged14. If readable, disassemble the thunk.
        Extract P_FINISH -> call <impl> pattern to resolve impl.
        Then classify impl (REAL / FOLDED-STUB / STILL-DARK).
      - If thunk still dark, report STILL-DARK.
  - If thunk was readable but impl was dark:
      - Check impl page in merged14. Classify.

Known folds (from CLAUDE.md FK-1 register + FK-1 batch hunt S152):
  0x0F7EC20  c2 00 00                        ret 0                  (universal void_ret)
  0x0F7EB50  33 c0 c3                        xor eax,eax; ret       (false/nullptr)
  0x0F7EB60  32 c0 c3                        xor al,al; ret         (LokiIsServer, hardcoded FALSE)
  0x0B9E1F0  b0 01 c3                        mov al,1; ret          (LokiIsClient, hardcoded TRUE)
  0x0FC6CF0  0f 57 c0 c3                     xorps xmm0,xmm0; ret   (0.0f)
"""
import struct, sys

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

DUMP = "dumps/merged14.dump.exe"

with open(DUMP, "rb") as f:
    D = f.read()
PE = struct.unpack_from("<I", D, 0x3C)[0]
NSEC = struct.unpack_from("<H", D, PE + 6)[0]
IMAGE_BASE = struct.unpack_from("<Q", D, PE + 0x30)[0]
# find .text
for i in range(NSEC):
    s = D[PE + 0x108 + i * 0x28 : PE + 0x108 + (i + 1) * 0x28]
    name = s[:8].rstrip(b"\0").decode("latin1")
    if name == ".text":
        TEXT_VA = struct.unpack_from("<I", s, 0x0C)[0]
        TEXT_RAW = struct.unpack_from("<I", s, 0x14)[0]
        TEXT_SIZE = struct.unpack_from("<I", s, 0x10)[0]
        break

def bytes_at(rva, n):
    off = TEXT_RAW + (rva - TEXT_VA)
    if off < 0 or off + n > len(D):
        return None
    return D[off:off + n]

def page_is_readable(rva):
    """A .text page (4KB) is decrypted iff at least one byte is non-zero."""
    page_base = rva & ~0xFFF
    page_bytes = bytes_at(page_base, 0x1000)
    if page_bytes is None:
        return False
    return any(b != 0 for b in page_bytes)

def classify_impl(rva, follow_jmp=True, depth=0):
    """Return (verdict, note). Verdict: FOLDED-STUB / REAL / STILL-DARK / OUT-OF-RANGE.

    If `follow_jmp` and the initial byte is `E9` (JMP rel32) — a 5-byte trampoline
    that MSVC/link.exe emits for ICF-folded targets — chase one level and
    classify the final target. Depth-limited to 3 to bound tail-jump chains.
    """
    if rva < TEXT_VA or rva >= TEXT_VA + TEXT_SIZE:
        return ("OUT-OF-RANGE", f"impl RVA 0x{rva:X} not in .text [0x{TEXT_VA:X}..0x{TEXT_VA+TEXT_SIZE:X})")
    if not page_is_readable(rva):
        return ("STILL-DARK", f"page 0x{rva & ~0xFFF:X} all-zero in {DUMP}")
    body = bytes_at(rva, 16)
    for fold_rva, sig in FOLD_BYTES.items():
        if body.startswith(sig):
            return ("FOLDED-STUB", f"impl 0x{rva:X} == fold: {FOLDS[fold_rva]}")
    # JMP trampoline detection: E9 <rel32> as the first 5 bytes means this is a
    # thin forwarding stub emitted by ICF. Chase one level and re-classify.
    if follow_jmp and depth < 3 and body[0] == 0xE9:
        rel = struct.unpack_from("<i", body, 1)[0]
        tgt = rva + 5 + rel
        sub_verdict, sub_note = classify_impl(tgt, follow_jmp=True, depth=depth + 1)
        return (sub_verdict, f"jmp-trampoline 0x{rva:X} -> 0x{tgt:X}; " + sub_note)
    return ("REAL", f"impl 0x{rva:X}: {body.hex()}")

def extract_impl_from_thunk(thunk_rva):
    """Read the thunk body and try to find the P_FINISH -> call <impl> pattern.
    UHT exec thunks tail-call the impl via `E8 <rel32>` (or `E9` for jmp/tail).
    Returns (impl_rva, offset_of_call) or (None, None) if not found.
    """
    body = bytes_at(thunk_rva, 0x80)
    if body is None:
        return (None, None)
    # Scan for E8 or E9 opcodes. UHT thunks are small; the LAST call typically
    # targets the impl (after P_FINISH sets up the frame).
    calls = []
    i = 0
    while i < len(body) - 5:
        op = body[i]
        if op in (0xE8, 0xE9):
            rel = struct.unpack_from("<i", body, i + 1)[0]
            target = thunk_rva + i + 5 + rel
            calls.append((i, op, target))
            i += 5
        elif op == 0xC3:  # ret — thunk ended
            break
        else:
            i += 1
    if not calls:
        return (None, None)
    # The impl is typically the LAST call in the thunk before ret (tail-call pattern).
    return (calls[-1][2], calls[-1][0])

# The 18 entries (from exec_chain_grade.txt), extracted by awk
ENTRIES = [
    ("UPlayerInput",           "SetBind",                            0x3f44fc0, None),
    ("ALokiPlayerController",  "ServerDebugEnsureAllowRepeat",       0x534be80, None),
    ("ALokiCharacter",         "CheatToggleCharacterDebugMode",      0x52fe560, None),
    ("ALokiCharacter",         "DebugStatString",                    0x52fed90, None),
    ("AHUD",                   "PreviousDebugTarget",                0x38abd50, None),
    ("ALokiPlayerCheats",      "CheatChangeHero",                    0x534be80, None),
    ("ALokiPlayerCheats",      "CheatGetAllClientActorsByClassName", 0x5421fa0, 0x5422003),
    ("ALokiPlayerCheats",      "CheatMeasureCursor",                 0x5422050, None),
    ("ALokiPlayerCheats",      "CheatMuteAudio",                     0x5422070, None),
    ("ALokiPlayerCheats",      "CheatNoCooldowns",                   0x5422100, None),
    ("ALokiPlayerCheats",      "CheatSetEmote",                      0x5422180, None),
    ("ALokiPlayerCheats",      "CheatTeleportLocation",              0x5422360, None),
    ("ALokiPlayerCheats",      "SetGamepadAimSettings",              0x5428180, 0x55653e0),
    ("ULokiTimelineManager",   "DebugTimelineAddEvent",              0x54835b0, None),
    ("ULokiTimelineManager",   "DebugTimelinePrintEvents",           0x54836e0, None),
    ("UCheatManager",          "ViewActor",                          0x35ca710, 0x35c5560),
    ("UCheatManager",          "ViewClass",                          0x35ca7a0, 0x35c5940),
    ("UCheatManager",          "ViewPlayer",                         0x35ca850, 0x35c5eb0),
]

print(f"# S153 coverage re-grade — {DUMP} (ImageBase 0x{IMAGE_BASE:X}, .text VA 0x{TEXT_VA:X}, size {TEXT_SIZE//1024} KiB)")
print(f"# 18 FUNC_Exec entries that were COVERAGE-BLOCKED in tools/re/out/exec_chain_grade.txt")
print(f"# (S114 baseline: dumps/tutorial-hero/SUPERVIVE-Win64-Shipping.dump.exe)")
print()

# Positive control: verify our tooling works on a KNOWN-decrypted entry (God's impl)
CTRL_RVA = 0x35afd70  # UCheatManager::God impl, known REAL
ctrl_verdict, ctrl_note = classify_impl(CTRL_RVA)
print(f"CONTROL: UCheatManager::God impl 0x{CTRL_RVA:X} -> {ctrl_verdict}")
print(f"         {ctrl_note}")
if ctrl_verdict != "REAL":
    print("!! CONTROL FAILED — instrument is broken, do not trust results below")
    sys.exit(1)
print("         ==> tooling verified")
print()

# Second control: verify a KNOWN fold matches
FOLD_VERDICT, FOLD_NOTE = classify_impl(0x0F7EC20)
print(f"CONTROL: known fold 0x0F7EC20 -> {FOLD_VERDICT}")
print(f"         {FOLD_NOTE}")
if FOLD_VERDICT != "FOLDED-STUB":
    print("!! FOLD CONTROL FAILED")
    sys.exit(1)
print()

print(f"{'class':22s} {'verb':38s} {'thunk RVA':11s} {'was-dark impl':13s} {'thunk-page':13s} {'impl-page':11s} {'new-verdict':16s} note")
print("-" * 170)

thunk_now_readable = 0
impl_now_readable = 0
newly_stripped = []
newly_real = []
still_dark = []
tool_recovered_impls = []

for cls, verb, thunk_rva, known_impl in ENTRIES:
    thunk_readable = page_is_readable(thunk_rva)
    if known_impl is None:
        # Was THUNK-DARK. Try to read the thunk now.
        if thunk_readable:
            thunk_now_readable += 1
            impl_rva, off = extract_impl_from_thunk(thunk_rva)
            if impl_rva is None:
                verdict, note = "TOOL-CANT-EXTRACT", "thunk readable but no E8/E9 call found in first 0x80 bytes"
            else:
                tool_recovered_impls.append((cls, verb, thunk_rva, impl_rva, off))
                verdict, note = classify_impl(impl_rva)
                note = f"impl@thunk+0x{off:X}=0x{impl_rva:X}; " + note
        else:
            verdict, note = "STILL-DARK", f"thunk page 0x{thunk_rva & ~0xFFF:X} still all-zero"
    else:
        # Thunk was readable in tutorial-hero, impl RVA was already known.
        # Recheck impl page in merged14.
        if page_is_readable(known_impl):
            impl_now_readable += 1
            verdict, note = classify_impl(known_impl)
        else:
            verdict, note = "STILL-DARK", f"impl page 0x{known_impl & ~0xFFF:X} still all-zero"

    thunk_str = "YES" if thunk_readable else "no"
    impl_page_str = "YES" if (known_impl is not None and page_is_readable(known_impl)) else "no"
    print(f"{cls:22s} {verb:38s} 0x{thunk_rva:08X}  {'0x%08X'%known_impl if known_impl else 'THUNK-DARK':13s} {thunk_str:13s} {impl_page_str:11s} {verdict:16s} {note}")

    if verdict == "FOLDED-STUB":
        newly_stripped.append((cls, verb, thunk_rva, known_impl))
    elif verdict == "REAL":
        newly_real.append((cls, verb, thunk_rva, known_impl))
    elif verdict == "STILL-DARK":
        still_dark.append((cls, verb, thunk_rva, known_impl))

print()
print("=" * 90)
print(f"SUMMARY (18 previously COVERAGE-BLOCKED entries, re-graded against {DUMP}):")
print(f"  thunk was dark in tutorial-hero, now readable: {thunk_now_readable}/13")
print(f"  impl page was dark in tutorial-hero, now readable: {impl_now_readable}/5")
print(f"  NEW verdict FOLDED-STUB: {len(newly_stripped)}")
print(f"  NEW verdict REAL:        {len(newly_real)}")
print(f"  STILL-DARK:              {len(still_dark)}")

if tool_recovered_impls:
    print()
    print("--- Tool-recovered impls (thunk was dark before, now readable, impl extracted from tail call) ---")
    for cls, verb, thunk, impl, off in tool_recovered_impls:
        print(f"  {cls}::{verb}  thunk 0x{thunk:X} -> tail-call @+0x{off:X} -> impl 0x{impl:X}")

if newly_stripped:
    print()
    print("=== NEW FOLDED-STUB entries (add to FK-1-family findings) ===")
    for cls, verb, thunk, impl in newly_stripped:
        print(f"  {cls}::{verb}  thunk=0x{thunk:X}  impl={'0x%X'%impl if impl else 'via thunk tail-call'}")

if newly_real:
    print()
    print("=== NEW REAL entries (promoted from unknown to callable) ===")
    for cls, verb, thunk, impl in newly_real:
        print(f"  {cls}::{verb}  thunk=0x{thunk:X}  impl={'0x%X'%impl if impl else 'via thunk tail-call'}")

if still_dark:
    print()
    print("=== STILL-DARK (not yet decrypted in the sweep corpus) ===")
    for cls, verb, thunk, impl in still_dark:
        print(f"  {cls}::{verb}  thunk=0x{thunk:X}  impl={'0x%X'%impl if impl else 'THUNK-DARK'}")
