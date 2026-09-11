# ADVERSARIAL VERIFICATION — LANE 1 REPORT

Verdict: **3 load-bearing claims CONFIRMED, 5 sub-claims REFUTED or invalidated as evidence, 1 new confound the report missed.** The report's core conclusion (ADDSi operand == byte offset from the actor pointer; build the probe on it) survives intact and is stronger than the report argued. Its §(C) `bCanEverReplicate` control is broken.

---

## RE-DERIVATION OF THE THREE MOST LOAD-BEARING CLAIMS

### 1. "ADDSi/LoadThisR operand 1 is a byte offset from `this`" — **CONFIRMED [M]**

Independently replicated on **3** of the report's 12 classes (unit: AS classes), plus 3 corroborating instruments.

**x86 ↔ bytecode, `ALokiDropPod::ALokiDropPod()`.** Extent `0x5963A30..0x5964B66` (4406 B) from `tools/strxref/index/pdata_union.csv:317902`, ONE row (neighbours `0x59639F0..0x5963A23` and `0x5964B70..`, so unchained). Read from **merged2** (page IS decrypted there). Prologue:
```
0x05963A30  4889542410   mov [rsp+0x10], rdx        <- homes arg2
0x05963A3A  56 57        push rsi; push rdi
0x05963A3C  4881ec68040000 sub rsp, 0x468            <- shift 8+8+0x468 = 0x478 => rdx home at [rsp+0x488]
```
Linear capstone disassembly of the full 4406 B → **690 instructions, exactly 50 `add rax, imm`, every one immediately preceded by `mov rax, qword ptr [rsp + 0x488]`.** The AS ctor block (`tools/asdump/out/modules/GameMode/DropPhase/LokiDropPod.as.txt`, `/* ---- ALokiDropPod: 303 dwords / 163 instructions (cache offset 0x8ecf1) ----`) yields exactly 50 ADDSi+LoadThisR operands. The two sequences are **element-for-element identical**:
`1168,1216,1232,1248,1328,1368,1440,1528,1544,1560,1576,1608,968,968,976,976,984,984,992,1000,…,1116,1117,1120,1124,1144,1184,1192,1208,1520,1521,1522,1523,1524,1600,1601,1602`

