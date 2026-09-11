# S140 TIER 2 — ADVERSARIAL VERIFICATION OF `scratchpad/s140t2/L4-probe-review.md`

**2026-08-23. OFFLINE ONLY. No launches, no injection, no live process, no writes to tracked files.**
Everything below is from **my own** PE reader and scanners (throwaways under my scratchpad,
`v4/{v4pe,v4bytes,v4uht,v4props,v4arr,v4disp,v4ctx,v4more}.py`), written from scratch; I did not run
any lane script. Static reads against `dumps/merged13.dump.exe`, ImageBase `0x7FF608F40000`,
**file-offset == RVA verified on all 10 sections** (measured, not assumed).

**Instrument bounds I measured myself rather than quoting:**
`.text` **16,800 / 30,281 non-zero pages = 55.48 %** — every `.text` census below is a **FLOOR**.
`.rdata` **9,052 / 9,085 = 99.64 %** (33 all-zero pages) — so `.rdata` string absences are
99.64 %-complete, **not** "image-wide".

⚠ **My own classifier defect, declared up front:** my first displacement sweep decoded candidate
instructions by back-scanning up to 12 bytes and flagged `operands[0].type == MEM` as a write. That
(a) treats `cmp`/`test` as writes and (b) **manufactures instructions from mid-instruction bytes** —
it produced a false "second payload writer at `0x0559EA30`" that aligned disassembly killed. I
report it because it is the same family as the recorded capstone `regs_access` defect, one level up.

---

## 0. VERDICT

**No substantive claim L4 makes about the BINARY was refuted.** I attacked three specifically (a
second `+0x16B0` writer, a second `+0x16C8` clear, the exit-2 quote) and every attack failed. The
offsets, the byte strings, the vtable displacements, the exit-2 fallback and the `EMovementMode`
finding all reproduce on my own code.

**What IS refuted is the deliverable's provenance and currency.** L4 audited a file that no longer
exists at that path. Five of its ten "REQUIRED EDITS" were already implemented by a sibling lane
**48 seconds before L4 wrote its report**, and every one of its ~18 `:NNN` line citations points
into a superseded 452-line file while the shipped file is 524 lines.

---

## 1. CONFIRMED — independently re-derived with my own code (13 items)

**C1 — the 10 UHT offsets. 10/10 EXACT.** I did **not** assume L4's record layout. I located each
name's NUL-terminated ASCII, found 8-aligned `.rdata` qwords pointing at it, then **calibrated the
record layout on three independently-known offsets** (`Velocity 0xE8`, `Acceleration 0x328`,
`MaxAcceleration 0x28C`) before decoding anything new; the offset field is `u16 @ rec+0x32`.
Reproduced: `Acceleration 0x328` (rec `0x07FB05A0`) · `AnalogInputModifier 0x3D0` (`0x07FB07D0`) ·
`MaxSimulationTimeStep 0x3E0` (`0x07FB0808`) · `MaxSimulationIterations 0x3E4` (`0x07FB0840`) ·
`MaxJumpApexAttemptsPerSimulation 0x3E8` (`0x07FB0878`) · `MaxAcceleration 0x28C` (`0x07FAF970`) ·
`UpdatedComponent 0xD0` (`0x07FC7A10`) · `TimeSinceFallingStart 0x12B0` (`0x088F2CB0`) ·
`CurrentForces 0x16A0` Array (`0x088F5890`) · `LastAccelerationTime 0x16D0` (`0x088F58C8`).

**C2 — `NumJumpApexAttempts` has 0 ASCII occurrences. CONFIRMED** (`ascii=0`, `recs=0`), exact
NUL-terminated whole-string scan over the whole file, with **13 name controls that all resolved**.
Bounded by D-c below.

