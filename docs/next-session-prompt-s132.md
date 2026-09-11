# NEXT SESSION (S132) — the pod is alive, the wall is fully characterised, and there is a DATA-CLASS lever.

> ## ⛔ SUPERSEDED 2026-08-20 (end of S132) — THIS IS HISTORY, NOT A PLAN.
> **§1C WAS RUN AND IT WORKED: the drop-pod dismount runs and is usable.** Current documents are
> **`docs/s132-dismount-settled.md`** (the evidence) and **`docs/next-session-prompt-s133.md`** (the plan).
> This file is preserved as the record of what S132 was told, annotated in place with what actually
> happened. **Every `⇒ S132:` block below is the outcome; the surrounding text is the pre-registration.**
> ★ Read it that way — the value here is the *comparison*, i.e. which predictions held and which did not.

**One line: `AuthPlayerDetachPlayerFromRidable`'s only GATE is the single `TArray` append the wall
dies just before performing — so the dismount is one append away. ⚠ It is NOT fold-free (2 ×
`0xF7EC20`, see §B), so expect a PARTIAL dismount. Read §1 first — §1C is the experiment.**

> ⇒ **S132: CONFIRMED, and the pessimism was WRONG.** "One append away" was exactly right. The
> dismount is **not partial** — the hero is un-hidden, its collision and movement are restored, and it
> is teleported to a chosen landing point. See the §B annotation for why the two folds cost nothing.

**Written 2026-08-20 at the end of S131.** Read `docs/s131-pod-functionality-settled.md`, then
`docs/fk22-dropphase-reachability.md` §29. Evidence: `scratchpad/s131/evidence/`.

---

## 0. WHAT S131 DID

1. Built `PdPodDump()` — an **in-arm** pod-state readout (RM_DROPPOD + RM_POOLSPAWN), pure guarded
   reads, no extra `GUObjectArray` sweep, with a by-name calibration control and an
   Angelscript-offset cross-check printed beside every field.
2. **[M] `InitializeDropPod` ran and its three discriminating writes landed** — against a within-run,
   same-class negative control of three pods that all read class defaults in the same dump.
3. **[M] The pod is ALIVE and FLYING at its cooked `InitialSpeed` of 20,000 uu/s**, with Niagara drop
   VFX ticking and UE logging LWC tile recaches for it. It flies **because `StartPodGameplay` never
   ran** — and that is because `Loki::LokiIsServer()` is a stripped `return false`.
4. ⚠⚠ The fifth wall was NOT tested by the Route-E flight (null `PlayerState` -> silent return on
   instruction #1) — **but it WAS tested afterwards, on the same live client, and CONFIRMED. See §0.5.**
5. Free side result: **FK-31's kill jumps to one fixed address per boot session**, the same address
   across FK-7 and FK-31 alike — and that hands FK-31 its first cheap experiment (§3).

---

## 0.5 ★★★★★ SUPERSEDED SAME DAY — THE FIFTH WALL IS ALREADY CONFIRMED. §A1 BELOW IS DEAD.

**Do not spend a launch on §A1.** After writing it, S131 tested the wall directly on the *same live
client* and confirmed it. Read `docs/s131-pod-functionality-settled.md` §10.

* ⚠⚠ **§A1's lever is BLOCKED AT ITS PRECONDITION and was killed by ONE read-only command:**
  **[M] ZERO live instances of any class containing `TeamOnly`**; the only `TeamState`-named live
  object is `Comp_TeamState_GlobalShop_GEN_VARIABLE`, a template. **There is no TeamState actor to
  poke.** ⭐ Check a lever's precondition with a read-only pass *before* building the arm.
* ★ Instead, **`RM_RIDEABLE` (enum 29)** calls `AuthPlayerEnterWorldAttachedToRidable` **directly**
  on the pod's own `LokiRideable` component with a live, valid PlayerState. Against a verified
  baseline of 0, `Loki.log` gained
  `LogLokiRideable: Error: ULokiRideableComponent::AuthPlayerEnterWorldAttachedToRidable failed to
  get the round game mode` — **count 0 → 2, exactly one per call.**
* ⇒ **[M] the wall REACHES `0x55CD572`, gets 0 from the stripped `0xF7EB50` getter, and fails — with
  valid arguments.** Controls: `ContainsPlayer` on the same object through the same primitive
  (`fault=no`), both of the wall's own IsValid preconditions read out and PASSING, two independent
  PlayerStates, and an exact per-call count.
* ★ By-product: the log category, recorded COVERAGE-BLOCKED by lane 4, **named itself** the moment
  the path ran — **`LogLokiRideable`**.

## 1. ★★★★★ THE QUESTION IS ANSWERED, AND THERE IS A DATA-CLASS LEVER — START HERE

> ⇒ **S132: THE WHOLE OF §1 WAS FLOWN AND IT HELD.** The lever was correct, the risk class was
> correct, and the recipe in §1C was correct **instruction for instruction**. Four dismounts on one
> armed window (flight 1), then two more with a landing actor (flights 2 and 3). Zero `.text` writes,
> zero PI hooks, zero CDO pokes. Evidence: `docs/s132-dismount-settled.md`, raw in
> `scratchpad/s132/evidence/`.

**The offline follow-up ran and the wall is FULLY CHARACTERISED.** Two independent lanes agree on the
load-bearing claim. Reports: `scratchpad/s131/lanes2/`. Read them before building anything.

### A. The wall is ONE CALL, and the value it fetches is DEAD [M]

* `AuthPlayerEnterWorldAttachedToRidable` extent is **`0x55CD510..0x55CD7FA` = 746 B**, 5 chained
  `.pdata` rows, **fully decrypted in `merged4`** — nothing about it is coverage-blocked.
* Downstream of `0x55CD572` there are **11 call sites / 10 distinct targets and ZERO folds.** Every
  callee is a real body.
* ★★ **Register-liveness over the guard's fallthrough (`0x55CD590..0x55CD5CB`, every instruction,
  capstone `regs_access`): ZERO reads of RAX.** The round game mode is **a PRECONDITION, not a data
  dependency** — it is fetched, null-tested, `IsA<ALokiRoundGameMode>`-tested, and then never touched.
* ⛔ **No poke can satisfy the getter, permanently.** `0xF7EB50` is `33 c0 c3` — three bytes, **zero
  memory operands**, byte-identical in 4/4 images. It reads no argument, cache or global.
* ⛔ A `UFunction.Func` swap is also dead: exec thunk `0x5456380` has **0 direct callers**, and the
  game's own callers (`LokiDropShip.as::SpawnDropPodForTeam`, `LokiDropPod.as::SpawnCrewPod`) reach
  the **impl by rel32**, bypassing `Func` entirely. Removing an internal `call` needs a standing
  `.text` write — measured **10/10 lethal**. Not an option.

