# FK-1 stub claim — RE-CHECK, SETTLED

**S115, 2026-08-12. Entirely offline. Zero launches consumed. No game process touched.**

Resolves the conflict flagged at `docs/fk13-console-exec-settled.md` §6.1 between:

- **CLAIM A** — `CLAUDE.md:291-295` + `docs/fk1-angelscript-settled.md:160-172`: four server-authority
  C++ functions are EMPTY STUBS; `SpawnPlayer 0x534C070 = xor eax,eax; ret`, the other three `= ret`.
  Billed as *"THE REAL WALL"* and as what CLOSES `AvatarActor = NULL`.
- **CLAIM B** — FK-13 lane 3 (S114): three of those RVAs were measured in **two** independent dumps as
  **large real functions with security cookies and parameter steps**.

---

## 0. Verdict

> **Both measurements are correct. Neither describes the same address.**
>
> The four RVAs are `execFoo` **thunks** and they hold **real code** — CLAIM B's bytes are right [M].
> Each thunk's **implementation target** is a folded empty stub at a *different* RVA that CLAIM A's
> table never printed — CLAIM A's bytes are right too [M], including the otherwise-improbable
> `xor eax,eax; ret` for `SpawnPlayer`, which is exactly `0x0F7EB50`.
>
> **FK-1's substantive finding survives intact.** The four C++ implementations really are empty, and
> an empty impl is **rare** in this image — **1.2 %** base rate (78 / 6,669) [M]. FK-1's *"the real
> wall"* and its closure of `AvatarActor = NULL` **do NOT need re-opening.**
>
> What is wrong is one **address-column conflation**, and it was **manufactured in the `CLAUDE.md`
> digest, not in the source doc** (§6). `docs/fk13-console-exec-settled.md` §6.1 was right to flag a
> contradiction and right not to resolve it from one side; its inference that *"one of the two
> measurements is wrong"* is the only part that falls.

**No `.text` byte, no doc other than this one, and no `CLAUDE.md` line was changed by this session.**
The proposed `CLAUDE.md` correction is in §7 for the user to apply.

---

## 1. Images and ground rules

| | `dumps/merged.dump.exe` | `dumps/tutorial-hero/SUPERVIVE-Win64-Shipping.dump.exe` |
|---|---|---|
| ImageBase (read from the PE) | `0x7FF6AF000000` [M] | `0x7FF6505C0000` [M] |
| file size | 178,130,944 B | 178,130,944 B |
| flat (RVA == file offset) | yes, asserted per section [M] | yes [M] |
| `.text` | `0x1000 + 0x7649000` | identical |

Both images carry **byte-identical content at every address examined below** [M]. There is no
image-base or RVA/VA confusion on either side — that was the leading hypothesis going in and it is
**falsified**: the same RVA in both images yields the same bytes, and every quoted address is a
file offset that needs no base arithmetic at all.

Instrument: `scratchpad/stub_recheck{,2,3,4,5,6}.py` (this session), written from scratch.
It deliberately shares **no code and no constant table** with `tools/re/exec_chain_grade.py`, whose
`KNOWN_FOLDS` at line 50 already hardcodes `0x05254180: 'ret'` — i.e. that tool has *ingested the
claim under test* and cannot be used to adjudicate it.

---

## 2. ⚠ Three instrument artifacts I generated and caught, recorded per project rule

Per `memory/supervive-instrument-artifact-pattern`. All three would have produced a confident,
completely wrong negative.

