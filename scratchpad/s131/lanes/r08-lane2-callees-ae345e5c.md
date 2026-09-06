Verification complete. Findings below.

## LANE 2 — grade of every callee on the `SpawnDropPodForTeam` post-spawn path

### 0. The instrument, and whether it is fit for purpose

`scratchpad/s130/tools/recs.py` **is fit for purpose but has a range bug**: it does not bound-check the *name* pointer (only thunk/impl), and it emits `.rdata` false positives. I re-implemented it (`<scratchpad>/rectab.py`) and enumerated the whole table: **21,380 triples image-wide, 17,079 of them in `.data`** (unit: records).

**What the table actually is [I, strong]:** the Angelscript **C++-bind descriptor** table — `{const char* Name, FNativeFuncPtr ExecThunk, void* CppEntry}` at **stride 0x48**, in per-class **alphabetically sorted** blocks. Evidence: block neighbours reconstruct classes exactly (`SetActorTickInterval/SetLifeSpan/SetNetDormancy/SetOwner/SetReplicates` = `AActor`; `DeprojectScreenToWorld/DoesSaveGameExist/FinishSpawningActor/FlushLevelStreaming` = `UGameplayStatics`); 17,079 records vs **15,327** `member_kind=method` rows in `binds_members.csv`; and **every Angelscript-authored UFUNCTION is absent while every C++ one is present** (`SpawnDropPodForTeam`, `StartPodGameplay`, `QueueCrewForPodSpawn`, `SpawnCrewPodQueue`, `InitializeDropPod`, `GetTeamDropLeader`, `TransitionCameraToLeaderPod` — all absent; `SpawnPlayer`, `GoToPhase`, `OnNewPhase`, `BP_AuthSetCurrentPhase`, `AuthSetSpawnTeamLeader`, `SetDropLeader`, `OverridePlaneLocations`, `SpawnPoolableActorFromClassDeferred` — all present).

⚠ **Therefore "no record" for an Angelscript function is an instrument-scope fact, NOT an empty stub.** Recording it as a stub would be the 71st instrument-artifact instance.

**Validated 7/7 against independently-derived gold values** [M]: `SpawnPlayer` `0x534C070/0xF7EB50`; `GoToPhase` `0x5457200/0x5601020`; `OnNewPhase` rec `0x9C1F328` `0x5457480/0x330C56C`; `BP_AuthSetCurrentPhase` `0x53878D0/0x567A160`; `AuthSetSpawnTeamLeader` `0x5254180/0xF7EC20`; `SetDropLeader` `0x2C2CE30/0xF7EC20`; `SpawnPoolableActorFromClassDeferred` deferred `0x537F1A0/0x5670090`.

**Second, independent confirmation of the third field** [M]: disassembling two exec thunks shows the thunk's last direct call IS the recorded impl — `0x53375E0 → call 0x55E59E0`, `0x2C2CE30 → call 0xF7EC20`. ⚠ **This does NOT hold for virtual/RPC entries**: thunk `0x53BD130` (4 records) ends `call qword ptr [rax+0x4D0]`, so for those the field is the class's own C++ entry point rather than the thunk's callee. Grade the *field*, never assume the thunk reaches it.

`implof.py` I read but did not rely on — its `BASES` dict is vestigial and its `tail()` stops at the first `ret`, which truncates chained functions. `recs.py`'s output I reproduced independently before using.

---

### 1. The 11-row grade table

Fold multiplicity = records in the 17,079-row `.data` table sharing that address. Coverage = `.text` page non-zero in `s129` / `merged2` / `tuthero`.

