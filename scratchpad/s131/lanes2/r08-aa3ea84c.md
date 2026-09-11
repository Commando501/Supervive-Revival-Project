## VERDICT — 3 re-derived: **3 CONFIRMED, 0 refuted at the core**; 6 secondary claims corrected, 1 actionable recommendation **REFUTED** (it would crash).

All work offline against `dumps/merged4.dump.exe` (ImageBase `0x7FF6AF000000`, machine-read from the PE header) and `dumps/s131-rideable-live` (single-state, for the `.data` record table). Every VA→RVA conversion below was done by subtracting the header-read ImageBase in Python, never by hand.

---

## A. THE THREE LOAD-BEARING CLAIMS, RE-DERIVED

### A1. "Downstream of the wall: 11 call sites / 10 distinct targets, ZERO stripped folds; the game-mode pointer is DEAD after the two gates." → **CONFIRMED [M]**

Disassembled `0x55CD510..0x55CD7FA` in merged4. Call targets machine-decoded from the `E8` rel32 bytes:

| site | target | fold? |
|---|---|---|
| `0x55CD54E` | `0x55DCAA0` | no |
| `0x55CD56A` | `0x35AFC40` | no |
| **`0x55CD572`** | **`0x0F7EB50`** | **THE WALL** |
| `0x55CD583` | `0x55C7DD0` | no |
| `0x55CD5C6` | `0x56BE0D0` | no |
| `0x55CD5DA` | `0x54F8DC0` | no |
| `0x55CD614` | `0x20B9EA0` | no |
| `0x55CD654` | `0x10A50C0` | no |
| `0x55CD703` | `0x56680F0` | no |
| `0x55CD70D`,`0x55CD723` | `0x339A550` | no |
| `0x55CD719` | `0x55C1B20` | no |
| `0x55CD72B` | `0x37D9D40` | no |
| `0x55CD75B` | `0x0F988D0` | no |

Post-wall: **11 call sites, 10 distinct targets** — exactly as reported. None equals `0xF7EC20 / 0xF7EB50 / 0xF7EB60 / 0xB9E1F0`. 11 of the 12 targets' first bytes are non-zero in merged4 (the 12th is the declared coverage caveat, §A1b).

**Deadness is structural and I re-derived it:** the fold's return in `rax` is (a) never stored to memory between `0x55CD577` and `0x55CD583`, (b) copied only into `rcx` (volatile), and (c) `rax` is overwritten by `call 0x55C7DD0`'s return. From `0x55CD590` onward every operand is `rbx` (`&Location`), `rdi` (PlayerState), `rsi` (hero, from `0x55CD5CB`), `r14` (this). **CONFIRMED.**

I additionally closed the one hole the report left: **`0x55C7DD0` is provably side-effect-free w.r.t. the pointer.** Its body is `mov rbx,rcx ; call 0x5453580 ; mov rdi,[rbx+0x18] ; …` — a class-chain walk. The class name is `LokiRoundGameMode`, read as **UTF-16LE at `.rdata 0x8A4F332`** (rip-rel `0x54535CD + 0x35FBD65`, machine-computed). Same shape for `0x54F8DC0` → `0x5395720` → `LokiHeroCharacter` at `.rdata 0x899A832`. So it is `IsA<>`, not a registration call.

**Fold census one level deeper** (chained `.pdata` extents from `tools/strxref/index/pdata_union.csv`, unioned by machine):
`0x55C7DD0` 125 B / 0 folds · `0x56BE0D0` 53 B / 0 · `0x54F8DC0` 125 B / 0 · `0x20B9EA0` 149 B / 0 · `0x10A50C0` 621 B / 0 · `0x339A550` 484 B / 0 · `0x37D9D40` 65 B / 0 · `0x0F988D0` 149 B / 0 · `0x339A7A0` 429 B / 0 · **`0x55C1B20` 495 B / 2 folds at `0x55C1B6D` and `0x55C1CD9`** — both are `0xFAC920` (build FString) → `0xF7EC20` → `0xFF9310` (free) triads inside the null-character and NaN-location error branches. Off the success path. **The report's numbers reproduce byte-for-byte.**

