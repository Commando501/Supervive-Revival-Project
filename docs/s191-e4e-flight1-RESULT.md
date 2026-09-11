# S191 E4 Option E — Flight 1 [M] GATE-MODEL REFUTED + STRUCTURAL BOUND ON WALL P — 2026-09-10

★★★★★★★ **DIRECT-OFFSET POKE OF `spec.NonReplicatedInstances` IS INSUFFICIENT TO UNBLOCK
`GetAbilityByInputID(3)`. The workflow's 3-gate model at `RVA 0x44C28E0` is INCOMPLETE — a further
gate exists beyond `NonRep.Num > 0`. E4E is NON-LETHAL and non-crashy; the write class (aligned qword
+ two aligned dwords on the K_GRANT'd spec, A→B→A restored) is now measured safe.**

Design provenance: multi-agent adjudicated spec (16 refutations all VALID + adopted). Grade:
**Outcome CLEAN-REFUSE with a new structural signal.** ⚠ This REFUTES the workflow's headline
mechanism claim ("`spec+0x80 <- spec+0x10, Num=1, Max=1` unblocks the 3-gate filter") on live
byte-verified evidence — the poke lands exactly as designed and the readback stays NULL.

Session cost: **1 launch, 0 losses.** First-try flight success (no FK-31 staging).

## The chain, verbatim

`docs/s191-e4e-flight1-marker.log` (last 10 E4E lines):

```
[E4E] pre-poke: pASC=0x1C2AAB80100(LokiAbilitySystemComponent) minionPreHP=100.00
[E4E] Items header: Data=0x1C27ADB4ED0 Num=1 Max=4 stride=0xF8 target InputID=3
[E4E] Items[0] @0x1C27ADB4ED0 Handle=1 InputID=3 Ability=0x1C28E636930(GS_Ronin_LMB_Selector_C)
[E4E] target spec[0] @0x1C27ADB4ED0 Handle=1 Ability=0x1C28E636930 InstancePolicy@+0xEE=0x01 (InstancedPerActor OK) ; preNonRep Data=0x0 Num=0 Max=0
[E4E] E4E_READBACK_PRE resolved=yes faulted=no return=0x0 (NULL -- R-S191-h baseline confirmed live; ready to poke)
[E4E] E4E_POKE_ISSUE spec+0x80 <- 0x1C27ADB4EE0 (spec+0x10 game-heap self-ref) ; spec+0x88 <- 1 ; spec+0x8C <- 1 ; pre snapshot preserved for A->B->A restore
[E4E] E4E_POKE_VERIFY Data=0x1C27ADB4EE0 Num=1 Max=1 OK
[E4E] E4E_READBACK_POST faulted=no return=0x0(NULL) still NULL -- 3-gate model INCOMPLETE (a further gate exists beyond NonRep.Num>0 OR gate (b) instPolicy actually failed)
[E4E] E4E_RESTORE Data=0x0 Num=0 Max=0 OK (pre-poke state re-established)
[E4] E4_COMPLETE RESULT=TARGET_READY
```

## Gate-by-gate verdict — every workflow assumption tested against a live datum

| gate | workflow claim | live measurement | verdict |
|---|---|---|---|
| **Items match on InputID==3** | K_GRANT populates `[spec+0x24]==3` | `Items[0].InputID==3` ✓ | [M] confirmed |
| **(a) spec.Ability != NULL** | K_GRANT sets `[spec+0x10]` | `Ability=0x1C28E636930(GS_Ronin_LMB_Selector_C)` ✓ | [M] confirmed |
| **(b) `[Ability+0xEE]==1` InstancedPerActor** | offline recon claimed byte==1 | `InstancePolicy@+0xEE=0x01` ✓ (read LIVE, matched) | [M] confirmed |
| **(c) `NonRep.Num@+0x88 > 0` pre-poke** | K_GRANT leaves NonRep empty | `preNonRep Data=0x0 Num=0 Max=0` ✓ | [M] confirmed |
| **PRE-readback `GetAbilityByInputID(3)`** | should return NULL (R-S191-h) | `return=0x0(NULL)` ✓ | [M] confirmed |
| **POKE effect on NonRep header** | write should land at spec+0x80/+0x88/+0x8C | `Data=0x1C27ADB4EE0(=spec+0x10) Num=1 Max=1 OK` ✓ | [M] confirmed |
| **POST-readback `GetAbilityByInputID(3)` — THE CENTRAL PREDICTION** | should return `spec.Ability` (the CDO) | **`return=0x0(NULL)` — REFUTED** | [M] **workflow model INCOMPLETE** |
| **A→B→A restore** | restore original NonRep header | `Data=0x0 Num=0 Max=0 OK (pre-poke state re-established)` ✓ | [M] confirmed |

**⇒ 7/8 predictions CONFIRMED. The 8th — the central one, whether the poke unblocks the gate — is REFUTED.**

## The structural finding [M]

**A gate exists between "iterator matches on `[spec+0x24]==InputID`" and "return `spec.Ability`" that
neither `NonRep.Num > 0` nor the `NonRep.Data` deref satisfies.** Three possibilities, all now on
the offline task list:

1. **The `[Ability+0xEE]==1` gate is NOT `InstancingPolicy`.** Live `[Ability+0xEE]==0x01` matches
   the workflow's claim numerically, but the byte's SEMANTIC role could be a different UPROPERTY
   whose value coincidentally reads 1. The workflow attributed it from offline disasm; a live
   UHT `SetBitFunc` cross-check on `UGameplayAbility+0xEE` would settle it. If the byte is (say)
   `bReplicateInputDirectly` or another Bool at that offset, the *actual* InstancingPolicy byte may
   be elsewhere and reading whatever value the CDO happens to carry.

2. **A fourth gate exists in `0x44C28E0`.** The workflow's disassembly may have missed a branch
   before the `mov rax,[rcx+0x80]; mov rax,[rax]; ret` return path — e.g. a spec-flags check
   (`spec+0x39 & 0x08 bActivateOnce`? `spec+0x38 PendingRemove`?), a
   `SpawnedAttributes`/instance-type refinement, or a Handle-validity gate against the ASC's
   internal Handle table.

3. **The gate is UPSTREAM of `0x44C28E0`.** `GetAbilityByInputID` (impl `0x5526210`) calls the
   iterator via vtable slot 245; the iterator may bail before invoking `0x44C28E0` at all — e.g.
   on an `ASC.bIsBeingDestroyed` flag, an `ActivatableAbilities.Owner` mismatch, or a Handle-map
   consistency check. In that case our post-poke readback returns NULL because the iterator
   never returned our spec, not because the 3-gate filter rejected it.

**All three hypotheses are settleable OFFLINE against `merged14`.** The live measurement narrows
the search from "somewhere in the ASC" to "one function's control flow", and the E4E arm's own
byte-verified receipts provide the exact pre/post state the offline disasm must retrodict.

## Convergent-witness contrast with E4F F1 / E4C F1 — E4E is DISTINCT

| entry point | witness in Loki.log | interpretation |
|---|---|---|
| E4F F1 (BySourceObject via S55) | `LogAbilitySystem: Warning: TryActivateAbility called with invalid Handle` | call REACHED activation stack → refused at Handle-resolution step |
| E4C F1 (HandleAbilityActivation via CallBPGuarded) | SAME `invalid Handle` warning | BP dispatcher's `Self.TryActivateAbility` REACHED activation → same refusal |
| **E4E F1 (direct poke + GetAbilityByInputID readback)** | **NO `invalid Handle` warning fired** | call refused at ITERATOR level, upstream of the Handle-resolution step |

**⇒ [M] the E4F/E4C convergent-witness diagnosis ("single unpopulated GAS structure blocks BOTH")
is now RELOCATED, not falsified**: the missing structure is upstream of what `TryActivateAbility`
consults for `invalid Handle`. Our K_GRANT populates Items[0] correctly (Handle=1, InputID=3,
Ability=CDO), but the ability-system iterator refuses to hand out the spec at that Items[0]
address to *any* consumer that queries it by InputID or by Handle — the Handle-map and the
InputID-lookup path share the refusal.

## Independent live witness [M]

`docs/s191-e4e-flight1-loki-ability.log` (E4E-window filter, 10 lines):

```
[2026.09.10-19.33.08:747][617]LogLokiCharacter: Verbose: [Client][BP_HERO_Ronin_C_2147471315] Cleared ignored allies when moving
[2026.09.10-19.34.06:517][892]LogAbilitySystem: Initializing Set BaseSet
[2026.09.10-19.34.06:517][892]LogAbilitySystem: Property BaseStaminaRegenStunTime new value is: 4.50
[2026.09.10-19.34.06:518][892]LogAbilitySystem: Property AttackPowerRating new value is: 1.00
[2026.09.10-19.34.06:518][892]LogAbilitySystem: Property AbilityPowerRating new value is: 1.00
[2026.09.10-19.34.06:518][892]LogAbilitySystem: Property Toughness new value is: 1.00
[2026.09.10-19.34.06:518][892]LogAbilitySystem: Property CantStopFactor new value is: 0.00
[2026.09.10-19.34.06:518][892]LogAbilitySystem: Property DamageCoefficient new value is: 1.00
[2026.09.10-19.34.06:518][892]LogAbilitySystem: Property DamageTakenCoefficient new value is: 1.00
[2026.09.10-19.34.06:518][892]LogLokiCharacter: Verbose: [Client][BP_Minion_KaijuAxeLeader_Stagger_Tutorial_C_2147471215] Cleared ignored allies when moving
```

- `Cleared ignored allies when moving` on BOTH hero and minion: game is alive, AI is running.
- `LogAbilitySystem: Initializing Set BaseSet` at 14:34:06 (~58 s after probe injection) is the
  GAME'S OWN attribute-set init on the spawned minion — independent of our poke.
- **ZERO `TryActivateAbility called with invalid Handle` occurrences in the entire E4E flight
  window.** E4E does not touch the activation stack; the poke + readback pair operates one level
  higher.

## New [M] measurements from this flight

- **[M] R14 write-class safety confirmed empirically.** The poke `spec+0x80 <- (spec+0x10)`
  (game-heap self-reference; the write value is a pointer to the spec's OWN Ability field) is
  benign for the ~4 min the game ran after it. If the game's ability code later called
  `NonReplicatedInstances.Empty()` or `Free()` on that Data pointer, it would have attempted to
  free `spec+0x10` — an address the allocator does not recognize — and either no-op'd or aborted.
  It did neither. **The A→B→A restore ran cleanly and no fault surfaced downstream.** Precondition
  measured: `preNonRep Data=0x0 Num=0 Max=0`, so the game's ability code had never populated the
  array before our poke, meaning our poke was the first and only writer of that particular
  buffer's lifetime. Grade: **[M] SAFE for the tested duration; [I] SAFE indefinitely** — a longer
  hold or a route that actually iterates `NonReplicatedInstances` (which nothing on this route
  did) may still fault.

- **[M] `[GS_Ronin_LMB_Selector_C CDO + 0xEE] == 0x01` at live read** — first time this offset
  is measured on the ability CDO in this project. Whether the semantic role IS `InstancingPolicy`
  as the workflow claimed is unverified; the numeric value is.

- **[M] `ULokiAbilitySystemComponent.Items` layout confirmed on this build**:
  `Data@+0x538`, `Num@+0x540`, `Max@+0x544`, stride `0xF8`, `spec.Handle@+0xC`,
  `spec.Ability@+0x10`, `spec.InputID@+0x24`, `spec.NonReplicatedInstances{Data,Num,Max}` at
  `+0x80/+0x88/+0x8C`. Reproduced from CLAUDE.md's recorded layout; now independently corroborated
  by a live iterator walk producing `Items[0].Handle=1, InputID=3, Ability=CDO`.

- **[M] FK-32 did NOT fire within 265 s of probe injection** (past both the ~40-70s post-shim
  window measured across E4A/E4B/E4C/E4F and the ~285s ambient window). This is the FOURTH E4-arc
  flight where an ability-system probe did NOT trigger FK-32, corroborating that WALL-P lethality
  is specifically bound to `TryActivateAbilityByClass`-family calls and NOT to reads/pokes on the
  spec's own state.

## Rules banked

**R-S191-l** [M] (3-gate model refutation): the workflow's offline model of `0x44C28E0`
(`spec.Ability != NULL && [Ability+0xEE]==1 && NonRep.Num > 0`) is INSUFFICIENT to explain
`GetAbilityByInputID`'s NULL return. All three sub-conditions were live-verified passing (the
Ability write and the pre-existing `[+0xEE]==1` value + our poked `Num=1`) and the readback
still returned NULL. Either the semantic role of `[Ability+0xEE]` was misidentified, a fourth
gate exists in `0x44C28E0` between the last visible check and the `mov rax,[rcx+0x80]` return,
or the iterator upstream of `0x44C28E0` refuses to invoke it. Any offline follow-up must
retrodict the exact live measurements this flight recorded.

**R-S191-m** [M] (E4E write-class safe): a single aligned qword + two aligned dword writes to
`spec+0x80/+0x88/+0x8C` on a K_GRANT'd `FGameplayAbilitySpec` with pre-poke `NonRep={0,0,0}`
and post-flight A→B→A restore is a DATA-class write on game-heap memory owned by the ASC. No
fault, no protector kill, no crashpad handoff over 265 s of continued gameplay. Reusable
primitive for any future WALL-P probe that needs to mutate spec state.

**R-S191-n** [M] (upstream/downstream split on the WALL-P block): E4F F1 and E4C F1 produced
`invalid Handle` because their calls reached the activation stack and were refused at
Handle-resolution. E4E F1 produced NO warning because the block sits UPSTREAM — the iterator
never returned our spec to any consumer. ⇒ **fixing the iterator's refusal necessarily fixes
both the E4F/E4C activation-stack refusals AND E4E's readback null.** This is a stronger
localization than the E4C RESULT's convergent-witness diagnosis: the single missing GAS
structure is now bounded to whatever the iterator consults BEFORE hitting `0x44C28E0`.

## What this settles for the E4 predicate

**Refuted**: the workflow's direct-offset poke recipe as the mechanism to reach spec resolution.
The gate model is INCOMPLETE and a poke targeting only the modeled gate does nothing.

**Refined**: WALL-P's location moves from "somewhere in the activation stack" (E4F/E4C) to "the
iterator or the CALLER of the iterator refuses to return our K_GRANT'd spec to consumers that
query by InputID or by Handle". This is a tighter and more actionable target than the earlier
convergent-witness diagnosis.

**Path forward** (all OFFLINE-first, per R-S157-a — a live measurement on a WALL-P-family
mechanism cannot promote a dispatch-site attribution past `[I,strong]` when the kill primitive
is FK-10-family; and this flight was NON-lethal, so live-only investigation is safe but
disassembly-first is cheaper):

- **Option G** — offline: re-verify the semantic role of `[UGameplayAbility+0xEE]` from its UHT
  `SetBitFunc` (find the setter that writes bit `0x01` at that offset in the ability class's UHT
  bindings). If the byte is NOT InstancingPolicy, the workflow's gate (b) attribution was wrong
  and the poke targeted the wrong gate to begin with. Cheap (~1 hour of offline grep +
  disassembly), decisive.
- **Option H** — offline: full recursive-descent CFG on `0x44C28E0` from its function boundary
  to every `ret`, listing every branch and every early-exit. If a fourth gate exists between
  the modeled 3-gate chain and the return, this will name it. The function is ~60 bytes per the
  workflow; the CFG walk is trivial.
- **Option I** — offline: full disasm of the vtable-slot-245 iterator `0x4476F10` (which
  `GetAbilityByInputID` impl `0x5526210` calls). If the iterator returns NULL before invoking
  `0x44C28E0`, the block is upstream and the workflow's whole 3-gate analysis is analyzing an
  unreachable function. If the iterator DOES invoke `0x44C28E0`, Option H's finding is the
  answer.
- **Option J** — LIVE, but only after G/H/I have narrowed the target: with a named specific
  gate, a targeted read-only RPM probe on the field it consults settles which sub-condition
  the K_GRANT'd spec fails.

**Do NOT** rebuild the E4E arm with a modified poke target until at least one of G/H/I names a
new gate. A blind second poke against a still-unknown mechanism would be the "successful poke
that hides the true mechanism" trap S166-a warns about — that already happened once in this
project, on WALL-P's dispatch identification.

## Cost + gates

- **1 launch**, 0 losses. First-try FK-31-clean staging (contra E4C flight 1's 2/3 FK-31 losses).
- **0 collateral damage**: game alive at 265 s post-probe-injection with `Cleared ignored allies
  when moving` on both hero and minion (game AI still running). No crashpad handoff, no
  `LogAbilitySystem: Warning`, no `Fatal`, no `Error` past baseline.
- **Clean disarm**: `[BF] ===== RM_BOTFIGHT done =====` fired after E4_COMPLETE. Funcswap
  restore not printed in the marker tail (probably in a later callback the copy-off missed);
  A→B→A on the spec's NonRep header verified `Data=0x0 Num=0 Max=0 OK`.
- **Regression gates BYTE-IDENTICAL** to pre-flight:
  `botai b620e0ff3279e673` ✓
  `play 31af7667355f39d1` ✓
  `e4 69197ce6e9e38dda` ✓
  `e4-f 1f51942a2b8d164a` ✓
  `e4-c eb82b2b781996671` ✓
  (`KBFE4E=0` default truly dead-strips 22 policy #errors + ~180-line #if KBFE4E block)
- **Flown arm**: `e4-e-readonly RAW=34fc650f88491b79 VSIZE=599168e159d5297d` 231,936 bytes,
  KERNEL32-only, `verify_dll.py` VERDICT=PASS, `text_digest.py --dupes` clean for this arm.
- **`e4-e-activate` variant NOT added** — remains PARKED behind
  `KBFE4E_ACTIVATE_OFFLINE_VERIFIED` until offline recon proves
  `TryActivateAbilityByInputID` impl `0x5544F70`'s tail-call target `0x5531920` does NOT
  converge on S147 lethal `InternalTryActivateAbility 0x4480B30`. `0x5531920` is
  `PAGE_NOACCESS` in `merged14` and cannot be settled offline in this dump.

## Files

- `docs/s191-e4e-flight1-marker.log` — full E4E chain verbatim (125 lines)
- `docs/s191-e4e-flight1-loki.log` — general Loki.log excerpt around E4E window (54 lines)
- `docs/s191-e4e-flight1-loki-ability.log` — filtered ability-system events during E4E (10 lines)
- `tools/sigbypass-mod/tutorial_launch.cpp` — KBFE4E knob + 22 policy #errors + `#if KBFE4E` block
- `tools/sigbypass-mod/build.ps1` — `e4-e-readonly` variant

## S191 arc tally after this commit

| flight | outcome | grade |
|---|---|---|
| S191 E4 F3 | minion killed via KE4DIRECTGE; natural LMB refuted (input binding) | [M] |
| S191 E4A F1 | ByInputID clean-false NON-lethal; R-S191-h confirmed live | [M] |
| S191 E4B F1+F2 | BP_AuthGiveAbilityWithInputID = stripped stub; new FK-1 register entry | [M] |
| S191 E4F F1 | BySourceObject clean-false-fast NON-lethal + `invalid Handle` witness | [M] |
| S191 E4C F1 | BP dispatcher HandleAbilityActivation clean-refuse-fast + SAME `invalid Handle` witness (convergent diagnosis) | [M] |
| **S191 E4E F1** | **direct-offset NonRep poke lands but GetAbilityByInputID readback STILL NULL — workflow gate model INCOMPLETE, block relocated UPSTREAM of activation stack** | **[M]** |

Total S191 launches: 9 flown (3 lost to FK-31 this arc); 6 [M] results banked.
No shim ever triggered FK-32 in the S191 arc across 9 launches.