**C3 — the `0x16B0..0x16CF` hole. CONFIRMED.** I walked the **whole** `ULokiCMC` `PropPointers`
array (**219 slots, `0x088F59E0..0x088F60B0`**, `ChargeJumpVelocityBoostMultiplier`..`bOutOfBounds`,
max offset `0x19A0`) and filtered `[0x16A0,0x1700]`: **exactly two hits**, `CurrentForces@0x16A0`
(TArray, 16 B, ends `0x16AF`) and `LastAccelerationTime@0x16D0`. **No reflected property lies in
`0x16B0..0x16CF`.**

**C4 — every byte string L4 quoted. 9/9 reproduce byte-for-byte** (`0x0530ABF0`, `0x0530AC10`,
`0x055C2430` 80 B, `0x035EB569`, `0x036009B5`, `0x036009BC`, `0x036009C5`, `0x035E9EEE`,
`0x035AFC40`).

**C5 — vtable displacements. 10/10 PASS.** Loki `0x088F8570`: `+0x720 → 0x055C2430`,
`+0x830 → 0x055B89F0`, `+0xA50 → 0x0530ABF0`, `+0xAA8 → 0x055B8370`, `+0x6B8 → 0x035E64C0`.
Engine `0x07FBED58`: `+0x720 → 0x03600990`, `+0x830 → 0x035EC850`, `+0xA50 → 0x035D6790`,
`+0xAA8 → 0x035E9EC0`, `+0x6B8 → 0x035E64C0`.

**C6 — the two tail-jmps (not quoted by L4; both corroborate its model).**
`0x055C2470 jmp 0x3600990` (engine StartNewPhysics) and `0x0530AC00 jmp 0x35d6790` (engine disp
`0xA50`). Each lands exactly on the engine impl its own vtable slot names.