### A1b. The one honest gap, re-verified
`0x56680F0` (`LokiTeleportActor`) — I enumerated **27 PE images** on disk with a `.text` section (`dumps/*.dump.exe` + `dumps/*/SUPERVIVE-Win64-Shipping.dump.exe`). Its page is **all-zero in 27/27**, and its exec thunk page `0x537B000` is **0/27**. So its body is **COVERAGE-BLOCKED, not clean** — its REAL grade rests solely on the record table. The report said this; I confirm it and confirm the report did not restate blocked as absent.

**And the record-table method's positive control reproduces exactly.** `LokiTeleportActor` = rec `0x9BE64F0` {name, thunk `0x537B570`, impl `0x56680F0`}, multiplicity 1 in `byimpl`. Its contiguous `0x48`-stride run is **154 records** (unit: `{name,thunk,impl}` triples), of which **exactly 7 grade EMPTY** — `IsEditorPreviewActor` (`0xF7EB60`), `RespawnTeamInRandomRadiusAsync`, and all five `ServerDrawDebug*` (`0xF7EC20`). Same names, same count. The method discriminates inside that run.

### A2. "`AuthPlayerEnterWorld` is strictly worse — it carries the `SpawnPlayer` stubs." → **CONFIRMED [M], and the identification is upgraded from invalid to measured**

Machine-decoded every `E8` in `0x55CCE70..0x55CD506`: **three** hits on `0xF7EB50`, at `0x55CCF22` (the round-GM getter), **`0x55CD405`** and **`0x55CD4C7`**. Confirmed.

⚠ **The report identified those two as `SpawnPlayer` from `byimpl[0xF7EB50]` — that is naming a function from a folded address, the exact forbidden move** (`0xF7EB50` has **40 records** in the single-state table: `GetPlayerState`, `GetKills`, `GetHeroCharacter`, `SpawnPlayer`, …). I rescued it independently:

`tools/asdump/out/binds_members.csv:40275` gives
`ALokiCharacter SpawnPlayer(ALokiPlayerState PlayerState, const FTransform& SpawnTransform, AActor StartSpot = nullptr, bool bEnsurePositionIsValid = false)`

and the call frame at both sites matches all five slots:
`0x55CD39A mov rcx,[rsp+0x50]` (the null GM saved at `0x55CCF2F`) · `0x55CD3AE mov rdx,r12` (PlayerState) · `0x55CD39F lea r8,[rbp+0x40]` (FTransform) · `0x55CD3A3 xor r9d,r9d` (StartSpot = null) · `0x55CD3A6 mov byte [rsp+0x20],r14b` (the bool). Twin at `0x55CD48C/0x55CD486/0x55CD482/0x55CD47A/0x55CD47D`. **Identification is now [M] on signature, not on the fold.**

Two further confirmations of "eject path, not entry path", which I re-derived rather than accepted:
* the entry gate at `0x55CCEC2..0x55CCEEE` is a linear scan of `[this+0x120]` (count `[this+0x128]`) for the PlayerState, bailing to `0x55CD4E7` on miss — **CONFIRMED**;
* `tools/asdump/out/modules/GameMode/DropPhase/LokiDropPod.as:1543-1559`: the call sits inside `if (v12.PlayersInside.Contains(v32)) { if (PlayersAttached.Contains) Detach; else { …RandRange(-150,150)…; AuthPlayerEnterWorld(...); AuthPlayerDetachPlayerFromRidable(...); } }`. **Unambiguously the kick path.**

Ring-search details also reproduce: `0x55CD2C6 add esi,2 ; cmp esi,0x40 ; jl` ⇒ **32 iterations CONFIRMED**; `0x8B1D4BC = 0.09817477f` = **2π/64** exactly and `0x7794C80 = 150.0f`. (Calling 2π/64 a "golden angle" is a misnomer — the golden angle is 2.39996 rad — immaterial to the conclusion.)

And the designed call site is real: `tools/asdump/out/modules/GameMode/DropPhase/LokiDropShip.as:161`, `v42.AuthPlayerEnterWorldAttachedToRidable(v38, LandingLocation)`, immediately after `InitializeDropPod` + `FinishSpawningActor` — i.e. directly on S130's newly-working function. **CONFIRMED.**

