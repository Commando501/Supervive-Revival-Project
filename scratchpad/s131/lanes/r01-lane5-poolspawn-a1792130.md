## LANE 5 — AUDIT OF RM_POOLSPAWN'S THREE SPAWNS AS AN S131 WITHIN-RUN NEGATIVE CONTROL

⚠ **`tools/sigbypass-mod/tutorial_launch.cpp` is DIRTY in the working tree right now** (`git status` = ` M`, +464/−3 vs HEAD `af2bc43`) — a concurrent S131 agent has already added `PdPodDump` and wired it into `SpLadderStep` at after-P1/P2/P3 and `SpFinalReport`. **All line numbers below are working-tree numbers and will shift.** The diff touches **none** of `SpCallPooled` / `SpRefSpawn` / `SpawnActorCls`, so every finding in (a)–(d) holds for both the S130-flown binary and the current tree.

---

### (a) EXACTLY WHAT P1/P2/P3 CALL, AND WITH WHAT

All three share one argument-construction site per arm; every offset is bound **by name** from the live FProperty chain (`SpFn.ix*`), no positional fallback.

**P1 — `ULokiGameplayStatics::SpawnPoolableActorFromClassDeferred`** [M]
`SpCallPooled(&g_spDef, "P1 Deferred", …)`, `tutorial_launch.cpp:11138`. Dispatch at `:11223`:
```c
bool flt = bp ? CallBPGuarded(F->fn,(void*)g_spCDO,g_rbuf)
              : CallNativeGuarded((void*)F->fn,F->thunk,F->child,(void*)g_spCDO,g_spparms,g_rbuf);
```
Flown values (`RESULT-poolspawn-cdopoke-s130.txt:180,183`):
`WCO = 0x1D18565D260 'BP_LokiGameMode_Tutorial_C'` · `ActorClass = 0x1D195886280 'BP_DropPod_Tutorial_C'` · `SpawnTransform` slot @0x10, 96 B zeroed then written (quatW@+0x18=1.0, Translation@+0x20, Scale3D@+0x40=(1,1,1)) · `Collision = 0 (Undefined)` · `ScaleMethod = 1 (MultiplyWithRoot)` · **`Owner = NULL`, `Instigator = NULL`** · object = the CDO `Default__LokiGameplayStatics 0x1D04B08E7A0` · thunk `0x7FF7C93CF1A0`, grade 1 (native S55 direct-`Func`).
Owner/Instigator are never written — `:11199` `// Owner / Instigator deliberately left at ZERO`, and the params buffer is `memset(buf,0,cap)` at `:11165`.

**P2 — `ULokiGameplayStatics::SpawnPoolableActorFromClass`** [M]
Same function `SpCallPooled(&g_spImm, "P2 NonDeferred", …)`, identical argument set, same CDO, thunk `0x7FF7C93CEEE0`, grade 1. `RESULT…:193,196`.
⚠ The two UFunctions have **different declared parameter order** (Owner/Instigator 4th/5th on Deferred, 6th/7th on the other); the by-name binding is what makes them comparable (`:11168-11198`).

**P3 — the ordinary non-pooled path** [M]
`SpRefSpawn()` (`:11284`) → `SpawnActorCls(g_spPodCls,"P3-reference(non-pooled)")` (`:3480`):
```c
*(uint64_t*)(g_gsbuf+g_oBWorld)=(uint64_t)g_gm2;      // UGameplayStatics::BeginDeferredActorSpawnFromClass
*(uint64_t*)(g_gsbuf+g_oBClass)=(uint64_t)cls;
memcpy(g_gsbuf+g_oBXform,g_xform,xfsz);
g_gsbuf[g_oBColl]=2;   // AdjustIfPossibleButAlwaysSpawn   <-- STATED CONFOUND vs P1/P2's 0
… CallNativeGuarded(g_beginFn,…)  ->  def
*(uint64_t*)(g_gsbuf+g_oFActor)=(uint64_t)def;        // UGameplayStatics::FinishSpawningActor
memcpy(g_gsbuf+g_oFXform,g_xform,xfsz);
… CallNativeGuarded(g_finishFn,…)
```
No `Owner` slot is written (buffer zeroed first ⇒ `Owner = nullptr`). All 8 borrowed offsets were re-derived by name and **all 8 read OK** in the flown run (`RESULT…:211-218`), and `g_gm2 == g_spWco` — `sameWCOasP1P2=1` (`RESULT…:221,303`).

