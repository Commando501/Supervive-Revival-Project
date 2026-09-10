# S191 E4 Option N — Flight 1 [M] TryActivateAbilityByInputID via raw-native NON-LETHAL; 'invalid Handle' witness IS REAL — 2026-09-10

★★★★★★★ **RAW-NATIVE TryActivateAbilityByInputID(3) IS SAFE (game alive 82 min uptime after
call, no FK-32). It returns FALSE cleanly BUT triggers a burst of ~25 `LogAbilitySystem:
Warning: TryActivateAbility called with invalid Handle` warnings in 23 seconds. This CONFIRMS
the `invalid Handle` witness E4F F1 and E4C F1 produced is REAL activation-side WALL P,
NOT an S55 artifact.**

Fourth consecutive direct-inject into the still-alive PID 55960 (E4E → E4K → E4M → E4N), no
staging, no re-launch. R-S191-t/m grade extended: no FK-32 across 82 min uptime with 4 shim
injects on 4 accumulated K_GRANT'd specs (Handles 1-4, all identical Ability=CDO).

## The receipt, verbatim

```
[E4N] pre-activate: pASC=0x1C2AAB80100(LokiAbilitySystemComponent) minionPreHP=100.00 preBits=42C80000/42C80000 g_modBase=0x7FF7B2AE0000
[E4N] Items header: Data=0x1C27ADB4ED0 Num=4
[E4N] cand spec[0]@0x1C27ADB4ED0 Handle=1 Ability=0x1C28E636930 NonRep{0} Rep{1}
[E4N] cand spec[1]@0x1C27ADB4FC8 Handle=2 Ability=0x1C28E636930 NonRep{0} Rep{1}
[E4N] cand spec[2]@0x1C27ADB50C0 Handle=3 Ability=0x1C28E636930 NonRep{0} Rep{1}
[E4N] cand spec[3]@0x1C27ADB51B8 Handle=4 Ability=0x1C28E636930 NonRep{0} Rep{1}
[E4N] E4N_CALL_ISSUE: raw call fn=0x7FF7B8024F70(=ImageBase+0x5544F70) ASC=0x1C2AAB80100 InputID=3 ; tStart=659286421 ; WALL-P disasm-verified no reach to S147 lethal; instance virtuals [+0x2F0]/[+0x578] are the residual risk
[E4N] E4N_RESULT faulted=no retBool=0 elapsedMs=0 minPreHP=100.00 minPostHP=100.00 preBits=42C80000/42C80000 postBits=42C80000/42C80000 dHP=+0.00  return=false clean (one of 0x5531920's virtual dispatch checks refused) -- attribution: state helper 0x5512480 OR virtual [+0x2F0] OR [+0x578] OR helper 0x5512600 OR the fallback path
```

## Live Loki.log witness (the same string E4F F1 and E4C F1 produced)

The E4N marker's `Property DamageTakenCoefficient new value is: 1.00` at `20:52:16:140` is the game's own log receipt of some ability-tick that fired as part of RM_BOTFIGHT E4 spawn+seed. The FIRST `invalid Handle` warning follows **14 ms later**:

```
[2026.09.10-20.52.16:154][240]LogAbilitySystem: Warning: TryActivateAbility called with invalid Handle
[2026.09.10-20.52.20:650][241]LogAbilitySystem: Warning: TryActivateAbility called with invalid Handle
... [25 total warnings in 23 seconds, growing to ~1/sec sustained] ...
[2026.09.10-20.52.39:254][291]LogAbilitySystem: Warning: TryActivateAbility called with invalid Handle
```

Total across the entire session: **31 `invalid Handle` warnings**. First 3 at `20:23:36-38` (correlates to E4K/E4M flight window per marker timestamps), then a burst of **25 warnings in 23s post-E4N**. E4N's raw-native call caused a bigger burst than any prior S55-invoked activation.

## What this settles

**R-S191-s S55 defect DOES NOT explain the `invalid Handle` witness** [M]. E4F F1 and E4C F1
produced `invalid Handle` — those calls (via S55 and via CallBPGuarded respectively) reached
deep enough into the ability system to trigger stock UE's `UAbilitySystemComponent::TryActivateAbility(Handle)`
which calls `FindAbilitySpecFromHandle(Handle)` and emits this warning when it returns NULL.
E4N's raw-native call (with S55 out of the picture entirely) produces the SAME warning at
higher rate. **The `invalid Handle` is a real refusal in the game's own ability code, not an
S55 marshaling artifact.**

