# ADVERSARIAL VERIFICATION — L7 `ULokiRideableComponent::AuthPlayerEnterWorld`

Target: `scratchpad/s132/lanes/L7-enterworld-guards.md`.
Method: offline, `dumps/merged4.dump.exe` (ImageBase `0x7FF6AF000000`, file offset == RVA), independent
capstone passes written from scratch, an independent `UNWIND_INFO` parser, an independent `.data`
record sweep, `tools/asdump/out/binds_members.csv`, `tools/strxref/index/pdata_union.csv`. All address
arithmetic by `python -c`. Zero launches, zero injections.

**Headline: 21 load-bearing claims CONFIRMED, most re-derived by a different route. 5 items are
REFUTED or UNSUPPORTED** — one a wrong cited address that would mislead a successor, two grade
upgrades across an inference step, one an invalid argument for a true conclusion, one a verdict stated
unconditionally that an unexamined callee does not license.
No claim that changes the operational bottom line was refuted: `AuthPlayerEnterWorld` really is
foreclosed as a *direct-write* dismount route.

---

## A. REFUTED

### A1. `.data 0x9BE64C0` and `.data 0x9BE4978` are NOT the record addresses — off by `0x10`

Section 4 and Section 8 print:

    .data 0x9BE64C0 = {"IsValidPositionOnNavmesh", 0x537B450, 0x5666A00}
    .data 0x9BE4978 = {"FindNearbyPointOnNavMesh", 0x5371BE0, 0x5656550}

Measured at those addresses:

    0x09BE64C0 = 0x00007FF6B4666A00   (= rva 0x5666A00, the IMPL)
    0x09BE64C8 = 0x0000000000000000
    0x09BE64D0 = 0x0000000000000000
    0x09BE4978 = 0x00007FF6B4656550   (= rva 0x5656550, the IMPL)
    0x09BE4980 = 0x0000000000000000

The records actually begin **0x10 lower**:

    0x09BE64B0 = ptr -> rva 0x8974148  "IsValidPositionOnNavmesh"
    0x09BE64B8 = 0x00007FF6B437B450   thunk 0x537B450
    0x09BE64C0 = 0x00007FF6B4666A00   impl  0x5666A00

    0x09BE4968 = ptr -> rva 0x8978880  "FindNearbyPointOnNavMesh"
    0x09BE4970 = 0x00007FF6B4371BE0   thunk 0x5371BE0
    0x09BE4978 = 0x00007FF6B4656550   impl  0x5656550