**C7 — §4 exit-2 fallback (L4's genuinely NEW item). CONFIRMED.** `0x035E9EEE mov r13,[rcx+0xc0]` /
`test` / `jne 0x35e9f11`; else `call 0x35afc40`, and that fallback reads **`[rcx+0xb8]` (Owner)** and
**`[rbx+0x28]` (Outer)** and **never reads `+0xC0`**. L4's interpretation rule is sound.

**C8 — L4's exit-2 quote fidelity. ACCURATE.** `0x035E9F25 4d 85 ed test r13,r13` /
`0x035E9F28 0f 84 79 12 00 00 je 0x35eb1a7`. ⚠ Its `...` elides a *further* bail at `0x035E9F1F`
(`call [rdx+0x6b8]` HasValidData / `test al,al` / `je 0x35eb1a7`). An omission, not an error.

**C9 — `rcx == this` at the disp-`0xA50` call. [M].** `0x035EB566 mov rcx,rbx` immediately precedes
`0x035EB569 call [rax+0xa50]`, and `rbx` was set at `0x035E9EFD mov rbx,rcx` = `this`.

**C10 — "no subclass vtable exists". CONFIRMED.** Whole-file 8-aligned pointer census: **exactly ONE**
stored pointer to each of `0x055C2430`, `0x0530ABF0`, `0x055B8370`, `0x055B89F0`, `0x03600990`,
`0x035E9EC0`, each sitting at the predicted `vtable+disp` (`0x088F8C90`, `0x088F8FC0`, `0x088F9018`,
`0x088F8DA0`, `0x07FBF478`, `0x07FBF800`).

**C11 — the naming evidence for the whole latch retraction. CONFIRMED.** `.data 0x09BC9AD0` =
`{ptr → "GetRecentVelocity", 0x0530C7E0, 0x0530AC10}` (safe read: `merged13` is `.text`-only merged,
so `.data` comes from one seed). Semantics from the bytes: `cmp byte[rcx+0x16c8],0 ; mov eax,0x16b0 ;
mov r8d,0xe8 ; cmove eax,r8d` — flag set gives the snapshot, flag clear gives live `+0xE8`.

**C12 — the sentinel constant. CONFIRMED.** `struct.pack('<d', 0.0009765625)` =
`00 00 00 00 00 00 50 3f`, and `fmt()`'s `%.3f` really would render it `0.001`.

**C13 — D1/D2/D3/D4/D6/D7 and §5, checked against the CURRENT 524-line file. ALL STILL PRESENT.**
`CTRL.tickTarget==cmc` computed at `:297`, gate at `:300` tests only `CharacterOwner`; `find_actors`
`:256` has no break and no count; the predicate is `LokiBotController` only; `fmt` `:400` is `%.3f`
and `main` truncates to 27 chars; **zero** `lru_cache`/memo anywhere; `--watch` still uses `-1`.
`tools/re/movementmode_readout.py:52-53` carries **stock** `EMOVE` (`MOVE_Custom: 6`, no 7/8) — L4 §5
CONFIRMED.

Also confirmed: **L4 §7's non-independence caveat is real.** Both probes hardcode
`NAMEPOOL = BASE + 0x9D81450`, `OBJOBJECTS = BASE + 0x9E38930`, `PERCHUNK 65536`, `STRIDE 0x18` and
`0x3F8` (`movementmode_readout.py:37,:38,:39,:43`).

---

## 2. REFUTED

### R1 — L4 AUDITED A FILE THAT NO LONGER EXISTS AT THAT PATH. "453 lines" is wrong; it is 524. [M]

| artifact | lines | bytes | mtime |
|---|---|---|---|
| `scratchpad/s140t2/cmc_earlyout_readout.py.bak` | **452** | 21,835 | 2026-08-23 **22:03:18.587** |
| `tools/re/cmc_earlyout_readout.py` (shipped) | **524** | 26,544 | 2026-08-23 **22:03:18.635** |
| `scratchpad/s140t2/L4-probe-review.md` | 581 | 37,191 | 2026-08-23 **22:04:06** |

A sibling lane rewrote the probe **48 ms** before the current mtime and parked the old copy as
`.bak`; L4's report was written **48 s after that**. Every L4 anchor maps to the `.bak`:

| anchor | L4 cites | `.bak` | **shipped** |
|---|---|---|---|
| `def find_actors` | `:249-267` | 249 | **256** |
| `CTRL.tickTarget` | `:289-296` | 290 | **297** |
| `def fmt` | `:367-373` | 367 | **400** |
| `NO PLAYER-CONTROLLED PAWN` | `:383-385` | 384 | **417** |
| `READ IT AS` | `:447-449` | 447 | **519** |

So **every `:NNN` past ~line 103 is off by up to +72** against the file a successor opens, and the
`:409-425` "rewrite this verdict block" instruction points at unrelated lines today.
⚠ `git status --porcelain` is **silent** on this file (tracked, matches HEAD), so git gives no
warning at all. The `.bak` is the only tell.

### R2 — FIVE OF L4's TEN "REQUIRED EDITS" WERE ALREADY IMPLEMENTED BEFORE IT WROTE THEM. [M]

The shipped file contains a block marked `# ---- S140 Tier 2 additions ----` implementing L4 §8
items **1, 2, 3, 4 and 5**: `hex24()` plus `S140.payload@0x16B0 RAW` / `S140.Velocity@0xE8 RAW`
(§3.2); `S140.vptr` with `is ULokiCMC` / `is engine UCMC` (§3.4); `cmc.world 0xC0`,
`cmc.jumpapex 0x3DC`, `cmc.maxsimstep 0x3E0`, `cmc.maxsimiter 0x3E4` (§3.1/§3.3); the RANK-1 verdict
rewrite (D5); and a sentinel recogniser with an own/other **poison** vocabulary (§3.5).
`tools/sigbypass-mod/build.ps1:642` already ships **`gasattr-sentinel` (ARM H)**.

### R3 — "Walking the engine `UCharacterMovementComponent` `PropPointers` run" — REFUTED for 3 of 10. [M]

My array walk separates two arrays:

- **engine CMC**: slots `0x07FB1BB0..0x07FB20C8`, **164** entries,
  `CharacterOwner`..`CurrentDashInstance`, **max offset `0x1000`**.
- **ULokiCMC**: slots `0x088F59E0..0x088F60B0`, **219** entries, **max offset `0x19A0`**.

`TimeSinceFallingStart@0x12B0`, `CurrentForces@0x16A0` and `LastAccelerationTime@0x16D0` are in the
**Loki** array, not the engine one. The **values are right**; the stated provenance is wrong.
★ The correction is *favourable* to L4's own §3.4 argument: the engine array topping out at `0x1000`
is independent confirmation that a plain engine CMC has nothing at `0x16B0`/`0x16C8`.

### R4 — "Tier-1 §4 stands on my independent read as well as on the adjudicator's" — REFUTED IN SCOPE. [M]

What L4 reproduced is **byte strings plus vtable displacements**. It did **not** re-derive either
part the latch retraction actually rests on: **§4.6's writer-set completeness** or the
**dominance / post-dominance** argument. Reproducing bytes at an address is not verifying a CFG
claim. Tier-1 §4.6 explicitly records that `0x055B860B mov byte [r15+0x16c8],0` inside
`ULokiCMC::PerformMovement` "nearly caught two lanes" — **L4's report does not mention it at all**,
which is exactly what a real re-derivation of §4.6 would have surfaced.

---

## 3. DOWNGRADES

**D-a. §3.6 "Tier-1 §5 is WRONG and discards the best possible outcome" → OVERSTATED; it is
AMBIGUOUS, not wrong.** Tier-1 §5's three bullets read as an ordered decision rule, and bullet 1
("`+0x16B0` holds the sentinel ⇒ `StartNewPhysics` ran with `Iterations == 0` [M]") is unconditional
and already covers L4's CELL C. The real defect is that bullet 3 is **also** stated unconditionally
and the three are not mutually exclusive. The fix L4 asks for is right; the word "wrong" is not.
Grade the finding **[I] on severity, [M] on the ambiguity**.

**D-b. §2 "structurally airtight … the 32-byte hole is EXACTLY a `TOptional<FVector>`" is [I]
presented among [M] items.** The property table establishes only *"a 32-byte hole containing no
reflected property"* (which I confirmed, C3). The `TOptional` identity comes from the
**disassembly** (24 B write + flag byte + the `cmove`) — a different instrument. Cite both; do not
let the property-table half carry the structural claim alone.

**D-c. `NumJumpApexAttempts` "[M] — 0 ASCII occurrences image-wide" needs its measured bound.**
`merged13` has **33 all-zero `.rdata` pages of 9,085**. The honest form is "0 occurrences over a
99.64 %-complete `.rdata`, against 13 passing name controls". L4 wrote "Bounded: an ASCII-only scan"
and never quoted the page bound.

**D-d. D2's severity rationale ("HIGH for a two-tool flight") is conditioned on a superseded flight
design.** `build.ps1:642` ships `gasattr-sentinel` (**ARM H**), an **in-shim** poison — there is no
external poke tool to desynchronise from the reader. The last-match-wins defect is still real on the
**read** side; the stated consequence is not the live one.

**D-e. §6's central negative is UNDER-CONTROLLED, and the positive control exists next door.** L4
writes "There is NO liveness check … I checked `flymode_poke.py`, `livingstate_poke.py` and
`motion_watch.py`: **none of them has one either**" — a negative over four hand-picked files with
**no exhibited positive**. [M] **`tools/re/item_watch.py:172-175` implements exactly it**:
`alive_proc()` → `GetExitCodeProcess` → `code.value == 259 (STILL_ACTIVE)`; `MZ`/PE base canaries
exist in `console_census.py`, `dump_coverage_ledger.py` and `exec_surface_probe.py`. The §6 recipe
should be **copied**, not specified from scratch, and the negative as written covers "the four files
I opened", not "the repo".

**D-f. "Seven defects" is a count against the `.bak`.** All seven do reproduce in the shipped file
(I checked, C13), but L4 could not have known that, and the count is stated as if of the shipped tool.

---

## 4. NEW FINDINGS (mine — recorded by neither L4 nor the shipped probe)

**N1 — THE SHIPPED vptr CONTROL DOES NOT GATE; L4 §3.4's requirement is UNMET in the file that will
fly. [M]** The sentinel recogniser loop (`:455-473`) prints its verdict **first**; the
`S140.vptr is ULokiCMC` warning (`:487-491`) prints **afterwards**, as text, gating nothing. A reader
sees `***** StartNewPhysics RAN *****` before `!! NOT the ULokiCMC vtable … TEST VOID`.

**N2 — THE `--watch` "READ IT AS" TABLE SURVIVED THE REWRITE, still keyed on `latch 1` / `dt
FROZEN`. [M]** `:519-522`. The concurrent lane rewrote the RANK-1 block and left this one; all three
cells are unreachable for the reasons Tier-1 §4 gives. **L4's D5 item 4 is upheld and still
actionable — at line 519, not 447.**

**N3 — THE SHIPPED EXIT-2 VERDICT COMMITS EXACTLY THE MIS-ATTRIBUTION L4 §4 WARNS ABOUT. [M]**
`:483-485` prints `*** NULL -- EXIT 2 WOULD BAIL ***` on a null `WorldPrivate`, with **no `+0xB8`
read**. Per C7 that is unsound: a null `+0xC0` sends control to `0x035AFC40`, which can still return
a world from `Owner` or `Outer`. **L4 §4 is upheld AND unfixed — the single highest-value one-line
edit on the list.**

**N4 — `if not lp(plr): … return` (`:417-419`) STILL DISCARDS THE ENTIRE BOT SENTINEL RESULT. [M]**
The new S140-T2 sentinel block sits **after** that early return, so a sitting that loses the player
loses the whole experiment. L4 §6.4 is upheld and is now **higher-stakes** than when written.

**N5 — L4's CELL TABLE (§3.5) IS WEAKER THAN THE ALREADY-SHIPPED RECOGNISER; do not swap it in. [M]**
L4's **CELL D** ("a third value ⇒ POSITIVE for `StartNewPhysics`") has no discriminator against a
**wrong-object read**, which is live precisely because `ALokiCharacter` carries real fields at the
same `+0x16B0`/`+0x16C8` displacements (Tier-1 §4.6; the probe's own header `:31-32`). The shipped
scheme poisons bot and player with **different** sentinels and reports
`*** VOID: holds the OTHER object poison -> the CMC resolution is WRONG ***`. Keep the poison.

**N6 — L4 READ THE HEADER THAT NAMES THE OFFSET COLLISION AND NEVER USED IT. [M]** It quotes
`:30-34` verbatim to convict D1; the adjacent lines state "`ALokiCharacter` has its OWN live byte at
`+0x16C8`. A probe aimed at the PAWN instead of the COMPONENT decodes to a plausible, moving, WRONG
value." That hazard appears **nowhere** in L4's D2/D3 severity, its §3.2 raw-block spec, or its §3.5
cells — the three places it is load-bearing.

**N7 — AN UNRECORDED CONSUMER OF THE PAYLOAD: `0x055A9A30`. [M, FLOOR]** A 27-byte leaf:

```
0x055A9A30 0f 10 81 b0 16 00 00     movups xmm0,[rcx+0x16b0]
0x055A9A37 48 8b c2                 mov    rax,rdx
0x055A9A3A f2 0f 10 89 c0 16 00 00  movsd  xmm1,[rcx+0x16c0]
0x055A9A42 0f 11 02                 movups [rdx],xmm0
0x055A9A45 f2 0f 11 4a 10           movsd  [rdx+0x10],xmm1
0x055A9A4A c3                       ret
```

a 24-byte out-param read of the snapshot that **does NOT test the flag at `+0x16C8`**. Neither
Tier-1 §4.5/§4.6 nor L4 names it. It is a **reader**, so the sentinel test is unaffected — but "the
field's semantics come from its own consumer" rests on **one** consumer when there are at least two,
and this second one ignores the validity flag entirely.

**N8 — my own failed attacks, recorded because a failed attack is evidence.**

- *A second payload writer at `0x0559EA30`?* **NO** — my back-scan mis-decoded by one byte. Aligned
  disassembly shows the real instruction is `0x0559EA2F`, and Tier-1 §4.6 already attributes it to
  **`ALokiCharacter`**.
- *A second flag clear inside `ULokiCMC::PerformMovement` at `0x055B860B`?* **NO.** I resolved the
  base register instead of naming it: `0x055B8381 mov r15,[rcx+0x198]`, and `CMC+0x198 =
  CharacterOwner` (engine `PropPointers`, `gen=0x52`), with `0x055B83A6 xor r15d,r15d` on cast
  failure — so `[r15+0x16c8]` is the **hero's** byte. I confirmed the site really is inside
  `PerformMovement` from `.pdata` **chained UNWIND_INFO** (`0x55B85D5 → 0x55B85B4 → 0x55B8379 →
  0x55B8370`, head flags=0, extent `0x55B8370..0x55B88DE`) — inside, and still not the CMC.
  **Tier-1 §4.6 is right and I reproduced its resolution independently.**
- Therefore, within the **55.48 % FLOOR**, I could not refute "the only CMC-side writer of `+0x16B0`
  is `0x055C244F`". That is the load-bearing premise of the sentinel test and it survives an attack.

---

## 5. CONTROLS AUDIT (the five questions I was set)

| question | answer |
|---|---|
| does every negative have a positive control that could have failed? | **Mostly yes** — C2's 13 name controls and C10's six-way pointer census could each have failed. **Exception: §6** (D-e), whose negative has no exhibited positive and is contradicted by `item_watch.py`. |
| is any control CIRCULAR? | **None found.** D1's use of `s139-f1-BOT.txt:18` reading `YES` is *not* circular — a wrong `+0x68` would read `NO`. §7's `movementmode_readout.py` cross-check is **non-independent** (shared constants) and **L4 says so itself**, which is the correct handling. |
| any [M] resting on a cross-function inference, a folded RVA, or a dark-page census? | **D-b** ([I] as [M], §2) and **R4** (scope). No folded-RVA identification anywhere in L4 — it names functions by vtable displacement, which is the right form. |
| writes classified from `regs_access`? | **No** — L4 classifies from instruction semantics and quotes bytes. ⚠ **I** committed the adjacent defect (`operands[0]==MEM` including `cmp`, plus back-scan mis-decode) and declare it in the preamble. |
| counts quoted without their unit? | **Three.** "453 lines" (wrong file, R1); "14 vtable displacement controls" (never enumerated — I could only reconstruct 10); "~10^7 RPM syscalls" is graded `[I, strong]` and its arithmetic is sound (~52 reads/object × ~200 k objects) but the **object count is assumed, not measured**. |

---

## 6. WHAT A SUCCESSOR SHOULD DO WITH L4

1. **Re-anchor every citation** to the shipped 524-line file; `.bak` numbers are up to 72 lines off.
2. **Delete §8 items 1–5** — already implemented by the sibling lane.
3. **Do N1, N2, N3, N4** — four small edits, all in the shipped file, all still open; **N3 is the one
   that can emit a false claim about exit 2.**
4. **Keep §4 and §7** — both reproduce, and §4 is the best new thing in the report.
5. **Keep the shipped poison recogniser; do not replace it with L4's CELL table** (N5).
6. **Fix `movementmode_readout.py:52-53`'s `EMOVE`** — L4 §5 is correct and it is two lines.