> ⇒ **S132: §A stands and was never contradicted — the flight simply routed around it.** The
> conclusion "the round game mode is a precondition, not a data dependency" is what made the detach
> worth trying at all, and the detach ran.
> ⚠⚠ **But one instrument caveat now governs the "0 direct callers" style of claim in this section.**
> **A whole-image rel32 caller scan is a FLOOR even when UNCAPPED**: 44.91 % of `.text` is all-zero in
> `merged4`, and the scan cannot see a *reflected / Blueprint* caller at all. Demonstrated from inside
> S132's own result — `KickPlayersFromPod`'s bytecode has **TWO** `CALLSYS` sites and the scan found
> **ONE**, because the other's AOT body sits on a page that is all-zero in **30 of 30** images.
> ⇒ read "**N** direct callers" here as "**at least N**", never as an enumeration. (The §A conclusions
> do not depend on the count being exact — the argument is that the *known* callers bypass `Func`.)

### B. ★ THE ROUTE: the wall's only persistent COMPONENT-state output is one TArray append

The transcribed success path ends with **`this->PlayersAttached.Add(PS)`** (`+0x130` Data / `+0x138`
Num / `+0x13C` Max) — the only thing it writes on the COMPONENT.
⚠ **Corrected:** the rest is not merely "transient". It **moves the character** (`LokiTeleportActor`
`0x56680F0`, then `SpawnAndMoveLokiCharacter_MoveStep` `0x55C1B20`, collision toggled around them) and
stamps `[hero+0x1C10]` with `GetServerTime`. **Actor position is not transient.** ⚠ `LokiTeleportActor`
is **COVERAGE-BLOCKED** (all-zero page in `merged4`) — not a fold, but its body is unread; and
`SpawnAndMoveLokiCharacter_MoveStep` has **no record and no exec thunk** (a raw native address, a
different risk class, with 2 folds of its own).

And **`ULokiRideableComponent::AuthPlayerDetachPlayerFromRidable`** — impl **`0x55CCCB0`**, thunk
**`0x5456100`**, 440 B, 15 direct calls, **no round-game-mode reference of any kind** — has as **its
only real gate that `PlayersAttached` be non-empty.**

⚠⚠ **CORRECTED after adversarial verification — it is NOT fold-free.** My own uncapped rel32 scan
over its confirmed 9-row `.pdata` extent finds **TWO `0xF7EC20` (`ret 0`) calls, at `0x55CCD5B` and
`0x55CCE4E`**; the first takes the hero character immediately after the `IsA(ALokiHeroCharacter)`
gate, i.e. a stripped method ON THE HERO, not a diagnostic reporter. **"ZERO folds" was wrong;
"zero `0xF7EB50`" is right and is narrower.** Expect a PARTIAL dismount and read a null as locating
one of those two calls, not as a failure of the append. It un-hides the hero, resolves the landing location and places the character.

> ⇒ ★★ **S132: THE TWO-FOLD FINDING IS CORRECT; THE "PARTIAL DISMOUNT" EXPECTATION IT PRODUCED WAS
> TOO PESSIMISTIC, AND IS NOW MEASURED WRONG.** Kept here rather than deleted, because the *reasoning*
> ("a fold on the hero could gut the payload") was the right worry to have — it was answered by
> transcribing the function instead of by flying blind.
> **Why it cost nothing [M]:** `0xF7EC20` is `c2 00 00` = `ret imm16 0`, a **VOID** no-op, and
> **neither fold's return value is ever tested** — FOLD1 (`0x55CCD5B`, on the hero) and FOLD2
> (`0x55CCE4E`, on the PlayerState, args `(PS,3,0)`) are both fire-and-forget side effects sitting
> between real work. **Everything that makes a dismount a dismount is a REAL body:**
> `SetActorEnableCollision(true)` `0x339A550` · `SetPredropHidden(false)` `0x5599040` (byte
> `hero+0x1BE8`) · `GetLokiCharacterMovement` `0x55AC8E0` then `vt[+0x3E0](true)` and `[mv+0x1A0]=1.0f`
> · `GetLandingTeleportLocation` `0x55D89F0` (963 B) · the `SetActorLocation` teleport ·
> `MulticastOnPlayerEnteredWorld` `0x54537C0` · `PlayersAttached.Remove(PS)` `0x11F3860`.
> ⚠ **`0xF7EC20` is NOT "returns zero".** The repo's long-standing `ret 0` shorthand reads that way and
> it is a different claim — it does **not** zero `eax`; it is `ret` with a 0-byte stack pop. That
> distinction is exactly what makes these two folds harmless here.
> ⚠ **Correction to this section's own framing:** `PlayersAttached` is **NOT replicated** [M, two
> disjoint instruments — no `CPF_Net`]. An early S132 write-up called it "a replicated array"; that was
> wrong, and the correction makes the write **safer** than described, not riskier.

⇒ **The dismount is one append away from working, and the append is the exact thing the wall dies
just before doing.**

> ⇒ **S132: TRUE AS WRITTEN. This was the single load-bearing prediction of the whole handoff and it
> landed.** Hero X tracked the flying pod's X at each call time (flight 1: 1,453,041.8 → 4,859,800.1 →
> 11,648,502.8 → 14,428,083.3); run 2's hero Y is **bit-identical** to the pod's on a live read.

### C. THE EXPERIMENT, fully specified. Risk class DATA (measured 0/22).

