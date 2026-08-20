# ADVERSARIAL VERIFICATION — `scratchpad/s132/lanes/L1-detach-transcription.md`

**Method.** Every load-bearing claim re-derived from `dumps/merged4.dump.exe` by my own capstone
decode / raw byte scans, written fresh (`scratchpad/s132/lanes/verify_l1/vdis.py` + inline scripts).
Where a second route existed I used it (UHT `FPropertyParams` records, the `.data`
`{name,thunk,impl}` record table, the `SetBitFunc` bool oracle, the Angelscript bytecode appendix,
`pdata_union.csv` UNWIND_INFO chain decode). **Every address computed by `python`.** Zero launches,
zero injections, zero `.text` writes.

**Score: 15 headline claims + ~12 supporting claims examined.
25 CONFIRMED · 4 UNSUPPORTED · 1 REFUTED · 0 DEGENERATE-CONTROL.**

---

## A. REFUTED

### R1 — §10: *"every caller/xref count here comes from my own uncapped scan and is a **count**, not a floor."* — **REFUTED**

The report conflates **uncapped** with **complete**. A rel32 byte scan over `merged4` is bounded by
demand-decryption, and I can demonstrate it under-counts **inside the report's own subject**:

* [M] the Angelscript listing the report itself quotes has **TWO** `CALLSYS
  ULokiRideableComponent::AuthPlayerDetachPlayerFromRidable` sites in `KickPlayersFromPod` —
  bytecode `0x01D8` (the `PlayersAttached.Contains` branch) and `0x02EC` (after
  `AuthPlayerEnterWorld`). Verified in `tools/asdump/out/GameMode/DropPhase/LokiDropPod.as.txt`.
* [M] my **full-file** (not just `.text`) rel32 scan for `0x55CCCB0` returns exactly **two** sites:
  `0x54561B4` (the exec thunk) and `0x596A190`. So only **one** of the two AS sites is visible.
* [M] `0x596A190` is the **second** one: `call 0x55CCE70` (`AuthPlayerEnterWorld`) sits at
  `0x596A122`, 0x6E bytes earlier — exactly the bytecode `0x02D4 → 0x02EC` pair.
* [M] the AOT body **spans an all-zero page**: `0x596A1F2  jmp 0x59697C1` (machine-computed) targets
  page `0x5969000`, and `data[0x5969000:0x596A000].count(0) == 4096` — **ZERO in `merged4` and in
  all 30 same-size images on disk (0/30 decrypted)**. I checked every one.

⇒ [M] **the scan provably misses ≥1 real call site**; [I, strong] the missed site is the
bytecode-`0x01D8` call, compiled into `0x5969000`.

⇒ **Correction:** a rel32 caller scan over a **55.09 %-decrypted** image (16,683 / 30,281 `.text`
pages — I re-derived this figure) is a **FLOOR**. `fkdis`'s 200-row cap was correctly avoided; the
*coverage* cap was not. §10's sentence should read: *"uncapped by the tool, still bounded to the
decrypted image."* This is the project's own instrument-artifact pattern in a fresh instance.

---

## B. UNSUPPORTED (true or probably true, but not established by the evidence given)

### U1 — H11 *"The function has **exactly one** game caller"* graded **[M]** → should be **[M, bounded]**

Follows from R1. Two independent blind spots, neither acknowledged at the claim:

1. **44.91 % of `.text` is undecrypted** — and R1 shows a real call site hiding in it.
2. **A rel32 scan cannot see a reflected caller by construction.** The function is
   `BlueprintCallable`; a Blueprint reaches it through `ProcessEvent → UFunction.Func`, a pointer
   copied out of the `.data` record at runtime. "thunk `0x5456100` — 0 rel32 sites" is therefore
   *uninformative* about Blueprint callers, not negative.

**What survives:** the operational conclusion (*baseline zero, because `KickPlayersFromPod` is
behind `LokiIsClient` = `mov al,1; ret`*) is unaffected **for that caller** — I re-read the bytecode
gate (`CALLSYS LokiIsClient; JLowZ 2 -> L0028; JMP 192 -> L0328`) and confirmed the structurer did
**not** invert it. But "every observable is at baseline 0" inherits the bound.

**Two pieces of evidence I add that the report did not use, and should:**
* my **full-image** qword scan finds exactly **one** stored pointer to the impl VA (`0x9C1E538`) and
  exactly **one** to the thunk VA (`0x9C1E530`) — both in the `.data` record. That rules out
  indirect calls through any *statically stored* pointer, and is stronger than the rel32 result.