Instruction-level detail also confirmed verbatim:
```
0x0596484e  48055c040000  add rax, 0x45c   ; 0x5964863 mov byte [rax], cl   <- bPilotHasPodControl
0x05964872  48055d040000  add rax, 0x45d   ; 0x5964887 mov byte [rax], cl   <- bIsTeamLeaderPod (SEPARATE whole byte)
0x05964889  c7442450ffffffff  mov dword [rsp+0x50], 0xffffffff
0x05964899  480560040000  add rax, 0x460   ; 0x59648ad mov dword [rax], ecx <- PodTeamIndex = -1
```
**Replication (mine, not the report's):** `ALokiAirship_AS` @`0x5955350` → 36/36 MATCH; `ATemporaryFloor` @`0x598E980` → 12/12 MATCH. Both sequences are **non-monotone** (`…,5464,5544,5192,5200,…` and `992,1096,1176,944,960,…`), so coincidence is excluded.

**Corroborating instruments:** `propscan.py --name PilotPlayerState` → `.rdata 0x08934170 off=0x3C0`, and the AS class's first member `CrewDropPodClass` = 968 = `0x3C8` = `0x3C0+8`. `recs.py SetPilotPlayerState` → impl `0x55e59e0`, bytes `48 89 91 c0 03 00 00` = `mov [rcx+0x3C0], rdx`. Corpus consistency: **0 offset conflicts** reproduced (see R3 for the count defects).

### 2. "`Loki::LokiIsServer()` is a stub returning FALSE; the `SetTeamForActor` branch is dead" — **CONFIRMED [M], with a provenance defect**

`recs.py` (gold control `SpawnPlayer` → `impl=0xf7eb50`, byte-identical to `docs/fk1-stub-claim-recheck.md`):
```
LokiIsServer  rec=0x9bba7d8 thunk=0x52e7150 impl=0xf7eb60 FOLD xor al;ret  bytes=32c0c3…
LokiIsClient  rec=0x9bba790 thunk=0x52e64a0 impl=0xb9e1f0 FOLD mov al,1;ret bytes=b001c3…
```
Call site, every byte as the report printed it:
```
0x0596a3f9  e8624761fb  call 0xf7eb60          (rel32 = 0xfb614762, machine-computed)
0x0596a3fe  88442421    mov byte [rsp+0x21], al
0x0596a420  0fb6442420  movzx eax, byte [rsp+0x20]
0x0596a425  85c0        test eax, eax
0x0596a427  750a        jne 0x596a433
0x0596a429  e98e000000  jmp 0x596a4bc          <- al==0 taken; skips the block
0x0596a43b  480560040000 add rax, 0x460         <- this.PodTeamIndex
0x0596a495  e85618d9ff  call 0x56fbcf0         <- SetTeamForActor, NEVER REACHED
```
Ownership independently confirmed against the bytecode appendix of `LokiBeginPlay_Implementation` (`CALLSYS LokiIsServer / JLowZ 8 / LoadThisR 1120 / CALLSYS SetTeamForActor / L0040: PshGPtr NAME_None`) — 1:1 with the x86, including the `lea rax,[rip+0x46d2cf5]` global load at `0x596a4bc`.

⚠ **PROVENANCE DEFECT (not a refutation): the report never named the image.** That page is **all zeros in merged2, tuthero AND merged**; it is decrypted **only in `dumps/s129-poolgate`**. A reviewer re-deriving on the "canonical" merged2 gets a blank and, per `fkdis`'s own known defect, could read it as refuted.

### 3. "The observable-field table (offsets + cooked defaults)" — **CONFIRMED [M]**, three provenance errors

Every offset appears **literally** in the annotated bytecode (not interpolated): `1128 .ImpactIndicator` = 0x468 (`LokiDropPod.as.txt:1195`), `1136 .GroundLaserIndicator` = 0x470 (`:4593`), `1592 .PodMeshComponent` = 0x638 (`:1025`), plus 0x460/0x478/0x45D/0x45C/0x464/0x490/0x4B0/0x4B8/0x530/0x648 from the ctor.

`ar_query.py --name BP_DropPod_Tutorial` (36,625 Blueprint assets) really does carry AS UPROPERTY values — the `[AR]` provenance is legitimate: `PodTeamIndex = -1` · `CurrPodDestination = (X=0.000000,Y=0.000000,Z=0.000000)` · `bIsTeamLeaderPod = False` · `LeaderPod = None` · `ImpactIndicator = None` · `GroundLaserIndicator = None` · `PodMeshComponent = None` · `PodStateEvent = (DropPod=None,DropPodState=None,PodPilot=None,bIsLeaderPod=False)` · `bCanEverReplicate = true` · `ParentClass = BP_DropPod_C`. `bHasStartedGameplay` is **absent** from AR, as the report said.

`bpdump_BP_DropPod_Tutorial_PROPS.txt` — `Default__BP_DropPod_Tutorial_C` serializes **only** `MaxSteerDistance` / `MaxNonLeaderSteerDistance = 2000`. ✓
`InitializeDropPod` bytecode writes exactly `1144 / 1117 / 1120 / 1200` + `SetPilotPlayerState` + `SetOwner` + conditional `QueueCrewForPodSpawn`. ✓
`boolscan.py --name bCanEverReplicate` → `.rdata 0x07F1FDF0 … SetBitFunc=0x02078900 [mov byte ptr [rcx + 0x6c], 1] disp=0x6c mask=0x1`, pflags `0x0020080000010015` — exact. ⚠ note `fold=8` on that SetBitFunc, which the report did not print.
`propscan.py --name Owner` → `.rdata 0x07F202F0 off=0x150 … Net|RepNotify … repnotify=OnRep_Owner` — exact.
AS name census in s129: `PodTeamIndex/bIsTeamLeaderPod/CurrPodDestination/TeamDropPodClass/SpawnDropPodForTeam/MaxSteerDistance/bHasStartedGameplay/PodMeshComponent/AttachedCrewPods` all **0 ASCII / 0 UTF-16**, controls `bCanEverReplicate 1`, `bEnablePooling 1/1`, `bSupportsActorPoolPriming 1`, `PilotPlayerState 5/6`. ✓

⚠ **`[CTOR]` is cited for `ImpactIndicator`, `GroundLaserIndicator` and `PodMeshComponent`. None of the three is in the ctor** — I enumerated all 50 ops. Their defaults come from `[AR]` alone. Evidence label attached to a source it did not come from.

---

## REFUTED / INVALIDATED

**R1 — §(C)'s "free control" does not exist. The three pods POST-date the poke. [M]**
Report: *"The S130 BEFORE census already contains three live non-archetype `BP_DropPod_Tutorial_C` (`0x1D1956C0200`, `0x1D1A5DA7910`, `0x1D1FFDDE830`) that predate the poke."*
- `RESULT-poolspawn-cdopoke-s130.txt:61` — `P0-BEFORE CENSUS summary: DropPlane=3 DropPod=2 DropShip=0`; `grep -c "P0-BEFORE.*BP_DropPod_Tutorial_C.*chain="` = **0**. (The 2 "DropPod" are `WBP_UI_DropPodControls` and `WBP_UI_DropPodIndicator_Animated`.)
- `:154` pre-poke read `Default__BP_DropPod_Tutorial_C … bCanEverReplicate(+0x6C)=1`; `:170,:172,:174` the poke; `:177 poke summary: 3 written, 3 readback-verified`.
- `:187` P1 → `0x1D1FFDDE830` **NEW**; `:200` P2 → `0x1D1A5DA7910` **NEW**; `:228` P3 → `0x1D1956C0200` **NEW**.
They appear in `RESULT-routeE-after-poke-s130.txt` `C0-BEFORE` only because that is a **later injection into the same process** — its "BEFORE" is before Route E, not before the poke; the filename says `after-poke`.
⇒ Under the report's own decision table all four pods would read `0 / 0` = **VOID**. Worse: `grep '0x6C'` across both result files returns **only** `CDO Default__…` lines — **there is not a single `+0x6C` read on a pod INSTANCE anywhere in the S130 corpus**, so the archetype-copy question is wholly unmeasured. Correct design: census + `+0x6C` read taken **before** injecting the poke arm in a new flight, or use `-Variant poolspawn-cdoctrl` / `droppod-pe-cdoctrl` as the control arm.

**R2 — "`SetTeamForActor` … has exactly 1 caller in the whole AS body range — that is what identifies the function" is COVERAGE-BLOCKED, not a count. [M]**
Page census of `0x059128B0–0x05A7F070` (unit: 4 KB pages): **s129 121/366 = 33.1 %**, merged2 32.5 %, tuthero 32.2 %, merged 24.9 %. A rel32 sweep over a 67 %-dark range gives a **floor**, never a count, and cannot identify anything. (`0x56FBCF0` is also not itself inside the AS body range.) The identification is nevertheless **correct** by an instrument the report did not cite: `recs.py SetTeamForActor` → `rec=0x9c2a530 thunk=0x5485920 impl=0x56fbcf0`, `implcov=['s129','merged2','tuthero']`.

**R3 — "9,468 ops across 312 files → 784 distinct (typeid, member) pairs": unit inflated 3–4×, and 784 does not reproduce. [M]**
`tools/asdump/out` holds **78 distinct modules replicated across 4 trees**: `<Module>/` 78 files / 3,156 ops · `b/` 78 / 3,156 · `modules/` 78 / 3,156 · `a/` 78 / **0** (no disassembly appendix). So 9,468 = 3 × 3,156 and 312 = 4 × 78. **The real corpus is 3,156 ops over 78 module files.** Distinct (typeid, member) = **755**, and distinct (typeid, offset) = **755** as well under every derivation I tried — I could not reproduce 784. The **0-conflict conclusion reproduces exactly**, and the 755==755 bijection is a *stronger* statement than the report made.

**R4 — grade silently upgraded. [M]**
The FINDING header carries a single **[M]** over four chained propositions: *"`LokiBeginPlay` never calls `SetTeamForActor`, so … `GetTeamIndex() >= 0` fails, so `StartPodGameplay()` is NOT called."* Only link 1 is measured; the decisive link (ULokiTeamComponent's default team index) is the report's own §(D)#1 "NOT ESTABLISHED". Same laundering in the practical notes: *"`bHasStartedGameplay` and `PodMeshComponent` … are both predicted FALSE/null by the `LokiIsServer` stub."* Reading `StartPodGameplay` (`LokiDropPod.as.txt`, ~line 916-937): `bHasStartedGameplay = true` and `PodMeshComponent = USkeletalMeshComponent::Get(this, NAME_None)` are written **unconditionally at the top, NOT under the `LokiIsServer` guard**. The stub is not what predicts them; the unmeasured component default is.

**R5 — wrong file:line. [M]** `KPDTEAM = 0` is at `tools/sigbypass-mod/tutorial_launch.cpp:7838-7839` (`#ifndef KPDTEAM / #define KPDTEAM 0`), not `:7804` (a comment block listing which arms run). The values themselves check out: `RESULT-routeE-after-poke-s130.txt:216` — `Spawn=(-3206.4,5070.5,20100.0) Landing=(-3206.4,5070.5,100.0) … TeamIndex=0`.

---

## NEW CONFOUND THE REPORT MISSED — it changes the discriminator ranking

`CurrPodDestination` is ranked "strongest — 3 doubles cannot collide by accident". But the expected value `(-3206.4, 5070.5, 100.0)` is **byte-identical to the TrainingStart actor's own location**, which the same shim already reads and prints: `RESULT-poolspawn-cdopoke-s130.txt:145` `control actor = 0x1D011F0A030 loc=(-3206.4,5070.5,100.0)` and `:163` `P0c … got=(-3206.4,5070.5,100.0) | RPM ref=(-3206.4,5070.5,100.0)`. A wrong base pointer, or a read landing on any `RootComponent->RelativeLocation`, reproduces the "expected" triple exactly — a false positive indistinguishable from success. **Free fix: pass a Landing location deliberately offset from every actor in the world (e.g. Z = 137.0).** With that, `CurrPodDestination` really is unforgeable; without it, `PodTeamIndex` (−1 → 0, and −1 appears nowhere else in the neighbourhood) is the safer #1.

---

## CONFIRMED SUPPORTING CLAIMS (spot-checked, no findings)

- **`GetTeamDropLeader` returns null** — and the report under-claimed. The **disassembly appendix** (not just the pseudo-source) shows the fallback loop `L011C..L0188` is a no-op: `IsSpectator → JLowZ 0 → L0160`, `IsSpawnTeamLeader → JLowZ 2 → L0180`, `JMP 0 → L0180`, `JMP 0 → L0188`, **no `LOADOBJ`, no return**; and the tail is `L01B0 FreeNullV8 v30 … LOADOBJ v30; RET 3` — v30 is **explicitly nulled**, not merely uninitialized. ⚠ The report reasoned from the pseudo-source only, which also silently drops the second `IsSpawnTeamLeader()` call — against the standing rule that the appendix is ground truth. Conclusion unaffected.
- `SetDropLeader` impl `0xf7ec20` FOLD ret0; `AuthSetSpawnTeamLeader` impl `0xf7ec20` FOLD ret0 (`recs.py`). ✓
- `IsSpawnTeamLeader` impl `0x56c2060`, 70 B, transcribed correctly: `call 0x338c990; mov edx,[rbx+0xe88]; call 0x56f02e0; mov rcx,[rax+0x688]; call 0x3259330; cmp rax,rbx; sete al`. ⚠ The names `GetWorld` / `GetTeamState` / "resolve" are **[I], unshown**.
- `SetDropPodState` early-returns on `LokiIsClient` (`0x0030 CALLSYS LokiIsClient; 0x003C JLowZ 2; 0x0044 JMP 45 -> L0100`); `ELokiDropPodState::Descending == 3` (`CMPIi v1 3`). ⚠ `StartPodMovement()` runs **before** that check, so `SetDropPodState` is not wholly inert on the client — only its `PodStateEvent` writes are. The report over-generalised slightly.
- `SpawnImpactIndicator` guard is exactly `if(!LokiIsServer) v13=0 else v13=bIsTeamLeaderPod; if(v13) …`. ✓
- `QueueCrewForPodSpawn` early-returns on `PodTeamIndex < 0`, Adds every non-`IsSpawnTeamLeader` PS; `SpawnCrewPodQueue` Adds to `AttachedCrewPods` then `PlayersToSpawnCrewPodFor.Empty(0)`. ✓ (B)#6 stands.
- `PodStateEvent` sub-offsets: only `+8 .DropPod`, `+16 .DropPodState`, `+24 .PodPilot`, `+32 .bIsLeaderPod` are ever addressed (typeid 67120923); size `0x558−0x530 = 0x28 = 40 B`. ✓
- Every unreflected member the report lists is confirmed to carry **no `UPROPERTY()`** in the AS class declaration (`bHasStartedGameplay`, `bSteeringEnabled`, `SteeringStartTime`, `bIsHiding…`, `bPodIsDestroying`, `bRetry*`, `CrewPodBoneName`, `LeaderPodBoneName`, `DetachingFromLeaderPodStartTime`). ✓
- "1,702 pdata rows in the AS body range" reproduces exactly, **unit correctly stated**. ✓

---

## REMAINING UNGROUNDED, WITH WHAT SETTLES IT

| # | claim | grade | settle it with |
|---|---|---|---|
| 1 | `ULokiTeamComponent`'s default TeamIndex — **the load-bearing unknown behind the whole "pod is not functional" prediction** | [S] | `propowner.py` on the `TeamIndex` records → pick the one owned by `ULokiTeamComponent` → read its CDO offset (offline or one RPM read). ⚠ `propowner.py` is one of the four S130 tools the README says was **never re-run**. |
| 2 | "`SetDropLeader` is the ONLY writer of `[TeamState+0x688]`" | [I] — correctly graded | `propscan --off 0x688` shows a `TeamStateTeamOnly` record with **`Net`**, and CLAUDE.md's own rule says the net serializer writes replicated properties by computed-offset memcpy invisible to a displacement scan. Either accept [I] or do a store scan **qualified by decrypted coverage**. |
| 3 | which `GetTeamIndex` record (`0x55ae000` / `0x56bf8a0`) is the component's | [S] — report says so | `propowner` / vtable walk on `ULokiTeamComponent`. |
| 4 | `.DropPodState` is a "1-byte enum" | ungraded in the report | bytecode only bounds it ≤8 B; read the enum record or `struct_layout.py`. |
| 5 | archetype copy carries `bCanEverReplicate` to instances (§C) | [I], and per R1 with **no banked control** | new flight: `+0x6C` on instances **before** the poke arm, or the `cdoctrl` no-poke arm. |
| 6 | `PodStateEvent + 0` contents | unknown — report says so ✓ | — |
| 7 | 9 of the 12 ctor RVA matches | [M] by the report, 3/12 verified by me | re-run the ordered-sequence match on the other 9. |