### A3. "`GetLokiGameMode` is nulled; its same-TU sibling `GetLokiGameState` is intact; `UGameplayStatics::GetGameMode` is real and reads `World+0x250`." → **CONFIRMED [M]**

```
0x5630970  sub rsp,0x28 ; call 0x56F0330 ; xor eax,eax ; add rsp,0x28 ; ret     (16 B)
0x5630980  sub rsp,0x28 ; call 0x56F0330 ; test rax,rax ; jz ret ;
           mov rbx,[rax+0x258] ; call 0x55740F0 (IsA) ; ret rbx                (63 B)
0x37D7BF0  ... call 0x2EDBE70 (GetWorldFromContextObject) ;
           test rax,rax ; jz ret ; mov rax,[rax+0x250] ; ret
```
Record table (single-state, `dumps/s131-rideable-live`): `byimpl[0x5630970]=['GetLokiGameMode']`, `byimpl[0x5630980]=['GetLokiGameState']`, `byimpl[0x37D7BF0]=['GetGameMode']` with thunk `0x3804740`. Sizes 16 B / 63 B as reported. `World+0x250 = AuthorityGameMode` sits one slot below the `+0x258 = GameState` that CLAUDE.md already records [M] — mutually corroborating.

Supporting negative: I searched all 16,277 records for names containing `Round` — **24 hits, none is a round-game-mode getter**. So the stripped callee at `0x55CD572` is an unreflected C++ helper with no record; "nothing recoverable" **CONFIRMED**.

Also **CONFIRMED** and reproduced exactly, because it is the report's best unit-catch:
`0xF7EB50` = **80 `E8` rel32 call sites + 3 `E9` jmps** in merged4's decrypted `.text` (unit: rel32 matches; a **floor** at 55.09 % coverage) versus **27,217 qword-pointer occurrences image-wide** — i.e. CLAUDE.md's 27,217 is `findptr`'s pointer unit, and my uncapped rescan reproduces **27,217** and **165,789** for `0xF7EC20` to the digit. Different units, both correct. ✔
merged4 `.text` = **16,683 / 30,281 4-KiB pages = 55.09 %** — reproduced exactly.

---

## B. REFUTED / CORRECTED

**B1 — REFUTED, and it is the report's only actionable recommendation that is wrong.**
> "NOP‑ing the two `je`s is equally sufficient."

It is not; it **crashes**. NOP-ing `0x55CD57A` (`0F 84 32 02 00 00`) with `rax == 0` falls into `0x55CD580 mov rcx,rax` → `call 0x55C7DD0`, whose 6th instruction is `0x55C7DE7 mov rdi,[rbx+0x18]` with `rbx = rcx = 0` → AV reading `0x18`. The pointer being dead makes the *value* irrelevant; it does not make it safe to pass **null** to `IsA`.
**Correct minimal edit:** overwrite `0x55CD57A` with `EB 14 90 90 90 90` (`jmp 0x55CD590`), which skips the `mov`, the `IsA` call **and** the second `je` in one 6-byte patch. Or repoint the `E8` at `0x55CD572` at a stub returning a real `ALokiRoundGameMode`. Either is still a module-image write, the project's worst hazard class.

**B2 — mislabelled, and it contradicts today's own live measurement.**
> "2. `0x55CD7E4` → `0xF7EC20` — the `UE_LOG` emit inside the bail block we currently take."

The `UE_LOG` is **`0x55CD7C9 call 0x106B650`** and it is **intact** — that is what printed the measured `LogLokiRideable: Error: …failed to get the round game mode`. `0xF7EB50` at `0x55CD7E4` consumes an **FString** built at `0x55CD7DA` (`0xFAC920`) and freed at `0x55CD7F3` (`0xFF9310`) — a **second, different sink**, structurally identical to `SpawnAndMoveLokiCharacter_MoveStep`'s two and to `AuthPlayerPreSpawnOnAddToPlane`'s `0x55CD9CC`. If `0xF7EC20` were the log emit, today's line could not have appeared.
Also: `0x55CD7BB`'s `lea rdx` resolves to **`0x8B1CF08`, which is a 32-byte log *record*** (`{msg_ptr → 0x8B1CF30, 0x8B1CDD0, 0x12B, 2, …}`), not the string. The string is at `0x8B1CF30`. The report printed the record address as though it were a literal.

