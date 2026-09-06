# S138 offline follow-up — the TeamStates route is CLOSED, and an FK-31 lead is DEAD

Written 2026-08-23. Two offline lanes, each adversarially verified by an independently-written
toolchain. Zero launches, zero injections. Read `docs/s138-flight2-arme-fired.md` §2b first.

---

# PART 1 — `ALokiGameState::TeamStates` CANNOT BE POPULATED. Branch (b) is closed.

**VERDICT: NO.** [M], and the refuter CONFIRMED the headline on partly different evidence.

## The question this answers
`SpawnBot` left early via one of the jumps to `0x556DED2`. One candidate was `0x556DE6A` —
`GetTeamState(GS, teamIdx)` returning NULL because `ALokiGameState.TeamStates` (`+0x600` Data /
`+0x608` Num) is empty. **If TeamStates can never be populated, that branch is permanently blocked
and no amount of instrument-fixing makes it worth chasing.** It cannot be.

## The evidence

**The property.** `TeamStates` @ **`+0x600`**, Num `+0x608`, delegate `OnTeamStatesUpdated` `+0x610`
— confirmed three independent ways (UHT `FPropertyParams` Offset u16; `GetTeamState`'s own code;
`OnRep_TeamStates 0x569B430 = add rcx,0x610; jmp 0x3071c30`). Flags `0x0010000100000020` =
`Net|RepNotify|NativeAccessSpecifierPublic` — **no Blueprint access of any kind.**
★ **Positive control the first pass lacked and the refuter supplied:** the sibling `TeamScores`
reads `0x0014000100000034` — same `Net|RepNotify` **with** `BlueprintVisible|ReadOnly`. So the flag
decoder demonstrably discriminates, and "no BP access" is a measurement rather than a decode failure.

**The named factory is stripped.** `ALokiGameState::GetOrCreateTeamState`, thunk `0x53888A0`,
impl **`0x5634BD0`**, 16 bytes:

    05634BD0  4883ec28      sub  rsp,0x28
    05634BD4  e8b77dd5fd    call 0x338C990      ; AActor::GetWorld -- RESULT DISCARDED
    05634BD9  33c0          xor  eax,eax        ; return nullptr, UNCONDITIONAL
    05634BDB  4883c428      add  rsp,0x28
    05634BDF  c3            ret

`0x338C990` is `AActor::GetWorld` [M] — vtable slot 49 in 303 `AActor`-derived vtables including
`ALokiGameState`'s own. `ALokiGameState::SetNumTeams` impl = **`0x0F7EC20`**, the void fold.
★★ **And the designed path really does die there:** `0x5634BD0` has 5 rel32 callers, and
`0x564DE68` does `mov r14,rax / test rax,rax / je` — **it explicitly bails on the nullptr.**

★★★★★ **A SIXTH STUB SHAPE, AND IT DEFEATS THE PROJECT'S OWN FOLD TEST.**
`sub rsp,0x28; call <GetWorld>; xor eax,eax; ret` is **not** one of the five recorded ICF folds
(`0xF7EC20`, `0xF7EB60`, `0xF7EB50`, `0xB9E1F0`, `0xFC6CF0`). A two-state "is it a fold?" test
prints **REAL** for it, and a page check prints **3846/4096 non-zero** — i.e. **not DARK either**.
**Only reading the four instructions gets the right answer.** A void variant of the same idea is a
5-byte `jmp 0x338C990` (**10 sites**, incl. `ALokiGameState::AuthSetDeathCircle 0x55653E0`).
⚠ **REFUTED sub-claim:** the first pass called the shape "unique image-wide (1 occurrence)". It is
**5 sites** (`0x47E53A0`, `0x5630970`, `0x5634BD0`, `0x713EE30`, `0x751EE30`), each with a
*different* call target — a small stripped-stub **family**, separately compiled, not ICF-folded.
The "a two-state fold test prints REAL" consequence survives intact.

**No other writer exists.**
- **Reflected:** across all `FFunctionParams` records, exactly **two** functions could create or
  size a team state — the two above, both stripped. ⚠ Grade this **name-based, not behavioural**:
  the filter is a name regex and cannot exclude an oddly-named reflected mutator.
