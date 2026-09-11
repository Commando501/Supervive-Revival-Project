## VERDICT

**The report is largely sound.** All three of its most load-bearing claims re-derive cleanly from the artifacts, and one of them re-derives *stronger* than the report presented it. Nothing in the top three is refuted. What I found is: **two real omissions on the critical path**, **five grades that should be [I] rather than [M]**, and **one count whose unit will mislead the next person who re-runs the grep**.

---

## THE THREE LOAD-BEARING CLAIMS, RE-DERIVED

### 1. §1a — `LokiIsServer` is a compiled `return false`, `LokiIsClient` a compiled `return true` — **CONFIRMED, and strengthened**

I did not trust `recs.py`. Positive control first: `recs.py SpawnPlayer` → `rec=0x9bdb230 thunk=0x534c070 impl=0xf7eb50`, byte-identical to `docs/fk1-stub-claim-recheck.md`. Then I re-read the record bytes myself, `struct.unpack_from('<3Q', ...)`, in all three images:

```
tuthero  rec=0x9bba7d8 name@0x88ba8b0=LokiIsServer  thunk=0x52e7150 impl=0xf7eb60  bytes=32 c0 c3
tuthero  rec=0x9bba790 name@0x88ba768=LokiIsClient  thunk=0x52e64a0 impl=0xb9e1f0  bytes=b0 01 c3
s129/merged2: identical at the same RVAs.
```
`LokiIsServer\0` and `LokiIsClient\0` each occur **exactly 1 time** image-wide (unit: byte offsets in `dumps/tutorial-hero/SUPERVIVE-Win64-Shipping.dump.exe`), so there is no second UFunction of either name to confuse.

★ **The report did not print the link that closes the thunk-vs-impl trap, and it holds.** I scanned both exec thunks for rel32 edges into the fold set:
```
0x052E71BD  e8 9e 79 c9 fb   call 0xF7EB60      (LokiIsServer thunk)
0x052E650D                   call 0xB9E1F0      (LokiIsClient thunk)
```
and disassembled the control flow to confirm the call is **unconditional**: the thunk's only branch (`0x052E7178 je`) is the WorldContext-default split and both arms converge at `0x052E71A6`, five instructions above the call. So the fold is not merely *registered* as the impl — it is *reached* on every path.

Grade upheld: **[M]**.

### 2. §1/§4 — the state machine (`SetDropPodState` client-bail; `UpdatePodMovement` dead) — **CONFIRMED**

Read from the disassembly appendix, not the pseudo-source, in **two independent renderings** that agree.

`SetDropPodState` (`out/GameMode/DropPhase/LokiDropPod.as.txt:1440-1485`):
```
0008  CMPIi  v1 3
0010  JNZ    -> L0024          ; state != Descending -> skip
0018  PshVPtr this
001C  CALLINTF 84980           ; StartPodMovement          <-- BEFORE the client bail
L0024:
0030  CALLSYS LokiIsClient
003C  JLowZ  -> L004C          ; false -> do the write
0044  JMP    -> L0100          ; TRUE  -> RET, nothing written
L004C: ... ADDSi 1328 (.PodStateEvent) + ADDSi 16 (.DropPodState) ; WRTV1 NewPodState
```
`out/a/GameMode.DropPhase.LokiDropPod.as.txt:1350` renders the same bytecode as `if (!LokiIsClient) {...} else {}` — semantically identical, no structurer inversion in either direction. `1328+16 = 1344 = 0x540` ✓.

`UpdatePodMovement` (`:5484-5510`): `CMPIi v8 3 / JNZ -> L00B4`, then `CMPIi v9 4 / TNZ`, then `L00F0: JLowZ -> L0104` — continue **only** when state ∈ {3,4}; otherwise `JMP 435 -> L07D0` (RET). ✓

`Tick_Implementation` (`:656`): first bytecode is `LoadThisR 1208 ; bHasStartedGameplay / NOT / JLowZ -> L0024 / JMP -> L0258`. ✓ first statement, as claimed.