* a `grep -rl` of the whole extracted asset corpus (`tools/extractor/out`, 69k JSONs) for
  `AuthPlayerDetachPlayerFromRidable` returns **zero files** ⇒ no extracted Blueprint names it.
  **Positive control run and PASSED:** the same grep for `BulkClaimAllProgressionTrackRewards` — a
  native UFunction `CLAUDE.md` records as appearing in exactly one asset — returns
  `catalog/wbp/WBP_UI_LobbyRewards.json`, `bpdump_ExecuteUbergraph_WBP_UI_LobbyRewards.txt` and
  `names_mainmenu.txt`. So the instrument **can** see a Blueprint-referenced native UFunction name,
  and the zero is a real zero.
  ⚠ Corpus caveat: `CLAUDE.md` records that `extractor dump` writes **flat by basename with 586
  colliding basenames (last writer wins)**, so this is strong but not exhaustive.

### U2 — §3.1 raw-scan census — **numbers wrong, conclusion CONFIRMED**

> *"The raw scan found **16 candidate `E8`/`E9` bytes**; 15 are instruction-aligned (14 `call` + 1
> `jmp`) and exactly **one** (`0x55CCCD0`) is an operand byte, correctly rejected."*

My uncapped scan of `0x55CCCB0..0x55CCE64`:
* **20** candidate `E8`/`E9` bytes,
* **16** instruction-aligned = **15 `call` + 1 `jmp`**,
* **4** operand bytes: `0x55CCCCC`, `0x55CCCD0`, `0x55CCD6A`, `0x55CCE08` (three of the four decode
  to targets outside the image, presumably why they were filtered — but then "16" is a *filtered*
  count presented as a raw one).

The prose **contradicts the report's own §3.2 table**, which lists **15** direct calls + 1 indirect.
**The fold tally is unaffected and is CONFIRMED** (see C3). Flagged because a self-inconsistent
census is how a real miscount later gets defended.

### U3 — Prediction 10 *"No new log line of any kind is attributable to this function"* graded **[M]** — grade upgraded across the callee boundary

The premise (*"no logger call in the body"*) is **[M] and I confirmed it**: none of the 15 direct
targets is `0x106B650`, and there is no FString build/emit/free triad. The conclusion is about the
**whole call tree**, and the premise does not reach it. Measured:

| callee (on the executed path) | contains `call 0x106B650`? |
|---|---|
| `SetActorEnableCollision` `0x339A550` (W3a, **unconditional**) | **YES** — at `0x339A60F` |
| `IsA<ALokiHeroCharacter>` `0x54F8DC0` (gate 5, **unconditional**) | **YES** — at `0x54F8E05` |
| `GetLandingTeleportLocation` `0x55D89F0` (12 calls scanned) | no |
| `SetActorLocation` `0x339A7A0`, `MulticastOnPlayerEnteredWorld` `0x54537C0` | no |

Both live sites sit behind an `ensure`-shaped guard (`test esi,esi; jns` plus a verbosity byte test),
so they are unlikely to fire — but "unlikely" is not "[M] none". And **W7 routes through
`ProcessEvent`**, which can log.

**Internal contradiction:** prediction **7** says *"Possible knock-on UI/log/delegate activity …
watch `Loki.log` for anything new; do not treat silence as negative"*, while prediction **10** says
no log line is attributable and *"do not build a grep-based receipt"*. Both cannot stand.

**Correction:** *the body emits nothing [M]; callees on the path contain guarded logger sites, so a
log line is not excluded [M] — a grep receipt is unreliable, not impossible.* The same over-reach
appears in H8's *"never by a log line."*

### U4 — §6.1 *"`UActorComponent +0xB8` `OwnerPrivate` — `UActorComponent::GetOwner` impl `0x3215D20` = `mov rax,[rcx+0xB8]; ret`"* graded **[M]** → **[I, strong]**