---

### (b) CONTAMINATION CHECK — **CLEAN.** [M]

`InitializeDropPod` (`tools/asdump/out/GameMode/DropPhase/LokiDropPod.as.txt:843-893`, 30 instructions) writes exactly:

| write | member offset (AS `ADDSi`/`LoadThisR`) |
|---|---|
| `CurrPodDestination = LandingLocation` | 1144 = **`+0x478`** |
| `SetPilotPlayerState(PlayerState)` | native `ALokiDropPodBase::SetPilotPlayerState` |
| `bIsTeamLeaderPod = bIsTeamLeader` | 1117 = **`+0x45D`** |
| `PodTeamIndex = TeamIndex` | 1120 = **`+0x460`** |
| `LeaderPod = ParentPod` | 1200 = **`+0x4B0`** |
| `SetOwner(GetPilotPlayerState())` | `AActor::Owner` |
| `if (bIsTeamLeaderPod) QueueCrewForPodSpawn(DropShip)` | writes `PlayersToSpawnCrewPodFor`, then `SpawnCrewPodQueue()` |

⚠ *`ADDSi N` = byte offset* is [M] by one independent cross-check: `LokiDropShip.as` `ADDSi 1144 ; .TeamDropPodClass` and the shim's live RPM read `ship.TeamDropPodClass @0x478` agree (`RESULT-routeE…:167`). Still resolve by name in the probe, per the S131 handoff.

**None of P1/P2/P3 calls `InitializeDropPod`, `SetPilotPlayerState`, `SetOwner`, `QueueCrewForPodSpawn`, or any writer of those five fields.** `g_spP1Ret`/`g_spP2Ret`/`g_spP3Ret` appear only in report/verdict code (`:10200, 11356-11358, 11493-11578`) — grepped exhaustively; **no `FinishSpawningActor` is ever issued on `g_spP1Ret`**.

**Independent second check — nothing else in the process writes them either** [M]: `grep -nE "this\.(PodTeamIndex|CurrPodDestination|bIsTeamLeaderPod|LeaderPod) *=" LokiDropPod.as.txt` returns exactly **4 sites**: the AS constructor (`:308,310,313`), `InitializeDropPod` (`:848,850-852`), and `UpdatePodMovement` (`:5419`, `CurrPodDestination` only).
* AS ctor sets the defaults on **every** instance including deferred ones: `bIsTeamLeaderPod = false`, `PodTeamIndex = -1`, `CurrPodDestination = ZeroVector` [M, ctor listing + disasm appendix].
* **`Default__BP_DropPod_C` has ZERO serialized properties** and `Default__BP_DropPod_Tutorial_C` overrides only `MaxSteerDistance`/`MaxNonLeaderSteerDistance` [M, `bpdump_*_PROPS.txt`] ⇒ no asset-side override of any discriminator.
* **`BP_DropPod_C::UserConstructionScript` writes none of them** [M, freshly dumped this lane → `tools/extractor/out/bpdump_UserConstructionScript.txt`, 10 bytecode entries, complete]: it is two `K2_AttachToComponent` calls (Niagara thruster → `body_01_m_jnt`, `NS_Drop_Thruster_Center` → `jet_01_m_jntSocket`) behind `ClientOnly` + `bIsBabyPod`. ⇒ **the construction script cannot contaminate the control**, which is the one thing that separates the deferred from the finished pods.

⚠ **ONE residual contamination path, `CurrPodDestination` only:** `UpdatePodMovement` (`:5299`) does `CurrPodDestination += dir * (MaxNonLeaderSteerDistance/x) * DeltaSeconds` under `if (v11)` (requires a non-`None` MoveDirection). It would make a *finished, ticking* control pod drift **away from (0,0,0)**, never jump to the landing value. `PodTeamIndex` and `bIsTeamLeaderPod` are untouched by it, so a 3-field read localises any such drift. [I, strong]

