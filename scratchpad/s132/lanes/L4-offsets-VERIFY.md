# S132 LANE 4 — ADVERSARIAL VERIFICATION of `scratchpad/s132/lanes/L4-offsets.md`

**Method:** offline only, zero launches, zero injections. I did **not** use `fkdis.py`; I wrote an
independent PE reader (`scratchpad/s132/lanes/verify/v.py`) that parses the section table itself,
does its own VA→RVA arithmetic, and disassembles with capstone. Every address below was recomputed
with `python -c`. Where the report used one instrument I looked for a *different* one.

Images touched: `merged4` (primary), `merged3`, `merged2`, `merged`, `tutorial-hero`,
`s131-rideable-live`. Section table read from the file: `.text 0x1000+0x7649000`,
`.rdata 0x764A000+0x237D000`, `.data 0x99C7000+0x6F0000`.

**Score: 33 load-bearing claims CONFIRMED · 4 REFUTED (as stated) · 2 UNSUPPORTED · 1
DEGENERATE-CONTROL.** Every offset the report exists to deliver survived. What did not survive is
one control's wording, one string-search's wording, one completeness claim about instruction
encodings (the largest real defect), and one "unattributed" that is attributable in one instruction
— and that last one hands §7 a lever it says does not exist.

---

## A. WHAT I RE-DERIVED AND CONFIRMED (33)

### A1. `ULokiRideableComponent` reflection metadata — CONFIRMED, independently decoded

`FClassParams @ .rdata 0x8A503A0`, read raw:

```
08A503A0: 40 27 45 b4 f6 7f 00 00  30 c1 6b b6 f6 7f 00 00
08A503B0: 90 03 a5 b7 f6 7f 00 00  58 02 a5 b7 f6 7f 00 00
08A503C0: 70 02 a5 b7 f6 7f 00 00  f0 01 a5 b7 f6 7f 00 00
08A503D0: 00 00 00 00 00 00 00 00  22 81 06 00 a4 00 b0 00
```
→ ClassNoRegisterFunc `0x5452740` · ConfigName `0x76BC130` = `"Engine"` (read as a C string) ·
CppClassInfo `0x8A50390` (**verified 16 zero bytes**) · deps `0x8A50258` · funcs `0x8A50270`
(**(0x8A50390-0x8A50270)/16 = 18** ✓) · props `0x8A501F0` · packed `0x00068122` ·
ClassFlags `0x00B000A4`. **All 8 fields match the report.**

`PropPointers` 13 entries — my own walk returns the same 13 record addresses in the same order
(`0x8A4FEA0, 0x8A4FEE0, 0x8A4FF20, 0x8A4FF60, 0x8A4FFA0, 0x8A4FFF0, 0x8A50030, 0x8A50070,
0x8A500B0, 0x8A500F0, 0x8A50130, 0x8A50170, 0x8A501B0`).

**(1) The full 13-record decode is reproduced field-for-field**, including every `PropertyFlags`
value the report printed:

| # | name | gen | ArrDim | Offset | PropertyFlags | RepNotify |
|---|---|---|---|---|---|---|
|0|OnCanExitChanged|1b InlineMcastDlg|1|0x0D0|0x0010000010080000||
|1|OnPlayersInsideCountChanged|1b|1|**0x0E0**|0x0010000010080000||
|2|OnPlayerEntered|1b|1|0x0F0|0x0010000010080000||
|3|OnPlayerExited|1b|1|0x100|0x0010000010080000||
|4|InsideEffect|11 Class|1|0x110|0x0024080000010015||
|5|bCanExit|4c Bool\|NativeBool|1|(ElemSize slot)|0x0020080100000034|OnRep_bCanExit|
|6|PlayersInsideCount|03 Int|1|**0x11C**|0x0020080100000034|OnRep_PlayersInsideCount|
|7|PlayersInside (INNER)|12 Object|1|0x000|0||
|8|PlayersInside|16 Array|1|**0x120**|0x0020080000000034||
|9|PlayersAttached (INNER)|12 Object|1|0x000|0||
|10|PlayersAttached|16 Array|1|**0x130**|0x0020080000000014||
|11|PlayersThatExited (INNER)|12 Object|1|0x000|0||
|12|PlayersThatExited|18 Set|1|0x140|0x0020080000000014||