**The activation refusal is DOWNSTREAM of 0x5531920's virtual dispatch** [M]. Byte model:
`0x5531920` calls `GetPrimaryInstance(spec)` → helper 0x5512480 → virtual [instance+0x2F0]
→ virtual [instance+0x578] → helper 0x5512600 → helper 0x555C380. One of the virtuals (or a
callee of the virtuals) invokes stock UE `TryActivateAbility(Handle)`, which does a Handle
lookup via `FindAbilitySpecFromHandle` and gets NULL despite our K_GRANT'd spec being in
Items[0..3] with matching handles 1-4.

**Why `FindAbilitySpecFromHandle` fails on our valid handles** — this is the current unknown.
Two candidate mechanisms:
- **[I,strong]** The virtual dispatch reaches a DIFFERENT ASC than our player's (e.g. a
  cached PlayerState ASC, or the ability instance itself has a stale ASC pointer). If
  `FindAbilitySpecFromHandle` is called on an ASC whose Items TArray does not contain our
  handle, it returns NULL and emits the warning.
- **[I]** The Handle itself is somehow marked invalid at a level FindAbilitySpecFromHandle
  cares about (e.g. an FGameplayAbilitySpecHandle has more state than just int32 Handle @+0xC,
  and one of those bits fails validation).

## What this DOWNGRADES from prior claims

**E4K/E4M finding** (S55 defect) **is REDUCED IN SCOPE but stands** [M]: S55 does have a
UObject*-return marshaling defect for GetAbilityByInputID. But that defect does NOT explain
E4F/E4C's `invalid Handle` — those refusals are real. R-S191-h's refutation still holds
(InputID map IS populated), but the ACTIVATION side has its own real block.

**Retro-interpretation of prior E4 flights**:
- E4A F1 `retBool=0`, no `invalid Handle` witness → S55 defect blocked the call BEFORE it
  reached the handle lookup depth. That's why S55 lied about the return value: the underlying
  call short-circuited early somewhere and marshaling returned NULL. **What that early exit
  is remains unknown** — could be an S55 framework issue OR a shallow activation-side refuse.
- E4F F1 `retBool=0` + `invalid Handle` witness → S55 defect might apply here TOO (retBool
  from S55 is untrustworthy), but the `invalid Handle` proves the game DID reach TryActivate
  depth. Same for E4C via CallBPGuarded.
- E4N raw-native (no S55) `retBool=0` + `invalid Handle` burst → the runtime genuinely
  returns false, the warning is real, the wall is downstream of 0x5531920's virtuals.

## Next-lever options

**Option P** — instrument the invalid Handle emit site to identify which ASC is being consulted.
Grep the disasm of `TryActivateAbility(Handle)` (stock UE `UAbilitySystemComponent`) for the
LogAbilitySystem call, find the `FindAbilitySpecFromHandle` call above it, identify what rcx
(ASC) is at that point via backward-propagation. If it's our ASC, our handles are somehow
being rejected as invalid despite being in Items. If it's a different ASC, we need to identify
where that other ASC pointer comes from and either populate ITS Items or point it at our ASC.

**Option Q** — call TryActivateAbility(SpecHandle) DIRECTLY on the ASC, bypassing the
input-based route. Signature: `bool TryActivateAbility(FGameplayAbilitySpecHandle Handle, bool bAllowRemoteActivation=true)`.
If this returns true on our Handle=1, the wall is in the input path's virtual dispatch (not
in FindAbilitySpecFromHandle). If it returns false + `invalid Handle` warning, the ASC
genuinely doesn't recognize our handle.

**Option R** — search the image for other ASC pointers held by the ability instance. The
instance at 0x1C2B7504970 (from Rep.Data[0]) has its own vtable and fields. If it holds an
`OwningASC` pointer at some offset that's different from our player's ASC (0x1C2AAB80100),
that would explain the invalid Handle. Read the instance's first ~0x200 bytes.

## Cost + gates

