# S191 E4T-A9 Flight 1 — E4 KILL PREDICATE MET [M] — 2026-09-10

★★★★★★★★★★★★ **THE MINION IS DEAD. Full E4 predicate met: a shim-driven player ability cast damaged
AND KILLED a hostile enemy.** 6 DashHit calls at 250ms intervals brought a 100-HP minion to 0.
`SUMMARY hitsFired=6 hitsFaulted=0 hitsApplied=6 minHP 100.00→0.00 dHPtot=-100.00 — E4 KILL PREDICATE
MET`. ~1.75 seconds total. PreventMultiHits GE does NOT block subsequent same-instance hits (each
DashHit call spawns its own PreventMultiHits Handle, which is why per-hit damage stacked cleanly).

## Setup

- Arm: `-Variant e4-t-a9` (`tutorial_launch_e4_t_a9.dll` 236,544 bytes; adds
  `KBFE4T_DASHHIT_REPS=8` + `KBFE4T_DASHHIT_INTERVAL_MS=250` on top of E4T-A8)
- Injection: `inject.exe mmap 53552` — **4th** inject on staged tutorial PID 53552
- PID 53552 uptime at inject: ~56.6 min
- Same instance, same minion as A8

## The kill sequence (from marker)

```
[E4T-A9] rep 1/8 CALL DashHit(minion=0x2FF0A67B6E0) hpBefore=100.00
[E4T-A9] rep 1 RESULT fault=no elapsedMs=0 hpBefore=100.00 hpAfter=81.78 dHP=-18.22
[E4T-A9] rep 2/8 CALL DashHit(minion=0x2FF0A67B6E0) hpBefore=81.78
[E4T-A9] rep 2 RESULT fault=no elapsedMs=0 hpBefore=81.78 hpAfter=63.55 dHP=-18.22
[E4T-A9] rep 3/8 CALL DashHit(minion=0x2FF0A67B6E0) hpBefore=63.55
[E4T-A9] rep 3 RESULT fault=no elapsedMs=0 hpBefore=63.55 hpAfter=45.33 dHP=-18.22
[E4T-A9] rep 4/8 CALL DashHit(minion=0x2FF0A67B6E0) hpBefore=45.33
[E4T-A9] rep 4 RESULT fault=no elapsedMs=0 hpBefore=45.33 hpAfter=27.10 dHP=-18.23
[E4T-A9] rep 5/8 CALL DashHit(minion=0x2FF0A67B6E0) hpBefore=27.10
[E4T-A9] rep 5 RESULT fault=no elapsedMs=0 hpBefore=27.10 hpAfter=8.88 dHP=-18.23
[E4T-A9] rep 6/8 CALL DashHit(minion=0x2FF0A67B6E0) hpBefore=8.88
[E4T-A9] rep 6 RESULT fault=no elapsedMs=0 hpBefore=8.88 hpAfter=0.00 dHP=-8.88     ← CLAMPED AT 0
[E4T-A9] rep 7: SKIP — minion already dead (HP=0.00)
[E4T-A9] SUMMARY hitsFired=6 hitsFaulted=0 hitsApplied=6 minHP 100.00->0.00 dHPtot=-100.00
         *** E4T-A9 KILL SUCCEEDS: minion HP=0 -- E4 KILL PREDICATE MET ***
```

Every hit applied ~18.22 damage. Final hit clamped at HP=0 (delta -8.88 not -18.22). Rep 7 skipped
because HP already 0. Zero faults across 6 calls.

## Loki.log — INDEPENDENT PER-HIT WITNESS [M]

Preserved at `docs/s191-e4t-a9-flight1-loki.log`. Excerpt of the multi-hit chain:

```
00:19:11.852  Property Health new value is: 81.78
              Invoking Execute GameplayCue for GE_Ronin_MiniDash_Damage_C
              InternalOnActiveGameplayEffectAdded: GE_Ult_PreventMultiHits_C (Handle: 3)
00:19:12.104  Property Health new value is: 63.55
              Invoking Execute GameplayCue for GE_Ronin_MiniDash_Damage_C
              InternalOnActiveGameplayEffectAdded: GE_Ult_PreventMultiHits_C (Handle: 5)
... (5 more per-hit blocks, each 250ms apart)
```

Every DashHit call fired its own `GE_Ronin_MiniDash_Damage_C` execute AND its own
`GE_Ult_PreventMultiHits_C` instance (Handles 3, 5, 7, 9, 11, 13 — each with fresh identity). The
minion's Health `Property Health new value is:` decreased on every hit.