| # | Instrument | Artifact | What it would have said | Truth |
|---|---|---|---|---|
| **S115-a** | `.pdata` read from the PE **exception data directory** (dir #3) | dir #3 is **`rva=0, size=0`** in both dumps — the dumper did not rebuild it | *"NO RUNTIME_FUNCTION covers this RVA"* for **every** function, including known-real controls | the directory is zeroed, not the data |
| **S115-b** | `.pdata` read from the **section** instead | the `.pdata` section is **6,283,264 B and 100 % ZERO** in **both** dumps — never paged in | *"0 RUNTIME_FUNCTIONs exist in this image"* → every function is a leaf, no extents, no size grading | `.pdata` is simply absent from the capture; extents must come from `tools/strxref/index/pdata_union.csv` (382,282 entries, union of 68 dumps) |
| **S115-c** | contiguous-run scan for `FNameNativePtrPair {const char* Name; FNativeFuncPtr Ptr;}` | `FClassFunctionLinkInfo` is `{UFunction*(*Create)(); const char* Name;}` — the **opposite field order**, so a stride-16 scan at +8 reads it **phase-shifted**, pairing `Name[i]` with `Create[i+1]` | *"`ALokiGameMode::SpawnPlayer`'s registered thunk is `0x5340D90`, a 47-byte function with no impl call"* — i.e. **the wrong address entirely**, which is precisely the failure mode this task was set to look for | `0x5340D90` is `Z_Construct_UFunction_*`: `mov rax,[rip+X]; test; jne; lea rdx,<name>; lea rcx,<slot>; call 0x135F5E0; ret` — a lazy singleton calling `UECodeGen_Private::ConstructUFunction`, **not** an exec thunk |

**S115-c was caught by the positive control, not by inspection.** `APlayerController::LocalTravel`
and `UKismetSystemLibrary::ExecuteConsoleCommand` — whose thunks `0x3C64600` / `0x395D790` were
derived independently by a `Z_Construct` walk in `docs/fk13-console-exec-settled.md` §3E — came back
with the *same* spurious "alt" address shape (`0x3C1B580`, `0x38BCE90`, both 47 B / 10 insn, both
calling `0x135F5E0`). A systematic artifact across controls is an instrument fault, not a finding.

---

## 3. [M] Per-function measurement

For each: the RVA CLAIM A printed, disassembled in **both** images, plus the implementation target
recovered by following the thunk's only non-helper call. The helper set was derived **empirically**
(fan-in histogram over all 31,723 registered `.text` pointers; ≥200 distinct callers ⇒ helper), not
assumed — `0x135F5E0` fanin 15,816, `0x1345FB0` 12,948, `0x1345FE0` 12,917, `0x12F3FC0` 2,735, etc.

### 3.1 `ALokiGameMode::SpawnPlayer` — thunk `0x534C070`

`.pdata` (union): `0x534C070 – 0x534C24E`, **extent 478 B**, seen in 70 dumps. **115 instructions.**
Page coverage `0x534C000` = **3877 / 4096 nonzero** (not coverage-blocked). Identical in both dumps.

```
0534c070  40 53                    push rbx
0534c072  55                       push rbp
0534c073  56                       push rsi
0534c074  57                       push rdi
0534c075  41 56                    push r14
0534c077  48 81 ec c0 00 00 00     sub  rsp, 0xc0
0534c07e  48 8b 05 03 e1 98 04     mov  rax, [rip + 0x498e103]     ; __security_cookie
0534c085  48 33 c4                 xor  rax, rsp
0534c088  48 89 84 24 b0 00 00 00  mov  [rsp + 0xb0], rax
0534c090  33 ff                    xor  edi, edi
...
0534c228  e8 ..                    call 0x0f7eb50        <-- IMPL
0534c23b  e8 ..                    call 0x751deb0        ; __security_check_cookie (fanin 353)
```

first32 (both images):
`40 53 55 56 57 41 56 48 81 ec c0 00 00 00 48 8b 05 03 e1 98 04 48 33 c4 48 89 84 24 b0 00 00 00`

Four `FFrame::Step` sequences are present (`0x12F3FC0` ×2, `0x1345FB0` ×4, `0x1345FE0` ×4,
`0x133E870` ×1) — consistent with the documented 4-parameter signature `(PS, Xf, StartSpot, bEnsure)`.

**IMPL `0x0F7EB50` = `33 c0 c3` = `xor eax, eax ; ret`** [M, both images] — i.e. `return nullptr`,
which is exactly right for a function returning `APawn*`.

> **This is CLAIM A's quoted byte string, found verbatim — at `0x0F7EB50`, not at `0x534C070`.**

### 3.2 `ALokiPlayerState::AuthSetSpawnTeamLeader` — thunk `0x5254180`

No `.pdata` entry in the union (leaf). Body is **7 instructions**; page `0x5254000` = 3898/4096.

```
05254180  48 8b 42 20              mov   rax, [rdx + 0x20]      ; FFrame.Code
05254184  45 33 c0                 xor   r8d, r8d
05254187  48 85 c0                 test  rax, rax
0525418a  41 0f 95 c0              setne r8b
0525418e  4c 03 c0                 add   r8, rax
05254191  4c 89 42 20              mov   [rdx + 0x20], r8       ; P_FINISH
05254195  e9 86 aa d2 fb           jmp   0x0f7ec20              <-- IMPL (tail)
```

**IMPL `0x0F7EC20` = `c2 00 00` = `ret 0`** [M, both images].

⚠ **This RVA is 91-way ICF-folded** — it is the registered native for **91 distinct names** [M]
(`AddAllAssetsToGraph`, `AddLokiPlayerCheats`, `AlignToTerrain`, `AuthAddPreSpawnedEffect`,
`AuthBeginGlideDive`, … ). **The address does not identify the function.** This is the shared
zero-parameter exec thunk for *every* native UFunction whose impl is the universal empty stub — which
is why the same `0x5254180` appears in the record under at least seven different function names
(`docs/fk13-live-run-2026-08-12.md:18,19,27`, `docs/fk6-cheat-impl-census.csv:119,138,166`,
`docs/fk6-cheat-surface-settled.md:395,733,807`). Quoting it as *"AuthSetSpawnTeamLeader's address"*
is the single most confusing line in the corpus and should always carry the fold multiplicity.

Note the fold direction is still *sound* as an inference: ICF folds only byte-identical code, and the
tail target is inside the folded bytes, so `thunk == 0x5254180` ⟹ `impl == 0x0F7EC20` ⟹ empty.

### 3.3 `ALokiTeamState_TeamOnly::SetDropLeader` — thunk `0x2C2CE30`

`.pdata` (union): `0x2C2CE30 – 0x2C2CEB5`, **extent 133 B**, seen in 70 dumps. **34 instructions.**
Page `0x2C2C000` = 3784/4096. Registered native for **23 names** (ICF-folded 1-object-param thunk).

```
02c2ce30  48 89 5c 24 08           mov  [rsp + 8], rbx
02c2ce35  48 89 74 24 18           mov  [rsp + 0x18], rsi
02c2ce3a  57                       push rdi
02c2ce3b  48 83 ec 20              sub  rsp, 0x20
02c2ce3f  33 ff                    xor  edi, edi
02c2ce41  48 8b da                 mov  rbx, rdx
02c2ce44  48 89 7c 24 38           mov  [rsp + 0x38], rdi
02c2ce49  48 8b f1                 mov  rsi, rcx
02c2ce4c  e8 6f 71 6c fe           call 0x12f3fc0                ; FFrame::Step (fanin 2735)
...
02c2cea0  e8 ..                    call 0x0f7ec20                <-- IMPL
```

**IMPL `0x0F7EC20` = `c2 00 00` = `ret 0`** [M, both images].

### 3.4 `ALokiDropPlane::OverridePlaneLocations` — thunk `0x53372A0`

`.pdata` (union): `0x53372A0 – 0x533738E`, **extent 238 B**, seen in 70 dumps. **53 instructions.**
Page `0x5337000` = 3846/4096. Registered native for exactly **1** name.

```
053372a0  48 89 5c 24 08           mov  [rsp + 8], rbx
053372a5  57                       push rdi
053372a6  48 81 ec 90 00 00 00     sub  rsp, 0x90
053372ad  48 8b da                 mov  rbx, rdx
053372b0  48 8b f9                 mov  rdi, rcx
053372b3  e8 38 86 00 fc           call 0x133f8f0                ; FFrame::Step (fanin 1443)
...
05337378  e8 ..                    call 0x0f7ec20                <-- IMPL
```

**IMPL `0x0F7EC20` = `c2 00 00` = `ret 0`** [M, both images].

### 3.5 Summary table — the row FK-1 should have had

| function | **exec thunk** (what CLAIM A printed) | thunk body [M] | **IMPL** (never printed) | impl bytes [M] |
|---|---|---|---|---|
| `ALokiGameMode::SpawnPlayer` | `0x534C070` | REAL, 478 B / 115 insn, security cookie | **`0x0F7EB50`** | `33 c0 c3` = `xor eax,eax; ret` |
| `ALokiPlayerState::AuthSetSpawnTeamLeader` | `0x5254180` ⚠ **91-way ICF** | REAL, 7 insn `P_FINISH; jmp` | **`0x0F7EC20`** | `c2 00 00` = `ret 0` |
| `ALokiTeamState_TeamOnly::SetDropLeader` | `0x2C2CE30` ⚠ **23-way ICF** | REAL, 133 B / 34 insn | **`0x0F7EC20`** | `c2 00 00` = `ret 0` |
| `ALokiDropPlane::OverridePlaneLocations` | `0x53372A0` | REAL, 238 B / 53 insn | **`0x0F7EC20`** | `c2 00 00` = `ret 0` |

Minor byte-level correction to CLAIM A: three of the four are `ret 0` (`c2 00 00`, `retn imm16=0`),
not bare `ret` (`c3`). Functionally identical; worth stating because `c3` is a *different* fold in
this image and the distinction matters when grading by byte pattern.

---

## 4. Controls

### 4.1 Negative controls — known folded stubs, must grade EMPTY

| RVA | bytes | verdict |
|---|---|---|
| `0x00F7EC20` | `c2 00 00` | **EMPTY (`ret 0`)** [M] — the universal empty stub named in the brief |
| `0x00F7EB60` | `32 c0 c3` | **EMPTY (`xor al,al; ret`)** [M] — returns false |
| `0x00F7EB50` | `33 c0 c3` | **EMPTY (`xor eax,eax; ret`)** [M] — returns null/0 |

None of the three is itself a registered native (0 names point at them directly) — they are only ever
*impl targets*, which is what a folded stub should look like.

### 4.2 Positive controls — known real bodies, must grade REAL and must yield a real impl

| function | thunk | thunk body [M] | impl(s) [M] |
|---|---|---|---|
| `UKismetSystemLibrary::ExecuteConsoleCommand` | `0x395D790` (469 B / 123 insn) | REAL | `0x3EDBE70` **REAL 259 B / 70 insn**, `0x10F5290` REAL 179 B / 40 insn, … |
| `APlayerController::LocalTravel` | `0x3C64600` (157 B / 40 insn) | REAL | impl inlined — no non-helper target (see caveat) |

`ExecuteConsoleCommand` is the decisive positive control: **same method, same images, same code path,
and it returns a large real implementation.** The method therefore separates real from empty; the
four EMPTY verdicts in §3 are not a blanket artifact of the grader.

⚠ `LocalTravel` is a **weak** control and is reported as such: its thunk is real but its only
remaining call is `0x0FF9310` (fanin 4,381, a shared helper), so the method returns "no impl" rather
than a grade. It neither supports nor undermines the verdict — do not cite it either way.

### 4.3 Base-rate control — is "empty impl" informative at all?

If most native UFunctions folded to `0x0F7EC20`, then "these four are empty" would say nothing about
server-code stripping. Measured over all 31,723 registered `.text` pointers [M]:

| bucket | count |
|---|---|
| `Z_Construct_UFunction_*` singletons (excluded — not exec thunks) | 15,820 |
| exec thunks analysed | 10,110 |
| — thunk page all-zero → **COVERAGE-BLOCKED** (no claim made) | 5,793 |
| — impl **REAL** | 6,591 |
| — impl **EMPTY** | **78** |
| — impl coverage-blocked / inlined | 932 / 2,509 |

> **Empty-impl base rate = 78 / 6,669 = 1.2 %** [M].

Fold popularity: `0x0F7EC20` **58** thunks · `0x0F7EB60` 15 · `0x0F7EB50` 5.

★ **`58` reproduces FK-1's own "58 callers of the folded stub" exactly** — independent corroboration
that `scratchpad/stub_census.py` (not committed; absent from the tree and from git history) *was*
resolving impls correctly. Its per-row attribution of the counts was shuffled (FK-1 prints 58 against
`SpawnPlayer`, whose fold is the 5-member `0x0F7EB50`), but the census numbers themselves are real
quantities from a working instrument.

⚠ Do not confuse this `58` with the *"165,789 slots"* figure for `0x00F7EC20` in the brief — that is a
vtable-slot denominator, a different population. Both can be true.

---

## 5. How each side resolved the symbol → address

This was the most likely failure mode on either side, so it was measured twice, two ways.

1. **`FNameNativePtrPair` scan** (`{const ANSICHAR* NameUTF8; FNativeFuncPtr Ptr;}`, stride 16, name
   in `.rdata`, pointer in `.text`): 15,752 distinct names → 31,723 distinct pointers.
   `SpawnPlayer → {0x5340D90, 0x534C070}`, `AuthSetSpawnTeamLeader → {0x5254180, 0x542F3F0}`,
   `SetDropLeader → {0x2C2CE30}`, `OverridePlaneLocations → {0x5332320, 0x53372A0}` [M].
   The second member of each pair is the `Z_Construct_UFunction_*` singleton (artifact **S115-c**),
   disambiguated by calling convention: the exec thunks read `[rdx+0x20]` (`FFrame::Code`) and call
   `FFrame::Step`; the singletons call `ConstructUFunction @0x135F5E0` and return a `UFunction*`.
   ⇒ **the four RVAs CLAIM A printed are the genuine `execFoo` thunks** [M].

2. **Independent second instrument — a static 3-field `.data` record** carrying
   `{NameUTF8, execThunk, implPtr}`, one per function [M, both images]:

| record RVA | name string | +8 (exec thunk) | +16 (impl) | impl bytes |
|---|---|---|---|---|
| `0x9BDB230` | `"SpawnPlayer"` | `0x534C070` ✓ | `0x0F7EB50` | `33 c0 c3` |
| `0x9BD4B08` | `"OverridePlaneLocations"` | `0x53372A0` ✓ | `0x0F7EC20` | `c2 00 00` |
| `0x9C14FA0` | `"AuthSetSpawnTeamLeader"` | `0x5254180` ✓ | `0x0F7EC20` | `c2 00 00` |
| `0x9C29F50` | `"SetDropLeader"` | `0x2C2CE30` ✓ | `0x0F7EC20` | `c2 00 00` |

   The `+16` column **matches the impl recovered by disassembling the thunk, for all four, in both
   dumps** — two instruments that fail differently, agreeing. (`0x9BDB230` is the same slot
   `docs/strxref-open-questions.md:144` already recorded as *"FNameNativePtrPair slot 0x09BDB230 →
   exec thunk 0x534C070"* — that entry was correct.)

3. Owner-class attribution is independently corroborated by `tools/re/out/uht_funcflags_tuthero.csv`,
   which carries all four as `Final|Native|Public|…|BlueprintCallable` rows under exactly the classes
   CLAIM A names (`ALokiGameMode,SpawnPlayer`, `ALokiPlayerState,AuthSetSpawnTeamLeader`,
   `ALokiTeamState_TeamOnly,SetDropLeader`, `ALokiDropPlane,OverridePlaneLocations`) [M].

**Conclusion: neither side resolved the wrong address.** CLAIM A's addresses are right, CLAIM A's
bytes are right, and they belong to two different columns.

---

## 6. Which prior claim is wrong, and why

**`docs/fk1-angelscript-settled.md:167-172` is defensible as written.** Its table header is literally
`| function | exec thunk | body |` — column 2 *is* labelled "exec thunk" and column 3 *is* the body of
the implementation. The only defect is that **the impl's address is never printed**, so column 3's
bytes are unverifiable from column 2 and look like a description of it. Fix = add an IMPL column.

**`CLAUDE.md:291-295` is wrong.** Compressing the table into prose dropped the "exec thunk" header
and replaced it with an equals sign:

> ``ALokiGameMode::SpawnPlayer `0x534C070` = `xor eax,eax; ret` ``

That sentence asserts those bytes are **at** that RVA. They are not. **The false statement was
manufactured in the digest, not in the source document** — a compression that silently merged two
address spaces into one `=`.

**`docs/fk13-console-exec-settled.md` §6.1 is right on the measurement and wrong on the inference.**
Its bytes are correct and its decision to flag rather than resolve was correct. Only this sentence
falls: *"One of the two measurements is wrong — most likely an RVA/VA or image-base confusion on one
side."* Neither measurement is wrong, and there is no base confusion anywhere [M]. Its §6.1 header
*"An unrelated discrepancy"* is also right — it is unrelated to FK-13's conclusions, which stand.

### What does NOT need re-opening

- **FK-1's "the real wall"** — stands. Four server-authority C++ implementations are empty, at a
  1.2 % base rate. The `WITH_SERVER_CODE`-stripped hypothesis remains [I] (untested here; nothing
  measured contradicts it).
- **FK-1's closure of `AvatarActor = NULL`** — stands. It rests on `SpawnPlayer` having no body, and
  `SpawnPlayer`'s body is `return nullptr` [M].
- **FK-1's script-door synthesis** — untouched by this session.
- **FK-13's conclusions** — untouched. `0x395D790` `ExecuteConsoleCommand` is confirmed here as a
  large real function, independently re-measured (§4.2).

### What this changes

Nothing operational. This is a **documentation-integrity fix**, not a new capability or a new
blocker. Priced honestly: the conflict cost one offline session and closed cleanly.

---

## 7. Proposed `CLAUDE.md` correction — NOT APPLIED, left to the user

Replace `CLAUDE.md:291-295`. The substance is unchanged; only the addresses are disambiguated.

```markdown
- ★★★ **THE REAL WALL: four server-authority C++ functions have EMPTY IMPLEMENTATIONS in the
  shipping client** (byte-level, coverage-guarded, controls; re-verified in BOTH dumps S115 —
  `docs/fk1-stub-claim-recheck.md`). ⚠ The exec THUNK and the IMPL are different addresses; the
  thunks are real code, the impls are folded stubs:
  `ALokiGameMode::SpawnPlayer` thunk `0x534C070` → impl **`0x0F7EB50` = `xor eax,eax; ret`** ·
  `ALokiPlayerState::AuthSetSpawnTeamLeader` thunk `0x5254180` (⚠ 91-way ICF-folded, NON-IDENTIFYING)
  → impl **`0x0F7EC20` = `ret 0`** ·
  `ALokiTeamState_TeamOnly::SetDropLeader` thunk `0x2C2CE30` (⚠ 23-way ICF) → impl **`0x0F7EC20`** ·
  `ALokiDropPlane::OverridePlaneLocations` thunk `0x53372A0` → impl **`0x0F7EC20`**.
  Empty-impl base rate in this image is **1.2 % (78/6,669)**, so this is informative, not ambient.
  Likely `WITH_SERVER_CODE`-stripped [I]. **This explains ~7 failed spawn attempts across S68/S74 and
  CLOSES `AvatarActor = NULL`:** the design routes the whole GAS bind through `SpawnPlayer`
  (disassembly-verified in `FFA/LokiRespawnComponent::Respawn`, which null-checks the character but
  NOT the ASC) and the client's `SpawnPlayer` returns nullptr.
```

Also worth adding to `docs/fk1-angelscript-settled.md:167` — an IMPL column and this banner:

```markdown
> ⚠ **Column 2 is the exec THUNK (real code). The bytes in column 3 are the IMPL, at a different
> RVA.** Re-verified in both dumps, S115 — see `docs/fk1-stub-claim-recheck.md`. The finding stands;
> only the address bookkeeping was ambiguous.
```

And a one-line resolution stamp on `docs/fk13-console-exec-settled.md` §6.1 pointing here.

---

## 8. Method rules this session earned

1. **Never print a byte string next to an address it did not come from.** If a table has a thunk
   column and a body column, it needs a third column: the body's own address. This one omission cost
   a cross-session contradiction that looked like a hard factual conflict.
2. **Always print ICF fold multiplicity next to a folded RVA.** `0x5254180` is 91 functions.
   An address quoted without its multiplicity is an address that will be mis-attributed later — it
   already has been, at least seven times in this corpus.
3. **A digest is an instrument.** `CLAUDE.md` compressed a correct table into a false sentence. Treat
   summarisation as a measurement step that can introduce artifacts, and re-derive from the source doc
   before treating a `CLAUDE.md` line as measured.
4. **`.pdata` is absent from these dumps** (100 % zero, both). Any tool reading extents from the
   image itself is silently broken; use `tools/strxref/index/pdata_union.csv`. Two of my own passes
   died on this.
5. **`FClassFunctionLinkInfo` and `FNameNativePtrPair` have opposite field order.** A stride-16 scan
   for one will phase-shift onto the other and hand you a plausible wrong address with a plausible
   wrong body. Discriminate by calling convention (`[rdx+0x20]` + `FFrame::Step` = exec thunk;
   `call 0x135F5E0` = `Z_Construct_UFunction_*`).
6. **Do not adjudicate a claim with a tool that has already ingested it.**
   `tools/re/exec_chain_grade.py:50` hardcodes `0x05254180: 'ret'` from CLAIM A. It should be updated
   to `'P_FINISH; jmp 0x0F7EC20 (91-way ICF thunk; impl 0x0F7EC20 = ret 0)'`.

---

## 9. Artifacts

| Path | What |
|---|---|
| `scratchpad/stub_recheck.py` | pass 1 — raw bytes + disasm, `.pdata` from data dir (**artifact S115-a**) |
| `scratchpad/stub_recheck2.py` | pass 2 — `.pdata` from section (**artifact S115-b**) |
| `scratchpad/stub_recheck3.py` | pass 3 — union `.pdata`, coverage guard, `FNameNativePtrPair` both directions |
| `scratchpad/stub_recheck4.py` | pass 4 — empirical helper histogram, thunk → impl resolution |
| `scratchpad/stub_recheck5.py` | pass 5 — class attribution (**artifact S115-c**, caught by control) |
| `scratchpad/stub_recheck6.py` | pass 6 — empty-impl base rate over all 31,723 registered pointers |

Scripts are in this session's scratchpad; promote any that are worth keeping into `tools/re/`.
Nothing was written to `dumps/`, `CLAUDE.md`, or any pre-existing doc.