| # | function | exec thunk (fold mult) | **impl** (mult) | verdict | coverage |
|---|---|---|---|---|---|
| 1 | `ALokiDropPodBase::SetPilotPlayerState` | `0x53375E0` (1) | **`0x55E59E0`** (1) | **REAL** — 4 instructions | ZERO / **YES** / ZERO |
| 2 | `ALokiDropPodBase::GetPilotPlayerState` | — | — | **NOT A UFUNCTION** — AS-generated property getter | n/a |
| 3 | `AActor::SetOwner` | `0x33ACD80` (1) | **`0x3375780`** (3) | **REAL** — `mov rax,[rcx]; jmp [rax+0x538]` (virtual trampoline, slot 167) | YES/YES/YES |
| 4 | `UGameplayStatics::FinishSpawningActor` | `0x3802CC0` (1) | **`0x37D4470`** (1) | **REAL** — null-guard then `call [vtable+0x578]` | YES/YES/YES |
| 5 | `ALokiDropPod::QueueCrewForPodSpawn` | — (CALLINTF 85003) | — | **ANGELSCRIPT** — 86 dwords / 53 instrs, body intact | n/a |
| 6 | `ALokiDropPlane::RemovePlayerFromPlane` | `0x2C2CE30` (**23**, non-identifying) | **`0xF7EC20`** (377) | ⛔ **EMPTY STUB (`ret 0`)** | YES/YES/YES |
| 7 | `ULokiRideableComponent::Get(AActor,FName)` | — | — | **AS-PLUGIN GENERATED** → `AActor::GetComponentByClass` `0x33879B0` **REAL** | YES/YES/YES |
| 8 | `ULokiRideableComponent::AuthPlayerEnterWorldAttachedToRidable` | `0x5456380` (1) — **page ZERO in all 3 images** | **`0x55CD510`** (1) | **REAL body, ALWAYS-FAIL** (see §3) | YES/YES/YES |
| 9 | `ULokiPlayerDropPlaneComponent::MulticastOnDropPodLaunched` | `0x53BD130` (**4**, ICF, non-identifying) | **`0x542B2B0`** (1) | **REAL** — caller-side RPC stub → `ProcessEvent` | YES/YES/YES |
| 10a | `ALokiServerAnalyticsManager::GetFromContext` | `0x54636B0` (1) | **`0x558A4A0`** (1) | **REAL** — `GetWorld` → `0x55F9460` → tail-jmp `0x55FAD50`; returns null if absent | YES/YES/YES |
| 10b | `ALokiServerAnalyticsManager::AddTeamDropEvent` | `0x5463350` (1) | **`0x557EAE0`** (1) | **REAL** — 0xE0-byte frame | YES/YES/YES |
| 11 | `ALokiDropShip::GetTeamDropLeader` | — (CALLINTF 85087) | — | **ANGELSCRIPT** — 115 dwords / 69 instrs (see §4) | n/a |

**Row 8's thunk is the one genuinely COVERAGE-BLOCKED item** — `0x5456380` is on the never-decrypted page `0x5456000` FK-22 §2.5 already named. The record's impl field lives in `.data` and *is* readable, which is exactly the value of this instrument.

### 1b. Observable state each REAL callee writes (for an in-process probe)

| # | observable | grade |
|---|---|---|
| 1 | `pod + 0x3C0` ← PlayerState ptr. Confirmed twice: `mov qword ptr [rcx+0x3C0], rdx` in the body, **and** `classprops_uht.py --seed-name PilotPlayerState` → `ALokiDropPodBase` `NumProperties=1`, `PilotPlayerState @ 0x3C0`. Then `mov r8d,0xB; mov rdx,[rcx+0x30]; jmp 0x1E3CCD0` (push-model dirty, rep index 11). | **[M]** |
| 2 | reads the same `+0x3C0`; writes nothing | [M] |
| 3 | `pod + 0x150` ← Owner. `AActor::Owner @ 0x150` via `classprops_uht.py --seed-name bAlwaysRelevant` (114 props, **3/3 controls PASS**) | **[M]** |
| 4 | actor finishes spawning (components registered, BeginPlay). Returns the actor unchanged when passed null. Offsets not derived. | [I] |
| 6 | **nothing.** `ret 0`. ⚠ Its silence is uninterpretable — it can never be evidence of anything. | [M] |
| 8 | **nothing but a log line** (§3) | [M] |
| 9 | via `ProcessEvent`; on success `ULokiPlayerDropPlaneComponent::DropPod @ +0x110` (`DropPlane @ +0x108`, `CurrentRideableObject @ +0xD8`, `bDropComplete @ +0xD0`, `bDropLocationSelected @ +0xD1` — all from the UHT `PropPointers` walk, cross-checked by `AuthEnterDropPlane` impl `0x56DBE60` = `mov [rcx+0x108], rdx; ret`) | [M] offsets / [I] that the multicast writes them |

---

### 2. CRITICAL SUB-QUESTION — does the drop pod have a `ULokiRideableComponent`?

**YES. [M], from the cooked assets, three ways.**