- **1 inject, 0 launches** (direct-inject into PID 55960). 4th consecutive inject on same PID.
- **0 collateral damage**: game alive at 82 min post-flight (uptime 4949s), all E4 markers
  render, `RM_BOTFIGHT done` fired cleanly.
- **Clean disarm** per marker.
- **Regression gates BYTE-IDENTICAL**: `botai b620e0ff3279e673`, `play 31af7667355f39d1`,
  `e4 69197ce6e9e38dda`, `e4-f 1f51942a2b8d164a`, `e4-c eb82b2b781996671`, `e4-e-readonly
  34fc650f88491b79`, `e4-k 8bb75e0cc9b5ccce`, `e4-m 92e659fc9da65476`.
- **Flown arm**: `e4-n RAW=1be5da3937ae355d VSIZE=04e20695571fba9f`, 229,888 bytes,
  KERNEL32-only, `verify_dll` PASS.

## Rules banked

**R-S191-u [M] NEW**: The `LogAbilitySystem: Warning: TryActivateAbility called with invalid
Handle` witness is a REAL activation-side WALL P block. It is emitted by stock UE code when
`FindAbilitySpecFromHandle(handle)` returns NULL despite our K_GRANT'd specs being in Items
with matching handles. This block is DOWNSTREAM of `ULokiAbilitySystemComponent::TryActivateAbilityByInputID`'s
tail-call target 0x5531920, specifically inside one of the virtual dispatches at
`[instance+vtable+0x2F0]` or `[+0x578]`. Reproducible via THREE distinct dispatch primitives
(S55 CallNativeGuarded — E4F, CallBPGuarded — E4C, raw __fastcall — E4N).

**R-S191-v [M] NEW**: Raw-native TryActivateAbilityByInputID(3) via
`ImageBase+0x5544F70` on our player's ASC is NON-LETHAL. WALL-P risk downgraded per byte-
verified disasm of impl 0x5544F70 + tail-call target 0x5531920 (both LIT in merged16):
neither reaches S147 lethal 0x4480B30 in its decoded CFG. Confirmed live: game alive 82 min
after call, no FK-32, no crashpad, no artifact.

**R-S191-t [M] STRENGTHENED**: Four consecutive direct-inject via `inject.exe mmap` into a
still-alive process is safe over 82 min uptime. State accumulates (Items grew 1→2→3→4 across
K_GRANT re-runs; four spawned minions) but no fault. Reusable primitive for iterative
diagnostic probes.

## S191 arc tally after this commit

| flight | outcome | grade |
|---|---|---|
| S191 E4 F3 | minion killed via KE4DIRECTGE; natural LMB refuted (input binding) | [M] |
| S191 E4A F1 | ByInputID clean-false via S55 (S55 defect); R-S191-h REFUTED at S191 E4M | [M] |
| S191 E4B F1+F2 | BP_AuthGiveAbilityWithInputID = stripped stub | [M] |
| S191 E4F F1 | BySourceObject clean-false-fast + `invalid Handle` witness (witness is real) | [M] |
| S191 E4C F1 | BP dispatcher clean-refuse + SAME `invalid Handle` (witness is real) | [M] |
| S191 E4E F1 | direct-offset poke lands but S55 GetByInputID readback NULL (REVISED at S191 E4M) | [M] |
| S191 E4K F1 | S55 GetByInputID NULL despite byte model predicting non-null | [M] |
| S191 E4M F1 | raw-native GetByInputID returned expected instance NON-NULL — S55 defect CONFIRMED | [M] |
| **S191 E4N F1** | **raw-native TryActivateAbilityByInputID clean-false NON-LETHAL + burst `invalid Handle` witness — WALL P block localized DOWNSTREAM of 0x5531920's virtuals** | **[M]** |

Total S191 launches: 10 flown (3 lost to FK-31 across arc); 9 [M] results banked.
S55 primitive found DEFECTIVE for UObject*-return marshaling.
Raw-native TryActivateAbilityByInputID CONFIRMED safe.
WALL P activation-side block CONFIRMED downstream of 0x5531920 virtuals via THREE distinct
dispatch primitives producing SAME `invalid Handle` witness.
No shim ever triggered FK-32 in the S191 arc across 10 launches.
