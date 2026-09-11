# S131 LANE 4 - the `.data` record sweep over FK-22 section 2.5

Read-only, offline. **Zero launches, zero injections, zero `.text` writes.**
Tools, re-runnable from the repo root: `scratchpad/s131/tools/rectab.py`, `scratchpad/s131/tools/lane4_sweep.py`,
`scratchpad/s131/tools/gen_md.py`. Images: `dumps/s129-poolgate`, `dumps/merged2.dump.exe`, `dumps/tutorial-hero`.
Raw output: `scratchpad/s131/sweep_full.tsv` (112 keys x 11 columns).

## 0. THE CONTROL, FIRST - 7/7 PASS, non-degenerate, discriminating in both directions

| control | expected impl | source of expectation | record impl | result |
|---|---|---|---|---|
| `ALokiGameMode::SpawnPlayer` | `0xf7eb50` | FK-1, disassembly | `0xf7eb50` | PASS / EMPTY |
| `ALokiPlayerState::AuthSetSpawnTeamLeader` | `0xf7ec20` | FK-1 | `0xf7ec20` | PASS / EMPTY |
| `ALokiTeamState_TeamOnly::SetDropLeader` | `0xf7ec20` | FK-1 | `0xf7ec20` | PASS / EMPTY |
| `ALokiDropPlane::OverridePlaneLocations` | `0xf7ec20` | FK-1 | `0xf7ec20` | PASS / EMPTY |
| `ALokiRoundGameMode::GoToPhase` | `0x5601020` | S124, disassembly | `0x5601020` | PASS / REAL |
| `ALokiGameState::BP_AuthSetCurrentPhase` | `0x567a160` | S124 | `0x567a160` | PASS / REAL |
| `ALokiRoundGameMode::OnNewPhase` | `0x330c56c` | S124 | `0x330c56c` | PASS / VTABLE-FWD |

The handoff warned that "AS functions have no record" is a degenerate control. This one is not:
all seven are C++ functions whose REAL/EMPTY status was established independently by disassembly,
four are EMPTY and three are REAL, and the instrument separates them correctly. [M]

**Seven further agreements, none designed as controls, all [M]** - the sweep independently reproduces
impl addresses and bytes that FK-22 and CLAUDE.md derived by disassembly:
`ULokiGameModeDropPlaneComponent::AddPlayerToDropPlane` = `0x55cbb60`;
`ALokiServerAnalyticsManager::AddTeamDropEvent` = `0x557eae0`, prologue `48 8b c4 48 89 58 10` = `mov rax,rsp; mov [rax+0x10],rbx`;
`AuthSetDropComplete` = `0x2e09510`, bytes `c6 81 d0 00 00 00 01 c3` = `mov byte [rcx+0xd0],1; ret`;
`GetDropPod` = `0x3078470` = `mov rax,[rcx+0x110]; ret`;
`CanExit` = `0x525c240` = `movzx eax,byte [rcx+0x118]`;
`BroadcastEventRouterReady` = `0x56dd340` = `test rdx,rdx; jne ...; ret`;
`ALokiDropPodBase::SetPilotPlayerState` = `0x55e59e0`.

**An eighth control on the vtable route [M], reproduced in TWO images (`s129`, `tuthero`):**
`ULokiPlayerDropPlaneComponent` vtable `0x8a22520` - `+0x4c0 = 0x56face0` (REAL),
`+0x4c8 = 0xf7ec20` (EMPTY), `+0x4d0 = 0x56f26a0`, `+0x4d8 = 0x56df250`,
`+0x4e0 = 0xf7ec20` (EMPTY), `+0x4e8 = 0x56fae90` - byte-for-byte what section 2.5 records.

## 1. Record-table layout, measured

[M] 9 qwords, stride **0x48**; record start = `name_ptr - 8`.
`+0x08` name_ptr (`.rdata char*`), `+0x10` exec thunk (`.text`), `+0x18` impl (`.text`).
`+0x00` and `+0x20` are a constant dword pair; `+0x28..+0x40` are mutable runtime fields.
[M] **16,277 records in 1,551 contiguous runs** over `.data` (`0x99c7000..0xa0b7000`), unit: records.
Runs are **per-UClass and alphabetically sorted within a class** - that is what makes class attribution
possible. Attribution is by name-set overlap against the UHT oracle `tools/re/out/uht_funcflags_tuthero.csv`;
e.g. the `AddPlayerToPlane` run scores 21/21 against `ALokiDropPlane` and 1/25 against its nearest rival.
**15,720 of 16,277 records attributed** to a unique class.

[M] **Fold control over the whole table:** three of the four known folds are the top-1, top-2 and top-4
impl addresses by multiplicity - `0xf7ec20` x371, `0xf7eb60` x76, `0xf7eb50` x40, `0xb9e1f0` x15.
The other high-multiplicity impls are **not** folds: they are `48 8b 01 ff a0 <disp>` =
`mov rax,[rcx]; jmp [rax+disp]` vtable forwarders (largest `0x3234454` x48). Two further *near*-folds
exist and are worth knowing about (`0xfc57d0` x15 = zero a 16-byte out-param; `0xfc6cf0` x13 =
`xorps xmm0,xmm0; ret`); [M] **no key in this sweep uses either**, so no verdict here depends on them.