1. `scratchpad/s130/evidence/bpdump_BP_DropPod_PROPS.txt:234-238` — **`SCS_Node_13`**: `ComponentClass = Class'/Script/Loki.LokiRideableComponent'`, **`InternalVariableName = LokiRideable`**. Template export at line 142: `[UActorComponent] LokiRideable_GEN_VARIABLE (ExportType=LokiRideableComponent)`.
2. `bpdump_BP_DropPod_Tutorial_PROPS.txt` carries the same `LokiRideable_GEN_VARIABLE` template but only **one** SCS node of its own (`DefaultSceneRoot`) plus a **17-record `InheritableComponentHandler`** ⇒ it is an ICH *override* of the inherited node, not a new declaration.
3. **AssetRegistry cooked tags (the effective, inheritance-resolved value):** `BlueprintComponents = **17**`, `NativeComponents = 0` for **`BP_DropPod`, `BP_DropPod_Child` AND `BP_DropPod_Tutorial` — identical**. Control that this tag is inheritance-inclusive and not a per-file delta: `BP_DropPod_Tutorial` serializes 1 own node yet reads 17; and `BP_DropPlane_Straight_Tutorial` reads 9, matching its parent `BP_DropPlane_Base`'s 9.

- **Declared by:** `BP_DropPod` (`/Game/Loki/Environment/DropPlane/DropPod/BP_DropPod`). **Component name: `LokiRideable`.**
- `BP_DropPod_Tutorial` → `ParentClass = BP_DropPod_C`, `NativeParentClass = /Script/Angelscript.LokiDropPod` [M].
- The native/AS `ALokiDropPod`/`ALokiDropPodBase` contributes **none** (`NativeComponents = 0`; `ALokiDropPodBase` has exactly **1** reflected property, `PilotPlayerState`). `RideableComponent @ +0x3C8` exists but belongs to **`ALokiDropPlane`** (18-property block with `OnPlaneStarted`/`OnReachedEnd`/`StartLocation`/`EndLocation`/`Speed`), **not** the pod.

**What `Get` actually does — settled from the shipped transpiler templates [M].** UTF-16 literals in `.rdata`:

```
0x084D3DC0  '%s Get(const AActor Actor, const FName& WithName = NAME_None)'
0x084E5310  '\n %s Get(const AActor Actor, FName WithName = NAME_None) __generated
             {%s Value; __Actor_GetComponentByClass(Actor, %s, Value, WithName); return Value;}'
```

⇒ `ULokiRideableComponent::Get(pod, NAME_None)` **is** `__Actor_GetComponentByClass(pod, ULokiRideableComponent::StaticClass(), out, NAME_None)` — a plain `GetComponentByClass` with **no name filter** when `WithName == NAME_None`. It resolves to `AActor::GetComponentByClass`, record `0x9A5ED80`, thunk `0x33A7930`, impl **`0x33879B0` — REAL**, decrypted in all three images.

It is **not** a C++/Loki bind: **[M] by absence with a clean positive control** — only **4** members image-wide are literally named `Get` (`UToolMenus`, `UMediaPlaylist`, `ULokiBotManager`, `UVisibilityManager`), and the three shipping ones are all present in the record table under their own class blocks. The `XComponent::Get(AActor,FName)` form is used by 30+ component classes and binds nowhere.

⇒ **`Get` will return the component, and `AuthPlayerEnterWorldAttachedToRidable` WILL be called — provided `v38 != nullptr` (see §4).**

---

### 3. Row 8 re-verified from the bytes, and the log-strip question

**FK-22/S130's grade is CORRECT.** Machine-decoded rel32 (no hand arithmetic; `merged2` ImageBase `0x7FF6AF000000`):

```
0x55CD510  test rdx,rdx                       ; rdx = PlayerState  (rcx=component, r8=&SpawnLocation)
0x55CD513  je   0x55CD793                     ; -> bare `ret`, BEFORE the prologue. SILENT.
0x55CD535  mov eax,[rdx+0xC]; shr 30; not; test 1
0x55CD548  je   0x55CD77B                     ; IsValid() fail -> epilogue ret. SILENT.
0x55CD54E  call 0x55DCAA0 ; test al,al; jne 0x55CD77B   ; SILENT.
0x55CD55B  mov rax,[r14+0xC0] ; if 0 -> call 0x35AFC40  ; cached world / world getter
0x55CD572  call 0x0F7EB50   <-- e8, disp -0x464EA27, target bytes 33 c0 c3 = xor eax,eax; ret
0x55CD577  test rax,rax
0x55CD57A  je   0x55CD7B2   <-- ALWAYS TAKEN
```

The identical shape is at `AuthPlayerPreSpawnOnAddToPlane` (`0x55CD842 → 0xF7EB50`, then `je 0x55CD99A`) [M].

**The bail block, and the strip answer — there are TWO channels and only one is stripped:**