`OnIntroSequenceFinished` (`:4086-4104`): `v7 = 3`; `if (!bIsTeamLeaderPod && CrewDetachEvent.DetachState != 7) v7 = 2`; `SetDropPodState(v7)`; `AllowPodSteeringStarted()`. ✓

`SetCrewPodDetachState(Attached=1)` on a client — I traced the boolean chain the report marked [M]: `v1 = state ∈ {2,3,4,5}` = false for `Attached(1)`; `v3 = (!v1 && IsClient) = true`; `if (v3) return`. **Early-returns. [M] upheld.**

Grade upheld: **[M]** for the AS path. See correction (E) for the one hole.

### 3. §0/§5 — the offset calibration and `bHasStartedGameplay` as the receipt — **CONFIRMED**

Both §0 controls reproduce exactly (`propscan.py`, s129 image):
- `OnComponentHit off=0x660` = 1632, **hits: 1** image-wide ✓
- `Velocity off=0xE8` = 232, and it is the **only** `0xE8` among **31** records named `Velocity` (I printed the full offset histogram) ✓

Engine offsets: `PrimaryActorTick off=0x38` (**hits: 1**) ✓ · `RootComponent off=0x1B0` (**hits: 1**) ✓ · `RelativeLocation off=0x158` with `Net|RepNotify=OnRep_Transform` (4 hits, correctly disambiguated) ✓ · `ComponentVelocity off=0x1A0` — see (H).

`bHasStartedGameplay`: **`out/a/…:188` reads `bool bHasStartedGameplay;` with NO `UPROPERTY(...)` prefix**, against the immediately adjacent `LeaderPod`, `PodStateEvent`, `CrewDetachEvent` which all carry full `UPROPERTY(BlueprintReadable, BlueprintWritable, …, Replicated, RepNotify)`. That is the positive control the "non-reflected ⇒ no BP/replication writer" claim needs, and it passes. Exactly **4** `LoadThisR 1208 134230872` sites per rendering (ctor / Tick / SPG-read / SPG-write). ✓

Ctor defaults, all re-read from `:270-335`: `InitialDropPodSpeed 2500.0` · `IntroSequenceTotalTime 6.5` · `TotalTimeForPodControls 5.5` · `OutroSequenceTotalTime 1.0` · `TotalPodDestructionDelayTime 1.5` · `DetachingFromLeaderPodStartTime -1.0` · `PodTeamIndex -1` · `bIsHidingDropPhaseHiddenActors true` · `CurrPodDestination ZeroVector` · everything else false/0. **All match the §5 table.** ✓

Grade upheld: **[M]**.

---

## ALSO INDEPENDENTLY CONFIRMED (not among the top three)

- **§4 enum table.** I decoded `.rdata 0x8933870..0x89338C0` as 6×`{char*,int64}`: `None 0 · IntroSequence 1 · Attached 2 · Descending 3 · OutroSequence 4 · Destroying 5`, name strings starting at `0x89338D0`. Exact. The record immediately after `0x89338C0` decodes as garbage, confirming the stated extent.
- **§2 gate.** `LokiBeginPlay_Implementation` (`:504-556`): `CALLSYS LokiIsServer / JLowZ -> L0040` skips `SetTeamForActor`; then `ULokiTeamComponent::GetTeamIndex` → `CMPIi v2 0 / JS -> L0098`; `>=0` → `CALLINTF 84970 StartPodGameplay`, `<0` → `AddUFunction(OnTeamIndexChanged)`. `.OnTeamIndexChanged` at TeamComponent **+208 = 0xD0**, independently corroborating the report's property table.
- **§6 pod table**, from `RESULT-poolspawn-cdopoke-s130.txt`: `after-P1 … new=1` (pod only, **no** `ABP_DropPod_C`); `after-P2` adds `0x1D1824B0DC0 ABP_DropPod_C`; `after-P3` adds `0x1D1A5C0B380 ABP_DropPod_C`; `DropPod 3→5→7`. P3 printed `proxy(root)=null` exactly as the report warns. ✓
- **§6 E1 geometry**, `RESULT-routeE-after-poke-s130.txt:100/216`: `SpawnLocation (-3206.4,5070.5,20100.0)`, `LandingLocation (-3206.4,5070.5,100.0)`, `TeamIndex=0`. ✓
- **§3 tick**: `Default__BP_DropPod_C` has exactly **8** properties, `Default__BP_DropPod_Tutorial_C` exactly **2**; `PrimaryActorTick` appears in neither. ✓ `[S]` on `bStartWithTickEnabled` is honestly graded.
- **§5 Capsule**: `CapsuleHalfHeight 468.38165`, `CapsuleRadius 250.18869`. ✓
- `GetTeamIndex` is **not** a fold in either of its two `.data` records (`impl=0x55ae000` and `0x56bf8a0`, both real bodies), so the report's [I] on the TeamIndex default cannot be short-circuited that way. Its [I, moderate] grade is right.

