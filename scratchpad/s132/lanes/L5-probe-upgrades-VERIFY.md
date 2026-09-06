# S132 LANE 5 — ADVERSARIAL VERIFICATION of `scratchpad/s132/lanes/L5-probe-upgrades.md`

Offline. Zero launches, zero injections. Every address recomputed with `python -c` / capstone against
`dumps/merged4.dump.exe` (ImageBase `0x7FF6AF000000`, file offset == RVA, confirmed from the PE header:
`PE @0x240`, magic `0x20b`, ImageBase `0x7ff6af000000`, `.text VA 0x1000 VS 0x7649000`).
Disassembly was done with a **freshly written capstone harness**, i.e. a different instrument from the
report's `fkdis.py`. Shim-source claims were checked against
`git show HEAD:tools/sigbypass-mod/tutorial_launch.cpp`.

**Score: 16 load-bearing claims CONFIRMED, 2 REFUTED, 6 UNSUPPORTED / weaker-than-graded, 1 partially
degenerate control.** No headline conclusion collapses. One refutation is an **upgrade**: a limit the
report imposed on itself does not exist.

---

## A. REFUTED

### R1 — §6 LIMITS: "`SetOffset_Internal` (`0x2F3600`) is on an all-zero page in `merged4` — COVERAGE-BLOCKED … the ByteIndex to `Offset_Internal` step is therefore `[I, strong]`" — **REFUTED. The address is wrong by one hex digit and the step is [M].**

The instruction is at `0x01308F0F`. Bytes and machine-recomputed target:

```
0x01308F0F  e8 ec a6 fe ff        rel32 = 0xfffea6ec = -0x15914
            0x01308F0F + 5 + (-0x15914) = 0x012F3600      <-- NOT 0x2F3600
```
```
python: struct.unpack('<i', d[0x1308F10:0x1308F14])[0] -> -88852 ;  0x1308F14 - 0x15914 = 0x12F3600
```

Page coverage, both addresses:

| address | page | all-zero? |
|---|---|---|
| `0x2F3600` (the report's) | `0x2F3000` | **True** — this is the page it measured |
| `0x12F3600` (the actual callee) | `0x12F3000` | **False — decrypted** |

And the callee's bytes are unambiguous:

```
0x012F3600  89 51 44   mov dword ptr [rcx + 0x44], edx
0x012F3603  c3         ret
```

⇒ `SetOffset_Internal(FProperty* rcx, uint32 ByteIndex in edx)` writes the byte index to
**`FProperty + 0x44`**. The report's own caller shape (`mov edx, ebp` = byte index; `mov rcx, rbx` =
the FProperty) closes it. **ByteIndex to `Offset_Internal` is `[M]`, not `[I, strong]`, and nothing here
is coverage-blocked.**

Free by-products the report left on the table:
- **`FProperty::Offset_Internal @ +0x44` is now `[M]` from the binary** — the constant
  `FPROP_OFFSET = 0x44` the shim has carried is measured, not assumed. This is what actually
  underwrites the `sameOff` half of PATCH B's control, which the report never justified (see D1).
- Uncapped rel32 scan of all of `.text` (my own loop, **not** `fkdis callxref`, so no 200-row cap):
  `0x12F3600` has exactly **2** callers (`0x1308F0F`, `0x132E734`), and the byte sequence
  `89 51 44 c3` occurs exactly **1x** in `.text`. Small numbers, and still a floor (~45 % of `.text`
  undecrypted), but the identification does not rest on them.

**This is the instrument-artifact pattern turned on the report's own transcription:** a page-zero test
was run against an address the quoted instruction never encodes, and the null was recorded as a
property of the image.

### R2 — §1.3 listing: "`0x01308EFB  e89025caff  call 0xffab490  ; FMemory::Free(Buffer)`" — **REFUTED as printed.**

