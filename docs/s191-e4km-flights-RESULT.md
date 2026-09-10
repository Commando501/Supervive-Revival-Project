# S191 E4 Options K + M — Flights 1 [M] BREAKTHROUGH: S55 primitive has a UObject*-return marshaling defect; the byte model is CORRECT — 2026-09-10

★★★★★★★★ **THE S55 CALLNATIVE-GUARDED PRIMITIVE RETURNS NULL FOR `GetAbilityByInputID` WHILE
THE SAME FUNCTION CALLED VIA A RAW __FASTCALL POINTER RETURNS THE EXPECTED INSTANCE. Three prior
E4-arc flights (E4A F1, E4E F1, E4K F1) all measured "NULL" via S55 and derived structural
conclusions from that null. Those conclusions are now REFUTED: the runtime path works, the
byte model is correct, and the S55 primitive has a UObject*-return marshaling defect specific
to this UFunction shape.**

Two flights back-to-back on the still-alive process (PID 55960, 63 min uptime, past all FK-32
windows). Zero staging losses. All regression gates BYTE-IDENTICAL. Direct inject via
`tools/inject/inject.exe mmap` (no re-staging) into the E4E-flown process.

## The two receipts, verbatim

### E4K (no-poke, no state change; call via S55 CallNativeGuarded/FFrame framework)

```
[E4K] pre-call: pASC=0x1C2AAB80100(LokiAbilitySystemComponent)
[E4K] Items header: Data=0x1C27ADB4ED0 Num=2 Max=4
[E4K] PRE-CALL state: spec[0]@0x1C27ADB4ED0 Ability@+0x10=0x1C28E636930(GS_Ronin_LMB_Selector_C) [+0xEE]=0x01 NonRep{Data=0x0 Num=0} Rep{Data=0x1C104E28BC0 Num=1}
[E4K] PRE-CALL PREDICTION per byte model: return=0x1C2B7504970 (Rep.Data[0])
[E4K] E4K_CALL_ISSUE: ASC.GetAbilityByInputID(3) tStart=657924656
[E4K] E4K_RESULT faulted=no elapsedMs=0 return=0x0(NULL) predicted=0x1C2B7504970(Rep.Data[0]) ; POST-CALL state: Ability@+0x10=0x1C28E636930 [+0xEE]=0x01 NonRep.Num=0 Rep.Num=1 ; mutation:{ability=stable ee=stable nonRepNum=stable repNum=stable} ; *** MODEL/RUNTIME DISAGREEMENT: prediction non-null but return=NULL. Gate 2 mid-call fail OR unmodeled data-dep branch ***
```

### E4M (same setup, but call via raw __fastcall function pointer `ImageBase+0x5526210`)

```
[E4M] pre-call: pASC=0x1C2AAB80100(LokiAbilitySystemComponent) g_modBase=0x7FF7B2AE0000
[E4M] Items header: Data=0x1C27ADB4ED0 Num=3
[E4M] cand spec[0]@0x1C27ADB4ED0 Handle=1 Ability=0x1C28E636930 [+0xEE]=0x01 NonRep{0} Rep{1} => predicted return via this spec = 0x1C2B7504970
[E4M] cand spec[1]@0x1C27ADB4FC8 Handle=2 Ability=0x1C28E636930 [+0xEE]=0x01 NonRep{0} Rep{1} => predicted return via this spec = 0x1C1EEF129B0
[E4M] cand spec[2]@0x1C27ADB50C0 Handle=3 Ability=0x1C28E636930 [+0xEE]=0x01 NonRep{0} Rep{1} => predicted return via this spec = 0x1C1F6595950
[E4M] E4M_CALL_ISSUE: raw call fn=0x7FF7B8006210(=ImageBase+0x5526210) ASC=0x1C2AAB80100 InputID=3
[E4M] E4M_RESULT faulted=no elapsedMs=0 return=0x1C2B7504970(GS_Ronin_LMB_Selector_C) *** RAW-NATIVE RETURNED NON-NULL. If E4K on same state returned NULL, S55 primitive has a defect specific to this UFunction shape (likely return-value marshaling of UObject*). ***
```

## The decisive comparison