- **Native:** four complementary displacement scans over `merged13` ∪ `s138-arme`. Every Loki write
  at `+0x600/+0x608/+0x60C` is constructor bulk zero-init or an `rsp` frame. `inc/add/dec` at
  `+0x608` = **19 image-wide, all in one engine refcount subsystem at `0x15Bxxxx`; ZERO in Loki,
  ZERO in the Angelscript AOT band.**
  ★ **The refuter supplied the positive control that makes this null meaningful:** the same scan
  **does** detect replicated-property setters at displacement `0x600` in the Loki band (two dword
  setters at `0x56ADD1D`/`0x56AE759` on other classes). So the absence of a `TArray` one is a real
  negative, not a blind instrument.
- **Angelscript:** `TeamStates` is not AS-bound as a property at all; `GetOrCreateTeamState` has
  exactly one AS call site (`ALokiPlayerCheats::ServerSpawnWispAS`) into the stripped factory.
- **Shipped data:** `TeamStates` appears in **0 of 83** `bpdump_*_PROPS.txt` (control `TeamColors`:
  5). Full 69,270-asset sweep: `TeamStateClass` referenced in **2** assets, both GameState BPs
  (control `TeamColors` 13). **No Blueprint spawns a TeamState.** ⚠ `TeamStateClass` IS set
  (`BP_LokiTeamState_C` / `_LastMan_C`) and IS `Edit|BlueprintVisible|ReadOnly`, so a BP *could*
  legally spawn one — checked, and none does.

## ⚠⚠ WHAT THE REFUTER OVERTURNED — do not carry these forward

**R-a. `AuthSetTeamIndex impl 0x32F79FC (REAL)` IS THE FOLDED-RVA ERROR AND WOULD BURN A LAUNCH.**
`0x32F79FC = mov rax,[rcx]; jmp qword [rax+0x4C0]` — a **virtual-dispatch shim** with 15
stored-qword-pointer occurrences image-wide. The real body is at vtable displacement `0x4C0` and was
never examined. Discriminating controls in the same pass: `GetTeamState` 1, `SetTeamForActor` 1,
`GetOrCreateTeamState` 2. (`SetTeamForActor 0x56FBCF0` and `ResizeGrow 0xF988D0` both check out.)

**R-b. "The tail past `0x556DE6A` is unreachable ⇒ fixing the instrument has ZERO decision value"
is OVER-STATED, three ways.** (i) It conflates the tail with the **PlayerState-gated block
`0x556DD79–0x556DE53`**, which sits *before* the join, does **not** depend on TeamStates, and has
**real side effects** (`inc [rsi+0xE8]`, builds `"bot%d"` into `[rdi+0x8C0]`, a virtual
`call [rax+0x800]`). (ii) "Zero value" holds only if branch (a) passes; (a) failing needs a
different fix. (iii) **The ambiguity is 4-way, not 2-way** — `0x556DD63`, `0x556DE6A`, `0x556DE76`
(`pawn->Controller` null) and `0x556DE82` (controller `IsA` fail) all `je 0x556DED2`.
⇒ **Corrected: decision value is LOW BUT NON-ZERO. Do the free RPM read; do not spend a launch.**

**R-c. ⚠⚠ `merged13` IS NOT A STRICT SUPERSET — this corrects `CLAUDE.md`'s canonical-image line.**
Two `.text` pages are lit **only** in `dumps/s138-arme`: **`0x04656000`** and **`0x05566000`** — and
`0x05566000` is the BotController band holding `OnUnPossess 0x55667F0`, which `merged13` grades DARK.
⇒ **Grade against the UNION of `merged13` + `s138-arme`, or merge s138-arme in.**

**R-d. "All relevant pages are lit" was asserted, never measured, and is false for the class's own
neighbourhood.** The `ALokiGameState` cluster `0x5600000–0x56C0000` is **136/192 lit — 56 DARK
(29.2 %)**; the AS AOT band is **65.5 % dark**. So the native-scan null is a **FLOOR over ~71 %** of
the cluster. ★ What rescues the verdict is not that sentence but the two **coverage-independent**
instruments (the `.data` registration table and the AS binding table) plus the refuter's new control:
**all 92 registered native impls AND all 297 vtable slots of `ALokiGameState` are on LIT pages.**