```
python: 0x1308EFB + 5 + struct.unpack('<i', d[0x1308EFC:0x1308F00])[0]  ->  0xFAB490
```
The target is **`0xFAB490`** (one hex digit too many in the report). The distinction is not cosmetic in
this image: page `0xFFAB000` is **all-zero** while page `0xFAB000` is **decrypted**
(`0x00FAB490: e9 7b de 04 00  jmp 0xff9310`). The printed address would itself read as coverage-blocked.
Separately, the `; FMemory::Free(Buffer)` annotation is `[I]` and carries no grade marker.

---

## B. UNSUPPORTED (true or probably true, but not established by the evidence given)

### U1 — H2's second half: "**every bool the probe has printed so far is a native bool**", graded **[M]** — **UNSUPPORTED; it is 1-of-4 [M] and 3-of-4 circular.**

The probe has printed exactly **four** distinct bools, 28 samples each
(`scratchpad/s131/evidence/RESULT-poolspawn-s131-live.txt`):
`bCanEverReplicate`, `bIsTeamLeaderPod`, `bIsLocalPlayerPilot`, `bPilotHasPodControl`.

Byte-occurrence census of the whole 178 MB image (ascii + utf-16le), with the report's own two
properties as positive controls:

| name | ascii | utf-16 | UHT record? |
|---|---:|---:|---|
| `bCanEverReplicate` | 1 | 0 | **yes** — `.rdata 0x07F1FDF0`, gen `0x4C` ⇒ `[M]` native |
| `bHidden` (control) | 4 | 1 | yes |
| `bAlwaysRelevant` (control) | 1 | 1 | yes |
| `bIsTeamLeaderPod` | **0** | **0** | **none** |
| `bIsLocalPlayerPilot` | **0** | **0** | **none** |
| `bPilotHasPodControl` | **0** | **0** | **none** |