⚠ **`PodMeshComponent` is written only by `StartPodGameplay` (`:937`), not by `InitializeDropPod`.** It is a *StartPodGameplay* readout, not a fourth discriminator. Do not read it as one.

⚠ **`Owner` and `PilotPlayerState` are CONDITIONAL discriminators.** `SpawnDropPodForTeam` passes `v38 = GetTeamDropLeader(TeamIndex)`; if that returns null, the E1 pod's `Owner` and `PilotPlayerState` are **null — identical to the controls**. Non-null ⇒ positive evidence; null ⇒ **uninterpretable, not negative**. Use the three the S131 handoff names.

⚠ **The CDO poke is applied BEFORE P1** (`RESULT…:165-176`: `poke summary: 3 written, 3 readback-verified`, then P1 at `:178`), so all four pods are instantiated from `bCanEverReplicate = 0` CDOs. That variable is **held constant** across control and treatment — good, not a confound.

---

### (c) SPAWN LOCATIONS — **P1/P2/P3 ARE ALL AT THE SAME POINT; ONLY IDENTITY SEPARATES THEM** [M]

| arm | spawn Translation | source |
|---|---|---|
| P1 | **(−3206.4, 5070.5, 100.0)** | `RESULT…:179` |
| P2 | **(−3206.4, 5070.5, 100.0)** | `RESULT…:192` |
| P3 | **(−3206.4, 5070.5, 100.0)** | `RESULT…:227` |
| E1 spawn | (−3206.4, 5070.5, **20100.0**) | `RESULT-routeE…:216` (`landing + KPDSPAWNZ=20000`, `tutorial_launch.cpp:8548`) |
| E1 `LandingLocation` | (−3206.4, 5070.5, 100.0) | same line |

All four derive from the **same** origin actor — the `TrainingStart`-tagged actor `0x1D011F0A030` at (−3206.4, 5070.5, 100.0) (`RESULT…:144-146`).