---

## CORRECTIONS AND OMISSIONS

**(A) — count / unit, will mislead a re-runner.** The asdump corpus contains **four** renderings of this module: `out/a/GameMode.DropPhase.LokiDropPod.as.txt`, `out/b/GameMode/DropPhase/…`, `out/GameMode/DropPhase/…`, `out/modules/GameMode/DropPhase/…`. A literal corpus grep gives `CALLINTF 84970` → **8 hits** and `1208 134230872` → **16 hits**, not 2 and 4. The report's per-rendering numbers are correct and it did state a unit ("bytecode call sites"), but it should say *"2 per rendering; four renderings exist"* or the next reader will think it is refuted.

**(B) — REAL OMISSION, and it is a lever.** `StartPodGameplay` is **`UFUNCTION(BlueprintCallable, CanOverrideEvent)`** (`out/a/…:841`). So: (i) the "complete caller list — exactly TWO [M]" is a claim about *Angelscript* callers only, which the report's own COVERAGE-BLOCKED hedge concedes two paragraphs later — the headline should carry that scope; and (ii) **branch B does not need a `TeamComponent+0xE0` poke or a synthetic `OnPodTeamIndexChanged` call.** `StartPodGameplay` is reflected and reachable by the S55 direct-thunk primitive on the live E1 pod. (`recs.py StartPodGameplay` → `NO RECORD`, as expected — AS names are absent from the exe — so it must be resolved from live reflection, not offline.)

**(C) — REAL OMISSION, unreported hazard inside `StartPodGameplay` itself.** `out/a/…:882-889`:
```
if (Loki::LokiIsClient(__WorldContext)) {
    if (Loki::GetLocalTeamIndex(__WorldContext, true) != this.PodTeamIndex)
        this.SetActorHiddenInGame(true);
}
```
`IsClient` is always true, E1's `PodTeamIndex = 0`, and no team was ever assigned on this route. So in **branch A the E1 leader pod is very likely hidden as well** — the report's §6 warning names only the crew-pod `PreparePodForAttach` path. Harmless for RPM reads; fatal for any screenshot-based confirmation. Worth one line in the pre-registration.

**(D) — REAL OMISSION, unanalysed code on the branch-A critical path.** The last statement of `StartPodGameplay` is `BP_StartPodGameplay()`, and `BP_DropPod_C` really does implement it — `tools/extractor/out/BP_DropPod.json`: `"Type":"Function","Name":"BP_StartPodGameplay","Outer":"BP_DropPod_C","FunctionFlags":"FUNC_BlueprintEvent"`, `SuperStruct = LokiDropPod:BP_StartPodGameplay`. That graph is never read anywhere in the report, and its CDO carries `DropPodStateChangedEventListenerHandle` and `OutroAudioTimerHandle`, i.e. it subscribes to the very state event under discussion. **Every branch-A prediction is conditional on that graph being inert, and nothing establishes that.** Settle it offline for free: `bpdump BP_DropPod BP_StartPodGameplay` (+ its ubergraph).

**(E) — grade: [M] → [I].** §4's "`DropPodState` is 0 under every branch" is [M] for the *Angelscript* path only. The declaration (`out/a/…:192`) is `UPROPERTY(BlueprintReadable, **BlueprintWritable**, …, Replicated, RepNotify, ReplicatedUsing=OnRep_PodStateEvent)`. Replication is inert with no net driver, but a Blueprint write is not excluded — and per (D) there is unread BP code on the path. Contrast `bHasStartedGameplay`, which is genuinely non-reflected and *does* deserve [M]. Same downgrade applies to §7's `PodMeshComponent = non-null [M]` (it is `BlueprintWritable` too).

