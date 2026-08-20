## VERDICT: LARGELY SOUND — 3 core claims CONFIRMED at byte level, 1 sub-claim REFUTED, 1 name UNVERIFIABLE, 3 grade slips.

---

## RE-DERIVED: THE THREE LOAD-BEARING CLAIMS

### 1. (d) "P1 is UNFINISHED; P2 and P3 are FINISHED" — **CONFIRMED** [M], with the *name* of one callee doubted (see §REFUTED-2)

Re-derived from `dumps/merged2.dump.exe` (ImageBase `0x7FF6AF000000`, recovered from the disassembler's own VA↔RVA mapping: VA `0x7ff6b4670090` ↔ RVA `0x5670090`).

**Deferred impl `0x5670090`** — full body, `push`-prologue to `ret` at `0x056701C5`:
```
0x0567019B  e8b07efdff   call 0x7ff6b4648050      ; = RVA 0x5648050, the acquire
0x056701A0  488be8       mov rbp, rax
0x056701A3..0x056701C5   epilogue; ret
```
The report's quoted bytes `e8 b0 7e fd ff` are exact. **Nothing follows the acquire.** CONFIRMED.

**Non-deferred impl `0x566FF50`** — `ret` at `0x05670080`:
```
0x05670056  e8a57efdff   call 0x7ff6b4647f00      ; = RVA 0x5647F00, the wrapper
```
Bytes `e8 a5 7e fd ff` exact. CONFIRMED. And in the wrapper:
```
0x05647F41  e80a010000       call 0x7ff6b4648050  ; the SAME acquire
0x05647F49  4885c0           test rax, rax
0x05647F4C  742b             je 0x5647F79         ; null -> shipped fallback path
0x05647F4E  4c8b10           mov r10, [rax]       ; actor vtable
0x05647F5B  4088742420       mov byte [rsp+0x20], sil
0x05647F67/6A xor r9d,r9d ; xor r8d,r8d
0x05647F6D  41ff9278050000   call qword ptr [r10+0x578]
```
CONFIRMED: the non-deferred path performs a construction/finish virtual after the acquire that the deferred path does not.

**Arm→function binding independently confirmed** (the report asserted it from the shim's own arm label; I derived it from the marker's numbers): live base = `ProcessInternal 0x7FF7C53954A0 − 0x13454A0 = 0x7FF7C4050000`; P1 thunk `0x7FF7C93CF1A0 → RVA 0x537F1A0` = the **Deferred** thunk, P2 thunk `0x7FF7C93CEEE0 → RVA 0x537EEE0` = the non-deferred one (CLAUDE.md §S130). [M]

**AnimInstance ladder** re-derived from `RESULT-poolspawn-cdopoke-s130.txt` census summaries (lines 61/190/205/234/294) and the `*** NEW ***` lists: `DropPod` bucket 2 → 3 → 5 → 7, decomposing as baseline 2 widgets (`WBP_UI_DropPodControls` :25, `WBP_UI_DropPodIndicator_Animated` :32) + pods + `ABP_DropPod_C` = **0 / 1 / 2** ABPs after P1 / P2 / P3, and +1 after E1. CONFIRMED. `P4-AFTER` (:294) still reads `DropPod=7` after a 4 s settle, and Route E's `C0-BEFORE` (:61,64) still lists **2** ABPs for 3 pods ~160 s and one DLL injection later — so one pod *permanently* lacks an AnimInstance.

### 2. (b) Contamination check — **CONFIRMED** [M]

`tools/asdump/out/GameMode/DropPhase/LokiDropPod.as.txt:843` (`void InitializeDropPod(...)`), disassembly appendix at :864–:884, **30 instructions** as stated. Offsets re-decoded by hand and machine-checked:

| AS operand | hex | field |
|---|---|---|
| `ADDSi 1144` (:864) | **0x478** | `CurrPodDestination` |
| `LoadThisR 1117` (:869) | **0x45D** | `bIsTeamLeaderPod` |
| `LoadThisR 1120` (:871) | **0x460** | `PodTeamIndex` |
| `ADDSi 1200` (:875) | **0x4B0** | `LeaderPod` |

Byte-offset semantics cross-checked independently: `LokiDropShip.as:112` `ADDSi 1144 ; .TeamDropPodClass` vs the live shim read `TeamDropPodClass@0x478` (`RESULT-routeE…:167,180-182`). 1144 = 0x478. CONFIRMED.

Write-site enumeration reproduced exactly (:308,:310,:313 ctor — `bIsTeamLeaderPod=false`, `PodTeamIndex=-1`, `CurrPodDestination=ZeroVector`; :848,:850-852 Init; :5419 `UpdatePodMovement`). `PodMeshComponent` written only at :937. CONFIRMED.

I extended the search the report did **not** run — writes to those fields **through a non-`this` receiver, across the whole `tools/asdump/out/` tree**: zero hits outside `LokiDropPod`. So the enumeration survives the obvious hole.

Shim side CONFIRMED: `grep -c QueueCrewForPodSpawn tutorial_launch.cpp` = **0**; `InitializeDropPod`/`SetPilotPlayerState`/`SetOwner` appear only in comments and in the new `PdPodDump` labels; `g_spP1Ret`/`P2Ret`/`P3Ret` appear at 14 sites, all assignment or `Markerf`/verdict — **no `FinishSpawningActor` is issued on any of them**.

`BP_DropPod_C::UserConstructionScript` re-read (`tools/extractor/out/bpdump_UserConstructionScript.txt`, 140 lines, 10 entries): `ClientOnly` gate → `bIsBabyPod` switch → two `K2_AttachToComponent` calls onto `SkeletalMesh`. Writes none of the four fields. CONFIRMED.
★ **And the variant-generalisation trap the report could have fallen into does not fire**: `bpdump_BP_DropPod_Tutorial_PROPS.txt` lists **23 of 23** exports and **none is a UFunction** (`grep -ci "UserConstructionScript|ExecuteUbergraph"` = 0; the class export carries no `UberGraphFunction`, unlike `BP_DropPod_C`'s). The Tutorial leaf declares no construction script of its own, so the parent's dump does cover the spawned class. [M]

### 3. (e) Address reconciliation 3 + 1 — **CONFIRMED** [M]

`RESULT-routeE-after-poke-s130.txt` `C0-BEFORE` live `BP_DropPod_Tutorial_C` at lines **62, 65, 66** = `0x1D1956C0200`, `0x1D1A5DA7910`, `0x1D1FFDDE830` — set-identical to P3 (`:228`), P2 (`:200`), P1 (`:187`). Symmetric difference **0**. `after-E1` (:223,224) adds `0x1D015C87910` + `ABP_DropPod_C 0x1D1A4DA2740`. **3 + 1 = 4.** CONFIRMED.

Gap accounting CONFIRMED: poolspawn `after-P3` `DropPlane=3 DropPod=7 DropShip=0 objects=10` → routeE `C0-BEFORE` `DropPlane=4 DropPod=7 DropShip=1 objects=11`; the single new object is `BP_DropPlane_Straight_Tutorial_C 0x1D10A41B380` (:63), whose chain contains **both** `DropPlane` and `LokiDropShip`. One object, two buckets. ✔

Bucket-unit warning CONFIRMED at source: `DpEvalClass` (`tutorial_launch.cpp` ~:6194-6209) walks the class chain doing `strstr(n,"DropPod")` — so `DropPod=9` is objects-in-the-name-bucket, not pods. The report quoted the unit correctly.

---

## REFUTED

### R-1. "`Default__BP_DropPod_C` has **ZERO** serialized properties" — **REFUTED. It has 8.**

`scratchpad/s130/evidence/bpdump_BP_DropPod_PROPS.txt`, the single `## [UObject] Default__BP_DropPod_C` section, machine-counted = **8 properties** (unit: serialized property entries):
`UberGraphFrame`, `DropPodStateChangedEventListenerHandle`, `OutroAudioTimerHandle`, **`CrewDropPodClass = BP_DropPod_Child_C`**, `ImpactIndicatorClass`, `GroundLaserIndicatorClass`, `bReplicateMovement = True`, `LokiReplicationStrategy`.

The report cited this file as [M] for a value the file contradicts. **The conclusion survives** — none of the 8 is a discriminator, so "no asset-side override of any discriminator" still holds — but the stated evidence was wrong and two consequences follow:

* ★ **The report's own §(e) crew-pod caveat is stronger than it says.** It made the risk conditional on "*and* `CrewDropPodClass` is non-null". It **is** non-null: `BP_DropPod_Child_C`, inherited by `BP_DropPod_Tutorial_C` (which overrides only `MaxSteerDistance`/`MaxNonLeaderSteerDistance`). So the only remaining gate on synchronous crew pods inside E1 is a queued non-leader player state. The "capture the three control addresses and match by pointer" instruction is therefore mandatory, not prudential.
* ⚠ **New, unflagged**: the S130 CDO poke covered `BP_DropPod_Tutorial_C` / `BP_DropPod_C` / `LokiDropPod` — **not `BP_DropPod_Child_C`**. If crew pods spawn through the pooled path they hit an un-poked `bCanEverReplicate = 1` and C7 rejects them. That is a *prediction*, not a finding, but it changes what a crew-pod null would mean.

### R-2. "`[actorVtable + 0x578]` … is the shape of `AActor::FinishSpawning`" [I, strong] — **UNVERIFIABLE as named; the name is doubtful.**

I resolved the slot from the cold image rather than from shape. Using the marker's own provenance (`AActor::ProcessEvent` = RVA `0x3396280` at vtable disp `0x270`), `fkdis findptr 0x3396280` gives AActor-derived vtables; for **7 of 7 sampled** (`0x079FD468`, `0x07C18398`, `0x07C19868`, `0x07C1B678`, `0x07C1BE68`, `0x07C24698`, `0x07C24EF0`, each minus `0x270`), slot `+0x578` holds the **same** target: **RVA `0x3384680`**. [M]
⚠ `findptr` caps at 200 rows — I sampled 7 of a capped list, so "all AActor vtables agree" is a **floor**, not a census; but agreement on 7/7 is enough to identify the base implementation.

Body at `0x3384680`:
```
0x03384686  cmp byte [rcx+0x2d3], 0      ; +0x2D3 = the project's MEASURED AActor::bEnablePooling
0x03384699  test byte [rcx+0x6d], 0x40
0x0338469D  mov byte [rcx+0x373], 1      ; a "has finished" style latch, set unconditionally
0x033846A6  movzx eax, byte [rsp+0x60] / mov byte [rsp+0x60], al   ; bool-normalise the SIXTH argument
0x033846B4  jmp 0x7ff6b2380d50           ; tail-forward, 6 args
0x033846D3  call 0x7ff6b2399f70
0x033846DE  call qword ptr [rax+0x790]   ; one no-arg virtual on self
```
The objection: **`AActor::FinishSpawning` is non-virtual in stock UE5** — a vtable dispatch is the wrong shape for it — while `AActor::ExecuteConstruction(Transform, RotationCache, InstanceDataCache, bIsDefaultTransform, ScaleMethod)` *is* virtual and is a 6-slot (this + 5) call, which matches the callee's read of the 6th argument slot at `[rsp+0x60]`. Both readings fit the call site's registers. The `byte[+0x373]=1` latch argues for `FinishSpawning`; the arity and virtuality argue for `ExecuteConstruction`.
**I could not settle the name offline.** ⇒ record it as *"the AActor construction/finish virtual at slot 175 (`disp 0x578`, RVA `0x3384680`)"* and drop the specific name. **The report's structural conclusion is unaffected** — it holds under either name, and is independently carried by the AnimInstance ladder.

---

## GRADE SLIPS AND REMAINING [I]

1. **"by census ordering that is P1's"** — presented inside an [M] bullet; it is **[I, strong]**. The census alone permits the alternative assignment (P1's ABP appearing late, inside P2's census window, with P3's pod being the one that never registers). It is excluded only by *combining* the census with the deferred-path disassembly. Say so, or the conclusion inherits an unstated dependency.
2. **`Collision = 0 (Undefined)`, `ScaleMethod = 1 (MultiplyWithRoot)`** — the marker itself (`:181`) states the *values* are stock-UE numbering **[I]** and only the enum *names* are read live. The report printed the value-names bare. Same for **`Default__LokiGameplayStatics`** — the marker prints only `the object is the CDO 0x1D04B08E7A0`, never that name.
3. **"the AS constructor ran, so `PodTeamIndex = -1` … hold on P1's pod"** — [I]. Nobody has read those fields on any of the four pods; that is exactly what `PdPodDump` exists to settle. Present it as the prediction under test, not as an established property of the control.
4. **The 4-write-site enumeration is a *pseudo-source* grep**, and this project's own rule says the pseudo-source is a reading aid. I checked the failure mode directly: the alternate decompilation `tools/asdump/out/b/GameMode/DropPhase/LokiDropPod.as.txt:2289` renders the same statement **inverted** as `this.LeaderPod = this.CrewDetachEvent.LeaderPod;`, while the canonical file's appendix at :2536 shows `ADDSi 1200 ; .LeaderPod` followed by **`RDSPtr`** — a **read**. The canonical answer is right and variant `b` is the inverted one. Cite the appendix, not the grep.
5. **`UpdatePodMovement` drift is additive-from-(0,0,0)** — [I, strong], I did not re-derive :5419's arithmetic.
6. **`GetTeamDropLeader` conditionality** — well-founded and *not* settleable offline: the S130 marker (`:172`) reads `GetTeamDropLeader=0x0(owner -)` / "not on the ship's class chain -> NOT CALLED", so the shim never even resolved it.

---

## ONE STRUCTURAL POINT THE REPORT UNDER-STATES

`LokiDropShip.as:147/155/157` (canonical file; the report cited `:153`) shows E1's real path:
```
147:  v36 = LokiGameplay::SpawnPoolableActorFromClassDeferred(...)    <- the SAME call as P1
155:      v6.InitializeDropPod(TeamIndex, v38, LandingLocation, v3, this, nullptr)
157:      FinishSpawningActor(v6, v32)
```
So **E1 = P1's acquisition path + `FinishSpawningActor` + `InitializeDropPod`.** The report's "use P2/P3, P1 is a weaker control" is right for reading the five *fields* (P3 differs from E1 in exactly one variable: no `InitializeDropPod`; P1 differs in two). But P1 is the **acquisition-matched** arm, and calling it merely "weaker" hides that: P1 vs E1 isolates *finish + Init together*, P3 vs E1 isolates *Init alone*. Report all three separately, as the report says — but for that reason, not only the finished/unfinished one.

## CITATION HYGIENE (checked, mostly clean)

`RESULT-*` line citations are essentially exact: `:179`, `:180`, `:187`, `:193`, `:200`, `:211-218` (the eight `=> OK` offset lines — exact), `:221`, `:228`, `:303`; routeE `:62,65,66`, `:168`, `:179`, `:216`, `:223`, `:224`. One drift: P3's translation is at **`:222`**, not `:227`. `tutorial_launch.cpp` numbers are uniformly **~+91 stale** (`:11199 → 11290`, `:11223 → 11314`, `:11165 → 11257`) — the tree grew further after the report was written; the *content* matches at the shifted lines. `SpCallPooled(&g_spDef,"P1 Deferred",…)` is at **:11468**, not `:11138`.

## §(f) SPOT-CHECKS — all CONFIRMED

`build.ps1:380` `droppod-pe-cdoctrl = … -DKPDCDOPOKE=0`, `:381` `cdopoke = …=1`; `RESULT-routeE-after-poke-s130.txt:168,179` read `build KPDCDOPOKE=0 (CONTROL arm)` while the CDOs read `bCanEverReplicate=0` — so the third DLL **was** `cdoctrl` and the poke **did** persist. The misleading markers `docs/fk24-stage-s130-cdopoke{2,3}-4-probe-tutorial_launch_droppod_pe_cdopoke.txt` exist as described (those are the two dead attempts). `interactive.go:893 forceTutorialMatch = false` ✔ exact; `:1035 "address": ""` ✔ already empty; `SpawnActorCls` hardcodes `g_gsbuf[g_oBColl]=2` at `:3384`/`:3493` while `KSPCOLLISION` defaults to `0` (`:10632`) — the stated confound is real and correctly described; `inject.exe mmap` is the form `fk24-stage.ps1:276` uses.

**Summary: 3 core claims confirmed at byte level, 1 factual sub-claim refuted (0 → 8 properties, conclusion survives, one caveat strengthened), 1 function name unverifiable and probably wrong (conclusion unaffected), 4 items to downgrade [M] → [I].** The audit's operational recommendations — separate by identity, do not pool the three arms, treat `Owner`/`PilotPlayerState` as conditional — all stand.