**(2) `PlayersInsideCount @0x11C` — CONFIRMED.** UHT above, plus my own disassembly of
`OnRep_PlayersInsideCount` impl `0x55E0FC0`, raw bytes
`8b911c0100004881c1e0000000e9ae15cefd`:
```
055E0FC0  8b911c010000     mov edx, dword ptr [rcx + 0x11c]
055E0FC6  4881c1e0000000   add rcx, 0xe0
055E0FCD  e9ae15cefd       jmp 0x32c2580
```

**(3) `OnPlayersInsideCountChanged @0xE0`, 16 B — CONFIRMED**, and independently from the other end
by `OnRep_bCanExit` impl `0x55E1000` (`0fb69118010000 / 4881c1d0000000 / e9ada4e4fe`), which pins
`OnCanExitChanged @0xD0`.
⇒ the S131 §13 correction in CLAUDE.md (`+0xE0` on **this** class is a delegate, not a cached round
game mode) is re-confirmed on a third pass.

**(4) `PlayersInside @0x120` / Num `@0x128` — CONFIRMED four ways** — UHT, plus three disassembled
sites I re-read myself: `AuthPlayerEnterWorld 0x55CCEC2`, `ContainsPlayer 0x55D0270`,
`HasEverContainedPlayer 0x55DCAA0`. The report's claimed `this`-mirror is real:
`0x55CCEB7 488bf9 mov rdi, rcx`, and `0x55CCEC9 movsxd rax, [rdi+0x128]` therefore reads the same
object as `0x55CCEC2 mov rcx,[rcx+0x120]`.

**(5) `PlayersAttached @0x130 / 0x138 / 0x13C` — CONFIRMED**, append quoted from my own capstone
output, byte-identical to the report:
```
055CD738  49639e38010000   movsxd rbx, dword ptr [r14 + 0x138]
055CD73F  8d4301           lea    eax, [rbx + 1]
055CD742  41898638010000   mov    dword ptr [r14 + 0x138], eax     <-- Num written FIRST
055CD749  413b863c010000   cmp    eax, dword ptr [r14 + 0x13c]
055CD750  760e             jbe    0x55cd760
055CD752  8bd3             mov    edx, ebx
055CD754  498d8e30010000   lea    rcx, [r14 + 0x130]
055CD75B  e870b19cfb       call   0xf988d0
055CD760  498b8630010000   mov    rax, qword ptr [r14 + 0x130]
055CD767  48893cd8         mov    qword ptr [rax + rbx*8], rdi
```
and `0x55CD543 4c8bf1 mov r14, rcx` confirmed as the `r14 == this` establishment.

**★ (6) A THIRD, DISJOINT OFFSET INSTRUMENT THE REPORT DID NOT USE — and it agrees.**
The report says `binds_members.csv` "carries no offsets, so it is a type oracle, not an offset
oracle" (true — I checked, its offset columns are `0`/blank). But the **Angelscript `.as.txt` ADDSi
annotations are an offset oracle**, and CLAUDE.md grades that oracle **[M]** (76:0 live agreement,
784 conflict-free pairs). `tools/asdump/out/a/GameMode.DropPhase.LokiDropPod.as.txt`:
```
1524:  ADDSi  W0:288  ; ULokiRideableComponent::PlayersInside    (+288)   = 0x120
1546:  ADDSi  W0:304  ; ULokiRideableComponent::PlayersAttached  (+304)   = 0x130
```
Independent third confirmation of the two most load-bearing offsets in the whole lane.

**(7) `bCanExit @0x118`, real `bool` — CONFIRMED three ways.** Record `0x8A4FFF0` tail read raw:
`01 00 | 01 00 | e0 01 00 00 | 50 b9 32 b2 f6 7f 00 00`, SetBitFunc → `.text 0x332B950`:
`c6 81 18 01 00 00 01 | c3` = `mov byte ptr [rcx+0x118], 1; ret`. Plus `CanExit` impl `0x525C240`
= `0fb68118010000 c3` (a **1-byte** read ⇒ whole-byte NativeBool) and `OnRep_bCanExit` above.

**(8) `PlayersThatExited @0x140` + TSet internals — CONFIRMED** from `HasEverContainedPlayer`:
`[r10+0x140]` Elements.Data, `[r10+0x148]` ArrayNum, `[r10+0x174]` NumFreeIndices,
`[r10+0x178]` inline hash, `[r10+0x180]` Hash, `[r10+0x188]` HashSize; 16-byte set-element stride
(`add rax,rax` then `[rcx+rax*8]`). Report correctly grades the sub-field *names* [I].