## ⇒ CONSEQUENCE
**Branch (b) is permanently closed.** No client-side route populates `TeamStates`; the designed one
runs through a stripped factory whose caller explicitly bails on its nullptr. Anything past
`0x556DE6A` in `SpawnBot` is unreachable on this client without repairing `0x5634BD0` itself.

---

# PART 2 — FK-31 whole-corpus classification

The parser was sound: an independently-written reimplementation matched **537/537 rows, 0
substantive disagreements.** The failures were all upstream of the parser.

## The corrected table — SIX kill addresses, not three

| kill address | crashpad f/r | UECC-md f/r | UECC-xml r | TOTAL f/r |
|---|---|---|---|---|
| `0x7FF8F0400001` | 0/0 | 1/1 | 2 | 3/3 |
| `0x7FF90E000001` | 0/0 | 1/1 | 0 | 1/1 |
| `0x7FFA42600001` | 11/4 | 0/0 | 0 | 11/4 |
| `0x7FFB57400001` | 14/8 | 1/1 | 0 | 15/9 |
| **`0x7FFB9EE00001`** | 0/0 | 0/0 | 1 | 1/1 |
| `0x7FFD3B400001` | 343/99 | 9/9 | 2 | 354/110 |
| **TOTAL** | | | | **385 / 128** |

Inventory [M]: crashpad **402 files / 127 distinct reports** (3.17×, dedup by `.dmp` UUID);
UECC-live **110/110**; `unreal-stub/Saved/Crashes` 25 are **`UnrealEditor-Cmd.exe`, not the game**.
Positive control passes: `preloader.dll` **402/402** crashpad, `runtime.dll` **0/402** crashpad but
**99/99** UECC — so crashpad's `runtime.dll` absence is a finding, not a broken parse.
Every crashpad EXECUTE fault is FK-31: **368/368 files, 111/111 reports, zero exceptions.**
UECC gives the independent name route: `runtime.dll` ModuleList base == faulting address − 1,
**12/12 MATCH**, across four of the six addresses.

## ⚠⚠ FOUR CORRECTIONS THAT MATTER MORE THAN THE TABLE

**F1. THE "NEW ERAS" WERE NOT NEW — THEY ARE IN THE REPO, IN A DOC NOBODY OPENED.**
`docs/fk8-crash-clusters.md` §4.1, committed **2026-08-05** (`e5cd820`), already contains the FK-31
signature, **the ntdll-base-as-boot-key method**, the crashpad-vs-UECC module-list asymmetry *named
as an instrument artifact*, and a table at lines 222–226 listing `0x7FF90E000001` and
`0x7FF8F0400001` **and `0x7FFB9EE00001`**. Method rules #2 and #9, both.
⚠ **I seeded this error**: I briefed the lane from `CLAUDE.md`'s line that `0x7FF90E000000` appears
"ONLY in dumpimage manifests, never in any minidump" without grepping `docs/` first. **Grep the repo
for the claim before commissioning work to discover it.**

**F2. FIVE FK-31 REPORTS ARE INVISIBLE TO A MINIDUMP-ONLY INSTRUMENT.** They have a **0-byte**
`UEMinidump.dmp` and a perfectly readable sibling **`CrashContext` XML**. So "no report is lost" was
false; UECC FK-31 is **17 reports, not 12**. ★ The XML carries the boot key verbatim — its callstack
line is `ntdll 0x<base> + <off>` with `base+off == the kill address`, reconstructing **5/5**.
Positive control: where both instruments work they agree **12/12, zero disagreements**.

**F3. ⚠⚠ MY OWN FRAMING OF THE MemoryInfoList INSTRUMENT IS REFUTED — RETRACT IT.**
Yesterday I wrote that stream 16 is "a third, purely offline route to the protector signature".
Two things are wrong:
- **The lookup can never miss.** MemoryInfoList **tiles the entire user address space** — 0 gaps,
  0 overlaps, `0x0 → 0x7FFFFFFF0000`, ~12,644 `MEM_FREE` entries in a typical dump. A fabricated
  address gets a hit too. So "368 of 380 carry an entry covering the fault" is **vacuous**;
  **only the SHAPE discriminates.**
- **It carries NO module name.** Stream 16 can only say `RIP == <an unnamed MEM_IMAGE allocation of
  0x4066000> + 1`. The name `runtime.dll` comes from the UECC ModuleList and S131's live read.
  ⇒ **It is a joint inference, not an independent route to the name.**