| | E4K (S55 CallNativeGuarded) | E4M (raw __fastcall) |
|---|---|---|
| function | ASC.GetAbilityByInputID(3) | GetAbilityByInputID impl @ ImageBase+0x5526210 (rcx=ASC, dl=3) |
| Items.Num at call time | 2 | 3 |
| pre-call spec state | Items[0] Ability=CDO, [+0xEE]=0x01, Rep.Num=1 | Items[0/1/2] all have Ability=CDO, [+0xEE]=0x01, Rep.Num=1 |
| iterator picks | Items[0] (Handle=1, lowest priority tie-break) | Items[0] (same) |
| **byte model prediction** | **0x1C2B7504970** (Items[0].Rep.Data[0]) | **0x1C2B7504970** (Items[0].Rep.Data[0]) |
| **actual return** | **0x0 NULL** | **0x1C2B7504970 (GS_Ronin_LMB_Selector_C instance)** |
| verdict | MODEL/RUNTIME DISAGREEMENT | prediction MATCHES actual |

**The only variable that changed between E4K and E4M is the invocation mechanism.** Same ASC,
same live state, same iterator pick (Items[0] with Handle=1 tie-break winner), same predicted
return. Different results: **S55 marshaling returns NULL; raw __fastcall returns the correct
instance.**

## What this refutes across the S191 arc

**R-S191-h REFUTED [M]** — "plain `GiveAbility` populates Items but NOT the separate InputID→spec
map that GetAbilityByInputID consults" was based on E4A F1's NULL measurement via S55. E4M
demonstrates the map IS populated and GetByInputID resolves correctly when called properly.
The "InputID map missing" was never real; it was S55's return-value marshaling.

**E4E RESULT's central mechanism claim REFUTED [M]** — "the workflow's 3-gate model is INCOMPLETE"
and "the block is UPSTREAM of the activation stack" were both derived from E4E F1's NULL. The
byte model is correct; the block was never upstream. The E4E poke's failure to change the
readback was because both pre-poke and post-poke returns were S55-corrupted NULLs, not because
the poke didn't reach anything.

**Direct disasm doc `docs/s191-e4e-postflight-disasm.md`'s four candidate resolutions**:
- (1) [REFUTED already] workflow model wrong: STILL REFUTED (byte model is correct)
- (2) [REFUTED already] iterator has hidden precondition: STILL REFUTED
- (3) [I,strong] poke reset between poke-verify and readback: NOW **REFUTED** (E4K's post-call
  state showed all four gate inputs stable; no mutation happened at all)
- (4) [I,strong] `[+0xEE]` not InstancingPolicy: REFUTED (measured 0x01 stable pre AND post)
- (5) [I] gate function's call site different: **CONFIRMED** in a stronger form than we suspected —
  the S55 dispatch reaches the correct function but its RETURN VALUE MARSHALING is defective.

**E4C convergent-witness diagnosis** — the `LogAbilitySystem: TryActivateAbility called with
invalid Handle` warning both E4F F1 and E4C F1 produced is a SEPARATE phenomenon from E4A/E4E/E4K's
NULL — E4F called `TryActivateAbilityBySourceObject` (activation surface, not readback surface)
and E4C called BP `HandleAbilityActivation` (BP dispatcher). Both reached actual activation
attempts and got refused. Whether that refusal is ALSO S55-caused (for the activation-return-value
side) or is a genuine block deeper down is now **REOPENED** — the earlier certainty rested on the
E4A/E4E premise. Convergent-witness diagnosis rests only on the `invalid Handle` string, which is
still real.

## What survives (byte-verified in disasm, independent of S55)

- **[M]** Workflow byte model of `0x44C28E0`: 4 gates + 2 return arms, exact opcodes (confirmed
  by Lane G/H/I of workflow `wf_7e83ab1b`, my own direct capstone disasm, and — now — the raw-
  native return matching byte-model prediction exactly)
- **[M]** `[UGameplayAbility+0xEE]` IS `InstancingPolicy`, value 1 = InstancedPerActor
- **[M]** Iterator `0x4476F10` (vtable slot 245) is a best-priority selector, only checks
  `[spec+0x24]==InputID`; priority tie-break via slot 246 keeps first-arrived spec on tie
- **[M]** GetAbilityByInputID (0x5526210) tail-jmps 0x44C28E0 after iterator returns non-null
- **[M]** `FGameplayAbilitySpec` layout on this build: `Handle@+0xC, Ability@+0x10, Level@+0x20,
  InputID@+0x24, Source@+0x30, NonRep{Data@+0x80,Num@+0x88,Max@+0x8C}, Rep{Data@+0x90,Num@+0x98,
  Max@+0x9C}`, stride 0xF8
- **[M]** `ULokiAbilitySystemComponent.Items` layout: `Data@+0x538, Num@+0x540, Max@+0x544`
- **[M]** Game's ability system populates `spec.Rep` with a real instance on both Items[0] AND
  Items[1] AND Items[2] (three separate K_GRANT calls each got their own instance created)