## 2. Key-set reconstruction - HONEST STATUS

[M] **The per-key section 2.5 table is not on disk.** A repo-wide grep for `COVBLOCKED` returns
**exactly one file** (unit: files) - `docs/fk22-dropphase-reachability.md` itself. The doc states the
count (100) and the category split, and names about 25 keys in prose; it never enumerates the 100 and
it never lists the "8 drop classes". **The 100 keys had to be reconstructed.**

[M] **Three different 8-class sets sum to exactly 100** under the UHT oracle, so the reconstruction is
under-determined. I adopt **set C** and report the superset beside it:

```
set C (adopted, 100 keys):
  ALokiDropPlane 25 | ULokiPlayerDropPlaneComponent 34 | ULokiRideableComponent 18 |
  ALokiTeamState_TeamOnly 7 | ALokiDropPodBase 6 | ULokiGameModeDropPlaneComponent 4 |
  ULokiDropPhaseLibrary 4 | ULokiDropPhaseDebuggingTool 2
the two rejected alternatives swap ULokiDropOnDeathComponent (4) in for one of the last three
```

[M] **Set C is corroborated by a signal that was not used to select it:** it contains exactly **14**
non-`Native` keys, and section 2.5 independently reports **BlueprintImplementableEvent = 14**. The
cross-tab over set C is 86 `Native`/HAS-RECORD vs 14 non-`Native`/NO-RECORD with **zero** off-diagonal
cells. Over the 112-key superset there is exactly **one** exception, `ULokiRideableInterface::GetRidePosition`
- `Native` but no record, because an interface's native impl is registered on the implementing class
(`ULokiRideableComponent::GetRidePosition` does have one, `0x55dab50`). [I]

## 3. New verdict counts, set C (100 keys)

| verdict | n |
|---|---|
| `REAL` | 63 |
| `NO-RECORD` | 14 |
| `EMPTY` | 12 |
| `REAL/RPC-SEND-STUB` | 7 |
| `IMPL-PAGE-DARK` | 4 |

**Reconciliation against section 2.5's split:**

```
doc BPIE 14             -> NO-RECORD 14                                  [exact]
doc EMPTY-STUB 11       -> EMPTY 11, same keys                           [exact]
doc EMPTY-VIA-VTABLE 2  -> REAL/RPC-SEND-STUB 2 (blind spot; vtable read corrects to EMPTY)
doc COVBLOCKED-THUNK 11 -> 9 REAL + 1 EMPTY + 1 IMPL-PAGE-DARK           [10 of 11 RESOLVED]
doc COVBLOCKED-IMPL 5   -> 3 IMPL-PAGE-DARK + 2 unaccounted               [residual]
doc REAL 51 + INLINED 4 + CONST-BODY 2 = 57 -> REAL 57
---------------------------------------------------------------------------
mine: REAL 63 + REAL/RPC-SEND-STUB 7 + EMPTY 12 + IMPL-PAGE-DARK 4 + NO-RECORD 14 = 100
```

[I] **Residual: 2 keys.** The arithmetic requires 2 of the doc's 5 COVBLOCKED-IMPL to now read REAL and
I cannot exhibit them. It is **not** a coverage effect: [M] no set-C key has an impl page dark in
`merged2`+`tuthero` but lit in `s129`, so my 3-image coverage is not richer than the doc's 18-image union.
The likely cause is that set C differs from the doc's key set by about 2 keys. **Do not read the
reconciliation as proof the two sets are identical.**

## 4. THE HEADLINE - the 16 coverage-blocked keys

[M] **All 11 keys whose exec-thunk page is dark have their impl ADDRESS read straight out of `.data`,
and 10 of the 11 get a definite REAL/EMPTY verdict.** The count 11 matches section 2.5's
COVBLOCKED-THUNK = 11 exactly. Page `0x5456000` (`ULokiRideableComponent`, 7 thunks) is confirmed dark
in all three images - the page-boundary finding stands - and the sweep reads past it without needing it:

| key | thunk | impl | NEW verdict |
|---|---|---|---|
| `ULokiRideableComponent::AuthPlayerDetachPlayerFromRidable` | `0x5456100` | `0x55cccb0` | **REAL** |
| `ULokiRideableComponent::AuthPlayerEnterWorld` | `0x54561d0` | `0x55cce70` | **REAL** |
| `ULokiRideableComponent::AuthPlayerEnterWorldAttachedToRidable` | `0x5456380` | `0x55cd510` | **REAL** |
| `ULokiRideableComponent::AuthPlayerEnterWorldNew` | `0x5456460` | `0xf7ec20` | **EMPTY** |
| `ULokiRideableComponent::AuthPlayerPreSpawnOnAddToPlane` | `0x5456540` | `0x55cd800` | **REAL** |
| `ULokiRideableComponent::ContainsPlayer` | `0x5456700` | `0x55d0270` | **REAL** |
| `ULokiRideableComponent::GetLandingTeleportLocation` | `0x5456c80` | `0x55d89f0` | **REAL** |
| `ALokiTeamState_TeamOnly::GetByTeamIndex` | `0x5483940` | `0x56e6740` | **REAL** |
| `ALokiTeamState_TeamOnly::GetDropLeader` | `0x5483c00` | `0x3259330` | **IMPL-PAGE-DARK** |
| `ALokiTeamState_TeamOnly::GetFuzzyPlayerLocationComponentByTeamIndex` | `0x5483db0` | `0x56e7b90` | **REAL** |
| `ULokiGameModeDropPlaneComponent::SetDropPlane` | `0x5352f20` | `0x55e55e0` | **REAL** |

**The two results that matter for FK-22 section 3:**
- `ULokiRideableComponent::AuthPlayerEnterWorldNew` is **EMPTY** (`0xf7ec20` = `ret 0`) - a NEW empty
  stub, raising the drop-class empty count from the doc's 13 to **14**.
- `AuthPlayerEnterWorld` `0x55cce70`, `AuthPlayerEnterWorldAttachedToRidable` `0x55cd510`,
  `AuthPlayerPreSpawnOnAddToPlane` `0x55cd800` and `AuthPlayerDetachPlayerFromRidable` `0x55cccb0` are
  **REAL** - large bodies with security cookies. Disassembled to confirm: `0x55cce70` opens
  `test rdx,rdx / je / push rbp / lea rbp,[rsp-0x170] / sub rsp,0x270`. This **confirms CLAUDE.md's S130
  note by a fully independent route** and **retires section 2.5's "not-looked-at"** on this family:
  a C++ route to put a player on a rideable does exist as code; what S130 measured is that it always fails.

[M] **4 keys remain unresolved** (`IMPL-PAGE-DARK`) - `ULokiPlayerDropPlaneComponent::FindValidDropLocationInRadius`
`0x5605b90`, `::SelectDropPodDestination` `0x56fa590`, `::TryLaunchDropPod` `0x56ff1d0`, and
`ALokiTeamState_TeamOnly::GetDropLeader` `0x3259330`. For these the impl **address** is now known and is
**not** any fold, but the body is unreadable in these images: COVERAGE-BLOCKED, not ABSENT.

## 5. The instrument's own blind spot, stated [M]

**7 of the 112 keys carry `Net`**: `ServerLaunchDropPod`, `ServerPassDropLeader`, `ServerSetDropPodDestination`,
`MulticastOnDropPodLaunched`, `MulticastOnPlayerEntered`, `MulticastOnPlayerEnteredWorld`, `MulticastOnPlayerExited`.
For an RPC the record's impl field is the **UHT-generated send stub** - all four `ULokiPlayerDropPlaneComponent`
ones cluster at `0x542b2b0..0x542b600`, i.e. one translation unit - **not** the `_Implementation`. The record
therefore reads REAL where the `_Implementation` is EMPTY. Section 2.5's vtable route is the correct one and
I reproduced it (`+0x4c8` and `+0x4e0` are `0xf7ec20`). **Never grade a `Net` key from this table alone.**
The three `Multicast*` keys on `ULokiRideableComponent` are UNRESOLVED by both routes here (that class's
vtable was not located) - uninterpretable, not REAL.


## 6A. SET C - the candidate 100-key table - 100 keys