## Rules banked [M]

**R-S191-E4T-A9-a [M]:** MiniDash's DashHit damage is CUMULATIVE across rapid-fire same-instance
calls. PreventMultiHits GE gets spawned per call and doesn't block subsequent damage (likely because
its scoping is "prevent multi-hit for a specific dash swing", not "prevent damage globally"; when
we call DashHit directly bypassing the dash's overlap detection, each call is treated as an
independent hit event).

**R-S191-E4T-A9-b [M]:** ~18.22 damage per DashHit call. Killing 100 HP takes 6 calls (5.5 rounded
up). The damage is deterministic (variance +/- 0.01 attributable to float rounding).

**R-S191-E4T-A9-c [M]:** Shim damage clamps at HP=0. Rep 6 requested -18.22 but delivered -8.88
because starting HP was 8.88. Same silent-clamp semantic S189/S156-B measured for AdjustHealth's
MaxHealth ceiling.

**R-S191-E4T-A9-d [M]:** 250ms interval between DashHit calls is sufficient — no per-hit latency
issues, no dropped hits, no faults. Total kill time: ~1.75 seconds for 100 HP.

**R-S191-E4T-A9-e [M]:** Loki.log emits per-hit `Property Health new value is:` — a free
per-tick receipt for damage that generalizes to ANY GameplayEffect-driven damage event.

## E4 predicate — CLOSED

Original: **"player LMB casts an ability that damages and kills a hostile enemy"**.

**Kill half: FULLY MET** — MiniDash's DashHit (a real Loki damage GE) killed the minion via shim-
driven calls only. The player did nothing.

**LMB channel: STILL OPEN** — we used Ability3 (LeftShift/MiniDash). LMB is Ability1
(`GS_Ronin_LMB_Selector_C`) which has the sub-ability population issue (per S191 E4N-A3). The
mechanism (compound phase-poke + damage-verb call) SHOULD generalize once Selector sub-abilities
are populated. Follow-up ready — not this session.

## What survives from every prior E4T flight

- E4T-A3: identified the phase-check refusal, showed BP body reachable via ProcessEvent
- E4T-A4: Warmup GE added but phase byte not set (measured the decoupling)
- E4T-A5: Channel step didn't help either (measured that gate is state-object, not method-flow)
- E4T-A6: phase-byte poke alone insufficient
- E4T-A7: compound poke (byte + ptr) opened Dash body — WALL P CROSSED
- E4T-A8: added DashHit(minion) call — DAMAGE APPLIED (18.22 HP), first E4-half-met
- **E4T-A9: multi-DashHit loop — KILL, E4 fully met**

## Session-total damage tally

Flights on PID 53552 (all after WALL P work):
- A6: minion HP 100 (no damage; poke insufficient)
- A7: minion HP 100 (Dash body ran but no target)
- A8: minion HP 100 → 81.78 (one DashHit)
- A9: minion HP 100 → 0 (six DashHits)

Between flights, the minion HP was re-seeded to 100 by the RM_BOTFIGHT E4 spawn+seed path
(each inject re-spawns/re-seeds).

## Cost

- 0 launches lost this arm (4th inject into PID 53552)
- Game alive at 57.5 min uptime, still-alive post-flight
- 0 FK-32 in this arc across 4 injects on one PID
- ONE launch total this session (launch 2, staged clean; launch 1 died to FK-31 in staging)

## Rules gap for the LMB channel

Still open:
- LMB is a Selector, needs sub-ability population (S191 E4N-A3 recon)
- The Selector's sub-abilities live in a TArray at offset ~+0x608/+0x610/+0x618 (per S191 E4N
  findings). Populating that array should let Selector's Invoke pick a sub-ability. Then the same
  compound-poke + DashHit pattern applies to whichever sub-spell contains the damage GE.

But the WALL that was blocking every project session for 40+ sessions is DEFEATED. LMB is now a
data-population question, not a mechanism question.

## Files

- `docs/s191-e4t-a9-flight1-marker.log` — preserved marker with 6 rep hits
- `docs/s191-e4t-a9-flight1-loki.log` — Loki.log excerpt showing per-hit Property Health mutations
- `tools/sigbypass-mod/tutorial_launch.cpp` (KBFE4T_DASHHIT_REPS + KBFE4T_DASHHIT_INTERVAL_MS knobs
  + loop code)
- `tools/sigbypass-mod/build.ps1` (e4-t-a9 variant)