The three Angelscript members have **zero byte occurrences**, so `CLAUDE.md`'s own rule applies:
*"`propscan`/`boolscan` returning 0 on an AS name is COVERAGE-BLOCKED, not absent."* There is no offline
route to grade them native. Their nativeness is inferred **from** the `fs=1 bo=0 bm=0x01 fm=0xFF`
reading whose validity is precisely what is under test — the circularity the report itself names two
paragraphs later ("it cannot separate 'we are reading `FBoolProperty` metadata' from 'we are reading
four bytes of unrelated memory'"). Correct grade: **1 of 4 `[M]`, 3 of 4 `[I]`, offline-unresolvable.**
This does not touch H2's *first* half (the constant is verbatim what the native branch stores), which is
CONFIRMED.

### U2 — §2's line-number anchors are correct against **HEAD** and **wrong against the file on disk.**

The report says "Line numbers are against the current `tools/sigbypass-mod/tutorial_launch.cpp`
(14,793 lines)". `git show HEAD:` is **14,793** and **every anchor verifies against it**. But the
**working tree is dirty — 15,377 lines, `+585 / -1` uncommitted** (`git diff --stat`), so "current"
names a file that does not exist. Applying §2 as written to the file on disk:

| patch | intended anchor (HEAD) | what is at that line **on disk** | result |
|---|---|---|---|
| C `replace 10076` | `if(doCalibrate) PdPodCalibrate(cls,cn);` | `Markerf("[PD] pod[%d] …` (header of a multi-line call) | **compile error** — deletes the header, orphans its continuations |
| H `replace 10184-10188` | the summary `Markerf` | `PdPodOne(pod,i,…);` + the loop's `}` | **compile error** |
| B `after 10026` | `PdPodSweep`'s closing `}` | a string-literal continuation line | **compile error** |
| F `after 10087` | end of the `LeaderPod` `PdPodField` call | *first* line of that call | **compile error** |
| D `after 9988` | `PdPodLoc`'s closing `}` | a statement inside `PdPodLoc`'s body | nested function |
| E `after 9965` | `PdPodField`'s closing `}` | `}` (coincidence) | ok |
| A `after 9807` | `PDPOD_OFF_STARTED = 0x4B8` (end of block) | `PDPOD_OFF_TEAMIDX` (mid-block) | harmless |
| G `after 10138` | location block's `}` | `L[0],L[1],L[2]);` | **compile error** |

**Apply against HEAD, or re-anchor by landmark text** (`if(doCalibrate) PdPodCalibrate(cls,cn);`,
`POD STATE (%s) end`, each function's closing brace). The report is auditable only because it printed
the line count — that is the disambiguator and it is worth keeping.

### U3 — PATCH F's pre-registration: "**`QueueCrewForPodSpawn` is the only writer**" — **wrong twice.**

Enumerated over **all** of `tools/asdump/out/a/` — `AttachedCrewPods` appears in exactly one file:

| site | function (verified by reading back to the decl banner) | operation |
|---|---|---|
| `:221` | ctor | `= TArray<ALokiDropPod@>()` |
| `:3632` | **`void SpawnCrewPodQueue()`** (decl `:3615`) | `this.AttachedCrewPods.Add(v20)` |
| `:3109` | **`void FinishDetachingPodFromLeader()`** (decl `:3097`) | `this.LeaderPod.AttachedCrewPods.Remove(this)` |

`QueueCrewForPodSpawn(ALokiDropShip@)` (decl `:3518`) writes **`PlayersToSpawnCrewPodFor`**, not
`AttachedCrewPods`; it then *calls* `SpawnCrewPodQueue()` at `:3552`. So the named function is not a
writer at all, and there is a **second** mutator (a `Remove`). The predicted **value** (`Num = 0`) is
unaffected — nothing on the measured route calls either — but the mechanism baked into the
pre-registration string is wrong. This is the incomplete-enumeration failure `CLAUDE.md` already
records **on this exact class family** ("`AuthSetSpawnTeamLeader`'s flag feeds three Angelscript
readers, not one").
**Suggested replacement:** *"`SpawnCrewPodQueue` is the only `Add` site (reached only from
`QueueCrewForPodSpawn`); `FinishDetachingPodFromLeader` is the only `Remove` site. Neither is on the
measured route, so Num=0."*

### U4 — H9's scope exceeds §4.3's verification list.

H9 claims the additions cannot move `play`, `dropplane_b1only`, `rideable`, **`cheatmgr*`,
`dropmarkers*`, `phaseladder*`**. §4.3's hash gate specifies baselines for **three** of the six. The
call-graph reasoning does cover all six, but the report's own standing rule is *"verify by hash, not by
argument"* — so record the other three baselines too, or narrow H9 to the three that will be gated.

*(One hypothesis that would have broken every other variant was tested and does not apply: there is no
`-Werror`. `build.ps1:946` uses clang `-shared -O2 -w`; `:940` uses MSVC `/W0`. The new `static`
functions being unreferenced in other run modes will not fail those builds.)*

### U5 — minor citation errors (none changes a conclusion, all against HEAD)

| report says | actual (HEAD) |
|---|---|
| `FBOOLPROP_*` constants at `9812-9815` | **`9813-9816`** (9812 is the last comment line) |
| `PdFindPropOn` at `9827-9855` | function starts at **`9833`** |
| `PdFmtValue` bool arm at `9865-9887` | function starts `9859`; the bool arm at **`9867`** |
| `static const int kRunMode = KRUNMODE;` at "line 164" | **line 173** |
| `PdPodDump` called "`PdLadderStep` x4, `SpLadder` x5" (=9) | **4 + 4 = 8** call sites: `PdLadderStep` x3 (`10258/10303/10318`) + `PdFinalReport` x1 (`10343`); `SpLadderStep` x3 (`11524/11539/11554`) + `SpFinalReport` x1 (`11579`). The 9th grep hit is the **definition** at `10146` — the report counted it as a call and mis-split the two arms. Conclusion unaffected. |

### U6 — one instruction is printed with an operand it does not encode (S115-d class, in miniature)

```
report:   0x01308F42  48094338   or  qword [rbx+0x38], 0x1040000200
actual:   0x01308F42  48094338   or  qword ptr [rbx + 0x38], rax
          0x01308F38  48b80002004010000000  movabs rax, 0x1040000200
```
The immediate comes from the *preceding* instruction. Semantics unaffected; the presentation is the
recorded failure mode ("never print a byte string next to an address it did not come from").

Related, milder: §1.3's quoted selector chain shows `shr al,6; not al; test al,1`. There is a **first
`not al` at `0x01308F1E`** which the listing elides (the H3 table marks the gap with an ellipsis; the
§1.3 block does not). Read literally as printed, the three-instruction chain **inverts the branch**.
With the real four-instruction chain the polarity is:
`al = ~((~g)>>6)` → `al & 1 == bit6(g)` → `je` (ZF=1 iff bit6 clear) → `0x1308F63` = bitfield.
So the report's **conclusion is correct**; only the quoted evidence is short.

---

## C. DEGENERATE / WEAK CONTROL

### D1 — PATCH B's coded verdict is weaker than the claim §3 rests on it. **PARTIALLY DEGENERATE.**

```cpp
int sameOff  = (h.off==a.off);
int diffMask = (h.bm!=a.bm) && h.bm && a.bm;
int exact    = (h.off==0x68) && (a.off==0x68) && (h.bm==0x80) && (a.bm==0x08);
g_pdPodBoolCtl = (sameOff&&diffMask)?1:0;      // <-- exact is NOT in the verdict
```

- `h.off` / `a.off` come from `PdFindPropOn`'s `offOut` = `*(uint32_t*)(f + FPROP_OFFSET)` = **`+0x44`**.
  So `sameOff` tests the `Offset_Internal` constant and **says nothing about `+0x70..0x73`**.
- The only term touching the bool metadata is `diffMask`, i.e. *"two distinct `FProperty` objects hold
  different non-zero bytes at `+0x72`"*. That is satisfied with high probability by **varying** garbage.
  It rules out only the **constant**-garbage hypothesis — which is the one the in-code comment carefully
  scopes to ("No **constant** garbage at +0x70..0x73 can produce that"), and which §3's prose then
  over-states as *"closes the last calibration gap on this readout."*
- The genuinely discriminating predicate is `exact` (both offsets `0x68`, masks `0x80` vs `0x08`) and it
  is computed — but it does not gate the verdict, and **PATCH H's summary line prints only the weak
  verdict**. A run in which `exact` DIFFERS still reports `bool two-sided control=PASS` on the summary.

**One-line fix:** `g_pdPodBoolCtl = (sameOff && diffMask && exact) ? 1 : 0;` — or surface `exact`
alongside it in PATCH H. The offline `[M]` values are strong enough to gate on; there is no reason not to.

*(The report's `UNAVAILABLE`-is-not-`FAIL` handling, by contrast, is correct and well designed, and the
`[I]` grade on "AActor's bools appear in the live `ChildProperties` chain" is honest.)*

---

## D. CONFIRMED (16)

Each re-derived independently, most by a different route than the report used.

1. **H1 — `FBOOLPROP_FIELDSIZE/BYTEOFFSET/BYTEMASK/FIELDMASK = 0x70/0x71/0x72/0x73`.** Re-disassembled
   with capstone: `0x1308F4D mov byte [rbx+0x70], r8b`, `0x1308F51 mov word [rbx+0x71], 0x100`
   (LE ⇒ `[0x71]=0`, `[0x72]=1`), `0x1308F57 mov byte [rbx+0x73], 0xff`. The **role** of `+0x71` is
   independently pinned on the bitfield branch: `0x1308FB5 mov byte [rbx+0x71], al` where `al` is the
   scan index into `TestBitmask`. OK
2. **H3 — selector is `EPropertyGenFlags & 0x40`, `je` to bitfield at `0x1308F63`.** Polarity worked out
   by hand over the full 4-instruction chain (see U6). OK (conclusion).
3. **H4 — `bHidden` `0x68`/`0x80`, `bAlwaysRelevant` `0x68`/`0x08`.** Byte-exact:
   `0x03368980: 80 49 68 80  or byte ptr [rcx + 0x68], 0x80` and
   `0x032F7100: 80 49 68 08  or byte ptr [rcx + 0x68], 8`, both reached via record `+0x38`. OK
4. **H5 — `FieldMask == ByteMask` on the bitfield branch.**
   `0x1308FBD movzx eax, byte [rbx+0x72]` / `0x1308FC1 mov byte [rbx+0x73], al`, and the native branch
   `ret`s at `0x1308F62` before reaching it. OK
5. **H6 — `ComponentVelocity` Offset `0x1A0` = 416.** Confirmed from the record, and **strengthened by a
   route the report did not use**: I walked the whole 31-entry `PropPointers` array containing it
   (`.rdata 0x7EE0280..0x7EE0378`) and the `+0x32` values form a strict monotone progression —
   `RelativeLocation 344 -> RelativeRotation 368 -> RelativeScale3D 392 -> ComponentVelocity 416`,
   **stride 24 = 3x double (LWC)**. An arithmetic progression of that shape *is* an offset series; it
   cannot be ElementSize. It also independently justifies PATCH D's `ve==24` branch. OK
6. **H6's class attribution to `USceneComponent` — CONFIRMED** (I checked this specifically, expecting
   `UActorComponent`). The owning array is unmistakably `USceneComponent`'s: `PhysicsVolume`,
   `AttachParent`, `AttachSocketName`, `AttachChildren`, `RelativeLocation/Rotation/Scale3D`,
   `ComponentVelocity`, `bVisible`, `Mobility`, `DetailMode`, `PhysicsVolumeChangedDelegate`, and the
   adjacent `FClassParams` block carries `SetVisibility` / `SetWorldScale3D` / `ToggleVisibility` and
   package `"Engine"`. OK — `RelativeLocation @ 0x158` likewise OK.
7. **H7 — `FProperty::ElementSize @ +0x34`.** Confirmed by the report's route *and* by a **second,
   independent function**: the FProperty base ctor `0x12DF8A0`, at `0x12DF94D`, emits the stock init
   sequence — `mov qword [rdi+0x30], 1` (ArrayDim=1 **and** ElementSize=0 in one store),
   `mov qword [rdi+0x38], rsi` (PropertyFlags), `mov word [rdi+0x40], ax` (RepIndex),
   `mov byte [rdi+0x42], al`, `mov dword [rdi+0x44], eax` (Offset_Internal). That fixes
   `ArrayDim@0x30 / ElementSize@0x34 / PropertyFlags@0x38 / RepIndex@0x40 / Offset_Internal@0x44`
   without relying on the bool ctor at all. OK
   Discrimination check: the four bool records read `word@+0x32 == 1` while the two generic records read
   `416` / `344`. If `+0x32` were an Offset on bool records, `bHidden` would read `0x68`, not `1`. So the
   layout split (bool = ElementSize, generic = Offset) is measured, not assumed. OK
8. **H8 — `AttachedCrewPods` = `+0x490`.** `ADDSi W0:1168`, `1168 == 0x490` (machine-checked), six
   consistent sites, declared `TArray<ALokiDropPod@>` at `:184`. OK
9. **The §0 positive control.** `bCanEverReplicate` -> `0x02078900: c6 41 6c 01 mov byte [rcx+0x6c], 1`;
   `bEnablePooling` -> `0x03368BF0: c6 81 d3 02 00 00 01 mov byte [rcx+0x2d3], 1`; both gen `0x4C`.
   Reproduces two S130 `[M]` answers by a different instrument. **Non-degenerate** — a wrong `+0x38`
   would not have yielded two 4-/7-byte stores at two independently-known offsets. OK
10. **The ICF-fold multiplicities** (`0x02078900` <- 8, `0x032F7100` <- 2, `0x03368980` <- 1,
    `0x03368BF0` <- 1). Reproduced **exactly**, uncapped, by my own whole-image qword scan (not
    `fkdis findptr`, which caps at 200). All hits are in `.rdata`. OK
11. **The `.pdata` chain** `0x1308E20 -> 0x1308E2E -> 0x1308E9B -> 0x1308F0A -> 0x1308F38..0x1308FCF`.
    Reproduced row-for-row from `tools/strxref/index/pdata_union.csv` (`seen_in_dumps 71` on all five). OK
12. **§6's floor claim — exactly one `mov byte [reg+0x73], 0xFF` in decrypted `.text`.** My own scan
    covered the disp8 form **with and without REX.B** *and* the disp32 form `C6 8x 73 00 00 00 FF`
    (which the report did not mention): **1 hit total, `0x01308F57`**, 0 disp32 hits. Correctly labelled
    a floor. OK
13. **§4.2's call-graph conclusion.** `PdFindPropOn` <- `PdPodField(9935)`, `PdPodCalibrate(10039,10040)`
    only. `PdFmtValue` <- `PdPodField(9937)`, `PdPodSweep(10005)` only. `PdPodDump` <- `PdLadderStep` /
    `PdFinalReport` / `SpLadderStep` / `SpFinalReport` only, all reached from `OnPI`'s
    `if(kRunMode==RM_DROPPOD){ DoDropPod(); … }` (`:1267`) and
    `if(kRunMode==RM_POOLSPAWN){ DoPoolSpawn(); … }` (`:1269`), with `kRunMode` a compile-time
    `static const int` (`:173`). ⇒ **no other run mode compiles any patched function.** OK
    (count error noted in U5; conclusion stands)
14. **§4.3 item 1 — do not touch `PdTypeOf`.** `PdWalkParams` calls it at `:8352`, and `PdWalkParams`
    is used by the RIDEABLE (`:13142`), DROPPLANE/DROPMARKERS and POOLSPAWN (`:11189`) paths. OK
15. **`__builtin_sqrt`, not `sqrt`.** The file's includes are `windows.h / tlhelp32.h / cstdint / cstdio
    / cstdarg / cstring` — no `<math.h>` — and `__builtin_sqrt` already appears 4x. OK
16. **§3's two mechanism claims about `PdPodSweep`.** (a) it walks the **pod's** class chain
    (`for(uintptr_t c=cls; …)`, `cls` = pod class), so it structurally cannot reach a property on the
    root **component** — `ComponentVelocity` is invisible to it. OK (b) its `boring` filter suppresses a
    no-decoder type whose first 8 bytes are zero, i.e. **an empty `TArray` is dropped and a populated
    one prints only `<ArrayProperty, size=16 … no decoder>`** — exactly as PATCH E argues. OK
    All patch dependencies resolve in HEAD order: `KPDPODASOFF :9792`, `g_pdPod{Dumps,Moved,CalOk,
    Agree,Disagree,NameFail} :9821-9824`, `GetFNameStr :429`, `NameId :437`, `ClassOf :439`,
    `GcAlive :1975`, and `PdFmtValue`'s 9-parameter signature matches PATCH B's call exactly. OK
    `root` is in scope at PATCH G's insertion point (declared `:10110`, and `:10139` is
    `if(detail) PdPodSweep(pod,cls);` as the report states). OK

---

## E. NET EFFECT ON THE LANE

- **Nothing the report set out to establish is overturned.** The bool decode is calibrated correctly,
  the two-sided control exists and its offline values are right, `0x1A0` / `0x158` / `0x34` / `0x490`
  are all confirmed, and the blast-radius argument holds.
- **One limit dissolves (R1):** the ByteIndex to `Offset_Internal` step is `[M]`, and
  `FPROP_OFFSET = 0x44` is now measured from the binary. §6's second bullet should be deleted and
  §1.4's caveat rewritten.
- **Three things need editing before this is acted on:** the verdict expression in PATCH B (D1), the
  pre-registration string in PATCH F (U3), and the revision the line numbers are applied against (U2).
- **One grade needs demoting:** H2's "every bool … is a native bool" from `[M]` to 1-of-4 `[M]` (U1).