⇒ **P1/P2/P3 are mutually indistinguishable by position and MUST be separated by object identity** (the probe's own printed return pointers), never by coordinates.
⇒ ★ **AND THERE IS AN ALIASING TRAP:** the E1 pod's expected `CurrPodDestination` **is numerically identical to the three control pods' actor location** — both are (−3206.4, 5070.5, 100.0). A readout that prints an actor location next to a `CurrPodDestination` invites exactly the field-confusion that would read as confirmation. **Label the field on every line.** (Mitigation available for free: change `KSPORIGIN`, or read `CurrPodDestination` against the ctor default `(0,0,0)`, which is the actual discriminator.)
⇒ At spawn, E1's pod is 20,000 uu above the controls on Z — a usable *secondary* separator, but the pod carries a `ProjectileMovementComponent`, so **do not rely on it after the first frame**.

---

### (d) DEFERRED STATUS — **P1 IS UNFINISHED; P2 AND P3 ARE FINISHED. THE CONTROL IS NOT HOMOGENEOUS.** [M]

Settled from the disassembly, not inferred (`fkdis.py … --dump merged2`):

* **Deferred impl `0x5670090`** calls the acquire **`0x5648050` directly** at `0x0567019B` (`e8 b0 7e fd ff`). Nothing else follows. ⇒ **no FinishSpawning.**
* **Non-deferred impl `0x566FF50`** calls the wrapper **`0x5647F00`** at `0x05670056` (`e8 a5 7e fd ff`), and that wrapper does:
```
0x05647F41  call 0x5648050            ; the acquire
0x05647F46  mov rbx, rax
0x05647F49  test rax, rax
0x05647F4C  je 0x5647F79              ; null -> fallback path
0x05647F4E  mov r10, [rax]            ; actor vtable
0x05647F6D  call qword ptr [r10+0x578](actor, xform, 0, 0)
```
`[actorVtable + 0x578]` with `(rcx=actor, rdx=transform, r8d=0, r9d=0)` is the shape of `AActor::FinishSpawning(const FTransform&, bool bIsDefaultTransform, const FComponentInstanceDataCache*)` [I, strong — shape + the live corroboration below].
* **Live corroboration, from the flown census** [M]: `ABP_DropPod_C` AnimInstances appear **0 / 1 / 2 / 3** after P1 / P2 / P3 / E1 (`RESULT…:189, 202-204, 229-233`; `RESULT-routeE…:223`). Exactly one pod of the four lacks an AnimInstance, and by census ordering that is P1's. ⇒ P1's pod never registered its `SkeletalMeshComponent`.

**What "deferred" means for the fields being read:**
* `UserConstructionScript` has **not** run on P1's pod ⇒ its two Niagara components are unattached. **[M] it writes none of the five discriminator fields, so this does not contaminate the control.**
* `PostActorConstruction` / `RegisterAllComponents` / `BeginPlay` have not run ⇒ no AnimInstance, no `StartPodGameplay`, no ticking, no `UpdatePodMovement`.
* The **AS constructor ran** (it is the class constructor, executed at object allocation), so `PodTeamIndex = -1`, `bIsTeamLeaderPod = false`, `CurrPodDestination = (0,0,0)` hold on P1's pod as much as on the others.

⇒ **Use P2 and P3 as the primary controls** — they are construction-matched to E1's pod (finished, registered, ticking). **P1 is a second, weaker control** whose value is that it isolates "unfinished" as a third state. Report the three separately; do not pool them.

---

### (e) ADDRESS RECONCILIATION — **THE ARITHMETIC CLOSES AT 3 + 1. THE POPULATION IS CORRECTLY MODELLED.** [M]

| arm | returned pointer | census line |
|---|---|---|
| **P1** Deferred, pooled | **`0x1D1FFDDE830`** | `RESULT…:186-189` |
| **P2** NonDeferred, pooled | **`0x1D1A5DA7910`** | `RESULT…:199-204` |
| **P3** ordinary, non-pooled | **`0x1D1956C0200`** | `RESULT…:228-233` |
| **E1** `SpawnDropPodForTeam` | **`0x1D015C87910`** | `RESULT-routeE…:224` |

Route E's `C0-BEFORE` lists exactly the three pre-existing `BP_DropPod_Tutorial_C` — `0x1D1956C0200`, `0x1D1A5DA7910`, `0x1D1FFDDE830` (`RESULT-routeE…:62,65,66`) — **set-identical to P3, P2, P1.** Zero symmetric difference. `after-E1` adds exactly `0x1D015C87910` + `ABP_DropPod_C 0x1D1A4DA2740`. **3 + 1 = 4.** ✔

Two further checks that close, and one that must be stated:
* ⚠⚠ **The `DropPod` bucket is NOT a pod-actor count.** `DpClassify` (`:6199-6205`) does a **class-CHAIN substring** match on `"DropPod"`, so it counts `ABP_DropPod_C` AnimInstances and `WBP_UI_DropPodControls_C` / `WBP_UI_DropPodIndicator_Animated_C` UserWidgets. Decomposition: baseline `DropPod = 2` = the two widgets; poolspawn `AFTER = 7` = 2 widgets + 3 pods + 2 ABPs; Route E `= 9` = +1 pod +1 ABP. **Quote the unit: 7 and 9 are objects-in-the-name-bucket, not pods.** A successor that reads `DropPod=9` as "nine pods" would be badly wrong.
* Between the two runs: `objects 10 → 11` (+1) while `DropPlane 3 → 4` **and** `DropShip 0 → 1`. That is **one** object in two buckets — `BP_DropPlane_Straight_Tutorial_C 0x1D10A41B380` (`RESULT-routeE…:79,81`), whose chain contains both `DropPlane` and `LokiDropShip`. ⇒ **exactly one object was created between the poolspawn AFTER census and the Route E BEFORE census** — the `dropplane_b1only` ship. Nothing else spawned in the gap. ✔
* **[M] Zero crew pods were produced.** `InitializeDropPod` ran with `bIsTeamLeader = true` ⇒ `QueueCrewForPodSpawn` → `SpawnCrewPodQueue` → `SpawnCrewPod` per queued player state — and the E1 delta was **+2 (one pod + one ABP)**, so the queue produced nothing. ⚠ This is a property of *that* run, not a guarantee: if S131's world has a non-leader player state on team 0 **and** `CrewDropPodClass` is non-null, crew pods will appear **synchronously inside E1** with `PodTeamIndex = 0` and `bIsTeamLeaderPod = false` (`LokiDropPod.as:3706`). ⇒ **capture the three control addresses from the poolspawn marker and match by pointer; do not assume "the pods that were there before" is a stable set.**

⚠ Addresses are per-process (ASLR + heap). S131 gets its own; the S130 values are for reconciliation only.

---

### (f) THE REPRODUCIBLE COMMAND SEQUENCE

⚠⚠ **THE THIRD DLL WAS THE `cdoctrl` BUILD, NOT `cdopoke` — and both the marker filenames and `CLAUDE.md` invite the wrong reproduction.** `RESULT-routeE-after-poke-s130.txt:168,179` read verbatim `build KPDCDOPOKE=0 (CONTROL arm) | THIS call: read-only`. The file *name* ("after-poke") and the stale attempt-2/3 markers (`docs/fk24-stage-s130-cdopoke{2,3}-4-probe-tutorial_launch_droppod_pe_cdopoke.txt`) both say "cdopoke". **Inject `droppod-pe-cdoctrl` (`.text 780da72fbf4d34e7`).** Re-poking is not harmful but it costs another ~2 s game-thread `GUObjectArray` walk and it destroys the "the poke persisted across two further injections" observation, which is the only evidence a class-default poke is durable.

**0. Prep (offline).**
```powershell
# server/internal/interactive/interactive.go:893  ->  const forceTutorialMatch = true
#   (ConnectionDetails "address" is ALREADY "" at :1035 -- do not change it)
& "$env:ProgramFiles\Go\bin\go.exe" build -C server -o ags.exe ./cmd/ags

cd "G:\git\Supervive Revival Project\tools\sigbypass-mod"
.\build.ps1 -Name tutorial_launch -Variant poolspawn-cdopoke     # -> build\tutorial_launch_poolspawn_cdopoke.dll
.\build.ps1 -Name tutorial_launch -Variant dropplane-b1only      # -> build\tutorial_launch_dropplane_b1only.dll
.\build.ps1 -Name tutorial_launch -Variant droppod-pe-cdoctrl    # -> build\tutorial_launch_droppod_pe_cdoctrl.dll
python verify_dll.py build\tutorial_launch_poolspawn_cdopoke.dll   # + the other two; diff .text, never size
```
⚠ **`-Variant X` without `-Name tutorial_launch` silently builds the DEFAULT SET** and reports `N built, 0 failed`, which reads like success (S124). Pass `-Name`.
S130 `.text` sha256 for reference: `poolspawn-cdopoke 8d4a81045820ebec` · `poolspawn-cdoctrl 4e9c12ae866f5359` · `droppod-pe-cdoctrl 780da72fbf4d34e7` · `droppod-pe-cdopoke bc1c1a5b1e66b54a`. ⚠ The `PdPodDump` edit now in the tree **will change all of these** — re-record, don't reuse.

**1. Launch (ELEVATED PowerShell; Steam running first).**
```powershell
cd "G:\git\Supervive Revival Project"
.\configs\launch-redirect.ps1 -NoHook
```

**2. Stage + first injection (SECOND elevated shell, once the game is up).**
```powershell
.\configs\fk24-stage.ps1 `
  -Probe tools\sigbypass-mod\build\tutorial_launch_poolspawn_cdopoke.dll `
  -Label s131-podstate
```
This does `gft_ready_fix` → `tutorial_launch_fo` → `tutorial_launch_sp` → probe, gating each on measured evidence, `-InjectGapSeconds 20` minimum. S130's measured spacing for the successful sitting: fo `01:16:04`, sp `01:16:24` (+20 s), probe `01:16:46` (+22 s). ⚠ Do **not** derive the gft→fo gap from `…-1-gft.txt` — step 1 copies a stale marker `gft` never writes (CLAUDE.md).
Wait for `[PS] done (step=8 …)` in `docs\tutorial-launch-marker.txt` (S130: ~94 s after injection), **then copy the marker off** — the next injection truncates it (FK-25).

**3 & 4. The two manual injections (same shell, same PID).**
```powershell
$pid_ = (Get-Process SUPERVIVE-Win64-Shipping).Id
Copy-Item docs\tutorial-launch-marker.txt scratchpad\s131\RESULT-poolspawn-s131.txt

& tools\inject\inject.exe mmap $pid_ tools\sigbypass-mod\build\tutorial_launch_dropplane_b1only.dll
Start-Sleep -Seconds 25          # >= the 20 s minimum gap (S109)
# wait for DropPlane/DropShip to appear, then:
Copy-Item docs\tutorial-launch-marker.txt scratchpad\s131\RESULT-dropplane-s131.txt
& tools\inject\inject.exe mmap $pid_ tools\sigbypass-mod\build\tutorial_launch_droppod_pe_cdoctrl.dll
# ... wait for the [PD] ladder to finish, then:
Copy-Item docs\tutorial-launch-marker.txt scratchpad\s131\RESULT-routeE-s131.txt
```
S130's real timing: poolspawn result at `01:18:20`, Route E result at `01:21:02` — ~162 s covering both injections plus the Route E ladder.

**Preconditions that are load-bearing** (S130 burned three launches on the second one):
* `dropplane_b1only` **must** run before Route E — it creates the only live `LokiDropShip`. `DropShip = 0` in the census ⇒ `PdResolve` has no ship and E1 cannot be called.
* The pods must be spawned **after** the poke. `poolspawn-cdopoke` handles this itself (poke at ladder step 6, immediately before P1).
* **Budget on armed windows, not launches** — S130 took **4 launches for 1 armed result**, and **all 3 armed windows died artifact-less** (§13.7). Copy the marker off after **every** stage.

---

## VERDICT

**THE 3-POD NEGATIVE CONTROL IS SOUND — with two stated qualifications, neither fatal.** [M]

1. **Uncontaminated on every field `InitializeDropPod` writes** [M]. No arm calls `InitializeDropPod`, `SetPilotPlayerState`, `SetOwner`, or `QueueCrewForPodSpawn`; `Owner` is explicitly `NULL` in all three; and the only other writers of the three discriminators image-wide are the AS constructor (which sets the defaults) and `UpdatePodMovement` (`CurrPodDestination` only, additive from `(0,0,0)`). The construction script — the one thing that could have differed between deferred and finished pods — **writes none of them** [M, dumped this lane].
2. **Same-instrument, same-process, same-class, same-transform, same WorldContextObject** (`sameWCOasP1P2 = 1`, all 8 borrowed offsets re-derived by name) — a genuinely matched spatial control, and free.
3. ⚠ **Qualification 1 — the three are NOT homogeneous.** P2/P3 are **finished**; P1 is **deferred and unfinished** [M, from `0x5647F00`'s `call [actorVtable+0x578]` vs the deferred impl's bare acquire, plus the 0/1/2/3 AnimInstance ladder]. Treat P2 and P3 as the construction-matched controls for E1 and P1 as a separate, third state. Reporting a pooled "3 controls agreed" would hide a real structural difference.
4. ⚠ **Qualification 2 — collision handling differs on P3** (`2 = AdjustIfPossibleButAlwaysSpawn`, hardcoded in the shared `SpawnActorCls`) vs `0 = Undefined` on P1/P2/E1. Irrelevant to the five fields; relevant if a *location* is ever read as evidence. `poolspawn-collmatch` (`KSPCOLLISION=2`) removes it if needed.
5. ⚠ **Separate by IDENTITY, never by position** — all three spawn at the identical point, and the E1 pod's `CurrPodDestination` value is numerically identical to the controls' actor location. Capture the three pointers from the poolspawn marker and match on them.
6. ⚠ **`Owner` and `PilotPlayerState` are conditional**, not discriminators: null on the E1 pod is uninterpretable if `GetTeamDropLeader` returned null. The three named in the S131 handoff (`PodTeamIndex −1→0`, `CurrPodDestination (0,0,0)→landing`, `bIsTeamLeaderPod False→True`) are the sound ones. `LeaderPod` is a trap (null both ways) and `PodMeshComponent` measures `StartPodGameplay`, not `InitializeDropPod`.

**Not contaminated. Not non-existent. Sound, with the deferred/finished split made explicit.** The concurrent edit already in the tree (`PdPodDump` at after-P1/P2/P3 + `P4-AFTER`) is the right shape for it — it labels each arm by spawn path, which is exactly the distinction this audit says must not be collapsed.