**B3 — wrong RVA (the hand-arithmetic class the prompt warns about).**
Report: "`IsValidPositionOnNavmesh 0x5666A00` / **`0x46CB9F0`**". Machine-decoded, the two sites `0x55CD2B9` and `0x55CD36B` both target **`0x56CB9F0`**. No `0x46CB9F0` target exists in the function.

**B4 — row count off by one.** `AuthPlayerEnterWorld` = `0x55CCE70..0x55CD506`, **1686 B** (correct) across **6** chained `.pdata` rows, not 7. Enumerated: `0x55CCE70, 0x55CCEFA, 0x55CCF0A, 0x55CD07D, 0x55CD464, 0x55CD4E7`. The other three extents reproduce exactly, including `AuthPlayerEnterWorldAttachedToRidable` = `0x55CD510..0x55CD7FA`, **746 B, 5 rows**.

**B5 — a grade silently upgraded.**
> "Member offsets confirmed against the AS property list: `+0x120/+0x128` = `PlayersInside`, `+0x130/+0x138/+0x13c` = `PlayersAttached`."

`binds_members.csv:44952-44954` gives **declaration order only** (`PlayersInside` prop 7, `PlayersAttached` prop 8, `PlayersThatExited` prop 9) — **it carries no offsets**. This is [I], not [M]. It is a *strong* [I]: two adjacent `TArray{Data,Num,Max}` at `+0x120`/`+0x130` in the right order, and the AS guard `if (PlayersInside.Contains(v32))` at `LokiDropPod.as:1543` matches the compiled `[this+0x120]` precondition at `0x55CCEC2` exactly. But it was not measured.

**B6 — denominators drifted.** "30 images" → I find **27** with a `.text` section; "16,253 records" → my scan of the same file yields **16,277** triples (fold split: 371 → `0xF7EC20`, **40** → `0xF7EB50`, 76 → `0xF7EB60`, 15 → `0xB9E1F0`; the 371 and 40 match the report). Neither difference is material, but the record-count method is not reproducible as stated.

**B7 — headline scope over-reach.** "the wall is ONE CALL, not the first of N" is established **for this function only**. The report's own sibling table shows `AuthPlayerDetachPlayerFromRidable` — the pod-lands-and-drops-the-rider handoff — carries **2** stripped calls (`0x55CCD5B`, `0x55CCE4E`, both `0xF7EC20`; I verified both), and the report flags it as "the next wall". Those two facts cannot both be summarised as "one call, not the first of N" without a scope qualifier.

---

## C. CLAIMS I ALSO SPOT-CONFIRMED (no correction needed)

* Success-path transcription: `Location.Z + 7500.0` (`0x8B1D4C8`, double, = 7500.0 ✔); `0.5f` at `[rsp+0x28]` (`0x76A10E0` ✔); default rotator `{0,0,0}` at `.data 0x99C87B8` ✔; `rcx=hero / rdx=&{X,Y,Z+7500} / r8=&FRotator` at `0x55CD6C9/0x55CD6B1/0x55CD6A3` ✔; `PlayersAttached.Add` at `0x55CD760/0x55CD767` ✔.
* `0x56BE0D0` = `mov rbx,[rcx+0x430]` ⇒ **`ALokiPlayerState+0x430` = character [M]** ✔.
* `HasEverContainedPlayer` (`0x55DCAA0`): `[this+0x120]` linear scan, then Murmur3 finalizer `imul ecx,eax,0x85EBCA6B` at **`0x55DCAE0`** into a TSet at `+0x148/+0x174/+0x178/+0x180/+0x188` ✔. Precondition direction correct: `0x55CD553 test al,al ; jne bail` ⇒ must be **false**.
* `AuthPlayerPreSpawnOnAddToPlane`: getter `0x55CD842`, GM saved in `rsi`, two gates, and **the GM IS used** — `0x55CD8DD mov r9,[rsi] ; mov rcx,rsi ; 0x55CD8E9 call [r9+0xA48]` ✔. Its `0x55CD91C call 0xF7EC20` takes `rcx = rbx =` the hero ✔.
* `AuthPlayerDetachPlayerFromRidable`: **zero** `0xF7EB50` sites (no GM getter) ✔; `GetLandingTeleportLocation 0x55D89F0` → `0x339A7A0` → `MulticastOnPlayerEnteredWorld 0x54537C0` all present ✔.
* Record-table sweep of the family reproduces: `AuthPlayerEnterWorldNew`, `AuthAddPlayer`, `AuthRemovePlayer`, `AuthSetCanJump` all impl `0x0F7EC20` = EMPTY ✔; `ContainsPlayer 0x55D0270`, `GetRidePosition 0x55DAB50` REAL ✔. Note `HasEverContainedPlayer` has **two** records (`0x55DCA90` and `0x55DCAA0`); the call site takes `0x55DCAA0`, the `ULokiRideableComponent` one — the report picked the right one but never printed the ambiguity.