```
0x55CD7B2  cmp byte [0x0A035E80], 2      ; category runtime verbosity gate
0x55CD7B9  jb  0x55CD7CE
0x55CD7BB  lea rdx,[0x08B1CF08]          ; static log record
0x55CD7C2  lea rcx,[0x0A035E80]          ; FLogCategoryBase
0x55CD7C9  call 0x0106B650               ; ** REAL emit ** (bytes 48 89 54 24 ...)
0x55CD7CE  lea rdx,[0x08B1CF30]          ; same message text
0x55CD7DA  call 0x00FAC920               ; FString ctor
0x55CD7E4  call 0x00F7EC20               ; ** STRIPPED (ret 0) ** — 2nd reporting channel is DEAD
```

⇒ **The `UE_LOG` itself is NOT stripped.** Positive control that `0x106B650` is a live dispatcher: 22 other call sites share category `0x0A036AC0`, two of whose records (`Client is ready to play.`, `%s is ready to play.`, both verbosity 4) appear verbatim in the live corpus as `LogLokiGameMode: Display: …` [M]. So **`0x0A036AC0 = LogLokiGameMode`** and the emit path demonstrably works.

**Records recovered (source file `C:\TheoryCraft\build-staging\Loki\Source\Loki\DropPhase\LokiRideableComponent.cpp`, 4 records total):**

| rec | line | verb | category | text |
|---|---|---|---|---|
| `0x8B1CC98` | 171 | 3 = **Warning** | `0x09D28CF8` (unnamed) | `Could not find a valid 3D terrain location to spawn this player, this may result in the player respawning in an unexpected location.` |
| `0x8B1CE28` | 257 | 2 = **Error** | `0x0A035E80` (unnamed) | `ULokiRideableComponent::AuthPlayerPreSpawnOnAddToPlane failed to get the round game mode` |
| `0x8B1CF08` | 299 | 2 = **Error** | `0x0A035E80` (unnamed) | `ULokiRideableComponent::AuthPlayerEnterWorldAttachedToRidable failed to get the round game mode` |
| `0x8B1CFF0` | 327 | 2 = **Error** | `0x0A036AC0` = **`LogLokiGameMode`** | `AuthPlayerEnterWorldAttachedToRidable: Attempting to attach ourselves to a drop pod whithout a pre-spawned hero.` |

Verbosity numbering is UE-standard (2=Error, 3=Warning, 4=Display) — pinned by the `Display` control above; and the gate constant equals the record's verbosity in 2/2 checked sites [M]. All three Errors therefore **print at default verbosity — no `[Core.Log]` change needed**.

⚠ **Category `0x0A035E80` is COVERAGE-BLOCKED, not unnamed-in-the-game.** It has exactly **2** rip-relative references in the decrypted 54.9 % of `.text` and both are these emits; its `FLogCategory` ctor site is on an undecrypted page, and the `FName` at `cat+4` needs the runtime name pool. Grep by message text, not by category.

---

### 4. ⚠⚠ THE FINDING THAT DECIDES WHETHER S131 CAN REACH THE FIFTH WALL AT ALL

Read from the **disassembly appendix** of `GetTeamDropLeader` (`tools/asdump/out/GameMode/DropPhase/LokiDropShip.as.txt:255+`), not the pseudo-source:

- Loop 1 returns the first PlayerState with `IsSpawnTeamLeader() == true`.
- **Loop 2 is dead code** — `0x0158 JLowZ 0 -> L0160`, `0x0170 JLowZ 2 -> L0180`, `0x0178 JMP 0 -> L0180`, `0x0180 JMP 0 -> L0188`: every branch falls through, both call results discarded.
- Fall-through is `L01B0: FreeNullV8 v30 … LOADOBJ v30` ⇒ **returns nullptr** (nulled, not garbage) [M].

`ALokiPlayerState::IsSpawnTeamLeader` impl `0x56C2060` is **REAL**, but its only writer `ALokiPlayerState::AuthSetSpawnTeamLeader` impl is **`0xF7EC20` = EMPTY STUB** (reconfirmed by this instrument, matching FK-1). ⇒ **[I, strong] `v38 = GetTeamDropLeader(TeamIndex)` returns nullptr on the client route.**