★ And the shape alone is not a kill either: in **34/34** non-kill crashpad dumps a region with the
**identical** `MEM_COMMIT/READONLY/MEM_IMAGE/EXECUTE_WRITECOPY/0x7000` shape sits at that boot's
kill address. The protector is *always* mapped. **The FK-31 evidence is the CONJUNCTION — an EXECUTE
fault whose address lands inside it.**

**F4. Counting defects to not repeat.** Crashpad non-EXECUTE is **34 files / 16 reports** (not
32/16) — the earlier "record confirmed exactly" was an exclusion artifact that dropped the two
signature-zero files that would move it. Era E is **342/99 under the stated glob**, bit-identical to
the record with **zero drift** (a 343rd file lives in a different directory). And one section
silently re-included the 25 `UnrealEditor-Cmd` dumps its own inventory had excluded.
⚠ Also: "faulting address" was used to mean `ExceptionAddress` in some sections and
`ExceptionInformation[1]` in others, which **inverts** the `0x205d` control. Correct form:
*`ExceptionInformation[1] & 0xFFFF == 0x205d` in 0/16 reports; `ExceptionAddress`/`RIP` in 14/16.*

## ★★★ THE RESULT THAT CHANGES WHAT IS WORTH BUILDING

**THE STACK DOES NOT NAME THE CALLER — 111/111.** In every FK-31 crashpad report the qword at
`[rsp]` is **`KERNEL32.DLL+0x17374` (`BaseThreadInitThunk`)** with nothing below it, and the UECC XML
independently prints the same two-frame stack. ⇒ the protector jumps to `base+1` **from a thread
whose entry point is effectively the kill itself.**

⛔ **This FORECLOSES the payoff half of `CLAUDE.md`'s standing FK-31 experiment.** That entry reads:
*"Map an executable page there before arming … If the jump returns instead of faulting, the process
may survive **and the stack names the caller** — the protector code that decided to kill, which is
what FK-10's Wall #7 has been hunting."* **It will not name anything**: a `ret` at `base+1` returns
into `BaseThreadInitThunk` and the thread simply exits. Only the *"does the process survive"* half
remains live. **Write this into CLAUDE.md before anyone builds the `VirtualAlloc` arm.**

## ★ A FREE LEAD THAT OPENED
The **third hidden mapping** — a `MEM_IMAGE` allocation of exactly `0xA9E1000`, the game's own
`SizeOfImage` — is present in stream 16 of **127/127** crashpad reports, base included.
`CLAUDE.md` calls this "a lottery ticket … on the table since 2026-08-04" and says it is not
settleable offline. **Its per-crash base is now available offline for free**, which is the input that
experiment needed.
★ Also corroborated for free: the `0x80000004` (`STATUS_SINGLE_STEP`) dump is
`UECC-Windows-166396E2…`, which `CLAUDE.md` already names as the FK-24 DR-mode watchpoint probe
self-killing — a single-step exception is exactly what a debug register raises.

---

# WHERE THIS LEAVES THE THREE FKs

| | status |
|---|---|
| **branch (b) / TeamStates** | **CLOSED** — permanently unpopulatable on a client [M] |
| **FK-22** | not solved; the premade short-circuit is a real bypass for *this* consumer only |
| **FK-31** | not solved; mechanism solid at n=128 reports / 6 eras; **one recorded lead now DEAD**; trigger still unattributed |
| **FK-32** | not solved; n=5, no dose-response, no artifact |

## NEXT, ranked
1. **Fix `tutorial_launch.cpp:14339`'s substring latch, rebuild, re-digest as a unit.** Still the
   gate on everything live.
2. **One free RPM read of `[PS+0x8C8]` on a staged client** — discriminates the surviving `SpawnBot`
   divert candidates. Low but non-zero value (R-b); do NOT spend a dedicated launch on it.
3. **Read `LivingState` on a bot pawn**, player hero as control — Q2's follow-up, still cheapest.
4. `runtime.dll` `packer0 0x1831C0` kill vtable + installer `0x7F86F0` — FK-10 Wall #7, offline.
5. The third-hidden-mapping read, now that its base is free.