### A2. `AActor` — the two headline claims, CONFIRMED EXACTLY, by exhaustive decode

**(9) `AActor` `FClassParams @ .rdata 0x7F227E0`** — ClassNoRegisterFunc `0x2BE1050`, ConfigName
`"Engine"`, PropertyArray `0x7F21540`, deps `0x7F218D0`, packed `0x00390992`.
**(10) `(0x7F218D0-0x7F21540)/8 = 114` entries — CONFIRMED.**

**(11) I decoded ALL 43 `AActor` bool records, not just the four the report needed.** Every one
resolved to an offset+mask. Results for the claims under test:

```
[  3] bAlwaysRelevant     rec 0x7F1F730  SetBitFunc 0x32F7100  80 49 68 08 c3          -> 0x68 / 0x08
[  7] bHidden             rec 0x7F1F880  SetBitFunc 0x3368980  80 49 68 80 c3          -> 0x68 / 0x80
[ 27] bCanEverReplicate   rec 0x7F1FDF0  SetBitFunc 0x2078900  c6 41 6c 01 c3          -> 0x6C / NativeBool
[100] bEnablePooling      rec 0x7F21160  SetBitFunc 0x3368BF0  c6 81 d3 02 00 00 01 c3 -> 0x2D3
```
**`bHidden` → 0x68 mask 0x80 and `bAlwaysRelevant` → 0x68 mask 0x08 are CONFIRMED EXACTLY**, and
the two CLAUDE.md controls (`0x6C`, `0x2D3`) reproduce.

