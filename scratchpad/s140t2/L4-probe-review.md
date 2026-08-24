# S140 TIER 2 — LANE 4: AUDIT AND SPEC OF `tools/re/cmc_earlyout_readout.py`

**2026-08-23. OFFLINE ONLY: no launches, no injection, no live process touched, no writes.**
Static reads against `dumps/merged13.dump.exe` (ImageBase `0x7FF608F40000`, RVA == file offset,
`.text` **55.48 %** decrypted — every census below is a **FLOOR**), plus a full source read of
`tools/re/cmc_earlyout_readout.py` (453 lines) and the S139 evidence file `docs/s139-f1-BOT.txt`.

My own scripts were throwaways (`/tmp/l4a.py` … `/tmp/l4i.py`); every byte they produced is quoted
verbatim below so nothing here depends on them surviving.

---

## 0. HEADLINE

1. **The probe's field decode is sound.** I independently re-derived **10 of its offsets from the
   UHT `PropPointers` records** and **5 more from the disassembly**; all agree. The two S139 defects
   (FNamePool block table; FField name at `+0x28`) are **both fixed** in the current file and I
   confirmed the fixed forms by reading them.
2. **It carries the CORRECT `EMovementMode`** (`MOVE_Dashing` at 6, `MOVE_Custom` 7, `MOVE_MAX` 8).
   `tools/re/movementmode_readout.py` carries **stock** (`MOVE_Custom` 6) and is wrong at ≥ 6.
3. **Seven defects**, three of which can produce a false reading; one is a documented *class* this
   project has burned sessions on. Ranked in §1.
4. **The RANK-1 VERDICT block is KNOWN-INVALID** per `docs/s140-tier1-cfg.md` §4 and **must be
   rewritten before the flight.** It does **fail safe** — the player-latch control gate catches
   every real world, so it prints `THE BISECTOR IS UNINTERPRETABLE` rather than a false verdict —
   but its *stated alternatives* are wrong and a reader will act on them.
5. **NEW, and it changes the flight's decision table** (§3.6): Tier-1 §5's outcome cell *"`+0xE8` no
   longer holds the sentinel ⇒ the probe's own control failed; the run is void"* **mislabels the
   single most interesting possible outcome as an instrument failure.** If `StartNewPhysics` runs
   *and* `CalcVelocity`/`PhysFalling` produce velocity, `+0xE8` will have moved on — that is a
   **success**, not a void.
6. **NEW, about exit 2** (§4): `CMC+0xC0` is [M] the field engine `PerformMovement` reads
   (`0x035E9EEE mov r13,[rcx+0xc0]`), **but a zero there does NOT mean exit 2 bails** — there is a
   `GetWorld()` fallback at `0x035AFC40` that reads `+0xB8` (Owner) and `+0x28` (Outer) and **never
   reads `+0xC0`**. Tier-1 §7 item 2 prescribes "one qword"; one qword half-closes the term.

---

## 1. AUDIT — DEFECTS, RANKED

### D1 ⚠⚠ `CTRL.tickTarget==cmc` IS COMPUTED BUT NEVER GATES ANYTHING — and the header says it does

`cmc_earlyout_readout.py:30-34` states, verbatim:

> `⚠⚠ MANDATORY IDENTITY CONTROLS … Both are asserted before any verdict is printed; a failure
> prints RUN IS VOID.`

**That is false for the second control.** Source, `:289-296`:

```python
tt = p(cmc + O["cmc.tickTarget"])
r["CTRL.tickTarget==cmc"] = (tt == cmc)
r["cmc.tickTarget"] = tt
if not r["CTRL.CharacterOwner==pawn"]:        # <-- only the FIRST one gates
    r["void"] = (...)
    return r
```

`CTRL.tickTarget==cmc` is stored, printed as **one row of a 40-row 118-column table**, and consulted
by nothing. A `*** NO ***` there is a silent instrument failure.

**Grade [M]** — read directly from the source. **Severity: MEDIUM.** It has never mis-fired
(`docs/s139-f1-BOT.txt:18` reads `YES` on both sides, so `FActorComponentTickFunction::Target
@CMC+0x68` is live-validated on this build), but **the documentation of the control is stronger than
the control**, which is the "a verdict line can lie" family one level up.

**Fix:** gate on it, or delete the claim from the header. Do not leave both.

### D2 ⚠⚠ CLASS LOOKUP IS "LAST MATCH WINS", SILENTLY — next member of the recorded blind-spot family

`find_actors()` `:249-267`:

```python
if "LokiBotController" in ch:
    if lp(p(o + O["ctl.pawn"])): botc = o        # no break, no count
elif ("LokiPlayerController" in ch or "PlayerController" in ch):
    if lp(p(o + O["ctl.pawn"])): plrc = o        # no break, no count
```

The `in ch` test is against a **list**, i.e. exact element match — that half is **correct** and
deliberately avoids the `obj_by_class.py` substring trap. The defect is the other half: **it never
counts matches and never prints how many it saw.** With more than one possessing bot controller or
more than one possessing PlayerController (S137 flight 4 had three controllers live at once; S114
recorded `PC_MainMenu_C` coexisting with a game PC), the probe silently takes whichever comes last
in `GUObjectArray` order — and slots are **reused**, so index order is not creation order
(`CLAUDE.md`, S136: *"`InternalIndex` IS NOT MONOTONE — REFUTED"*).