Consequences, all straight from the `SpawnDropPodForTeam` bytecode [M]:
- `bIsTeamLeader` is a **hardcoded literal `true`** (`0x0108 SetV1 v3 1`) ⇒ `QueueCrewForPodSpawn` always runs.
- `InitializeDropPod(TeamIndex, nullptr, …)` → `SetPilotPlayerState(nullptr)` writes `pod+0x3C0 = 0`; `SetOwner(nullptr)`.
- `AuthPlayerEnterWorldAttachedToRidable(nullptr, …)` → **`test rdx,rdx; je` fires on instruction #1 and returns SILENTLY. The "failed to get the round game mode" Error NEVER PRINTS.**
- `if (v38 != nullptr)` guards the entire `ULokiPlayerDropPlaneComponent::Get` + `MulticastOnDropPodLaunched` block (`0x01AC CmpPtrNull v38; JZ -> L0204`) ⇒ row 9 is skipped too.

⇒ **A flight that reaches `SpawnDropPodForTeam` and logs nothing says NOTHING about the fifth wall.** The absence of the Error is UNINTERPRETABLE unless `v38 != nullptr` is separately established.

★ **The free discriminator is `pod + 0x3C0`.** After `InitializeDropPod`: `0x3C0 == 0` ⇒ `GetTeamDropLeader` returned null, the rideable path was never entered, the run is VOID for this question. `0x3C0 == <a real ALokiPlayerState>` ⇒ the path was genuinely exercised and the Error line **must** be in `Loki.log`. Same read also grades rows 1 and 2 in one RPM.

---

### 5. Grep patterns for `Loki.log`

Format is `LogXxx: <Verbosity>: <message>`.

```
AuthPlayerEnterWorldAttachedToRidable failed to get the round game mode      # Error, cat 0x0A035E80 (name coverage-blocked)
AuthPlayerPreSpawnOnAddToPlane failed to get the round game mode             # Error, same category
Attempting to attach ourselves to a drop pod whithout a pre-spawned hero     # Error, LogLokiGameMode  [sic: "whithout"]
Could not find a valid 3D terrain location to spawn this player              # Warning, cat 0x09D28CF8
Failed to spawn actor of type                                                # S130's per-attempt NULL receipt
```
One combined form: `grep -nE "failed to get the round game mode|whithout a pre-spawned hero|valid 3D terrain location|Failed to spawn actor of type" Loki.log`

**Emits NOTHING (never use their silence as evidence):** `RemovePlayerFromPlane`, `AuthPlayerEnterWorldNew`, `AuthAddPlayer`, `AuthRemovePlayer`, `AuthSetCanJump` (all `0xF7EC20`); `AuthPlayerEnterWorldAttachedToRidable` **when `PlayerState == nullptr`**; and the stripped second channel at `0x55CD7E4`.

---

### 6. Corrections and residual unknowns

- **FK-22 §2.5's COVERAGE-BLOCKED list shrinks.** `ULokiRideableComponent::GetLandingTeleportLocation` is **REAL** (`0x55D89F0`); `AuthPlayerPreSpawnOnAddToPlane` **REAL** (`0x55CD800`); `AuthPlayerEnterWorldNew` **EMPTY** (`0xF7EC20`) — all read from `.data` with the code pages irrelevant. The record instrument answers these without decryption, as predicted.
- **NEW empty stub not previously in FK-1's four:** `ALokiDropPlane::RemovePlayerFromPlane` → `0xF7EC20`. Its sibling `ALokiDropPlane::AddPlayerToPlane` (rec `0x9BD4640`) is also `0xF7EC20`, and `OverridePlaneLocations` (rec `0x9BD4B08`) reproduces FK-1's grade — an in-block positive control.
- **`ULokiPlayerDropPlaneComponent` is declared by NO cooked Blueprint** — `grep -rl` over all 69k extracted JSONs returned 0 files; positive control `grep -c LokiRideableComponent tools/extractor/out/BP_DropPod.json` = **5**. ⇒ [I] it is a native `CreateDefaultSubobject` (`BP_LokiPlayerState` reads `NativeComponents = 2`). **Whether an `ALokiPlayerState` actually carries one is OPEN** — but it only gates row 9, a notify, not the wall.
- Row 9's impl is the **caller-side** stub (`FindFunctionChecked`-shaped lookup on a cached `UFunction*` at `.data 0x0A028700`, then `call [vtable+0x270]`). Whether it executes locally or is swallowed by net routing is [I], untested.
- Row 10a will likely return null on a client (server-only analytics manager); the AS null-check then skips 10b. Harmless.
- ⚠ My own error worth recording: I mis-added `0x7FF6B006B650 − 0x7FF6AF000000` by hand and read the log emit as `0x6B650`, an undecrypted page, briefly concluding the emit was coverage-blocked. It is `0x106B650` and is real. **`fkdis.py` prints absolute VAs in operands and RVAs in the address column — recompute with a machine, every time.**