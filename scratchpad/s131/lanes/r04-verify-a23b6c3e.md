## LANE 1 RESULT — the ADDSi/LoadThisR operand IS a byte offset from `this`. **CONFIRMED [M], not refuted. Build the probe on it.**

### 0. VERIFICATION OF THE SEED INFERENCE (this was the ask; it holds, with N=214, not N=2)

**Instrument 1 — internal consistency (whole corpus).** Parsed every annotated `ADDSi`/`LoadThisR` in `tools/asdump/out/**/*.as.txt`: **9,468 ops across 312 files → 784 distinct (typeid, member) pairs, ZERO offset conflicts.** Operand 1 is a stable per-(class,member) constant.

**Instrument 2 — the AOT-compiled x86 (INDEPENDENT of the bytecode listing).** FK-1 established the script layer is AOT-transpiled into `.text 0x059128B0–0x05A7F070`. The compiled `ALokiDropPod::ALokiDropPod()` at **`.text 0x5963A30–0x5964B66`** (pdata row, `tools/strxref/index/pdata_union.csv`) computes every member as `mov rax,[rsp+0x488] ; add rax, <imm>`, where `[rsp+0x488]` is `this` (prologue `mov [rsp+0x10],rdx`; `push rsi; push rdi; sub rsp,0x468` ⇒ shift 0x478 ⇒ rdx home at +0x488; first use is `add rax,0x490` = `AttachedCrewPods`, the ctor's first statement).

> **The AS ctor's 50-op operand sequence and the x86 function's 50 `add rax,imm` sequence are ORDERED-IDENTICAL. 50/50. [M]**

Value-level corroboration inside that match: `mov dword [rsp+0x50], 0xffffffff` → `this+0x460` reproduces the source line `PodTeamIndex = -1`; `0x45C`/`0x45D` are two *separate whole-byte* stores, matching `bPilotHasPodControl` then `bIsTeamLeaderPod`.

**Instrument 2 replicated on 11 more AS classes** (every AS ctor with ≥8 member ops, matched against all 1,702 pdata rows in the AS body range): **12/12 exact ordered-sequence matches**, 214 pairs total — `ALokiDropPod` 50 @`0x5963A30` · `ALokiAirship_AS` 36 @`0x5955350` · `ULokiDropPhase_PlayerStateComponent` 25 @`0x5A1C290` · `ALokiAimingLaser` 18 @`0x5947550` · `ATemporaryFloor` 12 @`0x598E980` · `ULokiInteractionPlayerComponent` 12 @`0x5A3EFA0` · `UBarracudaGameStateComponent` 11 @`0x59DF6B0` · `ALokiAimingLaser_Huntress` 11 @`0x5941740` · `ULokiPlayerControllerArmoryComponent` 10 @`0x5A57DC0` · `ULokiTeamElimBoxComponent` 10 @`0x5A71B70` · `ULokiGameStateUAVComponent` 10 @`0x5A32DE0` · `ABarracudaMinionSpawner` 9 @`0x591E2A0`.

**Instrument 3 — the UHT oracle on the native base, an unrelated table.** `ALokiDropPodBase` `FClassParams 0x08934240`, `PropPointers 0x089341B0`, **NumProperties = 1**: `PilotPlayerState` **off = 0x3C0** (record `.rdata 0x08934170`). The AS subclass's first member `CrewDropPodClass` is **0x3C8 = 0x3C0 + 8**. The derived class begins exactly where the base's last property ends.

**Instrument 4 — a direct compiled write of that same field.** `ALokiDropPodBase::SetPilotPlayerState` impl **`0x55E59E0`** (via `recs.py`) is literally `mov qword ptr [rcx+0x3C0], rdx ; mov r8d,0xB ; mov rdx,[rcx+0x30] ; jmp 0x1E3CCD0` (net-dirty push). **It writes `+0x3C0` and nothing else.**

**Instrument 5 — live.** S130's own `RESULT-routeE-after-poke-s130.txt` read `TeamDropPodClass@0x478` off 12 live ship objects and it resolved to the *correct class object by name* (`BP_DropPod_Tutorial_C` on the tutorial planes, `BP_DropPod_C` on the rest). That is the seed, semantically validated.

⚠ **The UHT oracle is structurally BLIND to Angelscript members** — `PodTeamIndex`, `bIsTeamLeaderPod`, `CurrPodDestination`, `TeamDropPodClass`, `SpawnDropPodForTeam` have **0 ASCII and 0 UTF-16 occurrences** in `dumps/s129-poolgate/SUPERVIVE-Win64-Shipping.dump.exe` (positive controls in the same scan: `bCanEverReplicate` 1, `bEnablePooling` 1/1, `bSupportsActorPoolPriming` 1). `propscan`/`boolscan` returning 0 hits on an AS name is **COVERAGE-BLOCKED, not absent.**

---

### ⚠⚠ FINDING THAT CHANGES THE EXPECTATION TABLE: `Loki::LokiIsServer()` IS A STUB THAT RETURNS **FALSE**

Two independent routes, agreeing:
* `recs.py` → `LokiIsServer` rec `0x9bba7d8`, thunk `0x52e7150`, **impl `0x0F7EB60` = `32 c0 c3` = `xor al,al; ret`** (known fold). `LokiIsClient` rec `0x9bba790`, thunk `0x52e64a0`, **impl `0x0B9E1F0` = `b0 01 c3` = `mov al,1; ret`**.
* Direct disassembly of the AOT-compiled `ALokiDropPod::LokiBeginPlay_Implementation`:
```
0x596a3f9  call  0xf7eb60          <-- LokiIsServer  (xor al,al; ret => 0)
0x596a3fe  mov   [rsp+0x21], al
0x596a420  movzx eax,[rsp+0x20] ; test eax,eax
0x596a427  jne   0x596a433 ; jmp 0x596a4bc     <-- al==0 => SKIP the whole block
0x596a433  mov   rax,[rsp+0x1a8] ; add rax, 0x460     <-- this->PodTeamIndex
0x596a495  call  0x56fbcf0         <-- LokiTeam::SetTeamForActor  (NEVER REACHED)
```
(`SetTeamForActor` impl `0x56FBCF0` has **exactly 1** caller in the whole AS body range — this one. That is what identifies the function.)

⇒ **[M] `LokiBeginPlay` never calls `SetTeamForActor`, so the pod's `ULokiTeamComponent` is never given `PodTeamIndex`, so `GetTeamIndex() >= 0` fails, so `StartPodGameplay()` is NOT called at BeginPlay** (it binds `OnTeamIndexChanged` instead). Everything `StartPodGameplay` writes stays at class default. Same stub kills the `LokiIsServer && bIsTeamLeaderPod` guard on `SpawnImpactIndicator`.
⚠ **Scope:** `0xF7EB60` is ICF-folded, so the address identifies a *behaviour* (`return false`), not a function. That is sufficient here — the call site is identified by its surroundings, not by the callee address.

---

### (A) THE OBSERVABLE-FIELD TABLE

Offsets are **byte offsets from the pod actor pointer**, verified as above. Cooked defaults: **[AR]** = `ar_query.py --name BP_DropPod_Tutorial` (the cooked effective value, validated 3/3 in both polarities live in S130 §12); **[CTOR]** = `ALokiDropPod::ALokiDropPod()` AS source + its 50/50-matched x86 body; **[UHT]** = `FClassParams` record. `Default__BP_DropPod_Tutorial_C` serializes **only** `MaxSteerDistance`/`MaxNonLeaderSteerDistance = 2000` (`bpdump_BP_DropPod_Tutorial_PROPS.txt`), so nothing below is overridden by either BP.

| field | owning class | AS byte off | type | reflected? | cooked default (source) | S131 call writes | discriminates? |
|---|---|---|---|---|---|---|---|
| **PodTeamIndex** | ALokiDropPod | **0x460** | Int32 | ✅ UPROPERTY | **-1** [AR][CTOR] | **0** (`KPDTEAM=0`) | **Y — cleanest.** −1→0 is unambiguous |
| **CurrPodDestination** | ALokiDropPod | **0x478** | FVector (**24 B**, 3×double; corroborated by S130's PE layout `size24`) | ✅ | **(0,0,0)** [AR][CTOR] | LandingLocation `(-3206.4, 5070.5, 100.0)` in the S130 geometry | **Y — strongest.** 3 doubles cannot collide by accident |
| **bIsTeamLeaderPod** | ALokiDropPod | **0x45D** | bool, **own whole byte** (`WRTV1`; x86 `mov byte [rax],cl`) | ✅ | **False** [AR][CTOR] | **true** | **Y** |
| **LeaderPod** | ALokiDropPod | **0x4B0** | Object ptr (`ALokiDropPod*`) | ✅ | **None** [AR][CTOR] | `ParentPod = nullptr` | **N — TRAP.** null→null |
| **PilotPlayerState** | **ALokiDropPodBase** (native) | **0x3C0** [UHT `0x08934170`] | Object ptr, `Net\|RepNotify` | ✅ | **None** [AR] | `GetTeamDropLeader(0)` | **N in practice** — see (B) |
| **Owner** | **AActor** | **0x150** [UHT `0x07F202F0`, AActor `FClassParams 0x07F227E0`, idx 45/114, controls 3/3 PASS] | Object ptr, `Net\|RepNotify` | ✅ | **null** (not overridden; stock) | `SetOwner(GetPilotPlayerState())` | **N** — tracks PilotPlayerState, not independent |
| **PodMeshComponent** | ALokiDropPod | **0x638** | `USkeletalMeshComponent*` | ✅ | **None** [AR][CTOR] | **NOT written by this chain** — only `StartPodGameplay()` (LokiDropPod.as:937) writes it | **Y, as a *reachability* probe** — non-null ⇒ StartPodGameplay ran |
| **bHasStartedGameplay** | ALokiDropPod | **0x4B8** | bool | ❌ **NO UPROPERTY** — by-name resolve **will fail**; AS offset is the only route | **false** [CTOR] (absent from AR, consistent with unreflected) | not written by this chain | **Y** — the single cleanest "did the pod come alive" bit |
| **PlayersToSpawnCrewPodFor** | ALokiDropPod | **0x648** | `TArray<ALokiPlayerState*>` (16 B) | ✅ | **empty** [CTOR] | `QueueCrewForPodSpawn` runs (PodTeamIndex 0 ≥ 0) and **Add()s every non-leader PS on team 0**, then `SpawnCrewPodQueue()` **`Empty(0)`s it** | **Partly** — final `Num` is 0 either way; use `AttachedCrewPods` instead |
| **AttachedCrewPods** | ALokiDropPod | **0x490** | `TArray<ALokiDropPod*>` | ✅ | **empty** [CTOR] | `SpawnCrewPodQueue` Adds one per queued PS | **Y** — `Num>0` ⇒ `GetPlayerStatesOnTeam(0)` returned live PlayerStates ⇒ the world is populated |
| **bIsLocalPlayerPilot** | ALokiDropPod | **0x464** | bool | ✅ | **False** [AR][CTOR] | only inside `StartPodGameplay`'s `if(!LokiIsServer)` — which **is** taken, but only if StartPodGameplay runs | **Y**, second-order |
| **ImpactIndicator** | ALokiDropPod | **0x468** | Object ptr, Replicated | ✅ | **None** [AR][CTOR] | `SpawnImpactIndicator` gated on `LokiIsServer && bIsTeamLeaderPod` ⇒ **[M] dead** | **N** — predicted null by a *measured* stub |
| **GroundLaserIndicator** | ALokiDropPod | **0x470** | Object ptr | ✅ | **None** [AR][CTOR] | not written by this chain | N |
| **bPilotHasPodControl** | ALokiDropPod | **0x45C** | bool | ✅ | **False** [AR][CTOR] | not written by this chain | N (useful as an *adjacent-byte* control for 0x45D) |
| **PodStateEvent** | ALokiDropPod | **0x530** (40 B) | struct `FGameEvent_OnDropPodStateChanged_PlayerState`; sub-offsets measured from the chained `ADDSi`: `.DropPod` **0x538**, `.DropPodState` **0x540** (1-byte enum), `.PodPilot` **0x548**, `.bIsLeaderPod` **0x550** | ✅ | `(DropPod=None, DropPodState=None, PodPilot=None, bIsLeaderPod=False)` [AR] ⇒ enum 0 == `None` | written only by `SetDropPodState`, itself reached only from `StartPodGameplay`; **and `SetDropPodState` early-returns on `LokiIsClient` — [M] always TRUE (`0x0B9E1F0`)** ⇒ **can never be written on this client** | **N — foreclosed by two measured stubs.** Do not read a null here as a pod-state result |
| **bCanEverReplicate** | **AActor** | **0x6C**, **bitfield mask 0x1** (`SetBitFunc 0x02078900 mov byte [rcx+0x6c],1`; AActor idx 27/114) | bool bitfield | ✅ | **true** [AR] | not written by the chain; **inherited from the poked CDO** | see (C) |

Positions used by the S130 arm, for the `CurrPodDestination` comparison: `Spawn=(-3206.4, 5070.5, 20100.0)`, `Landing=(-3206.4, 5070.5, 100.0)`, `TeamIndex = KPDTEAM = 0` (`tutorial_launch.cpp:7804`).

---

### (B) FIELDS THAT CANNOT DISCRIMINATE

1. **`LeaderPod` (0x4B0)** — `ParentPod` is passed `nullptr` by `SpawnDropPodForTeam`, and the class default is `None`. **Can only ever agree.** Already correctly labelled in the shim.
2. **`PilotPlayerState` (0x3C0)** — **[I, strong] `GetTeamDropLeader()` returns null in this client**, so this is null→null. Mechanism, from the AS body (`LokiDropShip.as`) + two measured stubs:
   * It returns the first PlayerState on the team with `IsSpawnTeamLeader()` true; the fallback loop has an **empty body** and it falls through to an uninitialized local (`v30`, i.e. null).
   * `ALokiPlayerState::IsSpawnTeamLeader` impl **`0x56C2060`** (real, decrypted in all 3 images) is: `GetWorld()` → `edx = [this+0xE88]` (team id) → `GetTeamState` (`0x56F02E0`) → `rcx = [TeamState+0x688]` → resolve (`0x3259330`) → `sete al` on `== this`. It is a **pure read of a team-state field**.
   * The only writer of that field, `ALokiTeamState_TeamOnly::SetDropLeader`, is one of FK-1's four empty stubs (impl `0x0F7EC20 = ret 0`), as is `ALokiPlayerState::AuthSetSpawnTeamLeader` (impl `0x0F7EC20`). **Nothing on this client can set a drop leader.**
   ⇒ null here is **expected**, not a fault. Grade [I] not [M] because replication could theoretically deliver `[TeamState+0x688]` — impossible in a shim-driven local world.
3. **`Owner` (0x150)** — `SetOwner(GetPilotPlayerState())` ⇒ `SetOwner(null)`. Null→null, and **not independent** of #2.
4. **`ImpactIndicator` (0x468)** — its spawn is gated on `LokiIsServer` [M false]. Predicted null with no information content.
5. **`PodStateEvent.*` (0x538/0x540/0x548/0x550)** — foreclosed twice: unreachable (no `StartPodGameplay`) *and* `SetDropPodState` returns before writing whenever `LokiIsClient` [M true].
6. **`PlayersToSpawnCrewPodFor` (0x648)** at the *final* read — `SpawnCrewPodQueue` calls `Empty(0)` on exit, so `Num == 0` under both "never populated" and "populated and drained". **Read `AttachedCrewPods` (0x490) instead** — that one is additive and never cleared on this path.

---

### (C) `bCanEverReplicate` (+0x6C) ON THE SPAWNED INSTANCE

**Prediction: 0 (bit 0 clear) for a pod constructed after the CDO poke; 1 for one constructed before. [I], not [M].**

* `AActor::AActor()` sets it TRUE (`0x03371841 mov byte [rdi+0x6c], 1`) [M, CLAUDE.md/S130 §11], and the cooked effective default for `BP_DropPod_Tutorial` is `true` [AR], live-confirmed 1 on all three loaded ancestors in S130 §12.
* It is a **reflected** `FBoolProperty` on AActor (idx 27 of 114, `FClassParams 0x07F227E0`), flags `0x0020080000010015` = `Edit|BlueprintVisible|BlueprintReadOnly|DisableEditOnInstance|Protected|NativeAccessSpecifierProtected` — **not** `CPF_Transient`, **not** `CPF_DuplicateTransient`. (⚠ `propscan`'s `gen=WeakObject|Config` label is the README's known-bad type table; ignore it.)
* In UE, `FObjectInitializer::PostConstructInit` → `InitProperties(Obj, Class, Archetype=CDO)` runs **after** the C++ constructor and copies reflected non-transient properties from the archetype. Structural argument: if it did not, no Blueprint could ever override `bCanEverReplicate` to false in the editor — and Blueprints demonstrably do (S130's joint distribution over 36,625 Blueprints found 80 pooling∧¬replicate classes).

**Is it a usable "constructed after the poke" receipt? Yes, but only with a control, and the control is free.** The S130 BEFORE census already contains **three live non-archetype `BP_DropPod_Tutorial_C`** (`0x1D1956C0200`, `0x1D1A5DA7910`, `0x1D1FFDDE830`) that predate the poke. Print `+0x6C` for the pre-existing pods AND the new ones AND the CDO in the same pass:

| pre-existing pods | new pod(s) | reading |
|---|---|---|
| 1 | 0 | ✅ two-sided: inheritance works, new pod post-dates the poke |
| 1 | 1 | archetype copy does **not** cover this bit ⇒ the field is **not** a construction-order receipt (uninterpretable, not negative) |
| 0 | 0 | ⚠ **VOID** — something poked more than the CDOs, or the pre-existing pods also post-date it |

Without the pre-existing arm a lone `0` is uninterpretable — exactly the S130 §12.4 failure mode.

**What an instance inherits, and when:** allocate → zero → C++ ctor chain runs (`AActor::AActor` writes 1) → `FObjectInitializer::PostConstructInit` copies the reflected property block from the **archetype** (the CDO, or a template for a component) → `PostInitProperties`. So the CDO value wins for reflected properties, and the ctor value wins for anything unreflected. ⚠ A pod handed back by a **warm** actor pool is *not* re-constructed and does *not* re-inherit — irrelevant in S130 (pool disabled, `bSupportsActorPoolPriming=False`, fallback `UWorld::SpawnActor` at `0x5648E48`), but it becomes a live confound the moment pooling is ever enabled.

---

### (D) NOT ESTABLISHED

1. **`ULokiTeamComponent`'s own default team index** — needed to decide whether `LokiBeginPlay`'s `GetTeamIndex() >= 0` branch can be taken *without* `SetTeamForActor`. `BP_DropPod_Tutorial`'s `LokiTeam_GEN_VARIABLE` serializes **no properties**, so it inherits the component CDO; `propscan --name TeamIndex` returns 84 records with no way to attribute one to `ULokiTeamComponent` without a `propowner` walk I did not run. ⇒ **`bHasStartedGameplay`/`PodMeshComponent` are predicted default but the prediction rests on this unknown.** They are still the right things to read — they *measure* it.
2. **Which of `recs.py`'s two `GetTeamIndex` records (impl `0x55AE000` vs `0x56BF8A0`) is `ULokiTeamComponent::GetTeamIndex`** — not disambiguated.
3. **Whether `GetPlayerStatesOnTeam(world, 0)` returns anything in the staged tutorial world** — i.e. whether the hero's PlayerState is on team 0. `LokiGameplay::GetPlayerStatesOnTeam` impl `0x5695030` is real and covered, but its behaviour here was not traced. This is the whole information content of `AttachedCrewPods`.
4. **`ELokiDropPodState`'s full value table** — only `None = 0` [M, from the AR default string `DropPodState=None`] and, from AS source, `Descending = 3` with literals 2 and 4 in use. The enum's own declaration is native and was not located.
5. **Byte at `PodStateEvent + 0` (0x530)** — the struct is 40 B (0x558 − 0x530) and the bytecode only ever addresses `+8/+16/+24/+32`. What occupies `+0` is unknown.
6. **`FGameEvent_*` / `FLokiPodDetachData` internal layouts** beyond the four sub-offsets above — not needed, not derived.
7. **Whether `bCanEverReplicate` is on `AActor`'s `PostConstructLink`** (the exact UE copy path) — argued structurally in (C), not measured in this image.

---

### PRACTICAL NOTES FOR THE PROBE

* **The by-name path will FAIL, correctly, on unreflected members.** FK-1 measured that only `UPROPERTY()` AS members are reflected (470 of 581). On `ALokiDropPod` these have **no** `UPROPERTY` and are AS-offset-only: `bHasStartedGameplay` **0x4B8**, `bSteeringEnabled` **0x4A0**, `SteeringStartTime` **0x4A8**, `bIsHidingDropPhaseHiddenActors` **0x5F0**, `bPodIsDestroying` **0x5F1**, `bRetryLeaderPodCameraGlue/CrewPod/Character` **0x640/0x641/0x642**, `CrewPodBoneName` **0x44C**, `LeaderPodBoneName` **0x454**, `DetachingFromLeaderPodStartTime` **0x438**. A `NAME NOT RESOLVED` on these is the instrument working, not a defect — the existing `PdPodField` "resolved to 0 vs never resolved" wording already covers it, but the AGREE/DISAGREE verdict must be **suppressed**, not scored as DISAGREE, for these.
* **AS bools each own a whole byte** here [M, from the ctor's separate `mov byte` stores at 0x45C/0x45D and 0x5F0..0x5F4], so the raw-byte fallback is exact for them. `bCanEverReplicate` is the exception — it is a real **bitfield, mask 0x1**; read `byte & 1`.
* **Full verified `ALokiDropPod` map** (offset → member), if the probe wants more fields: `0x3C0` PilotPlayerState(base) · `0x3C8/0x3D0/0x3D8` CrewDropPod/ImpactIndicator/GroundLaserIndicator Class · `0x3E0..0x440` 13 doubles · `0x448` bIsCrewPod · `0x44C/0x454` FNames · `0x45C` bPilotHasPodControl · `0x45D` bIsTeamLeaderPod · `0x460` PodTeamIndex · `0x464` bIsLocalPlayerPilot · `0x468` ImpactIndicator · `0x470` GroundLaserIndicator · `0x478` CurrPodDestination · `0x490` AttachedCrewPods · `0x4A0` bSteeringEnabled · `0x4A8` SteeringStartTime · `0x4B0` LeaderPod · `0x4B8` bHasStartedGameplay · `0x4C0` DetachingCrewPods · `0x4D0` AllDetachedCrewPods · `0x4E0` PodDetachData · `0x530` PodStateEvent · `0x558` CrewDetachEvent · `0x5A0` LeaderDetachEvent · `0x5F0/0x5F1/0x5F2/0x5F3/0x5F4` bIsHiding/bPodIsDestroying/CurrentInputDirection/LastInputDirection/bReadyForOutro · `0x5F8/0x608/0x618/0x628` the four delegates · `0x638` PodMeshComponent · `0x640/0x641/0x642` bRetry* · `0x648` PlayersToSpawnCrewPodFor.
* **Ranked discriminator set for "did `InitializeDropPod` run":** `CurrPodDestination` (0x478) > `PodTeamIndex` (0x460) > `bIsTeamLeaderPod` (0x45D). All three must move together; any split is a decode fault, not a game result.
* **Ranked discriminator set for "is the pod FUNCTIONAL":** `bHasStartedGameplay` (0x4B8) and `PodMeshComponent` (0x638) — and both are **predicted FALSE/null** by the `LokiIsServer` stub. A false here is the *expected* answer and localises the next wall at `ULokiTeamComponent::GetTeamIndex`, not at the spawn.
* The `RM_POOLSPAWN` pods (raw spawn, never through `InitializeDropPod`) remain the correct spatial negative control: they must read `-1 / (0,0,0) / False` on the three discriminators.