**Correction: the record bases are `0x9BE64B0` and `0x9BE4968`.** The *content* of both records is
confirmed exactly as stated — only the cited address is wrong. This is the S115-d house rule ("never
print a byte string next to an address it did not come from") re-committed: a successor who reads
`0x9BE64C0` as `{name,thunk,impl}` gets `name = NULL` and concludes the record is absent. The other
record citations are exact (`0x9C1E570`, `0x9C1E8D0`, `0x9BFBC70` all reproduce as record bases), so
this is a two-instance slip, not a systematic offset.

### A2. "positive control in the same table **two records later**" — one record later

Record stride is `0x48`, measured over 18 consecutive rows: `0x9C1E570` (`AuthPlayerEnterWorld`)
to `0x9C1E5B8` (`AuthPlayerEnterWorldAttachedToRidable`) is `0x48` = **one** record. Cosmetic; the
control itself is valid and the wall thunk/impl match the handoff.

---

## B. UNSUPPORTED (true, or partly true, but not established by the evidence given)

### B1. "All four bails are silent, **and provably so**: the first `call` instruction anywhere in the function is at `0x55CCF1A`, which is after the last bail, so no log line is even possible on a bail path."

**Conclusion CONFIRMED. Argument INVALID.** It is an *address-order* argument, but both bail targets
sit at **higher** addresses than `0x55CCF1A` and are reached by forward jumps. The `0x55CD4E7` bail
block contains a call:

    0x055CD4E7  mov  rcx, [rbp + 0xa0]
    0x055CD4EE  xor  rcx, rsp
    0x055CD4F1  call 0x751deb0          <-- A CALL, ON THE BAIL PATH OF G2/G3/G4
    0x055CD4F6  add  rsp, 0x270 ; pops ; 0x055CD505 ret

The report own Section 4 call table lists `0x55CD4F1 -> 0x751DEB0`, so the document contradicts itself.

**Correct argument, re-derived:** the only code reachable on a bail path is `0x55CD4E7..0x55CD505`
plus the bare `ret` at `0x55CD505`; the sole call in it is `0x751DEB0`, which I disassembled and
confirmed is `__security_check_cookie`:

    0x0751DEB0  cmp rcx, qword ptr [rip + 0x27bc2d1]
    0x0751DEB7  jne 0x751dec9
    0x0751DEB9  rol rcx, 0x10
    0x0751DEBD  test cx, 0xffff
    0x0751DEC2  jne 0x751dec5
    0x0751DEC4  ret

It does not log. So all four bails are silent — **by inspection of the bail blocks, not by
instruction ordering.**

### B2. "Exactly one (`0x55CCF22`) **is** the round-game-mode getter" — [I] presented as [M]

`0xF7EB50` is a fold with ~27,217 call sites, and the report itself says the address "identifies
nothing". What is [M] at `0x55CCF22`: `rcx` is the `UWorld*` returned by `0x35AFC40`, and the result
is **not tested** (next insn `lea rcx,[r12+0x470]`, stashed to `[rsp+0x50]` and `rbx`, no `test`/`jcc`)
— I re-derived both. The *identity* is an analogy to the wall, where the error string names it. I
confirmed the wall site is `0x55CD572`, same fold, same `GetWorld` predecessor, but **gated**:

    0x055CD56A  call 0x35afc40
    0x055CD56F  mov  rcx, rax
    0x055CD572  call 0xf7eb50
    0x055CD577  test rax, rax
    0x055CD57A  je   0x55cd7b2

That structural contrast is the entire basis for the naming. Grade it **[I, strong]**.

### B3. "the only reflected writers of `PlayersInside` do nothing in this client ... a poke is the only route, by construction" — fold grading is [M]; the implication is [I] presented as [M]

My independent sweep of `0x9C1E300..0x9C1EC00` reproduces all 18 rows of Section 4a exactly, including
`AuthAddPlayer` / `AuthRemovePlayer` / `AuthSetCanJump` / `AuthPlayerEnterWorldNew` = `impl 0x0F7EC20`.
But the record-table instrument grades **bodies it cannot read**. Nothing measures that
`AuthAddPlayer` / `AuthRemovePlayer` would have written `PlayersInside` — that attribution comes from
the *names*, and `AuthPlayerEnterWorldNew` (also a fold) has an equally suggestive name. "**The only**
reflected writers" is a universal quantifier this instrument cannot establish at all.

**What is empirically supportable, and I strengthened it:** a **16-alignment** linear sweep of
`0x55CC000..0x55E4000` (not just page-aligned, so the misalignment caveat is largely removed) finds
**exactly one** write site to displacement `0x118/0x11C/0x120/0x128/0x12C` with a non-stack base —
`0x55E3D94`, the stride-24 false positive — and `CanExit` (`0x525C240`), `MulticastOnPlayerEntered`
(`0x5453780`) and `MulticastOnPlayerExited` (`0x5453800`), which sit **outside** that range and were
therefore not covered by the report sweep, reference none of those displacements. Pages `0x55D1000` and
`0x55D2000` are confirmed all-zero, so the negative stays [I, strong].

### B4. VERDICT "[M] FORECLOSED ... a poke that produced a round game mode would still change nothing" / "It will not move the hero. Pre-register that." — UNSUPPORTED at [M]; should be [I]

Both halves the report measures are CONFIRMED by me (C7, C9, C10). What is **not** established is the
categorical downstream claim. On **both** passing paths, unconditionally, the function calls:

    0x055CD4CC  mov rdx, r12          ; PlayerState
    0x055CD4CF  mov rcx, rdi          ; this
    0x055CD4D2  call 0x54537C0        ; MulticastOnPlayerEnteredWorld -- graded REAL by the report

and `0x54537C0` is a reflected dispatch:

    0x054537D5  mov  rdx, [rip+0x4bd721c]   ; -> FName record 0xA02A9F8
    0x054537DC  mov  rbx, [rax + 0x270]     ; ProcessEvent slot
    0x054537E3  call 0x1344150              ; FindFunction
    0x054537ED  mov  rdx, rax
    0x054537E8  lea  r8, [rsp + 0x30]       ; &params{PlayerState}
    0x054537F3  call rbx                    ; ProcessEvent

Its exec thunk `0x3BCD5B0` ends in `call qword ptr [rax + 0x4c0]` — a **virtual `_Implementation`**
that the report never located or graded, and which receives the PlayerState. Additionally `0x4467B90`
is COVERAGE-BLOCKED (all-zero page in **every** dump on disk), though it is only reachable when
`EffectClass != null`.

**Correction:** "FORECLOSED **as a direct-write route**" is [M] — the function writes no transform, and
the two calls that receive `(PlayerState, &FTransform)` are stripped folds. "Nothing downstream moves
the hero" is **[I], untested**: it rests on an un-graded `ProcessEvent` dispatch that has never
executed on this client. The pre-registration should read: *no direct transform write is possible; any
movement would have to come out of `MulticastOnPlayerEnteredWorld`, which is unexamined.*

### B5. Section 6 "Risk assessment" is incomplete — an omission, not a false claim

It argues only the `TArray` foreign-pointer / free hazard away, correctly. It does not mention that
past G4 the function makes an **unconditional** indirect dispatch that has *never executed* on this
client:

    0x055CCF27  lea  rcx, [r12 + 0x470]     ; &sub-object inside the PlayerState
    0x055CCF34  mov  rdx, [rcx]             ; treated as a vptr
    0x055CCF3A  call qword ptr [rdx + 0x10] ; virtual slot 2

The report itself grades `[PlayerState+0x470]` as **[I]** ("no name was recovered"). Every prior live
call bailed at G3, so `0x55CCF3A` onward is untested code running on the game thread. The `lea` shape
implies an *inline* sub-object, so it is probably safe — but "probably" belongs in a risk section.

Also: the "REAL" grades on `0x5666A00` and `0x5656550` are **[I]**, not [M]. Both pages are
undecrypted, and "not one of the *five known* folds" is not proof of a real body — CLAUDE.md records
that the fifth fold (`0x00FC6CF0`) was found late, so the fold table is not closed.

---

## C. CONFIRMED (re-derived independently)

| # | claim | how I re-derived it | verdict |
|---|---|---|---|
| C1 | `.data 0x9C1E570 = {"AuthPlayerEnterWorld", 0x54561D0, 0x55CCE70}` | own `.data` sweep `0x9C1E300..0x9C1EC00`; name string at rva `0x8A4E290` | CONFIRMED [M] |
| C2 | extent `0x55CCE70..0x55CD506` = `0x696` = 1686 B, **six** chained `.pdata` rows, next root is the wall | own `UNWIND_INFO` parser: root flags `0x3` (handler `0x751DDB8`), then five rows with `flags=0x4` and every chain target reproduced; `0x55CD510` has `flags=0x0` | CONFIRMED [M] |
| C3 | coverage: pages nonzero 3689 / 3703; 172 zero bytes in extent; 353 instructions covering 1686/1686, ending on `ret` at `0x55CD505`; junk `ad c3 ec 38` after | own capstone linear decode — **every number reproduced to the digit** | CONFIRMED [M] |
| C4 | signature, two disjoint instruments | thunk extent `0x54561D0..0x5456371` from pdata contains `0x5456357 e8 14 6b 17 00`; machine check `0x545635C + 0x176B14 = 0x55CCE70`; `binds_members.csv:44931` verbatim, including both defaults | CONFIRMED [M] |
| C5 | G1-G4 transcription | byte-for-byte identical to my own disassembly at all four sites | CONFIRMED [M] |
| C6 | 32 branches; only 4 leave the extent; `0x55CD4E7 <- 0x55CCEBC / 0x55CCED7 / 0x55CCEEE`, `0x55CD505 <- 0x55CCE73` | own capstone branch enumeration | CONFIRMED [M] |
| C7 | THREE `0xF7EB50` at `0x55CCF22` / `0x55CD405` / `0x55CD4C7`; 26 direct / 5 indirect / **14** distinct targets | own uncapped capstone call sweep — exact match, target for target | CONFIRMED [M] |
| C8 | `0x55CCF22` result NOT gated | `lea rcx,[r12+0x470]` next; `mov [rsp+0x50],rax`; `mov rbx,rax`; no `test`/`jcc` | CONFIRMED [M] |
| C9 | payload arg shape at both sites: `rcx` = stashed null, `rdx` = `r12` = PlayerState, `r8` = &FTransform (96 B at `rbp+0x40`), `r9` = 0, `[rsp+0x20]` = 0 | traced `xor r9d,r9d` at `0x55CD3A3` and `xor r14d,r14d` at `0x55CD0FA` on the reposition path; `xor r9d,r9d` / `mov byte [rsp+0x20],0` at `0x55CD47A` / `0x55CD47D` on the default path; `mov rbx,[rsp+0x50]` at `0x55CD063` restores the null | CONFIRMED [M] |
| C10 | **zero writes to any actor/component field**; the only non-stack writes are two `lock xadd` refcounts | full enumeration of every memory operand with a non-`rsp`/`rbp`/`rip` base across all 353 instructions: **46 reads, 2 writes** (`lock xadd [rbx+8]`, `lock xadd [rbx+0xc]`) | CONFIRMED [M] |
| C11 | positive control is NOT degenerate | the same pass on the wall `0x55CD510..0x55CD7FA` finds **7** non-stack writes, including `0x55CD730 movss [rsi+0x1c10]`, `0x55CD742 mov [r14+0x138]`, `0x55CD767 mov [rax+rbx*8]` | CONFIRMED — control valid |
| C12 | Section 5 single `+0x128` write at `0x55E3D94` is a stride-24 false positive in `RequestMoveTowardAlive` | 16-alignment sweep gives one hit; element store is `mov [rax+rcx*8], rbx` with `rcx = rbp*3`; it calls `0xF98B40` (the 24-byte ResizeGrow); `.data 0x9BFBC70 = {"RequestMoveTowardAlive", 0x53C3870, 0x55E3D70}` | CONFIRMED [M] |
| C13 | `0x4467B90` COVERAGE-BLOCKED "in all six dumps" | zero in **all 30** `*.dump.exe` on disk, as are `0x5666000` and `0x5656000` — understated, not overstated | CONFIRMED (stronger) |
| C14 | `0x4445BC0` = `UGameplayEffect::StaticClass()` | rip-relative targets decode to `u"/Script/GameplayAbilities"` (`0x8398F78`) and `u"GameplayEffect"` (`0x83CA77A`) | CONFIRMED [M] |
| C15 | `0x35AFC40` = `push rbx; sub rsp,0x20; mov rcx,[rcx+0xB8]` | byte-for-byte | CONFIRMED (the name "GetWorld slow path" is [I] from shape; not load-bearing) |
| C16 | `0x1225F20` = `mov rax,[rcx]; jmp [rax+0x428]` | byte-for-byte | CONFIRMED [M] |
| C17 | `[rbp+0x1c0] == entry_rsp+0x28 == 5th arg slot` = `bRepositionPlayer` | machine: `0x28+0x170 = 0x198`, `0x1C0-0x198 = 0x28`; corroborated by the thunk `mov byte [rsp+0x20], bpl` at `0x545634F` | CONFIRMED [M] |
| C18 | log line `LokiRideableComponent.cpp:171` | record `0x8B1CC98` = {msg `0x8B1CCC0`, file `0x8B1CDD0` = `C:\TheoryCraft\build-staging\Loki\Source\Loki\DropPhase\LokiRideableComponent.cpp`, line `0xAB` = **171**, verbosity **3** = Warning} | CONFIRMED [M] |
| C19 | offsets `bCanExit@0x118`, `PlayersInsideCount@0x11C`, `PlayersInside{0x120,0x128,0x12C}` | `ContainsPlayer 0x55D0270` is a byte-twin of G3+G4; `HasEverContainedPlayer 0x55DCAA0` opens with the same two loads; plus a **new** instrument the report did not use, the `binds_members.csv` property table | CONFIRMED [M] |
| C20 | ordering trap: `HasEverContainedPlayer` searches `PlayersInside` first, and the wall gates on it **before** its getter | `0x55CD54E call 0x55DCAA0` / `0x55CD553 test al,al` / `0x55CD555 jne 0x55CD77B`, versus the getter at `0x55CD572` | CONFIRMED [M] |
| C21 | `0x0F988D0` is the ResizeGrow the wall calls for a stride-8 array; the 24-byte one is `0x0F98B40` | `0x55CD754 lea rcx,[r14+0x130]` / `0x55CD75B call 0xf988d0` / `0x55CD767 mov [rax+rbx*8], rdi` | CONFIRMED [M] for the wall; the transfer to `PlayersInside` is [I], but **stronger than argued** — see D1 |

Fold counts across the family also reproduce exactly, including the Section 14.1 correction:

    AuthPlayerEnterWorld                  0xF7EB50 x3 [0x55ccf22, 0x55cd405, 0x55cd4c7]  0xF7EC20 x0
    AuthPlayerEnterWorldAttachedToRidable 0xF7EB50 x1 [0x55cd572]                        0xF7EC20 x1 [0x55cd7e4]
    AuthPlayerPreSpawnOnAddToPlane        0xF7EB50 x1 [0x55cd842]                        0xF7EC20 x2 [0x55cd91c, 0x55cd9cc]
    AuthPlayerDetachPlayerFromRidable     0xF7EB50 x0                                    0xF7EC20 x2 [0x55ccd5b, 0x55cce4e]

---

## D. Free corrections and strengthenings the report could adopt

**D1. The `ResizeGrow` argument is available at a higher grade than "same stride".**
`tools/asdump/out/binds_members.csv` carries the class property table, which the report did not use:

    property 6  int                      PlayersInsideCount
    property 7  TArray<ALokiPlayerState> PlayersInside
    property 8  TArray<ALokiPlayerState> PlayersAttached
    property 9  TSet<ALokiPlayerState>   PlayersThatExited

`PlayersInside` and `PlayersAttached` have the **identical declared element type**, not merely the same
stride, so they are the same `TArray<T>` instantiation by construction and `0x0F988D0` is the right
helper on far better evidence than a stride coincidence. The same table independently corroborates
(a) the stride-8 reading of G3/G4, (b) `OnPlayersInsideCountChanged` as a real delegate property — a
second instrument for the S131 Section 13 correction — and (c) `PlayersThatExited` being a `TSet`,
matching the "falls through to a pointer-hash TSet lookup" reading of `HasEverContainedPlayer`.

**D2. The `cpp:171` receipt is live at *default* verbosity**, which is worth stating because it is the
whole point of the instrument arm. The gate is:

    0x055CD2D2  cmp byte ptr [rip + 0x475ba1f], 3   ; -> FLogCategory 0x9D28CF8
    0x055CD2D9  jb  0x55cd2ee

and the category bytes at `0x9D28CF8` read `05 00 05 07`, i.e. (this build layout)
`Verbosity=5, DebugBreakOnLog=0, DefaultVerbosity=5, CompileTimeVerbosity=7`. `5 >= 3`, so the Warning
emits with **no ini change**. The report said "real, unstripped" but never showed the gate clears.

**D3. Methodological note for anyone re-running the write scan.** capstone `op.access & CS_AC_WRITE`
**misses SSE stores** — it does not flag `movups xmmword ptr [rax], xmm1` in the wall, while a
mnemonic-based pass does; conversely a mnemonic-based pass misses `lock xadd` unless the `lock` prefix
is stripped first. Neither method alone is complete. I ran both, plus a full enumeration of *every*
non-stack memory operand (48 in this function: 46 reads, 2 writes), which is the only form that cannot
silently under-report. The report conclusion survives all three.

---

## E. Bottom line

The operational conclusion stands and I could not break it: `AuthPlayerEnterWorld` cannot itself
reposition anything (46 reads, 2 refcount writes, zero transform writes, positive control valid), the
`PlayersInside` membership requirement is real and every bail is silent, and the two calls that receive
`(PlayerState, &FTransform)` are stripped folds. What needs fixing is **grade discipline** on four
statements (B1-B4), **two wrong `.data` addresses** (A1), and a **missing risk item** (B5).