**(12) The byte-0x68 and byte-0x69 bit families — CONFIRMED EXHAUSTIVELY, including the 0x02 gap.**
My 43-record sweep produces exactly the report's two tables, and independently reproduces the
missing `0x02` slot (stock UE's non-reflected `bNetStartup:1`). This upgrades the report's family
table from "for anyone reaching for a second flag" to a closed enumeration of bytes 0x68/0x69.
⇒ the report's `or`/`and`-the-mask warning is correct and necessary: four of byte 0x68's other
occupants are replication controls.

### A3. `FBoolPropertyParams` layout — CONFIRMED, and the two-sided control is real

**(13) `ArrayDim u16@0x30 · ElementSize u16@0x32 · SizeOfOuter u32@0x34 · SetBitFunc ptr@0x38`,
sizeof 0x40 — CONFIRMED.** The decisive bytes (`bHidden`, `0x7F1F8B0`):
`01 00 | 01 00 | 90 03 00 00 | 80 89 36 b2 f6 7f 00 00`. A `SIZE_T SizeOfOuter@0x38` layout is
excluded by the data: `+0x38` is a `.text` pointer, and `+0x40` is the *next record's* NameUTF8
(`bTearOff`, `0x7F1F8C0` = `0x7F1F880 + 0x40`).

**(14) The `SizeOfOuter` two-sided control is genuine — and I verified the two functions' IDENTITY,
which the report asserted without showing.**
* `0x54527D5 c7442420e0010000 mov dword [rsp+0x20], 0x1e0` lies inside `0x5452740`, and that
  function's own `lea rdx` / `lea rcx` resolve (machine-computed) to UTF-16 `"LokiRideableComponent"`
  @ `0x8A4FE6A` and `"/Script/Loki"` @ `0x88152C0` ⇒ it **is** `ULokiRideableComponent::StaticClass`.
* `AActor`'s ClassNoRegisterFunc `0x2BE1050` is `e9bbac7a00 jmp 0x338bd10`; `0x338BDA4
  c744242090030000 mov dword [rsp+0x20], 0x390` lies inside `0x338BD10`, whose strings resolve to
  `"Actor"` @ `0x7F1F65A` and `"/Script/Engine"` @ `0x773DBE0`. Both call the same
  `GetPrivateStaticClassBody` at `0x1224BB0`.
⇒ 0x1E0 and 0x390 come from two *different* functions, each independently identified. Not degenerate.

**(15) "`ObjectFlags = 0x45` on every record image-wide" — CONFIRMED**, and stronger than stated:
over all **13,101** bool-shaped `.rdata` records image-wide the distribution is `{0x45: 13101}`,
i.e. 100.000 %, zero exceptions.

### A4. Inner type, replication, ABI

**(16) `PlayersAttached` inner = `ObjectProperty`, `ObjectPtr` bit clear — CONFIRMED** (gen `0x12`).
**(17) ClassFunc chain — CONFIRMED.** All three inners (`0x8A50070`, `0x8A500F0`, `0x8A50170`) carry
the *same* `+0x38` = `0x5276490` = `e9dbaa1b00 jmp 0x5430F70`, whose lea targets I recomputed:
`0x5430FBD + 0x35F334D = 0x8A2430A` = UTF-16 `"LokiPlayerState"`, `0x5430FCC + 0x33E42F4 =
0x88152C0` = `"/Script/Loki"`, `InSize = 0xEB8`.
**(18) `PlayersAttached` is NOT replicated — CONFIRMED.** `0x0020080000000014`; `CPF_Net (0x20)`
clear, against the in-class discriminating control `PlayersInside = 0x0020080000000034` (identical
but for that bit). `bCanExit`/`PlayersInsideCount` additionally carry `CPF_RepNotify
(0x0000000100000000)` and name real `OnRep_` UFunctions. The instrument demonstrably sees
replication on this class.
**(19) `ResizeGrow 0x00F988D0` — CONFIRMED**, element size 8 baked in at four points
(`lea rcx,[rax*8]`, `mov edx,8`, `mov [rsp+0x20],8`, `mov r9d,8`), `Data+0x0 / ArrayNum+0x8 /
ArrayMax+0xC` read directly, and `0x0F988E8 3bda cmp ebx, edx` (already-updated ArrayNum vs OldNum
in `edx`) confirmed at exactly that address ⇒ the report's ordering warning is correct.
**(20) `callxref` caps at 200 and the report says so — CONFIRMED as an honest floor.** Uncapped
byte-level rel32 sweep: **4,363** callers of `0xF988D0`.

### A5. The wall, the detach, the folds

**(21) The ordering trap — CONFIRMED, and it is the *third* silent bail, not the first.**
```
055CD535  8b420c       mov eax,[rdx+0xc]   \
055CD53B  c1e81e       shr eax,0x1e         > object-flags gate on the PlayerState
055CD541  f6d0         not al               /
055CD546  a801         test al,1
055CD548  0f842d020000 je  0x55cd77b        <-- silent bail #2 (bail #1 is 0x55CD513 on rdx==0)
055CD54E  e84df50000   call 0x55dcaa0       ; HasEverContainedPlayer(this, PlayerState)
055CD553  84c0         test al,al
055CD555  0f8520020000 jne 0x55cd77b        <-- the ordering trap
055CD572  e8d9159bfb   call 0xf7eb50        ; the stripped round-game-mode getter
```
`0x55CD77B` is confirmed as the shared restore-and-`ret` epilogue (`lea r11,[rsp+0x160] … pop rbp;
ret` at `0x55CD793`); I hand-checked the stack arithmetic and it returns cleanly, i.e. it really is
silent. And `HasEverContainedPlayer 0x55DCAA0` really does scan `+0x120`/`+0x128` **first** and
`mov al,1; ret` at `0x55DCB57` on a hit, before ever touching the TSet.
**(22) Detach `0x55CCCB0` gated on `PlayersAttached` non-empty — CONFIRMED**
(`0x55CCCEC mov rcx,[rcx+0x130]`, `0x55CCCF3 movsxd rax,[rbp+0x138]`, `0x55CCD01 je 0x55CCE5B`).
**(23) "TWO `0xF7EC20`, ZERO `0xF7EB50`" — CONFIRMED TWO WAYS.** Byte-level rel32 scan over
`[0x55CCCB0, 0x55CCE68)` returns exactly `{0xF7EC20: [0x55CCD5B, 0x55CCE4E]}` and nothing else; an
independent capstone linear sweep lists all 16 call/jmp targets and contains no `0xF7EB50`. The
`call 0x11F3860` at `0x55CCE32` also checks out (rel32 `296ac2fb` recomputed by machine →
`0x11F3860`).
**(24) The whole §8a fold/REAL table — CONFIRMED** by my own `.data` `{name, thunk, impl}` search
(find the ASCII name, find 8-aligned qwords equal to its VA, read `+8`/`+0x10`). All 15 rows
reproduce, including the four folds (`AuthAddPlayer`/`AuthRemovePlayer` share thunk `0x2C2CE30`;
`AuthSetCanJump` `0x5296F30`; `AuthPlayerEnterWorldNew` `0x5456460` — all impl `0x00F7EC20`) and
both `HasEverContainedPlayer` records.
**(25) All five folds' bytes — CONFIRMED**: `0xF7EC20 c2 00 00` · `0xF7EB50 33 c0 c3` ·
`0xF7EB60 32 c0 c3` · `0xB9E1F0 b0 01 c3` · `0xFC6CF0 0f 57 c0 c3`.
**(26) `ArrayMax@0x12C` graded [I] — CONFIRMED as honest.** A disp32 scan over
`0x55CC000..0x55E2000` finds **0** candidate sites at `+0x12C` against **1** at `+0x13C`
(`0x55CD74C`, the append's compare), 11 at `+0x128`, 15 at `+0x138`.

### A6. `LokiRideable @ 0x6C8`

**(27) `ALokiDropPodBase` has exactly ONE reflected property — CONFIRMED**, found from the other
direction (search the name string, then who points at the record, then whose `FClassParams+0x28`
points at that array): prop array `0x89341B0` → deps `0x89341B8` ⇒ **1 entry**;
record `0x8934170`, gen `0x12 Object`, **Offset `0x3C0`**; `FClassParams 0x8934240`,
ClassNoRegisterFunc `0x53325A0` whose strings resolve to `"LokiDropPodBase"` / `"/Script/Loki"`
with `InSize = 0x3C8`. `PilotPlayerState@0x3C0` is the last 8 bytes of the class — an extra
internal consistency check the report did not have.
**(28) Angelscript oracle — CONFIRMED.** `class ALokiDropPod : ALokiDropPodBase` opens at line 152
of `tools/asdump/out/GameMode/DropPhase/LokiDropPod.as.txt`; the only `*Component` member in the
declaration block is `USkeletalMeshComponent@ PodMeshComponent`; `ULokiRideableComponent::Get(this,
NAME_None)` at lines **1530, 2258, 3940, 5104**, and `LokiDropShip.as.txt:159`. Exactly as reported.
The grep control is **live, not degenerate**: `tools/asdump/out/modules/` exists and
`modules/GameMode/DropPhase/LokiDropPod.as.txt` has **17** `LokiRideable` hits.
**(29) Cooked asset — CONFIRMED.** `tools/extractor/out/BP_DropPod.json` is an 83-element list;
export **#50** is exactly the quoted object, and export **#66** is `SCS_Node_13` with
`ComponentClass = LokiRideableComponent` — a Simple Construction Script node, which is positively
what makes it a BP-generated component property rather than a native one.

### A7. Housekeeping claims

**(30) Coverage control — CONFIRMED and extended.** I re-ran it over 21 regions (the report's 15
plus the extra addresses I introduced): **0 all-zero pages in `merged4`.**
**(31) `binds_members.csv` — CONFIRMED**: rows 44945-44954 list exactly the ten declared properties
in order 0-9 with the quoted types; the offset columns really are all `0`/blank.
**(32) The packed-count `props` field — CONFIRMED on a THIRD sample the report did not have.**
`ALokiDropPodBase` packed `0x8062`: `>>15 = 1`, and its measured prop-array extent is **1**. The
`deps` field also survives that third sample (2 in all three), once you notice the terminator — D2.
**(33) The `.text` half of the cross-image check does hold** — the four `SetBitFunc` bodies, the
append site, the wall prologue and `ResizeGrow` are byte-identical in `merged4`/`merged2`/
`tuthero`/`rideable`. (Its evidential value is another matter — see D1.)

---

## B. REFUTED

### B1. ⚠⚠ REFUTED — "**All four [images] agree byte-for-byte on every value**"

The preamble's cross-image control is **false as written**. The four load-bearing `.rdata` bool
records are **not** byte-identical across the four images, because two of their fields — the ones
the whole section rests on — are **absolute VAs subject to relocation**:

```
ImageBase:  merged4/merged2/merged 0x7FF6AF000000 · tuthero 0x7FF6505C0000 · rideable 0x7FF630E90000

bHidden record 0x7F1F880, first 8 bytes (NameUTF8) ... last 8 (SetBitFunc):
  merged4   a02af2b6f67f0000 ... 808936b2f67f0000
  tuthero   a02a4e58f67f0000 ... 80899253f67f0000     <-- DIFFERENT BYTES
  rideable  a02adb38f67f0000 ... 80891f34f67f0000     <-- DIFFERENT BYTES
```
Same for `bAlwaysRelevant`, `bCanEverReplicate`, `bEnablePooling` — 4/4 differ.

**Correction:** *the four images agree on every decoded RVA and every scalar field; they do not and
cannot agree byte-for-byte, because `NameUTF8@+0x00` and `SetBitFunc@+0x38` are relocated pointers.*
CLAUDE.md already records this exact hazard ("⚠ `.rdata` **pointer values** DO differ across
ImageBases … Read pointers only from an image whose base you are using"). **The substance is
unaffected** — every RVA I decoded from `tuthero`/`rideable` matches `merged4`.

### B2. ⚠⚠ REFUTED as a completeness claim — §4.3 "THE FOUR `SetBitFunc` ENCODINGS THE IN-ARM DECODER MUST HANDLE [M]"

I censused **every** `FBoolPropertyParams`-shaped record in `.rdata` (filter: gen&0x3F==0x0C,
high gen bytes 0, ObjectFlags 0x45, ArrayDim 1, ElementSize 1, `NameUTF8` in `.rdata`,
`SetBitFunc` in `.text`) — **13,101 records** — and classified each `SetBitFunc` body with capstone.

**The report's four encodings cover 9,950 of 13,101 = 75.9 %. 3,151 records (24.1 %) use one of
EIGHT further encodings, and a decoder built to the report's table mis-reads all of them:**

| bytes | instruction | count | in report? |
|---|---|---:|---|
| `c6 41 <d8> 01 c3` | `mov byte [rcx+d8], 1` | 5,526 | yes |
| `c6 81 <d32> 01 c3` | `mov byte [rcx+d32], 1` | 2,989 | yes |
| **`c6 01 01 c3`** | **`mov byte [rcx], 1`  (NO displacement)** | **1,795** | **NO** |
| `80 89 <d32> <m> c3` | `or byte [rcx+d32], m` | 838 | yes |
| **`83 89 <d32> <imm8> c3`** | **`or DWORD [rcx+d32], imm8`** | **608** | **NO** |
| `80 49 <d8> <m> c3` | `or byte [rcx+d8], m` | 597 | yes |
| **`83 49 <d8> <imm8> c3`** | **`or DWORD [rcx+d8], imm8`** | **397** | **NO** |
| **`83 09 <imm8> c3`** | **`or dword [rcx], imm8`** | **84** | **NO** |
| **`81 89 <d32> <imm32> c3`** | **`or dword [rcx+d32], imm32`** | **84** | **NO** |
| **`80 09 <m> c3`** | **`or byte [rcx], m`** | **69** | **NO** |
| **`81 49 <d8> <imm32> c3`** | **`or dword [rcx+d8], imm32`** | **69** | **NO** |
| **`81 09 <imm32> c3`** | **`or dword [rcx], imm32`** | **45** | **NO** |

Two of these are not merely "another encoding" — they break the report's stated **rule**
`ByteOffset = d, ByteMask = mask`:

* **the `dword` OR forms make ByteOffset ≠ the displacement.** Measured example, read from
  `merged4`:
  ```
  03328910  81 49 1c 00 01 00 00 | c3     or dword ptr [rcx + 0x1c], 0x100 ; ret
            (bOverride_RayTracingTranslucencyRefractionRays)
  ```
  The true answer is **ByteOffset 0x1D, ByteMask 0x01**. A decoder written to the report's table
  reads `disp = 0x1C` and "the byte after the disp" = `0x00` ⇒ **wrong offset and a zero mask**,
  silently. 198 records use an `imm32` mask.
* **`c6 01 01 c3` has no displacement byte at all** (1,795 records, the third most common form
  image-wide); a decoder keyed on `c6 41`/`c6 81` falls through it entirely.

**Correct general rule:** decode the instruction, then
`ByteOffset = disp + (bit_index(mask) >> 3)`, `ByteMask = mask >> (8 * (bit_index >> 3))`,
with `disp = 0` for the no-displacement forms and `mask = 0xFF` for the `mov …, 1` (NativeBool) forms.

**The report's own results are UNAFFECTED** — all 43 `AActor` bools and `bCanExit` use only the
four named encodings (verified by my exhaustive decode). The defect is in the *general* [M]-graded
guidance the report hands the arm, which is exactly the class of error §9's own closing caveat warns
about ("Decode the instruction, do not slice a fixed width" — right instinct, table still incomplete).

### B3. ⚠ REFUTED — §8a "the other [`HasEverContainedPlayer`] is unattributed and should not be quoted as this class's"

It is attributable in **one instruction**, and the attribution is corroborated by UHT metadata:

```
055DCA90  48 8b 89 c8 03 00 00     mov rcx, qword ptr [rcx + 0x3c8]
055DCA97  e9 04 00 00 00           jmp 0x55dcaa0
```
and, from the `.rdata` side, `ALokiDropPlane::RideableComponent` is an `ObjectProperty` at
**offset `0x3C8`** — record `.rdata 0x8933100`, name string `.rdata 0x8933730`, which is *the very
string the report used as its own positive control*. Owning class resolved the hard way, not
assumed: that record is `PropPointers[4]` of the array at `.rdata 0x8933460`, which is `+0x28` of
`FClassParams 0x89336B0`, whose `ClassNoRegisterFunc 0x5332DC0` carries the UTF-16 literals
`"LokiDropPlane"` (`0x8932FDA`) and `"/Script/Loki"` with `InSize = 0x478`.

⇒ the second record (`thunk 0x53369E0 → impl 0x55DCA90`) is **`ALokiDropPlane::
HasEverContainedPlayer`**, an actor-level forwarder that loads its cached rideable component and
tail-jumps into the component implementation. Two agreeing instruments, zero inference steps.

**And this partly undercuts §7's framing.** §7 concludes "No offline instrument in this repo can
produce it" for a rideable-component pointer offset. That is true of the **Blueprint-generated**
`LokiRideable` on `BP_DropPod_C` — but a **native** cached `ULokiRideableComponent*` at a
UHT-measurable offset does exist and is offline-derivable: `ALokiDropPlane + 0x3C8`. If the arm
ever needs a component pointer on the plane rather than the pod, it does not need a by-name walk.

### B4. ⚠ REFUTED as literally stated (substance CONFIRMED) — §7 "`"LokiRideable\0"` … [has] **0** byte occurrences in `merged4`"

In **UTF-16LE** it occurs once, at `.rdata 0x8B1ABE6`:
```
08B1ABE0: 4c 00 6f 00 67 00 4c 00 6f 00 6b 00 69 00 52 00
08B1ABF0: 69 00 64 00 65 00 61 00 62 00 6c 00 65 00 00 00     -> "LogLokiRideable"
```
i.e. the tail of the log-category literal S131 named. The report did not state the encoding, and
this project's own FK-10 rule is that "every behavioural string in these binaries is UTF-16LE. An
ASCII-only scan finds essentially nothing."

**Correction:** *ASCII* `"LokiRideable\0"` and `"LokiRideable_GEN_VARIABLE"` have 0 occurrences
(I reproduced both); UTF-16 `LokiRideable\0` has 1, as a substring of `LogLokiRideable`.
**The conclusion is unaffected** and the control is *not* degenerate: UHT `NameUTF8` fields are
ASCII, and the chosen control `"RideableComponent\0"` @ `0x8933730` is a genuine ASCII UHT property
name, so the search is valid for the question actually asked.

---

## C. UNSUPPORTED (true on the evidence shown, but not established by it)

### C1. §6 — "that delegate's only emitter is the OnRep (impl `0x55E0FC0`)"

Stated flatly, but it is a bounded negative. My scan of `0x55CC000..0x55E2000` finds exactly **one**
instruction that forms the address `this+0xE0` (`0x55E0FC6 add rcx, 0xe0`), which supports it — but
I also found `0x55CE17E mov [rbx+0xE0], rdi` and `0x55CE190 mov qword [rbx+0xE0], 0` and could not
exclude `rbx` from being this component, and the address range is itself an unproven boundary on
"all code that can broadcast this delegate". **Restate as: no other emitter appears in the
`0x55CC000..0x55E2000` window; [I], bounded scan.** The operational advice (poking
`PlayersInsideCount` will not fire the delegate) is sound regardless — a data poke cannot call
anything.

### C2. §3 — `jmp 0x032C2580 ; FMulticastScriptDelegate::Broadcast(int32)`

The jump target is [M]; the **name** is [I] and is printed inside a code block as if it were read
off the artifact. Nothing rests on it, but per this repo's own rule ("never print a byte string next
to an address it did not come from"), an unverified symbol name inside a quoted disassembly block is
the same failure in miniature.

---

## D. DEGENERATE CONTROL, AND SMALLER NOTES

### D1. The "four independent images" `.text` check has no discriminating power

The report says "(`.rdata` is not demand-decrypted — FK-18 — so the `.rdata` agreement is expected;
**the `.text` agreement is the informative half**)". It is not informative:

* all five images on disk are the **same build** (all exactly 178,130,944 bytes);
* CLAUDE.md/S121 **measured** that `.text` carries **0** of the image's 1,403,750 relocations and is
  byte-identical across ImageBases on every page two images both decrypted (0 differing bytes in
  10/10 pairwise comparisons).

⇒ for any page decrypted in all four images, byte-identity is **guaranteed a priori**. The check can
only fail by a page being *undecrypted*, i.e. it is a coverage check restated — which the report
already runs separately. Demonstration that this is the only thing it can detect: the same regions
in the older `merged` image read **all zero** (append site, wall prologue), while all four chosen
images carry them. **Not wrong, not load-bearing — but it is not independent corroboration.**

### D2. §1's "immediately followed by the 2-entry dependency array"

The dep array at `0x8A50258` is `{0x3554F20, 0x528A7A0, 0x0}`: two pointers **plus an 8-byte NULL
terminator** before the function array at `0x8A50270`. `AActor`'s dep array (`0x7F218D0`) is two
pointers with **no** terminator before its function array at `0x7F218E0`. The counts are right; the
"immediately followed" chain is not uniform, and anyone re-deriving a count from adjacency needs to
know that. (`ALokiDropPodBase` matches the terminated form: `0x89341B8..0x89341D0` = 2 + NULL.)

### D3. §5's "`ResizeGrow` … heavily ICF-shared"

The *sharing* is confirmed (4,363 uncapped rel32 callers), but nothing shown establishes ICF
**folding** specifically as opposed to one template instantiation with many callers. Cosmetic.

### D4. §8a grades `MulticastOnPlayerEntered/EnteredWorld/Exited` "REAL"

Their impls (`0x5453780`/`0x54537C0`/`0x5453800`) are real bodies, but they are **RPC send stubs** —
each loads `[vtable+0x270]` and calls it with a marshalled parm block. They are not local
implementations, so they are not a counter-route to §8a's "no working API to add to `PlayersInside`"
(which therefore still stands: I found no store to `+0x120`/`+0x128` anywhere in the scanned range —
only reads, in `AuthPlayerEnterWorld`, `ContainsPlayer` and `HasEverContainedPlayer`).

---

## E. THE WEAKEST SURVIVING CLAIM

§4.4's `FBoolProperty` runtime layout is already correctly self-graded **[S]** and explicitly
labelled "a failed search, not a negative result", so it is not a defect. The weakest claim that is
*presented as settled* is **C1** (§6's flat "only emitter"), because it is a negative from a scan
whose boundary was never justified.

## F. WHAT I WOULD ADD TO THE ARM'S PAGE

1. The AS ADDSi oracle independently gives `PlayersInside +288 (0x120)` and `PlayersAttached
   +304 (0x130)` — cite it; it is a third instrument, [M]-graded by CLAUDE.md, and it is free.
2. If any decoder is written against `SetBitFunc`, it must handle **twelve** encodings and must
   compute `ByteOffset = disp + (bit_index >> 3)` for the `or dword` / `imm32` forms. See B2.
3. `ALokiDropPlane::RideableComponent @ 0x3C8` is offline-measurable (B3) if a plane-side handle is
   ever wanted.
4. `AuthPlayerEnterWorldAttachedToRidable` has **three** silent bails before `0x55CD572`, not one:
   `rdx == 0` at `0x55CD513`, the PlayerState object-flags gate at `0x55CD548`, and the
   `HasEverContainedPlayer` trap at `0x55CD555`. All three land on the same shared epilogue
   `0x55CD77B`, so a null result cannot distinguish them from outside.

*Verification tooling: `scratchpad/s132/lanes/verify/v.py` (independent PE reader + capstone).*