---

## D. STILL UNGROUNDED — what would settle each

1. **`LokiTeleportActor`'s body** — 0/27 images, blocked. The "zero stripped folds" verdict is contingent on it. *Settle:* drive it once (any teleport) then `dumpimage`, or `mergedumps` a future in-world snapshot; §the S120 "push it, then dump" method applies verbatim.
2. **"`WITH_SERVER_CODE`-class strip"** — [S]. The macro is a guess; the *targeting* is [M] (adjacent sibling intact). Nothing settles the macro name offline; drop the label or grade it.
3. **`0x56F0330` = "LokiGetWorld"** — asserted, never shown. *Settle:* one `byimpl` lookup + 10 bytes of disassembly.
4. **`AActor+0x1b0` = RootComponent** — asserted from context only. *Settle:* the UHT `FPropertyParams` oracle, the same instrument S130 used for `AActor+0x6C`.
5. **`LokiDropPod.as:3942` is inside `SpawnCrewPod`** — I could not resolve the enclosing function from the pseudo-source (the file's declaration block defeats naive scoping). *Settle:* read the disassembly appendix, which the project's own reading rule says is ground truth.
6. **Lever (b)'s ninth step has no stated mechanism.** Four steps are registered UFunctions with live thunks (all four thunk/impl pairs confirmed from the record table), and `SpawnAndMoveLokiCharacter_MoveStep` is a native static — but `PlayersAttached.Add` is a raw `TArray` grow (`0x0F988D0`) with **no** reflected entry point, and the report lists it as a step without saying how a shim performs it.
7. **Whether anything downstream reads `PlayersAttached`** — i.e. whether lever (b) actually produces a ridden pod, or just a hero parked 7500 uu above the landing point. Unexamined in the report and unexamined by me. This is the difference between "the wall is one call away" and "the wall moves one function further".
8. **Whether an Angelscript path reaches the same effect without the C++ getter.** `LokiDropPod.as` / `LokiDropShip.as` were used only as call-site evidence; no survey was done for an AS-side attach that bypasses `0x55CD510` entirely. Free, offline, unstarted.

---

## E. BOTTOM LINE

The report's three structural findings are **sound and reproduce exactly** — including the two hardest ones (the pointer is dead; the `27,217`-vs-`80` unit conflation). It declared its own coverage gap on `LokiTeleportActor` rather than hiding it, and it built a real positive control for the record-table grading method (7 EMPTY in the same 154-record run — verified).

What must not be carried forward as written: **NOP-ing the two `je`s is a null-deref**, `0x46CB9F0` should be `0x56CB9F0`, `0xF7EC20` at `0x55CD7E4` is *not* the `UE_LOG` (the `UE_LOG` works and is `0x106B650`), the member offsets are [I] not [M], and the "ONE CALL, not the first of N" headline is true of `0x55CD510` and not of the feature — the landing half (`AuthPlayerDetachPlayerFromRidable`, 2 stripped) is already in the report's own table.