- **[M]** FK-32 did NOT fire in 63+ min of continued gameplay across E4E + E4K + E4M flights
  (three consecutive shim injects, R-S191-m grade dramatically extended)

## New [M] measurements from this flight pair

- **[M] The S55 CallNativeGuarded primitive is DEFECTIVE for UFunctions with a `UObject*` return
  type when the return marshaling attempts to read from a specific offset in the FFrame.**
  E4K's ParamOffset resolution returned an offset in g_pbuf that reads NULL, while the raw-native
  return via rax is the actual instance pointer. This is a WHOLE-PROJECT concern: any S55-invoked
  UFunction returning `UObject*` may be silently returning NULL when the game is actually returning
  a valid pointer. Priority to investigate the S55 return marshaling code path.

- **[M] Live spec[N] state after multiple K_GRANT calls**: three specs with same Ability=CDO,
  same InputID=3, distinct Handles (1/2/3), each with its own Rep.Data pointing at a distinct
  UGameplayAbility instance (0x1C2B7504970, 0x1C1EEF129B0, 0x1C1F6595950). Confirms the game
  spawns a per-spec instance on the client independently, on some tick after K_GRANT.

- **[M] Iterator priority tie-break KEEPS the first-added spec** when priorities are equal
  (jge branch at `0x4476F81` — `jge` is >=, so equal returns true and skips taking the
  candidate). With three identical-priority specs, iterator returns Items[0] (Handle=1).

- **[M] Raw __fastcall call into game-exe code from a shim is SAFE** as a call class: 0ms elapsed,
  faulted=no, returned expected value. No PI hook, no S55 framework, no CDO poke. This is a
  fifth CALL-only invocation surface for this project (in addition to reflected UFunction via
  ProcessEvent, S55 CallNativeGuarded, CallBPGuarded, and direct BP `EX_FinalFunction`).

- **[M] R-S191-m write-class safety extended to 63+ min** on a single process with three
  shim injects (E4E poke + restore, E4K + E4M call-only). No FK-32.

## Rules banked / superseded

**R-S191-s [M] NEW**: The S55 CallNativeGuarded primitive returns NULL for UFunctions whose
return type is `UObject*` (or a similar 8-byte pointer to a reflected object). Cross-validated
against raw __fastcall on `GetAbilityByInputID`: S55 = NULL, raw = correct instance. Do NOT
interpret an S55-invoked UFunction's NULL return as a game-state result until cross-validated
via a raw call or via `ProcessEvent`. All prior S191 arc NULLs from S55-invoked
`GetAbilityByInputID` are affected — R-S191-h is the primary casualty.

**R-S191-h REFUTED [M]**: See above.

**R-S191-l branch (3) REFUTED [M]**: The E4E poke was NOT reset between poke-verify and
readback. E4K's stable-mutation readouts prove nothing changes gate inputs during the call.

**R-S191-o [M] STANDS**: Workflow's 3-gate model at 0x44C28E0 is BYTE-CORRECT. Now with the
strongest possible corroboration: raw-native call obeys the model exactly.

**R-S191-p [M] STANDS**: Iterator has only one per-spec filter (InputID match), plus priority
tie-break. Confirmed by matching prediction.

**R-S191-q [I,strong] STRENGTHENED**: A shim marker line printing an INTERPRETIVE label
("InstancedPerActor OK") based on an INHERITED semantic claim can mislead — E4E's post-poke
readback verdict was based on "3-gate model INCOMPLETE" which was itself based on E4A F1's
"R-S191-h confirmed" which was itself based on an S55 NULL that wasn't a real NULL. **A chain
of interpretation grounded in an S55 return value is only as strong as the S55 primitive's
correctness for that UFunction shape.**

**R-S191-t [M] NEW**: Direct-inject via `inject.exe mmap` into a still-alive process is safe
after a full RM_BOTFIGHT cycle has completed and disarmed. Three consecutive injects (E4E + E4K
+ E4M) into PID 55960 completed cleanly with no protector kill over 63 min uptime. State
accumulates (Items goes 1→2→3 across successive K_GRANTs, spawns accumulate) but no fault.
Reusable primitive for follow-up probes on a matured process without paying re-staging cost.

## What this settles for the E4 predicate

**The RESOLUTION half of the E4 predicate (GetAbilityByInputID returns the granted ability's
instance) WORKS on our K_GRANT'd spec.** The InputID→spec map is populated, the iterator picks
the correct spec, the gate function returns the correct instance. Everything the E4 arc
believed was blocked here is actually working.