| key | old verdict (FK-22 2.5) | NEW verdict | impl | evidence |
|---|---|---|---|---|
| `ALokiDropPlane::AddPlayerToPlane` | EMPTY-STUB [M, doc-named] | **EMPTY** | `0xf7ec20` | FOLD ret0(c2 00 00) ; thunk `0x2c2ce30` |
| `ALokiDropPlane::AuthLaunchDropPodForTeam` | REAL [I-recon] | **REAL** | `0x55cb1d0` | bytes12 `4883ec28e8b717dcfd4883c4` ; thunk `0x5335b50` |
| `ALokiDropPlane::AuthStart` | EMPTY-STUB [M, doc-named] | **EMPTY** | `0xf7ec20` | FOLD ret0(c2 00 00) ; thunk `0x52fd620` |
| `ALokiDropPlane::BP_AuthLaunchDropPodForTeam` | BlueprintImplementableEvent [I-recon] | **NO-RECORD** | `-` | no `.data` record; UHT flags carry no `Native` bit |
| `ALokiDropPlane::CanJump` | REAL [I-recon] | **REAL** | `0x55cf390` | bytes12 `80b92404000000750d80b925` ; thunk `0x53361f0` |
| `ALokiDropPlane::GetDropPlaneMapIcon` | REAL [I-recon] | **REAL** | `0x5333e10` | bytes12 `48895c2410574883ec20488b` ; thunk `0x377c3a0` |
| `ALokiDropPlane::GetDropPosition` | REAL [I-recon] | **REAL** | `0x5333e60` | bytes12 `48895c240848897424105748` ; thunk `0x53364f0` |
| `ALokiDropPlane::GetDropZoneBorders` | REAL [I-recon] | **REAL** | `0x5333ed0` | bytes12 `488bc4488958084889681048` ; thunk `0x5336590` |
| `ALokiDropPlane::GetPlayerDropState` | REAL [I-recon] | **REAL** | `0x55d9ac0` | bytes12 `4c8bc94c8bc249c1e8044c8b` ; thunk `0x5336940` |
| `ALokiDropPlane::HasEverContainedPlayer` | REAL [I-recon] | **REAL** | `0x55dca90` | bytes12 `488b89c8030000e904000000` ; thunk `0x53369e0` |
| `ALokiDropPlane::IsPlayerInPlane` | REAL [I-recon] | **REAL** | `0x55dda10` | bytes12 `4c8b81c8030000498b802001` ; thunk `0x5336b20` |
| `ALokiDropPlane::IsReadyToSetDropPodDestination` | REAL [I-recon] | **REAL** | `0x5334140` | bytes12 `48895c2410574883ec20488b` ; thunk `0x5336bc0` |
| `ALokiDropPlane::IsValidDropPodDestination` | REAL [I-recon] | **REAL** | `0x55ddc90` | bytes12 `48895c2408574883ec40488b` ; thunk `0x5336bf0` |
| `ALokiDropPlane::IsWithinDropPlanePath` | REAL [I-recon] | **REAL** | `0x5334190` | bytes12 `488bc4488958084889701048` ; thunk `0x5336ce0` |
| `ALokiDropPlane::IsWithinMaxDropPodDistance` | REAL [I-recon] | **REAL** | `0x5334220` | bytes12 `48895c2408574883ec400f10` ; thunk `0x5336e30` |
| `ALokiDropPlane::OnPlayerEnteredRideable` | REAL [I-recon] | **REAL** | `0x55e0910` | bytes12 `41b001e9989d00004883ec28` ; thunk `0x5337000` |
| `ALokiDropPlane::OnPlayerExitedRideable` | REAL [I-recon] | **REAL** | `0x55e0920` | bytes12 `41b002e9889d00004883c428` ; thunk `0x5337090` |
| `ALokiDropPlane::OnRep_EndLocation` | BlueprintImplementableEvent [I-recon] | **NO-RECORD** | `-` | no `.data` record; UHT flags carry no `Native` bit |
| `ALokiDropPlane::OnRep_StartLocation` | BlueprintImplementableEvent [I-recon] | **NO-RECORD** | `-` | no `.data` record; UHT flags carry no `Native` bit |
| `ALokiDropPlane::OnRep_StartTime` | REAL [I-recon] | **REAL** | `0x55e0fe0` | bytes12 `c68124040000014881c19803` ; thunk `0x5337140` |
| `ALokiDropPlane::OnTeamDropped` | BlueprintImplementableEvent [I-recon] | **NO-RECORD** | `-` | no `.data` record; UHT flags carry no `Native` bit |
| `ALokiDropPlane::OverridePlaneLocations` | EMPTY-STUB [M, doc-named] | **EMPTY** | `0xf7ec20` | FOLD ret0(c2 00 00) ; thunk `0x53372a0` |
| `ALokiDropPlane::RemovePlayerFromPlane` | EMPTY-STUB [M, doc-named] | **EMPTY** | `0xf7ec20` | FOLD ret0(c2 00 00) ; thunk `0x2c2ce30` |
| `ALokiDropPlane::SetCanJump` | EMPTY-STUB [M, doc-named] | **EMPTY** | `0xf7ec20` | FOLD ret0(c2 00 00) ; thunk `0x5296f30` |
| `ALokiDropPlane::UpdatePlaneMovementAndCheckDone` | REAL [I-recon] | **REAL** | `0x53357d0` | bytes12 `48895c2410574883ec20488b` ; thunk `0x3872fe0` |
| `ALokiDropPodBase::GetDropAboveAmount` | REAL [I-recon] | **REAL** | `0x55d7b70` | bytes12 `f30f100568914602c3488b0b` ; thunk `0x5336430` |
| `ALokiDropPodBase::OnPilotPlayerStateReplicated` | BlueprintImplementableEvent [I-recon] | **NO-RECORD** | `-` | no `.data` record; UHT flags carry no `Native` bit |
| `ALokiDropPodBase::OnRep_PilotPlayerState` | REAL [I-recon] | **REAL** | `0x55e0fb0` | bytes12 `e91b33d5ff488b5c24404889` ; thunk `0x5337120` |
| `ALokiDropPodBase::SetPilotPlayerState` | REAL [I-recon] | **REAL** | `0x55e59e0` | bytes12 `488991c003000041b80b0000` ; thunk `0x53375e0` |
| `ALokiDropPodBase::StartPlayerPodSteering` | REAL [I-recon] | **REAL** | `0x55e6a70` | bytes12 `40534883ec3080b9b8030000` ; thunk `0x5337670` |
| `ALokiDropPodBase::StopPlayerPodSteering` | REAL [I-recon] | **REAL** | `0x55e7050` | bytes12 `40534883ec2080b9b8030000` ; thunk `0x5337690` |
| `ALokiTeamState_TeamOnly::GetByTeamIndex` | **COVBLOCKED-THUNK** [I-recon] | **REAL** | `0x56e6740` | bytes12 `48895c2408574883ec208bfa` ; thunk `0x5483940` |
| `ALokiTeamState_TeamOnly::GetDropLeader` | **COVBLOCKED-THUNK** [I-recon] | **IMPL-PAGE-DARK** | `0x3259330` | impl page dark in all 3 images ; thunk `0x5483c00` |
| `ALokiTeamState_TeamOnly::GetFuzzyPlayerLocationComponentByTeamIndex` | **COVBLOCKED-THUNK** [I-recon] | **REAL** | `0x56e7b90` | bytes12 `48895c2408574883ec208bfa` ; thunk `0x5483db0` |
| `ALokiTeamState_TeamOnly::GetTeamVaultDataComponentByTeamIndex` | REAL [I-recon] | **REAL** | `0x56ec410` | bytes12 `48895c2408574883ec208bfa` ; thunk `0x54841f0` |
| `ALokiTeamState_TeamOnly::OnRep_DropLeader` | REAL [I-recon] | **REAL** | `0x56f5610` | bytes12 `e9fb5000004883ec38e8f7ff` ; thunk `0x5484fe0` |
| `ALokiTeamState_TeamOnly::OnRep_ReplicatedBarkData` | REAL [I-recon] | **REAL** | `0x56f5ea0` | bytes12 `48895c2410574881ec900100` ; thunk `0x5485020` |
| `ALokiTeamState_TeamOnly::SetDropLeader` | EMPTY-STUB [M, doc-named] | **EMPTY** | `0xf7ec20` | FOLD ret0(c2 00 00) ; thunk `0x2c2ce30` |
| `ULokiDropPhaseDebuggingTool::OverrideDropPlaneLocations` | REAL [I-recon] | **REAL** | `0x55e1020` | bytes12 `48895c240848897424105748` ; thunk `0x5337160` |
| `ULokiDropPhaseDebuggingTool::PaintDotOnMouse` | REAL [I-recon] | **REAL** | `0x55e10a0` | bytes12 `4883ec68f20f10224c8d1561` ; thunk `0x5337390` |
| `ULokiDropPhaseLibrary::BroadcastDropPodCrewDetachEvent` | REAL [I-recon] | **REAL** | `0x55ce3a0` | bytes12 `4885c90f847801000048895c` ; thunk `0x5335d10` |
| `ULokiDropPhaseLibrary::BroadcastDropPodDirectionChangeEvent` | REAL [I-recon] | **REAL** | `0x55ce530` | bytes12 `4885c90f847801000048895c` ; thunk `0x5335e30` |
| `ULokiDropPhaseLibrary::BroadcastDropPodLeaderDetachEvent` | REAL [I-recon] | **REAL** | `0x55ce6c0` | bytes12 `4885c90f847801000048895c` ; thunk `0x5335f30` |
| `ULokiDropPhaseLibrary::BroadcastDropPodStateChangeEvent` | REAL [I-recon] | **REAL** | `0x55ce850` | bytes12 `4885c90f847801000048895c` ; thunk `0x5336060` |
| `ULokiGameModeDropPlaneComponent::AddPlayerToDropPlane` | REAL [I-recon] | **REAL** | `0x55cbb60` | bytes12 `4056574883ec38488bf1488b` ; thunk `0x5350630` |
| `ULokiGameModeDropPlaneComponent::GeneratePlanePoints` | REAL [I-recon] | **REAL** | `0x55d4940` | bytes12 `488bc4488958084889701057` ; thunk `0x5350bd0` |
| `ULokiGameModeDropPlaneComponent::SetDropPlane` | **COVBLOCKED-THUNK** [I-recon] | **REAL** | `0x55e55e0` | bytes12 `48895c240848897424104889` ; thunk `0x5352f20` |
| `ULokiGameModeDropPlaneComponent::SpawnPlane` | BlueprintImplementableEvent [I-recon] | **NO-RECORD** | `-` | no `.data` record; UHT flags carry no `Native` bit |
| `ULokiPlayerDropPlaneComponent::AuthEnterDropPlane` | REAL [I-recon] | **REAL** | `0x56dbe60` | bytes12 `48899108010000c340534883` ; thunk `0x542d580` |
| `ULokiPlayerDropPlaneComponent::AuthSetCurrentRideable` | EMPTY-STUB [M, doc-named] | **EMPTY** | `0xf7ec20` | FOLD ret0(c2 00 00) ; thunk `0x2c2ce30` |
| `ULokiPlayerDropPlaneComponent::AuthSetDropComplete` | REAL-INLINED / CONST-BODY [M, doc-named] | **REAL** | `0x2e09510` | bytes12 `c681d000000001c3488d8d38` ; thunk `0x542d610` |
| `ULokiPlayerDropPlaneComponent::BP_OnDropPodLaunched` | BlueprintImplementableEvent [I-recon] | **NO-RECORD** | `-` | no `.data` record; UHT flags carry no `Native` bit |
| `ULokiPlayerDropPlaneComponent::BroadcastEventRouterReady` | REAL-INLINED / CONST-BODY [M, doc-named] | **REAL** | `0x56dd340` | bytes12 `4885d20f8527e0d4ffc34883` ; thunk `0x542d650` |
| `ULokiPlayerDropPlaneComponent::CanLaunchDropPod` | REAL [I-recon] | **REAL** | `0x56deb00` | bytes12 `48895c2410574883ec20488b` ; thunk `0x542d6e0` |
| `ULokiPlayerDropPlaneComponent::ClearSelectDropPodInputBinding` | REAL [I-recon] | **REAL** | `0x56df010` | bytes12 `48895c241048897c24185548` ; thunk `0x542d710` |
| `ULokiPlayerDropPlaneComponent::ClearSelectedDropPodDestination` | REAL [I-recon] | **REAL** | `0x542b040` | bytes12 `48895c2408574883ec20488b` ; thunk `0x365bf40` |
| `ULokiPlayerDropPlaneComponent::FindValidDropLocationInRadius` | **COVBLOCKED-IMPL** [I-recon] | **IMPL-PAGE-DARK** | `0x5605b90` | impl page dark in all 3 images ; thunk `0x542de10` |
| `ULokiPlayerDropPlaneComponent::ForwardMovementInput` | REAL [I-recon] | **REAL** | `0x56e5db0` | bytes12 `e9fb55d4ff418d5030807c24` ; thunk `0x542df50` |
| `ULokiPlayerDropPlaneComponent::GetDropComplete` | REAL-INLINED / CONST-BODY [M, doc-named] | **REAL** | `0x3edb490` | bytes12 `0fb681d0000000c333d2488b` ; thunk `0x525f3e0` |
| `ULokiPlayerDropPlaneComponent::GetDropPod` | REAL-INLINED / CONST-BODY [M, doc-named] | **REAL** | `0x3078470` | bytes12 `488b8110010000c34883ec38` ; thunk `0x542e160` |
| `ULokiPlayerDropPlaneComponent::GetSelectedDropPodDestination` | REAL [I-recon] | **REAL** | `0x56eba30` | bytes12 `0f1081180100000f1102f20f` ; thunk `0x542e2e0` |
| `ULokiPlayerDropPlaneComponent::IsLocalPlayerStateComp` | REAL [I-recon] | **REAL** | `0x56ef2b0` | bytes12 `40534883ec20488b99b80000` ; thunk `0x542e430` |
| `ULokiPlayerDropPlaneComponent::MulticastOnDropPodLaunched` | REAL [I-recon] | **REAL/RPC-SEND-STUB** | `0x542b2b0` | bytes12 `48895c2410574883ec20488b` ; thunk `0x53bd130` |
| `ULokiPlayerDropPlaneComponent::OnDropPodEnded` | BlueprintImplementableEvent [I-recon] | **NO-RECORD** | `-` | no `.data` record; UHT flags carry no `Native` bit |
| `ULokiPlayerDropPlaneComponent::OnDropPodStarted` | BlueprintImplementableEvent [I-recon] | **NO-RECORD** | `-` | no `.data` record; UHT flags carry no `Native` bit |
| `ULokiPlayerDropPlaneComponent::OnEventRouterReady` | BlueprintImplementableEvent [I-recon] | **NO-RECORD** | `-` | no `.data` record; UHT flags carry no `Native` bit |
| `ULokiPlayerDropPlaneComponent::OnForwardMovementInput` | BlueprintImplementableEvent [I-recon] | **NO-RECORD** | `-` | no `.data` record; UHT flags carry no `Native` bit |
| `ULokiPlayerDropPlaneComponent::OnPlayerExitedDropPod` | EMPTY-STUB [M, doc-named] | **EMPTY** | `0xf7ec20` | FOLD ret0(c2 00 00) ; thunk `0x542e4a0` |
| `ULokiPlayerDropPlaneComponent::OnRep_CurrentRideableObject` | REAL [I-recon] | **REAL** | `0x56f54d0` | bytes12 `48895c2408574883ec20488b` ; thunk `0x542e580` |
| `ULokiPlayerDropPlaneComponent::OnRep_DropLocationSelected` | REAL [I-recon] | **REAL** | `0x56f5620` | bytes12 `488b89b8000000b201e9a28e` ; thunk `0x542e5a0` |
| `ULokiPlayerDropPlaneComponent::OnRep_DropPlane` | REAL [I-recon] | **REAL** | `0x56f5630` | bytes12 `4883b908010000000f85525e` ; thunk `0x542e5c0` |
| `ULokiPlayerDropPlaneComponent::OnRep_DropPod` | REAL [I-recon] | **REAL** | `0x56f5640` | bytes12 `48895c2408574883ec20488b` ; thunk `0x542e5e0` |
| `ULokiPlayerDropPlaneComponent::OnRightMovementInput` | BlueprintImplementableEvent [I-recon] | **NO-RECORD** | `-` | no `.data` record; UHT flags carry no `Native` bit |
| `ULokiPlayerDropPlaneComponent::OnSelectDropLocationEnded` | BlueprintImplementableEvent [I-recon] | **NO-RECORD** | `-` | no `.data` record; UHT flags carry no `Native` bit |
| `ULokiPlayerDropPlaneComponent::OnSelectDropLocationStarted` | BlueprintImplementableEvent [I-recon] | **NO-RECORD** | `-` | no `.data` record; UHT flags carry no `Native` bit |
| `ULokiPlayerDropPlaneComponent::RightMovementInput` | REAL [I-recon] | **REAL** | `0x56f9650` | bytes12 `e9ab1dd3ff4181f80000800f` ; thunk `0x542e8c0` |
| `ULokiPlayerDropPlaneComponent::SelectDropPodDestination` | **COVBLOCKED-IMPL** [I-recon] | **IMPL-PAGE-DARK** | `0x56fa590` | impl page dark in all 3 images ; thunk `0x542e940` |
| `ULokiPlayerDropPlaneComponent::ServerLaunchDropPod` | REAL [I-recon] | **REAL/RPC-SEND-STUB** -- CORRECTED via vtable `0x8a22520+0x4c0` -> `0x56face0` **REAL** | `0x542b530` | bytes12 `48895c2408574883ec20488b` ; thunk `0x3f74b90` |
| `ULokiPlayerDropPlaneComponent::ServerPassDropLeader` | EMPTY-VIA-VTABLE [M, doc-named] | **REAL/RPC-SEND-STUB** -- CORRECTED via vtable `0x8a22520+0x4c8` -> `0xf7ec20` **EMPTY** | `0x542b570` | bytes12 `48895c2408574883ec20488b` ; thunk `0x3c651a0` |
| `ULokiPlayerDropPlaneComponent::ServerSetDropPodDestination` | EMPTY-VIA-VTABLE [M, doc-named] | **REAL/RPC-SEND-STUB** -- CORRECTED via vtable `0x8a22520+0x4e0` -> `0xf7ec20` **EMPTY** | `0x542b600` | bytes12 `48895c2408574883ec400f10` ; thunk `0x542e9f0` |
| `ULokiPlayerDropPlaneComponent::SetDropPodDestination` | REAL [I-recon] | **REAL** | `0x542b970` | bytes12 `48895c2408574883ec400f10` ; thunk `0x542ee20` |
| `ULokiPlayerDropPlaneComponent::TryLaunchDropPod` | **COVBLOCKED-IMPL** [I-recon] | **IMPL-PAGE-DARK** | `0x56ff1d0` | impl page dark in all 3 images ; thunk `0x542eef0` |
| `ULokiRideableComponent::AuthAddPlayer` | EMPTY-STUB [M, doc-named] | **EMPTY** | `0xf7ec20` | FOLD ret0(c2 00 00) ; thunk `0x2c2ce30` |
| `ULokiRideableComponent::AuthPlayerDetachPlayerFromRidable` | **COVBLOCKED-THUNK** [I-recon] | **REAL** | `0x55cccb0` | bytes12 `4885d20f84ae010000488954` ; thunk `0x5456100` |
| `ULokiRideableComponent::AuthPlayerEnterWorld` | **COVBLOCKED-THUNK** [I-recon] | **REAL** | `0x55cce70` | bytes12 `4885d20f848c060000555741` ; thunk `0x54561d0` |
| `ULokiRideableComponent::AuthPlayerEnterWorldAttachedToRidable` | **COVBLOCKED-THUNK** [I-recon] | **REAL** | `0x55cd510` | bytes12 `4885d20f847a02000048895c` ; thunk `0x5456380` |
| `ULokiRideableComponent::AuthPlayerEnterWorldNew` | **COVBLOCKED-THUNK** [I-recon] | **EMPTY** | `0xf7ec20` | FOLD ret0(c2 00 00) ; thunk `0x5456460` |
| `ULokiRideableComponent::AuthPlayerPreSpawnOnAddToPlane` | **COVBLOCKED-THUNK** [I-recon] | **REAL** | `0x55cd800` | bytes12 `4885d20f84e601000048895c` ; thunk `0x5456540` |
| `ULokiRideableComponent::AuthRemovePlayer` | EMPTY-STUB [M, doc-named] | **EMPTY** | `0xf7ec20` | FOLD ret0(c2 00 00) ; thunk `0x2c2ce30` |
| `ULokiRideableComponent::AuthSetCanJump` | EMPTY-STUB [M, doc-named] | **EMPTY** | `0xf7ec20` | FOLD ret0(c2 00 00) ; thunk `0x5296f30` |
| `ULokiRideableComponent::CanExit` | REAL-INLINED / CONST-BODY [M, doc-named] | **REAL** | `0x525c240` | bytes12 `0fb68118010000c34883ec20` ; thunk `0x5260ec0` |
| `ULokiRideableComponent::ContainsPlayer` | **COVBLOCKED-THUNK** [I-recon] | **REAL** | `0x55d0270` | bytes12 `488b81200100004863892801` ; thunk `0x5456700` |
| `ULokiRideableComponent::GetLandingTeleportLocation` | **COVBLOCKED-THUNK** [I-recon] | **REAL** | `0x55d89f0` | bytes12 `40555356574157488dac2420` ; thunk `0x5456c80` |
| `ULokiRideableComponent::GetRidePosition` | REAL [I-recon] | **REAL** | `0x55dab50` | bytes12 `48895c240848897424105748` ; thunk `0x5457070` |
| `ULokiRideableComponent::HasEverContainedPlayer` | REAL [I-recon] | **REAL** | `0x55dcaa0` | bytes12 `488b81200100004c8bca4c63` ; thunk `0x5457280` |
| `ULokiRideableComponent::MulticastOnPlayerEntered` | REAL [I-recon] | **REAL/RPC-SEND-STUB** | `0x5453780` | bytes12 `48895c2410574883ec20488b` ; thunk `0x53bd130` |
| `ULokiRideableComponent::MulticastOnPlayerEnteredWorld` | REAL [I-recon] | **REAL/RPC-SEND-STUB** | `0x54537c0` | bytes12 `48895c2410574883ec20488b` ; thunk `0x3bcd5b0` |
| `ULokiRideableComponent::MulticastOnPlayerExited` | REAL [I-recon] | **REAL/RPC-SEND-STUB** | `0x5453800` | bytes12 `48895c2408574883ec30488b` ; thunk `0x54573b0` |
| `ULokiRideableComponent::OnRep_PlayersInsideCount` | REAL [I-recon] | **REAL** | `0x55e0fc0` | bytes12 `8b911c0100004881c1e00000` ; thunk `0x5457730` |
| `ULokiRideableComponent::OnRep_bCanExit` | REAL [I-recon] | **REAL** | `0x55e1000` | bytes12 `0fb691180100004881c1d000` ; thunk `0x54577b0` |