> ⇒ ★★★★★ **S132: FLOWN, AND THE RECIPE WAS CORRECT AS WRITTEN — INSTRUCTION FOR INSTRUCTION**,
> including the **increment-before-grow** ordering in step 2, which is the one detail a
> from-first-principles rewrite would most likely have got backwards. Risk class DATA held: no `.text`
> write, no PI hook, no CDO poke, and the arm was survivable enough to fire **four** times in one
> window and **three more across three later launches — seven calls in total across four launches,
> six of which moved the hero** (flight 5's call faulted before it could; see the step-1 annotation).
> ⚠ Quote that tally in its own unit: **6 dismounts, 7 calls, 4 launches**, re-derived in
> `docs/s132-dismount-settled.md` §8 from the seven canonical markers in `scratchpad/s132/evidence/`.
> ⚠ That same doc's §6a-2.1 says "**three** landings on three launches, plus the four calls of flight
> 1", which does not reconcile with its own §8 tally. **§8 governs** — it states it was re-derived
> from the markers; §6a-2.1 does not.
> ★ **Why it worked BY CONSTRUCTION and not by luck** — the recipe reuses the game's own
> `ResizeGrow` on the game's own array, so the allocator, the ABI and the element size are the ones
> the wall itself would have used. That is the transferable part: **when you must poke a container,
> mirror the shipped code's own tail rather than hand-supplying a buffer.**
> ⚠ **A within-run NEGATIVE CONTROL ran before EVERY call** — same detach, same component, same
> primitive, with `PlayersAttached` **empty** — and never moved the hero. The prediction was printed by
> the shim *before* each call. Do not drop that pattern; it is what makes "the hero moved" a
> measurement rather than an anecdote.

1. Resolve the pod's `LokiRideable` component **by name** (`BP_DropPod_C.LokiRideable @0x6C8`) and a
   live `ALokiPlayerState`. ★ `scratchpad/s131/tools/rideable_state.py` prints the whole component
   layout by name and is the readout.

   > ⇒ **S132: done as specified.** ⚠ **But GATE 5 is not a clean early-out for a bad PlayerState** —
   > MEASURED arm defect: when no candidate passes it, proceeding anyway **FAULTS**
   > (`GetLokiCharacter` on a *template* PlayerState → `0xC0000005 READ 0xFFFFFFFFFFFFFFFF` at
   > `rva 0x54F8C57`) rather than returning null. **Validate the PlayerState before calling; do not
   > rely on the function to reject it.**
2. **Append PS to `PlayersAttached`, mirroring the wall's own tail exactly:**
   `old=[c+0x138]; [c+0x138]=old+1; if (old+1 > [c+0x13C]) call 0xF988D0(rcx=c+0x130, edx=old);`
   `[[c+0x130] + old*8] = PS`
   ★★ **`0xF988D0` IS THE EXACT FUNCTION THE WALL'S OWN TAIL CALLS — verified: `0x55CD75B call
   0x0F988D0`, the only rel32 call in `0x55CD730..0x55CD7A0`.** So the buffer comes from the GAME's
   allocator and **the ABI and element size are correct BY CONSTRUCTION** — same function, same array,
   same element type. That removes the foreign-pointer hazard a hand-supplied buffer would carry
   (any later `Empty()`/`RemoveAt()` would free it).
   ★ Independently corroborated by disassembly: `0xF988D0` reads `[rcx+8]`=Num and `[rcx+0xC]`=Max,
   with `Max==0 -> 4` then geometric growth (`lea rax,[rbx+rbx*2]; shr rax,3`) — i.e. UE's
   `TArray::ResizeGrow(SizeType OldNum)` with `rcx` = the array. Matches the `{Data@0, Num@8, Max@0xC}`
   layout of `PlayersAttached` at `+0x130`/`+0x138`/`+0x13C` exactly.
   ⚠ **MEASURED LIVE, S131: `PlayersAttached` reads `Data=0, Num=0, Max=0`** — so `ResizeGrow` WILL be
   needed; this is not a pure RPM write and it needs an arm. `0xF988D0` is **not a UFunction**, so the
   S55 thunk primitive does not apply — it is a raw direct call and its ABI must be graded first.

   > ⇒ ★★ **S132: EVERY CLAIM IN THIS STEP HELD.** `ResizeGrow` at `0x00F988D0` was called exactly as
   > written, the buffer came from the game's allocator, and the append landed.
   > ★★★★★ **AND S132 FOUND WHY THE POKE IS THE *ONLY* ROUTE, BY CONSTRUCTION — the reflected writers
   > of both player arrays are EMPTY STUBS.** `AuthAddPlayer` (thunk `0x2C2CE30`, impl `0x0F7EC20`) and
   > `AuthRemovePlayer` (same) are folds, as is `AuthSetCanJump` (thunk `0x5296F30`). ⇒ the obvious
   > shortcut — "just call `AuthAddPlayer` instead of poking" — was **CHECKED, not assumed**, and it is
   > dead. That is also *why* both arrays read `Data=0 Num=0 Max=0` in a fully staged world.
   > ★ **Free property, worth knowing before you poke:** `TArray::Remove` (`0x11F3860`) writes **only
   > `Num`** — no free, no realloc. So the detach never frees a poked buffer, and S132's run-1
   > allocation survived intact into runs 2–4.
3. Call **`AuthPlayerDetachPlayerFromRidable`** via the S55 direct thunk (`0x5456100`), args
   `(ALokiPlayerState*, AActor* LandingActor)`; pass `nullptr` for the second and it defaults to the pod.

   > ⇒ **S132: confirmed in BOTH directions [M].** `UActorComponent`'s owner is at **`+0xB8`**, and the
   > substitution happens at `0x55CCCE5`. Runs 1–2 passed `nullptr`; runs 3–4 passed the pod
   > **explicitly**; all four behaved identically.
   > ★★★★★ **AND THE `LandingActor` ARGUMENT IS REAL — `GetLandingTeleportLocation` CONSUMES IT [M].**
   > Flight 2 passed a `LokiPlayerStart` **1,488,146 uu away** from the pod at that instant, and the
   > hero landed **at the PlayerStart** `(-3206.4, 5070.5, 138.0)`, settled to Z = 90.15 and held
   > position bit-for-bit across 9 s while the pod flew another 180,000 uu. Flight 3 reproduced it.
   > ⇒ **this is a placement primitive, not just an exit** — the successor can choose where the hero
   > lands. ⚠ *How* `GetLandingTeleportLocation` derives the point is still untranscribed (963 B);
   > only "it consumes the actor" is [M].
4. **Receipts:** RPM readback `[c+0x138] == 1` and `[[c+0x130]] == PS` *before* the call; *after*, the
   hero's actor location moves and `SetPredropHidden` un-hides it.
   ⚠ **There is NO log receipt** — the detach is silent (0 log strings in its extent, verified). The
   physical readout is the instrument, so sample the hero's location either side, as `RdState` does.

   > ⇒ **S132: the "no log receipt" warning is CONFIRMED — zero log strings in the 440-byte extent —
   > and it is the right way to run this.** The physical readout carried the whole result.
   > ★★ **AND A BETTER, LOG-FREE, THREE-WAY RECEIPT WAS FOUND: `PlayersAttached.Remove(PS)` at
   > `0x55CCE23` runs on EVERY path past GATE 4.** So after the call, `Num` **dropping 1 → 0** means
   > "ran past GATE 4" and `Num` **staying 1** means "bailed at a gate" — separating the two with no
   > log dependence at all. All six of the function's gates are silent, so this is the only structural
   > discriminator available. **Reuse it.**
   > ⚠⚠ **DO NOT USE `ContainsPlayer` AS THE APPEND RECEIPT — it manufactures a false negative on a
   > working append.** [M] at `0x55D0270` it scans **`PlayersInside` (`+0x120`)**, not
   > `PlayersAttached` (`+0x130`). After a correct append it still reads **FALSE**, and that false is
   > **EXPECTED**. (S131 used it as a *liveness* control on the wall, which is a different and valid
   > job — the trap is only in reading it as an append check.)
5. ⚠⚠ **ORDERING TRAP:** do NOT also poke `PlayersInside` (`+0x120`) first. That makes
   `HasEverContainedPlayer` true, which turns **the wall itself into a SILENT no-op** and destroys the
   error-line receipt any control arm depends on.

   > ⇒ **S132: honoured, and never violated.** `PlayersInside` was left alone throughout. The trap was
   > not re-tested (nothing needed it), so it remains **[I]** — recorded here as a live constraint on
   > any successor that wants both the wall's error line and the detach in one arm.

### D. ⚠ And the honest counterweight: the pod will never self-drive

**`Loki::LokiIsClient` impl `0x00B9E1F0` = `mov al,1; ret` — hardcoded TRUE. `Loki::LokiIsServer` impl
`0x00F7EB60` = `xor al,al; ret` — hardcoded FALSE** [M]. ⇒ `ALokiDropPod::KickPlayersFromPod()`, the
pod's own automatic exit driver — exactly the thing that would iterate `PlayersAttached` and call the
detach — returns immediately, unconditionally. **We must drive the detach ourselves; it will never
fire on its own.** Blast radius: 102 `LokiIsClient` / 100 `LokiIsServer` occurrences across 78 AS files.

> ⇒ **S132: STANDS, and it is exactly what the flight did — the detach was driven by the shim, six
> times, and the pod never initiated one.**
> ⚠⚠ **`KickPlayersFromPod` is also where S132's caller-scan blind spot was demonstrated** (see the §A
> annotation): its bytecode has **TWO** `CALLSYS` sites and the uncapped rel32 scan found **ONE**,
> because the other's AOT body is on a page all-zero in **30 of 30** images. ⇒ **a caller count from
> this class of scan is a floor, never an enumeration.**

### E. IS THE DROP PATH BOUNDED? — YES, AND IT IS NOT SPECIALLY TARGETED [M]

Full `.data` record-table census, **16,277 records**, 12/12 non-degenerate controls passing
(`scratchpad/s131/lane-d-empty-impl-census.tsv`):

| verdict | records | % |
|---|---:|---:|
| REAL | 11,517 | 70.76 % |
| IMPL-PAGE-DARK (coverage-blocked) | 3,092 | 19.00 % |
| FORWARDER | 1,153 | 7.08 % |
| **EMPTY** | **515** | **3.16 %** (4.28 % of gradeable) |

* ★★ **A FIFTH FOLD EXISTS AND WAS NEVER ENUMERATED: `0x00FC6CF0` = `0f 57 c0 c3` =
  `xorps xmm0,xmm0; ret` → 0.0f**, 13 records — including six `ALokiPlayerState` float getters.
  **Any census graded against only the four known folds under-counts and misses gameplay-authoritative
  stubs.** Add it to the fold table.
* ⚠⚠ **FK-1's "1.2 % (78/6,669)" does NOT survive — it is a UNIT artifact, not an error.** FK-1
  counted *distinct exec thunks*, and thunks are heavily ICF-folded (`0x5254180` alone is the
  registered thunk of 92 records). Per-record the rate is **3.16 %**; in FK-1's own unit it is **170**,
  not 78. **FK-1's conclusion — that an empty impl is informative, not ambient — STANDS.**
* ★★★ **THE ENRICHED CATEGORY IS `Auth*`, NOT "drop".** `Auth*` gradeable **67/158 = 42.4 %** empty
  vs non-`Auth` Loki **260/3,133 = 8.30 %**, Fisher **p = 1.6e-28**, spread over 41 classes. And it is
  the naming convention, not the reflection flag (`Auth*`-but-not-`BlueprintAuthorityOnly` is still
  **44/108 = 40.7 %** gradeable; `Auth*`+BAO is 23/50 = 46.0 %).
  ⚠ The first published figure for that decomposition was **32.8 %** — its denominator mixed
  *gradeable* with *all records*. The correction STRENGTHENS the finding. Against the **fair** control — the rest of the Loki-owned table — the drop-8 classes are
  **14.6 % vs 9.83 %, p = 0.11, NOT SIGNIFICANT.**
  ⇒ **There was no decision to remove *deploy*. There was one decision to remove *server authority*,
  and deploy is inside it like everything else.**
* **~23 empty native stubs on the immediate deploy chain, enumerated per-record**, and **almost every
  one is a pure state mutation on a replicated property, not a computation** — i.e. substitutable by
  this project's safest write class. The two that are not: `ALokiGameMode::SpawnPlayer` (returns a
  pawn) and `AuthBeginGlideDiveFromDropPod` (starts a movement mode).
* ⚠ **Unbounded for GAMEPLAY**: the same cut takes all 6 `GatherMovement`, 11 `Add*Stat`,
  `ALokiBaseItem` (23), `ALokiProjectile` (8), `ALokiMinionCharacter` (9), `ALokiTower` (7) — roughly
  200 reimplementations across 40+ classes with no reference implementation.
* ⚠ **The census is blind to Angelscript entirely** (0 records for `ALokiDropShip` / `ALokiDropPod`),
  so it says nothing about the AS half — which is where the *working* half of the drop path lives.
  Whether AS supplies an alternate route around each of the 23 stubs is what decides whether 23 is the
  real number or an over-count.

### E2. ⚠⚠ ONE LANE'S HEADLINE FIND IS REFUTED — do not chase `[RideableComponent + 0xE0]`

Lane A (`scratchpad/s131/lanes2/r04-*.md`) bills as *"the lane's most consequential find"* that
`0x55CE140` caches a round game mode at **`ULokiRideableComponent + 0xE0`**, and proposes reading it
as a free check. **REFUTED live, and following it would have you reading a delegate.**

**[M] `+0xE0` is `OnPlayersInsideCountChanged`, a 16-byte MulticastInlineDelegateProperty** — read BY
NAME off the live class (`scratchpad/s131/tools/rideable_state.py`), and independently assigned the
same offset by lane E from `OnRep_PlayersInsideCount` (`0x55E0FC6`). A raw read of `+0xD8..+0xF0` on
**all three** live rideable components returns **all zeros**.

Where it went wrong: the disassembly is correct, the **class attribution** is not. Lane A reached
`ULokiRideableComponent` from a vtable-boundary walk it flagged in the same paragraph as UNRESOLVED
("it reported 3142 slots, which is nonsense") and graded `[I, strong]` — then stated the consequence
as `[M]`. **A grade upgraded silently across one inference step.**

What survives: **[M] some unstripped `UActorComponent` lifecycle override does resolve
`World->AuthorityGameMode`, `IsA<ALokiRoundGameMode>`-check it, and cache it.** That corroborates
`UWorld+0x250` and shows the type check is unstripped. ⛔ It cannot help the wall — a getter with
**zero memory operands** cannot be fed a cached value from anywhere.
★★★★★ **RESOLVED, AND THE ANSWER IS BETTER THAN THE DISPUTE.** A second lane attributed
`0x55CE140` to **`ULokiGameModeDropPlaneComponent`**, and **one live read confirms it**:
```
Comp_GameMode_DropPlane_Tutorial 0x2BDBAA38680
  +0xC0 WorldPrivate            = 0x2BCD33540C0 'LVL_Tutorial'
  World+0x250 AuthorityGameMode = 0x2BD2D0BC020 'BP_LokiGameMode_Tutorial_C'
  World+0x258 GameState         = 0x2BDB251D030 'BP_LokiGameState_Tutorial_C'  <= control
  +0xE0                         = 0x2BD2D0BC020 'BP_LokiGameMode_Tutorial_C'   <= IDENTICAL
```
[M] **(1)** the class is `ULokiGameModeDropPlaneComponent`; **(2)** `UWorld::AuthorityGameMode @
+0x250` confirmed live with `+0x258 = GameState` as the control; **(3)** the round game mode object
EXISTS and is live (`BP_LokiGameMode_Tutorial_C`, the same object S124 flew `GoToPhase` on);
**(4) ★★★ it PASSES `IsA<ALokiRoundGameMode>`** — the caching code writes `+0xE0` only on the
success side of that check, using **the same helper `0x55C7DD0` the wall calls**. That was never
measured before.
⇒ **If the stripped getter had returned this object, the wall's own IsA check would have passed
too.** The obstacle is the accessor and nothing else on that stretch. ⛔ It still cannot be injected
(zero memory operands), but the framing changes: not "no round game mode on a client", but **"one
accessor was deleted while the object and the type check survive"**.
★ So the free readback IS real, on the right object: **`Comp_GameMode_DropPlane_Tutorial + 0xE0`**
is a live, verified `ALokiRoundGameMode*` for any future call site that consumes one.

★★ **METHOD, and it generalises:** two lanes were given the same region and disagreed about one
offset. The disagreement was visible only because **both printed the offset explicitly**, and it was
settled in one command by a third instrument (live reflection, read by name) rather than by preferring
the more confident write-up. **Ask two agents the same structural question and diff their offsets.**

### F. Corrections to the record that fell out of this

* **`GetLandingTeleportLocation` is REAL** (`0x55D89F0`, 963 B, 0 folds). FK-22 §2.5 lists it
  COVERAGE-BLOCKED — now resolved, exactly as lane 4 predicted the record table would.
  > ⇒ ★★ **S132 upgraded this from "REAL" to "REAL and it WORKS"**: the detach calls it, and it
  > **consumes its `LandingLocationActor` argument** [M] — flight 2's hero landed at a `LokiPlayerStart`
  > 1,488,146 uu from the pod. ⚠ Still untranscribed: *how* it derives the point from the actor.
* `AuthPlayerPreSpawnOnAddToPlane` (`0x55CD800`, 496 B) is REAL with **1** fold call — same wall, third
  instance (and S131 measured it failing live).
* **`AuthPlayerEnterWorld` is WORSE, not better**: **3** `0xF7EB50` calls; it does not bail on the
  null, it stashes it and passes it as `this` to two further stripped methods.
* **`UWorld::AuthorityGameMode @ UWorld+0x250`** [M], from `UGameplayStatics::GetGameMode` impl
  `0x37D7BF0`, with `GetGameState` → `+0x258` as the positive control in the same pass. The round game
  mode object EXISTS and is reachable — only the accessor was deleted. Moot for this wall (dead value).
* ★ `ULokiBlueprintLibrary::GetLokiGameMode` (`0x5630970`) is the **smoking gun**: the world fetch
  survived and the return was zeroed (`call get-world; xor eax,eax; ret`), so it did NOT fold onto
  `0xF7EB50` and is still identifiable. Its twin `GetLokiGameState` is fully REAL.

---

## A1 (ARCHIVE). ⛔ DEAD — the record of a lever that was killed. See §0.5. Do not run this.

> ⇒ **S132: UNCHANGED AND STILL DEAD.** Not attempted, not re-tested, and nothing this session bears
> on it. Its precondition (a live `ALokiTeamState_TeamOnly` to poke) is still unmet.
> ★ It is also now **moot for the dismount specifically**: S132 reached the hero-out-of-pod state
> without a drop leader, a pilot PlayerState, or `GetTeamDropLeader` ever returning non-null. Kept as
> the record of a lever that read as obvious and was killed by one read-only command.

Everything downstream of the pod now hinges on one null:

```
v38 = this.GetTeamDropLeader(TeamIndex)          -> null
  -> SetPilotPlayerState(null) ; SetOwner(null)   (both null->null, no information)
  -> RemovePlayerFromPlane(null)                  (empty stub anyway)
  -> AuthPlayerEnterWorldAttachedToRidable(null, Landing)
        0x55CD510  test rdx,rdx ; je <ret>        <-- SILENT RETURN, instruction #1
  -> MulticastOnDropPodLaunched                   SKIPPED (guarded on v38 != null)
```

**Why it is null, [M]:** `GetTeamDropLeader` returns the first PlayerState on the team with
`IsSpawnTeamLeader()` true. `ALokiPlayerState::IsSpawnTeamLeader` (impl **`0x56C2060`**, real,
decrypted in all three images) is a **pure read**: `GetWorld()` → `edx = [this+0xE88]` (team id) →
`GetTeamState` (`0x56F02E0`) → `rcx = [TeamState+0x688]` → resolve (`0x3259330`) → `sete al` on
`== this`. **The only writer of `[TeamState+0x688]` is `ALokiTeamState_TeamOnly::SetDropLeader`,
which is one of FK-1's four EMPTY STUBS** (`impl 0x0F7EC20 = ret 0`), as is
`ALokiPlayerState::AuthSetSpawnTeamLeader`. **Nothing on this client can set a drop leader.**

### 1.1 THE LEVER

**Poke `[TeamState+0x688] = <a live ALokiPlayerState*>`** on the live `ALokiTeamState_TeamOnly`, then
call `SpawnDropPodForTeam` again.

* Same write class as S130's CDO poke: **one aligned heap field, readback-verifiable, no module image
  touched.** On this project's hazard ladder that is the safest change there is.
* It **bypasses both empty stubs** rather than trying to make them work.
* The hero's `ALokiPlayerState` already exists in a staged world (`sp` possesses a hero), so a valid
  pointer is available — resolve it BY NAME off the PlayerController, do not hardcode.

### 1.2 WHAT IT BUYS, AND HOW TO READ IT

With a non-null drop leader, ALL of these become live for the first time:

| what | receipt |
|---|---|
| `SetPilotPlayerState` / `SetOwner` | `PilotPlayerState @0x3C0` and `Owner @0x150` become **non-null** — two fields that were null→null in S131 and carried no information |
| **the FIFTH WALL** | `AuthPlayerEnterWorldAttachedToRidable` passes its `test rdx,rdx` and reaches the round-game-mode lookup. ★ **`grep "failed to get the round game mode"` becomes INTERPRETABLE** — the emit is [M] not stripped (dispatches through the live logger `0x106B650`) |
| `MulticastOnDropPodLaunched` | its `if (v38 != null)` guard opens |
| `QueueCrewForPodSpawn` | `AttachedCrewPods @0x490` `Num > 0` would mean `GetPlayerStatesOnTeam` returned live PlayerStates |

⚠ **Pre-register the reading of a null result.** If `PilotPlayerState` still reads null after the
poke, that says `GetTeamDropLeader`'s scan did not accept the poked value — read `[this+0xE88]` (the
PlayerState's team id) and confirm it matches the TeamState you poked. Do NOT record it as "the wall
held" without that check.

### 1.3 SMALL PROBE UPGRADES WORTH MAKING FIRST (cheap, offline)

> ⇒ ⚠ **S132: ALL THREE DELIBERATELY DEFERRED. NOT AN OVERSIGHT — a decision, and the reason
> generalises.** `PdPodDump()` is compiled into the **shared** `tutorial_launch.cpp`, so touching it
> moves **`droppod-pe-cdopoke`'s `.text` hash** — and that arm is a **PRECONDITION of the dismount
> flight** (it is what puts a live, initialised pod in the world). Editing the probe would have forced
> a re-verification of the staging chain before the experiment could even start.
> ⇒ ★ **When a diagnostic lives in the same translation unit as a staging precondition, "one more read"
> is not free — it invalidates the precondition's hash.** Gate new reads on `kRunMode`, or land them in
> a session that is not depending on that arm. (S131 already recorded this pattern from the opposite
> direction: an **ungated** `strstr` in `DpEvalClass` moved `b1only`'s hash while its `.text` **size**
> stayed identical.) These three remain worth doing — they are unstarted, not refuted.

1. ★★ **Add the two-sided bool control** the S131 audit asked for and I could not land in time:
   `bHidden` and `bAlwaysRelevant` must **both** resolve to `Offset_Internal 0x68` with **ByteMask
   `0x80` and `0x08`** respectively. Same offset, different mask ⇒ unfalsifiable by garbage, and it
   turns the `FBOOLPROP_*` layout from **[I]** to **[M]** in-arm. (S131 measured every bool as
   `fs=1 bo=0 bm=0x01 fm=0xFF`, which is consistent but has no two-sided check behind it.)

   > ⇒ ★★ **S132 SETTLED THIS OFFLINE, and one instruction in it is WRONG AS WRITTEN.**
   > **The PREDICTED VALUES ARE CONFIRMED EXACTLY** — `bHidden` → offset `0x68` / mask `0x80`,
   > `bAlwaysRelevant` → offset `0x68` / mask `0x08`. The two-sided control is sound and should be
   > built.
   > ⚠⚠ **BUT NOT FROM `FBoolPropertyParams`.** This item asks for the decode to come from the UHT
   > record, and **that record carries NO `ByteOffset`, `ByteMask` or `FieldMask` field at all** — the
   > information simply is not in it. ⇒ **the shim must read LIVE `FBoolProperty` objects at
   > `+0x70..+0x73`.** Anyone implementing item 1 from the sentence above will look for fields that do
   > not exist and may read adjacent bytes as if they did. (This is why the values are quoted here as
   > the *target*, not as the *source*.)
2. Add **`AttachedCrewPods` (0x490)** as an explicit named field — it is `QueueCrewForPodSpawn`'s
   receipt, i.e. the LAST thing `InitializeDropPod` does, and S131 only saw it via the sweep.
3. Add **`ComponentVelocity`** to the location line. S131 had to take it by external RPM afterwards;
   in-arm it is one more read and it is what named the mover.

---

## 2. THE OTHER HALF OF §28.5 — "or carries a player"

Even with a drop leader, the pod carrying a *hero* runs into
`ULokiRideableComponent::AuthPlayerEnterWorldAttachedToRidable`'s **always-fail** body (S130 §26,
independently re-confirmed by S131 lane 4's `.data` record sweep: impl `0x55CD510`, REAL).

⚠ But S131 lane 4 also resolved the rest of that family for the first time, out of `.data`, **without
the code pages being decrypted** — and it found a NEW empty stub:

| key | impl | verdict |
|---|---|---|
| `AuthPlayerDetachPlayerFromRidable` | `0x55CCCB0` | REAL |
| `AuthPlayerEnterWorld` | `0x55CCE70` | **REAL** — large body, security cookie |
| `AuthPlayerEnterWorldAttachedToRidable` | `0x55CD510` | REAL (always-fail) |
| **`AuthPlayerEnterWorldNew`** | **`0x0F7EC20`** | **EMPTY — new, raises the drop-class empty count 13 → 14** |
| `AuthPlayerPreSpawnOnAddToPlane` | `0x55CD800` | REAL |
| `ContainsPlayer` | `0x55D0270` | REAL |
| `GetLandingTeleportLocation` | `0x55D89F0` | REAL |

> ⇒ ★★★★★ **S132 EXTENDED THIS TABLE — THERE ARE FOUR EMPTY `Auth*` STUBS ON THIS CLASS, NOT ONE
> [M, strong].** The three new rows:
>
> | key | thunk | impl | verdict |
> |---|---|---|---|
> | **`AuthAddPlayer`** | `0x2C2CE30` (⚠ **23-way ICF — NON-IDENTIFYING**) | `0x0F7EC20` | **EMPTY — new** |
> | **`AuthRemovePlayer`** | `0x2C2CE30` (same folded thunk) | `0x0F7EC20` | **EMPTY — new** |
> | **`AuthSetCanJump`** | `0x5296F30` | `0x0F7EC20` | **EMPTY — new** |
>
> ⇒ **THE ONLY REFLECTED WRITERS OF EITHER PLAYER ARRAY DO NOTHING IN THIS CLIENT.** That is the
> mechanism behind `PlayersInside` and `PlayersAttached` both reading `Data=0 Num=0 Max=0` in a fully
> staged world, and it is *why* a data poke is the only route **by construction** — not merely the
> cheapest one. ⚠ It also means the obvious shortcut ("skip the poke, call `AuthAddPlayer`") is dead;
> S132 **checked it rather than assuming it.**
> ★ Also REAL on this class and now named: `ContainsPlayer` `0x55D0270` · `HasEverContainedPlayer`
> `0x55DCAA0` · `GetRidePosition` `0x55DAB50`.

★ **`AuthPlayerEnterWorld` (`0x55CCE70`) is REAL and has never been called.** It is the obvious
sibling to try if the attached-to-ridable variant stays foreclosed.

> ⇒ ⛔ **S132: FORECLOSED [M] — do not spend an arm on it.** Its **two terminal actions are direct
> calls to the stripped `0xF7EB50`**, and it writes **no actor or component transform** of any kind. It
> cannot dismount anything. (S131 had already measured it dispatching with no fault, no log line and no
> hero movement — "a NAMED GAP, not a negative". The gap is now closed and the answer is negative.)
> ⇒ **The detach (`0x55CCCB0`) was the right sibling, and it is the one that works.**

Full table: `scratchpad/s131/lane4-record-sweep.md` (**7/7 non-degenerate controls PASS**, 4 EMPTY +
3 REAL, separated correctly). ⚠ Its stated blind spot governs: **for a `Net` key the record's impl is
the UHT send stub, not the `_Implementation`** — never grade an RPC from that table alone.

---

## 3. ⛔ FK-31 — THE KILL-ADDRESS EXPERIMENT IS DEAD, BUT THE TARGET IS NAMED

**Read `scratchpad/s131/evidence/FK31-kill-address-is-constant.md` — §7 GOVERNS THAT FILE.**

[M] The kill jumps to **`runtime.dll + 1`**. One live `VirtualQueryEx` on the S131 client reports the
page as **`MEM_COMMIT / READONLY / MEM_IMAGE`, `AllocationBase == the address itself`**, and at that
base sit **`MZ`**, a valid `PE`, `SizeOfImage 0x4066000`, and 11 sections named
`.pdata .rwx packer0 packer1 packer2 .rsrc .reloc packer30 packer40 packer31 packer42` — exactly
FK-10's recorded layout for `runtime.dll`. `(Get-Process).Modules` reports **no module at that base**,
so it is **manually mapped and hidden**, which is why it never appears in a minidump.

⇒ **The kill is a deliberate jump into the protector's own read-only DOS header** — the page being
READONLY is exactly why the fault is an EXECUTE violation. **This VINDICATES CLAUDE.md's
`RIP == runtime.dll base + 1` rule and measures it live for the first time**, and it explains the
per-boot constancy (the protector maps itself at a per-boot-stable base).

⛔ **The "map an executable page there" experiment is DEAD** — the page is already committed.
`scratchpad/s131/tools/fk31_map_kill_page.py` is read-only by default and refuses to `--commit`
unless the page is genuinely FREE.

★ **REPLACEMENT LEAD, purely offline and unstarted:** FK-10 established `runtime.dll` is NOT packed
(46.6 MB of plaintext x86-64; loader function table at RVA `0x14D8758`, 18,580 entries). **Search it
for code that computes its own image base + 1 and jumps there.** That lands on the routine that
decides to kill — what FK-10's Wall #7 has been hunting. Start in `packer30` (2.2 MB,
`call`-structured, holds the entry function).

> ⇒ ⚠⚠ **S132 RAN THIS LEAD (offline lane 6) AND THE PROPOSED METHOD IS DEFEATED. Do not re-run it as
> written.** The kill routine was **not** found, and the reason is a hard instrument limit, not a lack
> of effort.
> **[M] `runtime.dll` ImageBase == `0x200000000` == 2^33.** ⇒ **every "is this constant the ImageBase?"
> test is ALIASED with ordinary MBA arithmetic on bit 33** — and MBA is 43 % of this binary's
> instructions. The search cannot distinguish a base computation from routine obfuscation noise. All
> **13** candidate `movabs ±(ImageBase + 1)` sites were individually refuted by their consuming
> instruction. ⇒ ★ **a constant-search plan must first check whether its constant is degenerate
> against the target's arithmetic.**
> ★★ **AND THE ARCHITECTURE MAY EXPLAIN THE FAULT SHAPE ANYWAY — the architecture is [M], the
> explanation of the fault shape is [I]:** the protector uses **computed tail
> jumps** — **4,769 of 18,580** functions end in `jmp <reg>`, with targets carried as
> `movabs reg, -(ImageBase + RVA)` folded into an MBA polynomial. ⇒ **[I]** a jump to `base + 1` is the
> **native output shape of that dispatch** when the resolved target RVA is 1 — i.e. the kill may be a
> *resolution* result, not a hand-written `jmp base+1`.
> ★★★ **WHAT LANE 6 DID BANK — the next thing to read, and it is free:** FK-10's kill primitive was
> re-verified byte-exact (RVA `0x80F7F0` = `NtTerminateProcess([this+0x10], 0xDEAD)`) **and its OWNER
> was found** — it is **slot 4 of a 5-method vtable at `packer0` RVA `0x1831C0`**, installed by a
> **constructor at RVA `0x7F86F0`**, which is that table's **only xref image-wide.**
> **⇒ READ `0x7F86F0` NEXT.**
> ⚠ Reported with its denominator, not as a bare negative: **48,129,536 executable bytes scanned**
> (`.rwx` + `packer1` + `packer30` + `packer31`), blind spots enumerated.
> ★ Binary located and identity-confirmed at `G:\git\GAME BACKUPS FOR REVERSE ENGINEERING\SUPERVIVE\
> Loki\Binaries\Win64\runtime.dll` — 67,511,496 B, ImageBase `0x200000000`, `SizeOfImage 0x4066000`,
> with FK-10's `packer/3.3.1` Sentry DSN byte-identical at its recorded file offset `0x7C1BEC`.

⚠⚠ **And note how that correction happened:** the whole kill-address write-up came from ONE
instrument (minidumps), whose module list is blind to manually-mapped images BY DESIGN. A single
query from a different instrument refuted two of its claims within the hour — and it was only run
because a lever's precondition was being checked before an arm was built.
## 4. HOW TO RUN IT (S131's sequence, which worked)

1. `forceTutorialMatch = true` in `server/internal/interactive/interactive.go`, rebuild `ags`.
   **Set it back to `false` when done** — it is committed as `false`.
2. Back up `docs/capture.log` (its restart behaviour is recorded as both truncating and appending).
3. Elevated: `.\configs\launch-redirect.ps1 -NoHook`
4. `.\configs\fk24-stage.ps1 -Probe <arm> -Label <tag> -AllowStale`
   ⚠ **`-AllowStale` is REQUIRED.** The deployed `fo fa184b20934cc4b0` / `sp 4285c0dd22ae9976` in
   `tools/sigbypass-mod/` (NOT `build/`) are the known-good staging pair; both verified this session.
5. Into the SAME live PID, ≥20 s apart:
   `tools\inject\inject.exe mmap <pid> tools\sigbypass-mod\build\tutorial_launch_dropplane_b1only.dll`
   then your Route-E arm.
6. **Copy the marker off after every injection** — `RM_DROPPLANE` and each probe overwrite it.
7. ★ **While the client is still alive**: take external RPM reads
   (`scratchpad/s131/tools/pod_live_read.py`) and run `usmapdump dumpimage` — S131's dump added
   **+43 `.text` pages, 0 conflicts** to `dumps/merged3.dump.exe`.

⚠⚠ **A STAGER ABORT IS NOT A DEAD LAUNCH.** S131's launch 2 timed out on
`LVL_Tutorial load complete` because the **lobby map took 146 s to load** and `fo`'s console command
fired mid-`LoadMap`. The process was healthy; re-running `fk24-stage.ps1` on the same PID produced
the entire session's result. **Check `Get-Process` before spending another launch.**

⚠ Budget: S131 spent **2 launches for 1 armed window** (launch 1 died to FK-31 at `fo`+15 s). But the
armed window then lasted **>25 minutes** with the client alive throughout.

> ⇒ **S132: this sequence was followed and it worked — three armed windows, flights 1–3.** The
> `-AllowStale` requirement and the "copy the marker off after every injection" rule both held.
> ⚠ **Two deaths, NEITHER caused by the dismount:**
> * one **`0x0000DEAD` protector kill (FK-32)** during `play-atlanding` init, on the **7th** injection
>   into a single process. ⇒ that sitting is **VOID for the playability question, not a negative
>   result** — the arm never initialised.
> * one **`0xC0000005` FK-31 staging death** with only `gft`+`fo` resident. ★ **crashwatch DID catch
>   it** and a 41 MB crashpad minidump was archived to `dumps/crashpad-20260820-143225`.
>   ⚠⚠ **Its image reads `.text` 51.8 % vs a healthy 53.0 %, which LOOKS like a refutation of "a
>   crash-era image holds more decrypted `.text`" — it is NOT.** The comparison is **not matched**: it
>   died at 141 s having exercised far less game code than a staged run. **It does not test that
>   hypothesis in either direction.** Do not cite it as evidence.
> ★ **[I] Injection count may itself be a hazard variable.** S111 measured that *injection at all*
> causes deaths (25/90 injected arms vs **0/11** `-NoHook`) and S109 measured that injection *spacing*
> matters — but **no count-dependence has ever been measured**, so seven injections into one PID is
> only "more than this project usually does", not a threshold. Treat it as a budgeting heuristic:
> if a window is going to carry many arms, expect to lose the tail of it rather than reading a late
> death as a result.

---

## 5. REPO STATE

- ✅ Tree clean, everything committed. `forceTutorialMatch` is committed as **`false`**.
- **Build arms (`.text` sha256; `-Name tutorial_launch` must be given explicitly — `-Variant X` alone
  silently builds the DEFAULT set and reports success):**

| variant | `.text` | note |
|---|---|---|
| `droppod-pe-cdopoke` | `249a3cd2190eb334` | Route E + poke — **what S131 flew** |
| `droppod-pe-cdoctrl` | `61fd0745c23e89f0` | same, read-only CDOs |
| `poolspawn-cdopoke` | `efe8db553bf511ba` | the negative-control population |
| `poolspawn-cdoctrl` | `85f3cee44c31b1cd` | same, read-only CDOs |
| `dropplane_b1only` | `5b4467b0105dec1a` | **UNCHANGED** — Route E's precondition |
| `play` | `9bc10a4552c596e1` | **UNCHANGED** — hard regression gate |

> ⇒ **S132: ALL THREE REGRESSION GATES MATCHED THROUGHOUT** — `play` `9bc10a4552c596e1`,
> `dropplane_b1only` `5b4467b0105dec1a`, `droppod-pe-cdopoke` `249a3cd2190eb334`. That is what the
> §1.3 deferral was protecting (see the annotation there).
> **New arms S132 added:**
>
> | variant | `.text` | note |
> |---|---|---|
> | `dismount` | `03d807ab6d397537` | **the FLIGHT-1 artifact** — reproduce from commit `c2cdc56` |
> | `dismount` (HEAD) | `53483e6181bb3583` | HEAD has moved on since the flight |
> | `dismount-landstart` | `0d5fa554edac53c5` | **the FLIGHT-2/3 artifact** — passes a `LokiPlayerStart` |
> | `play-atlanding` | `0e816d359e5d09c5` | ⚠ **DEGENERATE — do not use** (see §6) |
> | `play-atlanding-walk` | `944a27728053359e` | ⚠ **UNFLOWN** — the arm that can actually answer playability |
>
> ⚠⚠ **`dismount`'s flown hash is NOT its HEAD hash.** To reproduce flight 1 exactly you must build
> from **`c2cdc56`**, not from HEAD. **Diff the hash, never the size** — the rule this file already
> states, applied to its own successor's artifacts.
> ★ **New cold image: `dumps/merged5.dump.exe`** = `merged4` + two live S132 dumps, **+6 `.text`
> pages, 0 conflicts.**

  ⚠ Each pair shares a `.text` **size**; only the hash separates them. Both verified DISTINCT.
  ⚠⚠ The new census latches are gated on `kRunMode` **precisely so the last two stay byte-identical**.
  An **ungated** `strstr` in the shared `DpEvalClass` moved `b1only`'s hash while leaving its `.text`
  size identical (120,832 B both ways — it fitted in section padding). **Diff the hash, never the size.**
- **New tools:** `scratchpad/s131/tools/` — `pod_live_read.py` (read-only RPM of a pod's fields),
  `pod_verdict.py` (evaluates a marker against the pre-registration), `rectab.py` / `lane4_sweep.py`
  (the `.data` record sweep).
  ⚠⚠ `pod_verdict.py` shipped a regex with ONE space where the probe prints `@0x%-4X` and reported
  **`UNINTERPRETABLE (nothing resolved)` for pods whose values were plainly in the log.** Fixed and
  documented in-file. **An analysis script is an instrument too — read the raw artifact beside it.**
- **New cold image:** `dumps/merged3.dump.exe` — strict superset of `merged2`, +43 `.text` pages from
  the live drop-pod process.
- 12 offline recon reports in `scratchpad/s131/lanes/` (6 lanes + 6 adversarial verifications).

---

## 6. WHERE FK-22 STANDS

```
markers        REFUTED  (S124)
phase          SOLVED   (S124)
subscription   DEAD     (S124)
SpawnPlane     FAULTS   (S124/S17) -- b1only still creates a live LokiDropShip
SpawnDropPodForTeam  ->  RETURNS TRUE, pod spawns                       FIXED    S130
  |
  +- InitializeDropPod RAN, 3/3 writes landed                           MEASURED S131
  +- the pod is ALIVE: 18 components, Niagara VFX ticking, engine
  |    logging LWC recaches, flying at its cooked 20,000 uu/s           MEASURED S131
  |    (it flies BECAUSE StartPodGameplay never ran -- LokiIsServer
  |     is a stripped `return false`)
  +- the RIDER HANDOFF fails, and the wall is CONFIRMED live            MEASURED S131
  |    one shared stripped round-game-mode getter, three consumers
  +- BUT the value it fetches is DEAD (zero RAX reads downstream), and
  |    its only persistent COMPONENT-state output is one TArray append  MEASURED S131
  +- NEXT: append PS to PlayersAttached (+0x130) with the game's own
  |    ResizeGrow, then call AuthPlayerDetachPlayerFromRidable          <-- DONE, S132: IT RUNS
  |    (0x55CCCB0 / thunk 0x5456100) -- REAL, 0 folds, gate = that array
  |    (^ "0 folds" is wrong -- 2 VOID folds, and they cost nothing)
  +- the pod will NEVER self-drive: KickPlayersFromPod returns at once
  |    because LokiIsClient is hardcoded true / LokiIsServer false
  +- C8 / C9 still never fired: unexercised, NOT excluded
```

> ⇒ **S132 ADVANCES THIS LADDER BY ONE RUNG. Current state:**
> ```
>   +- THE DISMOUNT RUNS AND IS USABLE                                    MEASURED S132
>   |    hero un-hidden, collision restored, movement restored,
>   |    teleported to a CHOSEN landing actor (LokiPlayerStart, 1.49 Muu
>   |    from the pod) -- and handed back to physics
>   |    6 dismounts / 3 flights; within-run negative control every time
>   +- the ONLY writers of either player array are EMPTY stubs
>   |    (AuthAddPlayer / AuthRemovePlayer / AuthSetCanJump) -- so the
>   |    data poke is the only route BY CONSTRUCTION, not by preference
>   +- NEXT: is the hero PLAYABLE at the landing point?          <-- YOU ARE HERE
>        OPEN. `play-atlanding` is DEGENERATE and does not answer it.
> ```
> ⚠⚠ **THE PLAYABILITY ARM IS DEGENERATE — do not read its output as a result.** `RM_PLAY` relocates
> the hero first (hardcoded teleport to `(-65,-1770,393)`, `tutorial_launch.cpp:4822-4830`, applied
> `:12315`), and with that skipped via `KNOTELE=1` **`KFLYMODE` still defaults to `5 = MOVE_Flying`**,
> so the hero **hovers**. MEASURED: the control moved **2,926 uu at CONSTANT Z = 13,240** — 13 km
> through mid-air. **Only `play-atlanding-walk` (`-DKFLYMODE=1`, `.text 944a27728053359e`) can answer
> the question, and it has not been flown.**

**Bounded?** For deploy, yes: ~23 empty native stubs, enumerated per-record, and almost all are pure
state mutations substitutable by a data poke. For gameplay, no: ~200 across 40+ classes. And the
census is blind to the Angelscript half, which is where the working half lives.

> ⇒ **S132: unchanged and still the right framing.** The dismount is one more instance of the pattern
> it describes — an empty server-authority stub substituted by a data write — and it cost one array
> append. ⚠ It is **not** evidence that the remaining ~22 will be as cheap; each still needs its own
> transcription. ⇒ **Continue at `docs/next-session-prompt-s133.md`.**