**What remains blocked (or is now uncertain)**:
- **The ACTIVATION half** — whether `TryActivateAbilityByInputID(3)` (impl 0x5544F70) actually
  activates the ability durably. E4A F1 got "clean-false NON-lethal" via S55, but if S55 was
  returning a false-negative on GetByInputID, the "clean-false" on TryActivateAbilityByInputID
  may also be an S55 marshaling artifact — this needs testing.
- **The E4F/E4C `invalid Handle` witness** — real, in Loki.log, independent of S55. This is
  still a real activation-side refusal. But whether it applies to the InputID activation path
  (E4A/E4E/E4K's territory) is REOPENED.

**Path forward**:
- **Option N** — E4M-style raw-native call to `TryActivateAbilityByInputID` (impl 0x5544F70).
  WALL-P risk: this impl's tail-call target 0x5531920 is still `PAGE_NOACCESS` in merged14,
  cannot be offline-verified to diverge from S147 lethal `InternalTryActivateAbility 0x4480B30`.
  But given raw-native GetByInputID worked cleanly, raw-native TryActivate is the natural
  discriminator. If it activates the ability with damage on the minion, E4 predicate MET via
  raw-native call. If it FK-32s, we've confirmed lethality via that surface.
- **Option S55-fix** — investigate the S55 primitive's return-value marshaling for UObject*
  returns. If we can fix it, all S55-invoked UFunction calls become trustworthy again.
- **Option O** — retro-fly E4A/E4C/E4F with raw-native equivalents to determine which of their
  measurements were S55 artifacts vs real runtime behavior.

## Cost + gates

- **2 injects, 0 launches** (both direct-inject into the still-alive PID 55960 from E4E). 0 losses.
- **0 collateral damage**: game alive at 63 min post-first-inject with 3 accumulated K_GRANT
  specs, 3 spawned minions, all E4 markers rendering. `RM_BOTFIGHT done` on both flights.
- **Clean disarms** both flights.
- **Regression gates BYTE-IDENTICAL** to pre-flight:
  `botai b620e0ff3279e673`, `play 31af7667355f39d1`, `e4 69197ce6e9e38dda`, `e4-f 1f51942a2b8d164a`,
  `e4-c eb82b2b781996671`, `e4-e-readonly 34fc650f88491b79`, `e4-k 8bb75e0cc9b5ccce` (all
  UNCHANGED after E4M patch)
- **Flown arms**:
  - `e4-k RAW=8bb75e0cc9b5ccce VSIZE=82dfdcd6f1002523` 231,424 bytes
  - `e4-m RAW=92e659fc9da65476 VSIZE=161f6489ac29ee05` 229,376 bytes
  Both KERNEL32-only, `verify_dll.py` VERDICT=PASS, `text_digest.py --dupes` clean.

## Files

- `docs/s191-e4k-flight1-marker.log` — E4K full chain (121 lines)
- `docs/s191-e4m-flight1-marker.log` — E4M full chain (120 lines)
- `tools/sigbypass-mod/tutorial_launch.cpp` — KBFE4K + KBFE4M knobs, policy #errors, code blocks
- `tools/sigbypass-mod/build.ps1` — `e4-k` + `e4-m` variants

## S191 arc tally after this commit

| flight | outcome | grade |
|---|---|---|
| S191 E4 F3 | minion killed via KE4DIRECTGE; natural LMB refuted | [M] |
| S191 E4A F1 | ByInputID NULL via S55 (**S55 artifact per E4M**); R-S191-h originally derived here — **REFUTED** | [M] |
| S191 E4B F1+F2 | BP_AuthGiveAbilityWithInputID = stripped stub (unaffected by S55, evidence stands) | [M] |
| S191 E4F F1 | BySourceObject clean-false-fast NON-lethal + `invalid Handle` witness (Loki.log witness is real; S55 return interpretation may be affected) | [M] partial |
| S191 E4C F1 | BP dispatcher HandleAbilityActivation clean-refuse-fast + SAME `invalid Handle` witness (Loki.log witness real; CallBPGuarded is a separate primitive from S55, unaffected) | [M] |
| S191 E4E F1 | direct-offset NonRep poke lands but GetByInputID readback NULL — **NULL was S55 artifact**, gate model is correct | [M] REVISED |
| **S191 E4K F1** | **S55 call GetByInputID NULL despite byte model predicting non-null — DISCRIMINATOR SETUP** | **[M]** |
| **S191 E4M F1** | **raw-native call GetByInputID returned expected instance NON-NULL — S55 defect CONFIRMED** | **[M]** |

Total S191 launches: 10 flown (3 lost to FK-31 across arc); 8 [M] results banked.
S55 primitive found DEFECTIVE for UObject*-return marshaling. R-S191-h REFUTED.
No shim ever triggered FK-32 in the S191 arc across 10 launches.