**Consequence for the sentinel flight:** the poke and the read must hit the **same** CMC. If the
poke tool and the read tool each independently "find the bot", they can pick **different** bots, and
the result is a false negative indistinguishable from "StartNewPhysics did not run."

**Grade [M]. Severity: HIGH for a two-tool flight.**

**Fix:** enumerate all matches; print `count=N` with every pointer + class name; if `N > 1`, refuse
unless an explicit pointer is supplied. Better: **accept `--cmc 0x…` / `--pawn 0x…` on the command
line** so the poke tool and the read tool are pinned to one object.

### D3 ⚠⚠ THE BOT-DISCOVERY PREDICATE IS `LokiBotController` ONLY

An AI pawn spawned by `botai` (`SpawnAIFromClass`) **without** S137's ARM D carries a plain
`AIController` — chain `AIController <- Controller <- LokiActor <- Actor <- Object` (`CLAUDE.md`,
S136). That chain contains no `LokiBotController`, so `find_actors` returns `bot = None` and the BOT
side prints `VOID: no bot (inject the arm first)`.

This is **exactly** the recorded S136 defect (`BsClassify` testing only `"BotController"`, which
made flight 2's `dCtl=0` *uninterpretable rather than negative*), reproduced in a different tool.

**Grade [M]. Severity: MEDIUM** — correct for an ARM-D flight, wrong for any other.
**Fix:** match `LokiBotController` **or** `AIController` (deliberately NOT bare `"Controller"` —
that also matches ~190 `Comp_PlayerController_*_C`), and **print which predicate matched.**

### D4 ⚠⚠ NO RAW BYTES ANYWHERE; VECTORS PRINT AT 3 DECIMAL PLACES

`fmt()` `:367-373`: `if isinstance(v, tuple): return "(%.3f,%.3f,%.3f)" % v`, and every cell is then
**truncated to 27 characters** (`:397`).

- The proposed sentinel `0.0009765625` formats as **`0.001`**.
- A signed zero prints `-0.000` — it *happens* to survive, but the S139 finding that was destroyed
  (a `set()` collapsing `-0.0 == 0.0`, flight 3) is the same family one layer up.
- **`cmc.off` printed as `1112`** in `docs/s139-f1-BOT.txt:12`, because `fmt` renders ints ≤ `0xFFFF`
  in decimal. That is `0x458`. An offset in decimal is unrecognisable.
- `R10.bRegistered(...)` can be the string `"InternalData NULL => NEVER REGISTERED"` (37 chars) →
  truncated to `"InternalData NULL => NEVER R"`, cutting off the punchline.

**Grade [M]. Severity: HIGH for the sentinel flight specifically** — the whole experiment turns on
distinguishing three 24-byte states, and the probe currently cannot print bytes.

### D5 ⚠ THE RANK-1 VERDICT BLOCK IS STALE — TWO OF ITS THREE BRANCHES ARE NOW FALSE

Per `docs/s140-tier1-cfg.md` §4 (which I re-derived independently — see §2), `CMC+0x16C8` is a
per-frame `TOptional<FVector>` validity flag, **cleared** by `ULokiCMC` vtable disp
`0xA50 = 0x0530ABF0`, called at `0x035EB569`, on a path the `StartNewPhysics` call site dominates.

| line | current text | status |
|---|---|---|
| `:409-411` | `CONTROL FAILED … Either the offset is wrong or the player's PerformMovement has never reached StartNewPhysics either.` | **outcome correct, ALTERNATIVES WRONG.** The true third reading — *the flag is cleared once per completed `PerformMovement`* — is missing. Exactly the omission Tier-1 §6.8 records. |
| `:415-418` (`latch == 1`) | `S1 … S2 ELIMINATED` | **wrong reasoning, right direction.** A sampled `1` now means *"caught mid-frame past `StartNewPhysics`, or the seventh bail `0x035EB14E` fired"* — a **strong positive**, but unreachable in practice (microseconds of a 16 ms frame). |
| `:420-425` (`latch == 0`) | `S2. The ladder broke at or ABOVE engine PerformMovement.` | **REFUTED [M].** `0` is the resting value in every world. **Delete.** |
| `:447-449` `--watch` READ IT AS | three rows keyed on `latch 1` / `dt FROZEN` | **all three cells unreachable.** `+0x12B0` is measured advancing at 1.0× on both pawns and `latch 1` is unobservable ⇒ a verdict table none of whose cells can legitimately be hit. |

It **fails safe** (the `pl != 1` guard catches every real world before any bot verdict prints), which
is why it never produced a false headline. But `docs/s139-f1-BOT.txt` was later cited *past* its own
`UNINTERPRETABLE` line (Tier-1 §3.2), so failing safe was not enough.

**Grade [M]. Severity: HIGH** — this is the block a reader acts on.

### D6 ⚠ COST — THE SCAN IS A MULTI-MINUTE `GUObjectArray` WALK WITH NO MEMOISATION

`find_actors()` calls `chain(ocls(o))` for **every non-`Default__` object**, and `chain()` walks up
to 12 supers doing `oname` (≈3 RPM each) plus a pointer read. Per object that is ~5 reads for the
name plus up to ~60 for the chain. Over ~200,000 live objects that is on the order of **10⁷
`ReadProcessMemory` syscalls from Python.**

There is **no cache keyed on the class pointer**, though the chain is a pure function of it and
there are only a few thousand distinct classes.

**Grade [I, strong]** — arithmetic from the source, not timed on a live client. **Severity: HIGH for
the sentinel flight**, where the read must land within a few frames of the poke. **Fix:** memoise
`chain`/`oname` by pointer; resolve actors **once, before the poke**, then re-read fields from cached
pointers.

### D7 ⚠ `--watch` IGNORES `void` ON RE-READ AND USES `-1` AS AN "UNREADABLE" SENTINEL

`:437-445` re-runs `read_side` each iteration but never checks `A2.get("void")`. If the object dies
mid-watch it prints `dt=None` and `moved=  -1.00`. **`-1.00` is a plausible-looking tiny negative
displacement, not an obvious error code** (`dm = lambda x, y: … if (x and y) else -1`).

**Grade [M]. Severity: LOW-MEDIUM.** Fix: print `UNREADABLE` and stop the watch.

### Things I checked and found CORRECT (so nobody re-audits them)

| item | verdict | how |
|---|---|---|
| FNamePool block table `NAMEPOOL + 8*blk` (`:154`) | **correct** — the S139 defect is fixed | source read |
| `FField` name at `NAME_OFF = 0x20` (`:187`) | **correct** — the S139 defect is fixed | source read |
| `AController::Pawn @+0x3F8` | **correct** | `docs/s137-playerstate-and-lokibot-settled.md:582` `mov rsi,[rcx+0x3F8]` inside slot 269, plus 4 other repo probes |
| `bCharacterControllable` read on the **CONTROLLER**, not the character (`:101`, `:361-363`) | **correct** | matches the S139 correction |
| `FTickFunction` decode: TickGroup `+0x48`, flags `+0x4A`, TickState `+0x4B`, InternalData `+0x60`, Target `+0x68` | **correct** — `PrimaryComponentTick @UActorComponent+0x40`, `sizeof(FTickFunction) = 0x28`, `Target` is the first derived member | S139 [M] + live PASS in `s139-f1-BOT.txt:18` |
| `RF_Garbage` = `CharacterOwner+0x0C` bit 30, read off the **pawn** | **correct** — the gating control proves `pawn == CharacterOwner` | `HasValidData 0x035E64C0`: `mov eax,[rax+0xc] / shr eax,0x1e` |
| `v3()` = 24 B as `<ddd` for the `+0x16B0` payload | **correct, and exactly right** — the write is `movups [rcx+0x16b0]` (16 B) + `movsd [rcx+0x16c0]` (8 B) = 24 B | bytes at `0x055C244F` / `0x055C245E`, re-read by me |
| `f32` for `+0x12B0`, `+0x28C`, `+0x3D0` | **correct** — all three are `gen 0x0A` = Float | my UHT record scan (§2) |
| `bool` tested before `int` in `fmt()` | **correct ordering** (`bool` is an `int` subclass) | source read |
| `findprop` walks `ChildProperties(+0x58)` / `SuperStruct(+0x48)`, offset at `+0x44` | **correct** | agrees with 4 other repo probes and with my UHT-derived offsets |
| `read_bool_uprop` reads the LIVE `FBoolProperty` `+0x71`/`+0x72` | **correct** — properly avoids the S132 `FBoolPropertyParams`-has-no-ByteOffset trap | source read + `CLAUDE.md` S132 |
| `objects()`: `Objects@+0x00`, `NumElements@+0x14`, `PERCHUNK 65536`, `STRIDE 0x18` | **correct** stock `TUObjectArray` | source read |

---

## 2. INDEPENDENT RE-DERIVATION OF THE OFFSETS ([M], my own scan)

Walking the engine `UCharacterMovementComponent` `PropPointers` run in `.rdata` (stride `0x38`; name
pointer at `+0x00`, `EPropertyGenFlags` at `+0x18`, `Offset` at `+0x32`):

```
rec 0x7FB05A0  off=0x328    gen=0x19(Struct) Acceleration
rec 0x7FB07D0  off=0x3D0    gen=0x0A(Float)  AnalogInputModifier
rec 0x7FB0808  off=0x3E0    gen=0x0A(Float)  MaxSimulationTimeStep
rec 0x7FB0840  off=0x3E4    gen=0x03(Int)    MaxSimulationIterations      <-- the 4th SNP early-out
rec 0x7FB0878  off=0x3E8    gen=0x03(Int)    MaxJumpApexAttemptsPerSimulation
rec 0x7FAF970  off=0x28C    gen=0x0A(Float)  MaxAcceleration
rec 0x7FC7A10  off=0x0D0    gen=0x52(Object) UpdatedComponent
rec 0x88F2CB0  off=0x12B0   gen=0x0A(Float)  TimeSinceFallingStart
rec 0x88F5890  off=0x16A0   gen=0x16(Array)  CurrentForces
rec 0x88F58C8  off=0x16D0   gen=0x0A(Float)  LastAccelerationTime
```

**Every one matches what the probe already uses.** Three things worth banking:

- **`CMC+0x3E0 = MaxSimulationTimeStep` (float)** and **`CMC+0x3E8 =
  MaxJumpApexAttemptsPerSimulation` (int32)** — neither is named anywhere in the S140 Tier-1
  document. `+0x3E4 = MaxSimulationIterations` is confirmed exactly as Tier-1 §7 item 3 states.
- **`NumJumpApexAttempts` has ZERO ASCII occurrences image-wide**, against **11 passing positive
  controls in the same scan** (every other name above resolved). ⇒ **`CMC+0x3DC` is not a reflected
  UPROPERTY and cannot be resolved by name.** Tier-1's `[I]` grade on that name is right; any probe
  must hardcode `0x3DC` **and print that caveat**. It sits in the unreflected gap `0x3D4..0x3DF`
  between `AnalogInputModifier@0x3D0` and `MaxSimulationTimeStep@0x3E0`.
- **`+0x16B0`/`+0x16C8` are structurally airtight.** `CurrentForces` is a `TArray` (16 B) at `0x16A0`
  → ends at `0x16AF`; `LastAccelerationTime` is at `0x16D0`. The 32-byte hole `0x16B0..0x16CF` is
  exactly a `TOptional<FVector>` (24 B payload + 1 B flag + 7 B pad). **Independent corroboration of
  Tier-1 §4.5 from the property table rather than from the disassembly.**

### Tier-1 bytes I reproduced (all PASS, my own PE reader)

```
LokiVT .rdata 0x088F8570 +0x720 -> 0x055C2430   +0xA50 -> 0x0530ABF0   +0xAA8 -> 0x055B8370
                          +0x830 -> 0x055B89F0   +0x6B8 -> 0x035E64C0
EngVT  .rdata 0x07FBED58 +0x720 -> 0x03600990   +0xA50 -> 0x035D6790   +0xAA8 -> 0x035E9EC0
0x0530ABF0  80 b9 c8 16 00 00 00 / 74 07 / c6 81 c8 16 00 00 00 / e9 8b bb 2c fe    (the CLEAR)
0x0530AC10  80 b9 c8 16 00 00 00 / b8 b0 16 00 00 / 41 b8 e8 00 00 00 / 41 0f 44 c0 (GetRecentVelocity)
0x055C2430  0f 28 d1 / 45 85 c0 / 75 3d / 44 38 81 c8 16 00 00 / 74 07 / 44 88 81 c8 16 00 00
            0f 10 81 e8 00 00 00 / 0f 11 81 b0 16 00 00 / f2 0f 10 89 f8 00 00 00
            f2 0f 11 89 c0 16 00 00 / 0f 28 ca / c6 81 c8 16 00 00 01 / e9 1b e5 03 fe
0x035EB569  ff 90 50 0a 00 00       call [rax+0xa50]
0x036009B5  44 3b 81 e4 03 00 00    cmp r8d,[rcx+0x3e4]     <-- the 4th SNP early-out
0x036009BC  0f 8d 24 02 00 00       jge
0x036009C5  ff 90 b8 06 00 00       call [rax+0x6b8]        <-- the 3rd HasValidData
```

**14 vtable displacement controls, 14 PASS; every quoted byte string reproduces.** Tier-1 §4 stands
on my independent read as well as on the adjudicator's.

---

## 3. SPEC — WHAT MUST BE ADDED FOR THE SENTINEL FLIGHT

Diff-ready description. **I have not written code.** Every item is additive; nothing in the existing
read path changes except D5's verdict text.

### 3.1 New entries in the `O` table

```
"cmc.world":         0xC0,    # engine PerformMovement 0x035E9EEE `mov r13,[rcx+0xc0]`     [M]
"cmc.owner":         0xB8,    # UActorComponent::OwnerPrivate; GetWorld 0x035AFC49 reads it [M]
"cmc.numapex":       0x3DC,   # NumJumpApexAttempts -- NOT reflected; hardcoded, print caveat [I]
"cmc.maxsimstep":    0x3E0,   # MaxSimulationTimeStep   float  [M, UHT rec 0x7FB0808]
"cmc.maxsimiters":   0x3E4,   # MaxSimulationIterations int32  [M, UHT rec 0x7FB0840]
"cmc.lastacceltime": 0x16D0,  # LastAccelerationTime    float  [M, UHT rec 0x88F58C8]
"world.timeseconds": 0x808,   # UWorld::TimeSeconds     double [M, Tier-1 §2.2 .data name triple]
```

`0x3E0`, `0x3E4` and `0x16D0` **are** reflected and must go through the existing `byname()` helper
with the hardcoded value as the printed cross-check. `0x3DC`, `0xC0` and `0xB8` are **not** and must
print `NOT REFLECTED (hardcoded)` beside the value — the same honest state `movementmode_readout.py`
already prints for `bHasStartedGameplay`.

### 3.2 RAW HEX — the load-bearing addition

A helper that prints, on its own lines **outside** the 27-char table, one block per side:

```
[RAW] BOT    cmc=0x1F3D8000010   vptr=0x00007FF60F838570 (BASE+0x088F8570)
[RAW]   +0x16B0 .. +0x16C7  velsnap payload (24B) : 00 00 00 00 00 00 50 3f 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
[RAW]                                     decoded : X=+0.0009765625000000 Y=+0.0000000000000000 Z=+0.0000000000000000
[RAW]                                    bits u64 : 3F50000000000000 0000000000000000 0000000000000000
[RAW]   +0x16C8  TOptional flag byte              : 00
[RAW]   +0x00E8 .. +0x00FF  Velocity (24B)        : 00 00 00 00 00 00 50 3f 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
[RAW]                                     decoded : X=+0.0009765625000000 Y=+0.0000000000000000 Z=+0.0000000000000000
[RAW]                                    bits u64 : 3F50000000000000 0000000000000000 0000000000000000
```

Rules, each of which exists because it has already cost this project a finding:

- **Hex first, decode second.** Standing rule *"record raw, derive afterwards."*
- **Print `%+.16f` (or `repr(float)`), never `%.3f`.** `%.3f` renders the proposed sentinel
  `0.0009765625` as **`0.001`** and would render any smaller sentinel as `0.000`.
- **Print the raw `uint64` bit pattern too.** That is the only form in which `+0.0`, `-0.0` and a
  denormal are distinguishable at a glance. Signed zero is precisely what a `set()` destroyed in
  S139 flight 3.
- **Never truncate these lines.** They go outside the aligned table.
- The sentinel `0.0009765625 = 2^-10` has byte pattern **`00 00 00 00 00 00 50 3f`**
  (`0x3F50000000000000`) — instantly recognisable in a hex dump. **Print that constant in the header**
  so the operator can eyeball it.
- Emit the same `[RAW]` block for the **PLAYER's** `+0xE8` as an untreated specificity control that
  the write landed only where intended — the pattern `flymode_poke.py:306` and
  `livingstate_poke.py:262` already use.

### 3.3 New scalar reads (add to the table AND to the `[RAW]` block as hex)

| key | address | type | why |
|---|---|---|---|
| `E2.WorldPrivate@0xC0` | `cmc+0xC0` | u64 ptr | exit 2's primary input — Tier-1 §1.6, **never read live** |
| `E2.OwnerPrivate@0xB8` | `cmc+0xB8` | u64 ptr | the **fallback** path — see §4; mandatory to close exit 2 |
| `E2.World.class` | `oname(ocls(world))` | str | must resolve to a `World`; a non-`UWorld` class means the offset is wrong |
| `S4.MaxSimulationIterations@0x3E4` | `cmc+0x3E4` | i32, by name | **fourth** engine-`StartNewPhysics` early-out `0x036009B5 cmp r8d,[rcx+0x3e4] / jge`; with `r8d == 0` it bails iff `<= 0` |
| `S4.MaxSimulationTimeStep@0x3E0` | `cmc+0x3E0` | f32, by name | its sibling; not a gate, but it is the value the step subdivides by and a `0.0` there is worth knowing |
| `L5.NumJumpApexAttempts@0x3DC` | `cmc+0x3DC` | u32 **raw hex** | Tier-1 §2.1 rank 5, the alternative poke target; raw so `0xDEADBEEF` is visible |
| `R11.LastAccelerationTime@0x16D0` | `cmc+0x16D0` | f32 | Tier-1 §2.2 rank-1 receipt |
| `R11.World.TimeSeconds@+0x808` | `world+0x808` | f64 | the comparand — **free** now that `+0xC0` is read |
| `R11.delta` | derived | f32 | `TimeSeconds − LastAccelerationTime`; **≈ 0 ⇒ the Super was CALLED AND RETURNED this frame** |
| `VPTR` | `*(u64)cmc` | u64 | see §3.4 |

⚠ **`R11` is interpretable only on a GAS-TREATED bot** (Tier-1 §2.2, verifier D3 upheld): the store
at `0x055B88CD` is guarded by `|Acceleration.X| > 1e-4 || |Acceleration.Y| > 1e-4`. On the untreated
player and on all 37 CMCs a stale `+0x16D0` is **uninterpretable, not negative.** The probe must
print that caveat inline, gated on the measured `R7.Acceleration`.

### 3.4 The vptr identity check — and it SHOULD gate

```
VPTR                     : 0x00007FF60F838570
VPTR - BASE              : 0x088F8570
CTRL.vptr==ULokiCMC      : YES        (expected BASE + 0x088F8570)
```

Rationale (Tier-1 §7 item 4): if the live component were a plain engine
`UCharacterMovementComponent`, vtable disp `0x720` resolves to `0x03600990` and **nothing in the
process ever touches `+0x16C8` or `+0x16B0`** — the whole sentinel experiment would be measuring a
field no code reads. Tier-1 §4.1 establishes [M] that **no subclass vtable exists** (exactly one
aligned pointer to each of `0x055C2430` / `0x0530ABF0` / `0x055B8370` image-wide, which I
reproduced), so the only live alternative is the engine base class.

**This is the one new control that MUST gate the sentinel verdict.** `cmc.class` reading
`LokiCharacterMovementCompon…` is *not* a substitute — that is the `UClass` name, which a
`ULokiCMC`-derived Blueprint component would also carry.

On failure: print `RUN IS VOID — the component is not a ULokiCMC; +0x16B0/+0x16C8 are meaningless on
it` and refuse the sentinel verdict (still print the raw block).

### 3.5 The pre-registered outcome cells

The probe must print exactly one `[SENTINEL]` line naming the cell. `S` = the 24-byte sentinel
vector, `Z` = 24 zero bytes, **compared as RAW BYTES, never as floats**:

| cell | `+0x16B0` (24 B) | `+0xE8` (24 B) | verdict text |
|---|---|---|---|
| **A** | `== S` | `== S` | `CELL A — ULokiCMC::StartNewPhysics RAN with Iterations==0. [M]` |
| **B** | `== Z` | `== S` | `CELL B — StartNewPhysics did NOT run. [M]` |
| **C** | `== S` | `!= S` and `!= Z` | `CELL C — StartNewPhysics RAN *and* Velocity has since been recomputed. [M] STRONGEST POSITIVE — read §3.6 before calling this a void.` |
| **D** | `!= S` and `!= Z` | any | `CELL D — the payload holds a THIRD value: the step ran on a later frame with a different Velocity. POSITIVE for StartNewPhysics; the sentinel has been overwritten by real data.` |
| **E** | `== Z` | `== Z` | `CELL E — the poke did not stick (or was zeroed). INSTRUMENT FAILURE, RUN IS VOID.` |
| **G** | any | unreadable, or the identity/vptr controls failed | `RUN IS VOID` |

Also print, unconditionally and **before** the cell line:

```
[SENTINEL] latch +0x16C8 = 0xNN   (0 is the resting value in EVERY world -- NOT a negative;
                                   only a sampled 1 is informative. docs/s140-tier1-cfg.md §4)
```

### 3.6 ⚠⚠ THE CORRECTION TO TIER-1 §5's DECISION RULE

`docs/s140-tier1-cfg.md` §5 states:

> `+0xE8` no longer holds the sentinel ⇒ **the probe's own control failed; the run is void.**

**That is wrong, and it discards the best possible outcome.** Three things can move `+0xE8` off the
sentinel:

1. **The game recomputed `Velocity`** — i.e. `PhysFalling` / `CalcVelocity` **worked**. This is the
   result the whole session is chasing, and the rule as written files it as an instrument failure.
2. `play`-style external writers — **not applicable to the bot**: `CLAUDE.md` records `play` writes
   `CMC+0xE8`/`+0x328` only on the pawn it drives, and the bot is not it. ⚠ **[I], not [M]** — state
   it explicitly and verify no `play` build is injected, or the exclusion is unearned.
3. A genuinely failed or mis-addressed write.

**The disambiguator is `+0x16B0`.** If `+0x16B0 == S` while `+0xE8` has moved on, the snapshot
captured *our* sentinel at the first post-poke frame and the velocity then evolved — that is
**CELL C**, the strongest possible positive, and it must not be reported as void. Only
`+0x16B0 == Z && +0xE8 == Z` (CELL E) is a real instrument failure.

**Recommended flight-design change:** read `+0x16B0` and `+0xE8` **together, at ~10 Hz for ~5 s**,
starting immediately after the write, and print **every sample raw**. A single read ≥ 3 frames later
can land in CELL D and lose the discriminating first frame.

---

## 4. NEW — EXIT 2 IS NOT CLOSED BY READING `CMC+0xC0` ALONE

Tier-1 §1.6 correctly flags `CMC+0xC0` as the one mandatory gate input never read live, and §7
item 2 prescribes "one qword". **Necessary, not sufficient.** My disassembly:

```
0x035E9EEE  4c 8b a9 c0 00 00 00     mov  r13, [rcx+0xc0]        ; WorldPrivate
0x035E9EF9  4c 89 6d 90              mov  [rbp-0x70], r13
0x035E9EFD  48 8b d9                 mov  rbx, rcx
0x035E9F00  4d 85 ed                 test r13, r13
0x035E9F03  75 0c                    jne  0x035E9F11             ; non-null -> use it
0x035E9F05  e8 36 5d fc ff           call 0x035AFC40             ; <-- FALLBACK GetWorld()
0x035E9F0A  4c 8b e8                 mov  r13, rax
...
0x035E9F25  4d 85 ed                 test r13, r13
0x035E9F28  0f 84 79 12 00 00        je   0x035EB1A7             ; EXIT 2
```

and the fallback `0x035AFC40` **never reads `+0xC0`**:

```
0x035AFC46  48 8b d9                 mov  rbx, rcx
0x035AFC49  48 8b 89 b8 00 00 00     mov  rcx, [rcx+0xb8]        ; UActorComponent::OwnerPrivate
0x035AFC50  48 85 c9 / 74 14         test rcx,rcx / je 0x035AFC69
0x035AFC55  8b 41 0c / c1 e8 04 / a8 01   Owner->ObjectFlags >> 4 & 1   ; RF_ClassDefaultObject
0x035AFC5D  75 0a                    jne  0x035AFC69
0x035AFC5F  e8 2c cd dd ff           call 0x0338C990             ; AActor::GetWorld()
0x035AFC64  48 85 c0 / 75 20         test rax,rax / jne <return rax>
0x035AFC69  48 8b 5b 28              mov  rbx, [rbx+0x28]        ; UObject::OuterPrivate
0x035AFC6D  48 85 db / 74 15         test rbx,rbx / je <return 0>
0x035AFC72  48 8b cb / e8 b6 bc a7 ff    call 0x0302B930         ; type test on the Outer
0x035AFC7A  84 c0 / 74 09            test al,al / je <return 0>
0x035AFC7E  48 8b c3                 mov  rax, rbx               ; return Outer
```

⇒ **Interpretation rule, [M] from the bytes:**

- `CMC+0xC0 != 0` ⇒ **exit 2 PASSES**, full stop. One read closes it.
- `CMC+0xC0 == 0` ⇒ **UNDECIDED.** You must also read `CMC+0xB8` (Owner) and, if that is non-null and
  not a CDO, the Owner's world. A probe that reads only `+0xC0`, sees `0`, and writes "exit 2 bails"
  would commit precisely the mis-attribution this project keeps recording.

`+0xB8 = OwnerPrivate` is corroborated independently by `CLAUDE.md` S132 (*"`[comp+0xB8] = 0x…870
cls=BP_DropPod_Tutorial_C` ⇒ `UActorComponent`'s owner is at `+0xB8`"*), so the two derivations come
from different subsystems. **Cost of the fix: one extra qword** (already in §3.3).

---

## 5. THE `EMovementMode` QUESTION (task item 2)

**`cmc_earlyout_readout.py` carries the CORRECTED table.** Source `:74-80`, verbatim:

```python
EMOVE = {0: "MOVE_None", 1: "MOVE_Walking", 2: "MOVE_NavWalking", 3: "MOVE_Falling",
         4: "MOVE_Swimming", 5: "MOVE_Flying", 6: "MOVE_Dashing(LOKI)", 7: "MOVE_Custom", 8: "MOVE_MAX"}
```

with the three-instrument citation in the comment above it. **No fix needed.**

**`tools/re/movementmode_readout.py` carries STOCK.** Source `:52-53`:

```python
EMOVE = {0: "MOVE_None", 1: "MOVE_Walking", 2: "MOVE_NavWalking", 3: "MOVE_Falling",
         4: "MOVE_Swimming", 5: "MOVE_Flying", 6: "MOVE_Custom"}
```

⇒ It mis-decodes `6` as `MOVE_Custom` (truth: `MOVE_Dashing`) and prints `?` for `7` and `8`.

**Consequence for §7:** if the two probes are run side by side and the mode is ever ≥ 6, they will
**disagree by design**, and that disagreement is the *known* defect, not evidence about the game. It
is harmless today (both pawns read `3 = MOVE_Falling`, agreeing), but must be written down before
anyone uses it as a cross-check. **Fix `movementmode_readout.py`'s table** — two lines, and the S139
citation is already in the sibling file.

---

## 6. RUN-IS-VOID BEHAVIOUR ON A DEAD / FK-32 CLIENT (task item 4)

**Exactly what it does today, traced through the source:**

| state | behaviour | verdict |
|---|---|---|
| PID does not exist / `OpenProcess` denied | `:107-110` prints `OpenProcess(N) failed -- err D. RUN IS VOID.` and `sys.exit(1)` | **CORRECT** |
| Process exited but the PID is not yet recycled and a handle is obtainable | `OpenProcess` **succeeds**; every RPM fails; `rpm → None`; `p() → 0`; `objects()` yields nothing; `find_actors` returns all-`None`; `main` `:383-385` prints `!! NO PLAYER-CONTROLLED PAWN -- no two-sided control exists. RUN IS VOID.` | **lands on a VOID, with the WRONG MESSAGE** |
| Process alive, **wrong `BASE`** passed | identical output to the row above | **indistinguishable** |
| Process alive, a decode defect (the S139 FNamePool / FField bugs) | identical output to the row above | **indistinguishable — and this exact string was printed on a HEALTHY client in S139** |
| Object dies mid-`--watch` | prints `dt=None  moved=  -1.00` and keeps looping; **no void** | **DEFECT D7** |

**There is NO liveness check.** No `GetExitCodeProcess`, no `WaitForSingleObject(h, 0)`, no
"did any RPM succeed at all" counter, no `MZ` canary at `BASE`. I checked `flymode_poke.py`,
`livingstate_poke.py` and `motion_watch.py`: **none of them has one either** — their `RUN IS VOID`
is likewise only the `OpenProcess` failure path.

**Required additions (three cheap reads, before anything else):**

1. **Liveness.** `GetExitCodeProcess(h, &code)`; if `code != 259 (STILL_ACTIVE)` print
   `CLIENT IS DEAD — exit code 0x%08X — RUN IS VOID` and exit. **If `code == 0x0000DEAD`, name FK-32
   explicitly** (`CLAUDE.md`: the protector's silent kill; `0xDEAD` is not ours) and if
   `0xC0000005`, name FK-31. S138 lost a key observation to a throwaway probe with no such check;
   this is the fix for that class.
2. **Base canary.** Read 2 bytes at `BASE` and 4 at `BASE + *(u32)(BASE+0x3C)`; require `MZ` and
   `PE\0\0`. On failure print `BASE 0x… does not look like a PE — wrong base or RPM broken — RUN IS
   VOID` — a **different** message from "no player pawn".
3. **Decode canary.** After `find_actors`, print `objects walked = N, named = M, classes = K`. If
   `N > 0` but `M == 0`, print `FNAME DECODE IS BROKEN — this is an INSTRUMENT failure, not a game
   fact` (the S139 defect verbatim). Only if `N > 0 && M > 0 && no player pawn` may it print the
   current message — and it should then read **`no player-controlled pawn found among M named
   objects`**, quoting the denominator.
4. **Split the gate.** Do **not** hard-return on `not lp(plr)` (`:383-385`). The player is a control
   on *structural* fields only, and Tier-1 §2.2 shows it is useless for the `+0x16D0` receipt. Print
   the BOT table and the `[RAW]` block regardless, and mark only the **control-dependent** verdicts
   void. A sitting that loses the player must not lose the bot data with it.

---

## 7. THE INSTRUMENT CONTROL TO KEEP ON HAND (task item 5)

**Primary: `tools/re/movementmode_readout.py`.** It is the probe S139 used to localise both
`cmc_earlyout_readout.py` defects in minutes, and it is the right choice again because it reaches the
*same objects* by a *different* code path: its own actor `find` (`CTL_PAWN 0x3F8`), its own by-name
property resolution, its own live `FEnumProperty::Enum` resolve (`prop+0x78`), and it prints the pawn
class and location.

**What it would show if the new reads are wrong:**

| symptom | `movementmode_readout.py` says | conclusion |
|---|---|---|
| `cmc_earlyout` prints `NO PLAYER-CONTROLLED PAWN — RUN IS VOID` | a populated table with `BP_HERO_Ronin_C`, `MovementMode=3`, a real location | the fault is in `cmc_earlyout`'s object/name decode. **This is the S139 case verbatim.** |
| `cmc_earlyout` prints `no CharacterMovement UPROPERTY` | resolves `CharacterMovement` by name fine | `findprop` / `FField` decode regression |
| `cmc_earlyout`'s VPTR control fails | reports the same `cmc` pointer for the same pawn | the vptr constant or `BASE` is wrong, not the object |
| both print nothing | — | the client, the PID or the `BASE` is the problem, not either probe |

**⚠⚠ AND THE MANDATORY CAVEAT, because this is a recorded failure mode (S114: *"two instruments that
fail the same way are not corroboration"*):** the two probes **share**, verbatim by copy,
`NAMEPOOL = BASE + 0x9D81450`, `OBJOBJECTS = BASE + 0x9E38930`,
`CLASS_OFF/NAME_OFF/SUPER_OFF = 0x18/0x20/0x48`, `STRIDE 0x18`, `PERCHUNK 65536`,
`CHILDPROPS_OFF 0x58`, `FIELD_NEXT 0x18`, `FPROP_OFFSET 0x44`, `CTL_PAWN 0x3F8` and the `lp()`
predicate. **They are NOT independent on any of those.** A wrong `BASE`, a post-patch `NAMEPOOL`
move, or a `GUObjectArray` layout change fails **both identically**, and their agreement would be
worthless.

**So keep a structurally different second control too**, one that shares no line of Python:

- **`usmapdump.exe dumpimage <proc>` / `threads` / `peek`** — a **Go** implementation with its own
  module-base discovery. If it reports a module base different from the `BASE` handed to
  `cmc_earlyout`, that is the fault, and no Python probe can tell you.
  ⚠ `dumpimage` needs the **`.exe` suffix** on the process name, or it prints `process not found` on
  a living client (recorded trap).
- **`tools/re/obj_by_chain.py`** with `=LokiCharacterMovementComponent` — a third census of the same
  population. ⚠ Use `=LokiBotController`, **never `=BotController`**: S137 measured that the latter
  is a degenerate query with **no positive control** on this hierarchy (`found 0` and
  `CDOs matched and EXCLUDED: 0` while a `LokiBotController` was live in that very process).

**For the flight itself, also keep `tools/re/motion_watch.py` staged.** The S138 rule is **start the
reader BEFORE the injection/poke** — flight 7 lost its key observation by polling afterwards. The
same applies here: `find_actors` is a multi-minute scan (D6), so the pointers must be resolved
**before** the write, not after.

---

## 8. SUMMARY OF REQUIRED EDITS, IN PRIORITY ORDER

1. **Rewrite the RANK-1 VERDICT block** (D5) — delete the `latch == 0 ⇒ S2` branch, add the
   "cleared every frame" alternative to the CONTROL FAILED text, replace the `--watch` READ IT AS
   table.
2. **Add the `[RAW]` hex block** for `+0x16B0..+0x16C7` and `+0xE8..+0xFF` on both sides (§3.2).
3. **Add the vptr control and make it gate the sentinel verdict** (§3.4).
4. **Add the `[SENTINEL]` cell line**, cells A–G (§3.5), including **CELL C/D, which Tier-1 §5
   mislabels as a void** (§3.6).
5. **Add `+0xC0`, `+0xB8`, `+0x3DC`, `+0x3E0`, `+0x3E4`, `+0x16D0`, `World+0x808`** (§3.1, §3.3),
   with the exit-2 interpretation rule from §4.
6. **Add the liveness / base / decode canaries and split the player gate** (§6).
7. **Enumerate and count class matches; accept an explicit `--cmc` / `--pawn` pointer** (D2/D3).
8. **Memoise `chain`/`oname` by pointer; resolve actors once before the poke** (D6).
9. **Gate on `CTRL.tickTarget==cmc`, or delete the header claim** (D1).
10. **Fix `movementmode_readout.py`'s `EMOVE`** (§5) so the cross-check probe stops disagreeing by
    design.
11. Cosmetic, same family: print offsets in hex (`cmc.off` currently prints `1112`), and stop
    truncating the `bRegistered` string (D4).

---

## 9. GRADES

| claim | grade |
|---|---|
| D1 (tickTarget control does not gate), D2 (last-match-wins), D3 (bot predicate), D4 (no raw / 3 dp), D5 (verdict stale), D7 (`--watch` ignores void) | **[M]** — read from the source |
| D6 (multi-minute scan) | **[I, strong]** — arithmetic from the source, not timed on a live client |
| All 10 offsets in §2 | **[M]** — my own UHT `PropPointers` scan, 11 passing positive controls |
| `NumJumpApexAttempts` is not reflected | **[M]** — 0 ASCII occurrences against 11 controls that all resolved. ⚠ Bounded: an ASCII-only scan; UHT names are ASCII in this image, which the 11 controls establish. |
| §4 exit-2 fallback (`+0xC0` insufficient; `+0xB8`/`+0x28` path) | **[M]** — disassembled from `0x035E9EEE` and `0x035AFC40` |
| §3.6 (Tier-1 §5 mislabels CELL C) | **[M]** on the logic; **[S]** that CELL C will actually occur |
| Tier-1 §4's vtable / byte evidence | **[M], independently reproduced** — 14/14 displacement controls PASS, every byte string reproduces |
| "`play` cannot contaminate the bot's `+0xE8`" | **[I]** — from `CLAUDE.md`'s description of which pawn `play` drives; verify no `play` build is injected before relying on it |
| Every `.text` census here | **FLOOR** — `merged13` is 55.48 % decrypted |