**(F) — `z ≈ 20100` is a shim knob, not a game property.** `RESULT-routeE-after-poke-s130.txt:100`: `[landing + KPDSPAWNZ=20000 uu on Z]`. The report presents it as an address-free identifier for E1; it is only that if S131 reproduces `KPDSPAWNZ=20000`. Say so.

**(G) — grade: [M] → strong [I].** "P1 never got `PostActorConstruction`" is inferred from the absence of an `ABP_DropPod_C`. The bridging premise ("`USkeletalMeshComponent::InitAnim` only runs on component registration") is engine knowledge asserted without a check against this binary. Its positive control is good (P2/P3/E1 each produced one, and P1's pod still has none after both later spawns), so it is a strong [I] — but it is an inference, and the §7 P1 predictions are all built on it.

**(H) — small count error.** `propscan --name ComponentVelocity` returns **2** hits (`0x07EDFD40 off=0x1A0` and `0x08374638 off=0x50 gen=UInt16`), not "1 plausible hit". The disambiguation is obvious; the printed count is wrong.

**(I) — instrument warning the report should have carried.** `scratchpad/s130/tools/README.md` documents that `propscan.py` is a *reconstructed* file and that its `gen=` type-name table is **misaligned for this build**. It duly prints `gen=InlineMulticastDelegate` for `FVector Velocity` and `gen=Enum` for `OnComponentHit`. The report never leaned on `gen=`, but a reader re-running these commands will see nonsense labels beside correct offsets and may distrust the whole result.

**(J) — incomplete enumeration that happened not to bite.** §5 says Capsule is "the only scene-component root node … the other three are `ProjectileMovement`, `LokiTeam`, and `SCS_Node_13`" — leaving one of four unidentified while asserting a uniqueness claim over all four. I resolved it: `SCS_Node_13` = `LokiRideableComponent`, exported as `[UActorComponent]`, so not a scene component. **Conclusion holds.** Two residual caveats the report should carry: `DefaultSceneRootNode = SCS_Node_0` (a plain `SceneComponent`) exists but is *not* in `RootNodes`, and the UE rule that decides which wins was not verified against this binary ⇒ [I]; and the whole reading is from **`BP_DropPod`**, while the spawned class is **`BP_DropPod_Tutorial_C`**, whose own SCS carries an `InheritableComponentHandler` with 17 records that was not opened. That is parent→child generalisation on the exact axis this project keeps getting caught on.

**(K) — an ungrounded precondition under a specific timed prediction.** §7's "E1 disappears ≈ T0+16 s" requires `OnDropPodHit` to fire, i.e. the Capsule must generate hit events. `bNotifyRigidBodyCollision` lives inside `BodyInstance`, which CUE4Parse renders as an opaque `FStructFallback` — so this is **COVERAGE-BLOCKED at the instrument, not established**. Do not read a non-disappearing pod as a falsification of the model until that is settled.

**(L) — unlisted CDO override worth knowing.** `Default__BP_DropPod_Tutorial_C` overrides `MaxSteerDistance` and `MaxNonLeaderSteerDistance` **7500 → 2000**. Not in the report's table and not load-bearing for the descent prediction, but it is the *entire* content of that CDO and it means "ctor defaults hold" is not universally true for this class.

---

## SUMMARY

3 of 3 top claims **CONFIRMED**, one of them (§1a) now with the thunk→impl call edge the report omitted. 0 refuted. Corrections: 2 real omissions on the branch-A critical path (**C**, **D**), 1 missed lever (**B**), 5 grade downgrades [M]→[I] (**E**, **G**, and the two conditional-on-BP-graph predictions), 3 count/unit fixes (**A**, **H**, **J**), 2 instrument caveats (**F**, **I**, **K**).

Nothing here changes the report's recommended experiment. `bHasStartedGameplay @ pod+0x4B8` really is the right one-byte question, and it really is non-reflected and single-writer.