The **bytes are [M]** (I re-read them: `48 8b 81 b8 00 00 00 c3`). The **class attribution is not**:
`0x3215D20` has **16** qword pointer sites image-wide, i.e. it is an **ICF fold**, and **six**
`.data` records are named exactly `GetOwner` (impls `0x20B9E90`, `0x3215D20`, `0x58449F0`, plus
three `.rdata`-resident). The owning `UClass` of the `0x3215D20` record was never resolved. The
report's own §10 boasts *"the `0x3E0` vtable resolution is fold-disambiguated, not fold-blind"* and
`CLAUDE.md` mandates *"always print fold multiplicity next to a folded RVA"* — that discipline was
applied to `0x3E0` and dropped here. Note the *cited control*, `AActor::GetOwner 0x20B9E90`, is
itself a **280-site** fold.

**Substance stands.** H10's equivalence also rests on the AS listing, which I confirmed: `v4 = this`
for a leader pod, and `v12 = ULokiRideableComponent::Get(this, NAME_None)`, so
`GetOwner(v12) == v4`. Only the grade is wrong.

### U5 (minor) — H12 header *"IT WRITES **8** THINGS"* vs §6's **ten**-row table (W1…W10)

W1/W10 are folds that write nothing, so the table is 8 state writes + 1 RPC + …, depending on
whether W3a/W3b and W5a/W5b are counted separately. The count is not reconstructible from the table.
Cosmetic, but it is the class of error `CLAUDE.md` records repeatedly ("re-derive counts, never
carry them").

---

## C. CONFIRMED (re-derived independently)

**C0 — the listing itself.** My capstone decode of `0x55CCCB0..0x55CCE68` was diffed line-by-line
against `_listing.txt`: **104 instructions vs 104, 0 byte mismatches, 0 mnemonic mismatches, 0
missing, 0 extra.** 440 bytes decode with no data-in-code, terminating on `ret` at `0x55CCE67`.

**C1 — H1 extent + chain.** `pdata_union.csv` rows reproduce exactly (43+44+38+41+198+45+18+5+8 =
**440**, machine-summed). I decoded the `UNWIND_INFO` structures myself (`Version|Flags`,
`CountOfCodes → ((n+1)&~1)*2` bytes of codes, trailing `RUNTIME_FUNCTION` when `UNW_FLAG_CHAININFO`
is set) and reproduced **all nine** chain targets and the primary `0x97FCAF0 flags=0x0`.
**Both boundary controls hold:** the prior row `0x55CCC66` chains to `0x55CCB80` (a different
function); the next row `0x55CCE70` is `flags=0x3`, **no chain bit ⇒ PRIMARY**, and the `.data`
record at `0x9C1E570` names it **`AuthPlayerEnterWorld`**. Padding `0x55CCE68..0x55CCE70` reads
`ba 01 00 00 00 57 57 57`, exactly as printed.

**C2 — H2 coverage.** Whole extent lies in page `0x055CC000`, **present**. Byte census reproduces
**63 zero bytes, longest zero run 4**. `lane-d-empty-impl-census.tsv:11084` first-16 bytes
`4885d20f84ae01000048895424105541` are byte-identical to my decode.

**Cross-image control I add (the report has none for this):** the 440 bytes
`0x55CCCB0..0x55CCE68` hash to **`d849b9936f4174df`** (sha256[:16]) in **28 of the 30** same-size
images on disk — including every single-state dump (`tutorial-hero`, `menu`, `store`, `loadout`,
`s131-rideable-live`, `s132-dismount-live`, …) — and the remaining 2
(`crash-20260815-160759`, `toggles`) have the page undecrypted. **Zero disagreements.** So
`merged4`'s bytes here are not a merge splice, and the `mergedumps` `.text`-only page merge
introduced no corruption at this address.

**C3 — H3 fold tally.** Two routes (capstone; uncapped raw `E8`/`E9` byte scan): `0xF7EC20` × **2**
(`0x55CCD5B`, `0x55CCE4E`) · `0xF7EB50` × **0** · `0xF7EB60` / `0xB9E1F0` / `0xFC6CF0` × **0**.
No unaligned candidate targets a fold either.
**The negative control is genuine, not degenerate:** `AuthPlayerEnterWorld` contains `0xF7EB50` at
`0x55CCF22` **and two more** (`0x55CD405`, `0x55CD4C7`) — same page `0x55CC000`, same scanner, so
the zero here is a real zero.

**C4 — H4.** capstone `regs_access` over the instructions following each fold: after fold #1 the
first four insns (`mov r8d,1`, two `lea`, `call`) read **no** `rax`/`eax`; after fold #2 the entire
epilogue reads none. **Neither return value is tested.** The derived correction to `CLAUDE.md` §14.1
("read any null as locating one of those two" is wrong as an inference rule) is sound.

**C5 — H5.** `data[0xF7EC20:0xF7EC23] == c2 00 00`; capstone renders `ret 0` = `ret imm16 0`. It is
a **void no-op** and does **not** zero `eax`. The warning is correct and worth keeping.

**C6 — H6/H7 gate structure.** All eight gates re-derived with correct branch targets
(1a→`0x55CCE67`, 1b→`0x55CCE60`, 2→`0x55CCE5B`, 3→`0x55CCE53`, 4/5/7→`0x55CCE23`, 6→`0x55CCDD4`,
8→`0x55CCE53`). Branch census: 12 total = 8 gates + the `r8`-null substitute + 2 loop-control.
**No gate missed, none spurious.** I also verified the spill/restore pairing is coherent on every
bail path (each skipped restore has a correspondingly skipped spill), so shrink-wrapping introduces
no extra hazard.

**H7's absence list is exhaustively confirmed.** I enumerated **every** memory operand in all 104
instructions; the only non-`rsp` displacements are `+0xC`, `+0xB8`, `+0x130`, `+0x138`, `+0x1F0`,
`+0x3E0`, `+0x1A0`, `+0xD0` and two zero-displacement derefs. **No `+0x118`** (`bCanExit`, which I
independently placed at `+0x118` from its `SetBitFunc 0x332B950 = mov byte [rcx+0x118],1; ret`),
**no `+0x11C`, no `+0x120`, no `+0x128`, no `+0x13C`, no authority/role/NetMode read, no `IsA` on
`this`.** Note H7's scope is *the body*: callees are a separate question (see U3).

**C7 — §4.2 hazard.** Confirmed by construction: `Data=0, Num=1` ⇒ `rdx = 0 + 1*8`, `cmp rcx,rdx`
unequal ⇒ gate 2 **passes** ⇒ `cmp qword ptr [rcx], rbx` dereferences address 0. Real.

**C8 — H9 signature.** Four independent instruments re-run:
(a) `binds_members.csv:44930` verbatim `"void AuthPlayerDetachPlayerFromRidable(ALokiPlayerState
PlayerState,const AActor LandingLocationActor)"`;
(b) the `.data` record — name ptr `0x9C1E528 → "AuthPlayerDetachPlayerFromRidable"`, thunk
`0x9C1E530 → 0x5456100`, impl `0x9C1E538 → 0x55CCCB0`, and my **full-image** qword scan finds
**exactly one** occurrence of each VA ⇒ multiplicity 1 confirmed *more strongly than claimed*;
(c) `FFunctionParams @0x9C1E0A0`: **NumProperties = 2, StructureSize = 16**; prop[0] `PlayerState`
`ArrayDim=1 Offset=0x0` `flags 0x0010000000000080`, prop[1] `LandingLocationActor` `Offset=0x8`
`flags 0x1010000000000082` — **no ReturnValue ⇒ `void` [M]**;
(d) the exec thunk `0x5456100` disassembled in full (201 B): two `P_GET_OBJECT` blocks (`FFrame`
`Code != null` test → `Step 0x345FB0`, else fast path `0x345FE0`), `P_FINISH`
(`rax=[rbx+0x20]; setne dil; add rdi,rax; mov [rbx+0x20],rdi`), then
`mov rcx,rsi; mov rdx,[rsp+0x48]; mov r8,[rsp+0x38]; call 0x55CCCB0` — **no authority check, no
guard, no marshalling beyond the two object fetches.**
(e) the AS push order `v4 / v32 / v12` reproduces from the bytecode.

**C9 — H14 flags.** `uht_funcflags_tuthero.csv:12567` = `0x04020405 =
Final|BlueprintAuthorityOnly|Native|Public|BlueprintCallable`. A sibling check I add:
`GetLandingTeleportLocation` is `0x04820401` — **not** `BlueprintAuthorityOnly`, which independently
corroborates §8.3's "call it alone first" advice.

**C10 — H12 writes + every offset in §6.1.** Re-derived independently from the UHT
`F*PropertyParams` records (name string → pointer to record → `ArrayDim@+0x30 / Offset@+0x32`):
`ViewDistance 0xE8` (**unique record image-wide**) · `PracticallyTouchingVisionRadiusOffset 0x196C`
(unique) · `PeripheralVisionRadius 0x1970` (unique) · `PracticallyTouchingVisionGranter 0x1978`
(unique) · `PeripheralVisionGranter 0x1980` (unique) · `CapsuleComponent 0x460` ·
`CapsuleRadius 0x6C4` · `GravityScale 0x1A0` · `BattleRoyalePlayerPhase 0xEA8` (unique) ·
`PlayersInsideCount 0x11C` · `PlayersInside 0x120` · `PlayersAttached 0x130` · **`Tags 0x1F0` — the
unique one of 106 `Tags` records at that offset**, exactly as claimed.

`bDropComplete @ +0xD0` confirmed by a **different** oracle: record `0x8A1C2F0`, `SetBitFunc` at
`0x2E09510` = `c6 81 d0 00 00 00 01 c3` = `mov byte [rcx+0xD0],1; ret`. Its owning class accessor
`0x5429740` resolves to wide string **`LokiPlayerDropPlaneComponent`** (`0x8A1C2AA`, `/Script/Loki`).

Callee identities confirmed from the `.data` record table (name at `rec+0x00`, each with exactly
**1** pointer site): `0x5599040 SetPredropHidden` · `0x55AC8E0 GetLokiCharacterMovement` ·
`0x56BE0D0 GetLokiCharacter` · `0x339A550 SetActorEnableCollision` ·
`0x54537C0 MulticastOnPlayerEnteredWorld` · `0x55D89F0 GetLandingTeleportLocation` ·
`0x5586530` **0 pointer sites ⇒ genuinely not reflected**, as stated.

`0x339A7A0` and `0x55C6E80` have **no** record — their names are [I], not [M] — but both are
corroborated structurally: `0x339A7A0` reads `[rcx+0x1B0]`, then `[rcx+0x220]`/`[rcx+0x230]` and
subtracts, byte-for-byte the same shape as the *reflected* `K2_SetActorLocation` impl `0x3390990`;
and `0x55C6E80` is structurally identical to the reflected `GetComponentByClass` impl `0x33879B0`
(`mov rax,[rcx]; rdi=[rax+0x760]; … lea rdx,[rsp+0x30]; call rdi`).

Literal `"MinionIgnore"` confirmed at rip-target **`0x8B1B5F0`** (machine-computed from
`0x55CCD6D + 0x354E883`). `FName::FName 0x1138DD0` confirmed as the **ANSICHAR** overload
(`cmp byte ptr [rdx+r9], 0`). `SetPredropHidden`'s **early-out** confirmed:
`cmp byte [rcx+0x1BE8], dl; je <ret>`, then `mov [rcx+0x1BE8], dl`, `call 0x1E3CCD0`, tail-jmp
`0x5592C70` — all three addresses machine-checked.
`GetLandingTeleportLocation`: **963 B over 6 chained rows `0x55D89F0..0x55D8DB3`, page present,
`0` fold calls** — all four sub-claims reproduce. (`SetActorEnableCollision` is likewise 484 B over
5 chained rows, matching the cited `fk6-cheat-impl-census.csv` figure.)

**C11 — H13 crash hazard. CONFIRMED, and slightly worse than stated.** `0x5586530` (106 B):
`mov rax,[rcx+0x460]` → immediately `movups xmm2,[rax+0x240]` and `mulss xmm0,[rax+0x6c4]`;
`mov rax,[rcx+0x1978]` → `movss [rax+0xE8], xmm0`; `mov rcx,[rcx+0x1980]` → `mov [rcx+0xE8], eax`.
**Three unguarded dereferences, two of which are WRITES.** Pre-reading all three before arming is
correct advice. (Counter-balancing detail the report omitted: `SetActorLocation 0x339A7A0` **does**
null-check `RootComponent` at `0x339A7B3`, so a null root there is safe.)

**C12 — H15 `TArray::Remove` `0x11F3860`.** Fully traced (275 B). Early-out `if (Num==0) return 0`.
Enumerating **every** memory store in the body: ten are `rsp` register spills and **exactly one is
not — `mov dword ptr [rax+8], r15d`**, where `rax` is the array pointer reloaded from its home slot.
**`Num` only.** `Data(+0x0)` and `Max(+0xC)` are never written; the sole call is
**`memmove` via the import thunk `0x752A65E`** (`ff 25 …`) — the report's address is **correct**.
Hand-simulated for `Num==1` + match: `r12b=0` ⇒ `test r12b,r12b; je` **skips the memmove**, `Num` is
written **0**, return value **1**. Prediction 1 is exactly right. Also confirmed the callee never
writes through its `rdx` ⇒ the `[rsp+0x88]` home slot survives ⇒ **gate 8 really is redundant**.

The sibling `TArray<FName>::Remove 0x10FF910` behaves identically — same `memmove 0x752A65E`, and its
only non-spill store is `mov dword ptr [r13+8], ebp` ⇒ **W2 also writes `Tags.Num` and nothing else.**

**C13 — fold #2 identity evidence (correctly graded [I]).** All three supporting facts reproduce:
the `EBattleRoyalePlayerPhase` enumerator array at `.rdata 0x8A2C9E0` decodes to
`None 0 · Pregame 1 · Dropping 2 · Combat 3 · PostGame 4` (I read the **names**, not just the
values); `GetBattleRoyalePlayerPhase 0x54333A0` = `movzx eax, byte [rcx+0xEA8]; ret`; my own decode
of all **86** `a8 0e 00 00` occurrences in `.text` (85 decodable) finds **no**
`mov byte ptr [obj+0xEA8], imm` on a non-stack base register. And the caveat is right: the exact
shape `{xor r8d,r8d; mov dl,imm8; call 0xF7EC20}` occurs **exactly once image-wide — this site**
(uncapped scan; the reverse operand order occurs 0 times).

**C14 — §10's class-identification control is GENUINE, not degenerate.** `0x54F8DC0` calls
`0x5395720`, whose `rdx` wide-string argument is **`LokiHeroCharacter`** (`0x899A832`, package
`/Script/Loki`); the sibling `0x54F8C40` calls **`0x52F01E0`**, whose string is **`LokiCharacter`**
(`0x88D6672`). Different input, different correct answer, same recipe.

> ⚠ **My own near-misses, recorded — TWO of them, both hand arithmetic, both in this verification.**
> (a) I nearly filed C14 as REFUTED after transcribing the callee VA by hand as `0x2F01E0` — a page
> that is all-zero in **every** image on disk, so the "control could not have been run" conclusion
> looked airtight. Machine recompute: `0x7FF6B42F01E0 − 0x7FF6AF000000 = 0x52F01E0`, a **present**
> page holding `LokiCharacter`. (b) I then flagged the report's `memmove 0x752A65E` as a typo for
> `0x652A65E`; machine recompute of `0x7FF6B652A65E` gives **`0x752A65E`** — the report was right and
> `0x652A65E` is an all-zero region I had invented.
> **Both errors would have produced a confident false refutation, and both were mine, in an audit
> whose stated subject is that exact failure mode.** The brief's "recompute with a machine" rule is
> not boilerplate.

**C15 — §8.4 ordering / the AS caller.** The bytecode excerpt in §9 is verbatim accurate
(`ADDSi 288 → .PlayersInside`, `ADDSi 304 → .PlayersAttached` — an independent oracle for `0x120` /
`0x130`), the push order matches `rcx/rdx/r8`, and the `LokiIsClient` gate is **not** inverted by
the structurer (`JLowZ 2 -> L0028` takes the work branch only when the call returns zero).

---

## D. Standing caveats a successor should carry

1. **`merged4` `.text` is 55.09 % decrypted (16,683 / 30,281 pages).** Every "no other site exists"
   statement inherits that bound, including H11. R1 is a worked example of it biting inside this
   very analysis.
2. The report's *positive* claims about the function **body** are strong precisely because the whole
   extent sits in one decrypted page. Nothing in §§1–8 about the body is coverage-limited.
3. Nothing found here changes the arm design in §8. The eight gates, the pre-flight reads, the
   `Data=0 / Num=1` hazard, the `0x5586530` crash hazard and the direct-`__fastcall` recommendation
   all survive verification unchanged.
4. **Omission, not an error, in H14 / §8:** *"call `0x55CCCB0` directly … no FFrame, no
   ProcessEvent, no marshaller"* is correct about **calling convention** but says nothing about
   **which thread**. The body reaches `SetActorEnableCollision` (which walks and re-registers the
   component tree), `SetActorLocation` (moves `RootComponent`) and a `ProcessEvent` multicast — all
   game-thread work. The S55 primitive is game-thread **by construction**; "direct impl call" is not.
   A successor should read this as *"dispatch on the game thread via the S55 primitive, but call the
   impl address rather than the thunk"*, and the arm should say so explicitly.