## 6B. Keys outside set C - superset plus FK-1 / section 3 extras - 12 keys

| key | old verdict (FK-22 2.5) | NEW verdict | impl | evidence |
|---|---|---|---|---|
| `ALokiDropHidableActor::ClientOnPlayerControllerReceived` | REAL [I-recon] | **REAL** | `0x564fd60` | bytes12 `488bc2488bd1488bc8e9127f` ; thunk `0x5336220` |
| `ALokiGameMode::SpawnPlayer` | REAL [I-recon] | **EMPTY** | `0xf7eb50` | FOLD xor eax;ret ; thunk `0x534c070` |
| `ALokiPlayerState::AuthSetSpawnTeamLeader` | REAL [I-recon] | **EMPTY** | `0xf7ec20` | FOLD ret0(c2 00 00) ; thunk `0x5254180` |
| `ALokiServerAnalyticsManager::AddTeamDropEvent` | REAL [I-recon] | **REAL** | `0x557eae0` | bytes12 `488bc4488958104889701855` ; thunk `0x5463350` |
| `ULokiCharacterMovementComponent::AuthBeginGlideDive` | REAL [I-recon] | **EMPTY** | `0xf7ec20` | FOLD ret0(c2 00 00) ; thunk `0x5254180` |
| `ULokiCharacterMovementComponent::AuthBeginGlideDiveFromDropPod` | REAL [I-recon] | **EMPTY** | `0xf7ec20` | FOLD ret0(c2 00 00) ; thunk `0x530bfd0` |
| `ULokiCharacterMovementComponent::EndGlideDive` | REAL [I-recon] | **REAL** | `0x55a8580` | bytes12 `c7814c120000000080bfc341` ; thunk `0x530c500` |
| `ULokiDropOnDeathComponent::AddDropItemOnDeath` | REAL [I-recon] | **REAL** | `0x564bb00` | bytes12 `4885c90f843d010000488974` ; thunk `0x5335a70` |
| `ULokiDropOnDeathComponent::DeathEvent` | REAL [I-recon] | **VTABLE-FWD** | `0x32f79fc` | bytes12 `488b01ffa0c004000033d2c3` ; thunk `0x3f74b90` |
| `ULokiDropOnDeathComponent::DropItems` | BlueprintImplementableEvent [I-recon] | **NO-RECORD** | `-` | no `.data` record; UHT flags carry no `Native` bit |
| `ULokiDropOnDeathComponent::GetDropOnDeathComponent` | REAL [I-recon] | **REAL** | `0x565c730` | bytes12 `40534883ec20488bd94885c9` ; thunk `0x5336460` |
| `ULokiRideableInterface::GetRidePosition` | BlueprintImplementableEvent [I-recon] | **NO-RECORD** | `-` | no `.data` record; UHT flags carry no `Native` bit |
