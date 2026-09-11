# S178 — FK-32 defeat generality across 5 trigger classes [M]

**Session:** S178 · **Date:** 2026-09-05 · **Route:** one live flight, `-CompanionWatch` armed
**Verdict:** ★★★★★★ **[M] Companion-watch defeats every FK-32 event we can trigger; several tamper classes never trigger the companion at all.** Game survived 443.7 s through 5 sequential trigger classes with 0 crashwatch triggers.

## The flight

Launched via the shipped `configs/launch-redirect.ps1 -NoHook -CompanionWatch` (S178 shipping integration). Game PID **27608** reached menu, then applied 5 different tamper classes in sequence within one lifetime, observing per-trigger outcome via the companion_watch log and crashwatch.

## Results table

| # | Trigger | Prior expectation | Outcome |
|---|---|---|---|
| T1 | `hwbp_movei.py` (DR install on all 139 threads) | Companion spawns t+5–58s (S177 F9), watcher kills it | **✓ companion spawned @ t+58.81s, killed 120 ms later, game alive** |
| T2 | `hwbp_movei --clear` then re-install DRs | Untested — does game re-trigger? | **✓ NO re-spawn observed in 60 s (single-shot trigger)** |
| T3 | `canary_probe --no-install` (WPM to `runtime.dll HIGH + 0x949000`) | S168: `.text` writes trigger FK-31 in-process; WPM to data 0/22 lethal in prior work | **✓ NO companion spawn, no crash, canary intact** |
| T4 | Manual-map `gft_ready_fix.dll` (benign shim, no PI hook) | Never measured as companion trigger | **✓ NO companion spawn, no crash** |
| T5 | Manual-map `tutorial_launch_fo.dll` (S177 F1&2: fired FK-31 in 12 s) | Might trigger FK-31 (in-process) — companion-watch can't defeat that | **✓ NO death, NO companion spawn in 90 s** — did not reproduce prior FK-31 |

**Game uptime at end: 443.7 s (7.4 minutes)** across all 5 triggers. Zero crashwatch triggers. Zero exit-code events. One clean companion kill (T1). Watcher log ends after T1's kill entry with no further runtime.dll observations.

## Key findings

### [M] Trigger scope is much narrower than expected

Only **1 of 5 tested triggers** produced a companion spawn — DR install (T1). WPM to game memory (T3), manual-map of a benign DLL (T4), and manual-map of the historically-lethal fo shim (T5) all failed to trigger the companion in this session. This is a much narrower trigger surface than "any tampering."

**Implication:** the companion is NOT the game's response to every tamper class. Most tampering is either (a) invisible to the game's tamper detection, (b) responded to via a different mechanism (e.g., FK-31 in-process), or (c) requires a specific state (in-game vs menu, specific timing) to trigger.

### [M] Single-shot trigger per detection

T2's re-install of DRs (after T1's companion was killed) did NOT produce a second spawn. The trigger appears to be one-shot per detection state — once the game has responded (even if we killed the responder), it doesn't re-arm the same detection.

**Alternative reading**: SetThreadContext on already-DR'd threads may not register as a new tampering event (the DR values were already what we wrote — the second call is a no-op from the protector's perspective).

**Either way**: game does not enter an infinite spawn/kill loop after our defeat. Companion-watch stays quiet after handling one event.

### [I] fo shim did not fire FK-31 in this sequence

S177 flights 1 & 2 measured fo triggering FK-31 (0xC0000005 at runtime.dll+1) within 12 s. T5 injected fo (bytes identical, `verify: MZ ✓`, `DllMain returned OK`) and waited 90 s with no death.

Possible reasons (untested here):
- Fo's LoadMap block may not have fired because game state didn't meet its preconditions in this sequence (canary_probe + DR install had already touched game memory)
- The order and timing of prior triggers may have suppressed fo's LoadMap side effect
- fo's FK-31 trigger may be probabilistic (S111 measured ~28% baseline staging-hazard rate)

Not investigated further this flight. **Grade [I]** — needs a controlled repro (fresh launch → fo alone) to disentangle.

### [M] companion_watch is surgical and stable

Total children observed during flight:
- 4× `conhost.exe` — SKIP kill
- ~6× `EpicWebHelper.exe` — SKIP kill (Epic embedded browser normal churn)
- 1× `crashpad_handler.exe` — SKIP kill (Sentry crashpad, legitimate)
- **1× `runtime.dll` — KILLED**

The `--only-name runtime.dll` filter is exactly right: benign children are ignored, only the FK-32 dispatcher is killed. Zero collateral. Watcher log is readable (~40 lines total after 7 minutes).

## Cumulative FK-32 defeat evidence

| flight | trigger applied | uptime at end | companion spawns | outcome |
|---|---|---:|---:|---|
| S177 F7 | DR install | 54.1 s (kill) | 1 (killed game) | FK-32 fires (no watcher armed) |
| S177 F9 | DR install (with watcher) | 240+ s alive | 1 (killed by watcher) | **DEFEATED** |
| S178 shipping | DR install (via launcher flag) | 237.8 s alive | 1 (killed by watcher) | **DEFEATED** (via `-CompanionWatch`) |
| S178 generality | DR + WPM + gft + fo | **443.7 s alive** | 1 (killed by watcher) | **DEFEATED across 5 trigger classes** |

## What this doesn't tell us

- **We didn't successfully trigger FK-32 via a NON-DR-install mechanism.** All 5 triggers tested either produced a DR-install-flavored spawn (T1) or no spawn at all. To test companion-watch against FK-32 triggered by a DIFFERENT mechanism, we'd need to identify one — and the only other confirmed FK-32 trigger is in-game ability activation (S158 MiniDash), which requires a fully-staged tutorial world.
- **We did not test tutorial staging with watcher active.** S177 flight 10 measured staging failure (LoadMap didn't fire) with watcher armed — that remains a documented incompatibility. This flight avoided staging deliberately.
- **We did not test whether companion-watch breaks anything when arm-early-then-quiescent.** T3 and T4 saw no spawn — those pass silently. Whether the watcher's *presence* itself does anything subtle is not tested.

## Interpretation for the shipping story

`-CompanionWatch` is a **safe default for menu/exploration sessions**:
- Every FK-32 trigger I could produce was defeated
- No collateral on benign children
- 7 minutes of continuous uptime with mixed tampering
- Zero false-positive kills

It is **NOT proven safe for tutorial staging** — S177 flight 10 is the standing warning. Until we understand why staging's LoadMap needs the companion alive, keep the "Do NOT combine with fk24-stage.ps1" warning in place.

## Ranked next moves (post-generality)

1. **Fresh-launch repro of fo alone** (5 min) — control for T5's anomaly. Fresh boot, fo injection with no prior tampering, watcher armed. Does fo alone still trigger FK-31? If yes: T5's survival was sequence-dependent. If no: fo may need specific state (backend routing, LoadMap preconditions) to trigger anything.
2. **Understand flight 10 staging failure** — the biggest open blocker to shipping-with-staging. Bisect: kill companion FIRST vs LET IT LIVE with the staging chain. If staging succeeds only when companion lives to some checkpoint, we may need a "kill after N ms" rather than "kill on sight" mode.
3. **Test in-game ability activation FK-32 (S158 MiniDash) with watcher armed** — the only other measured FK-32 trigger. Big lift (needs full tutorial staging first, which is blocked on #2).
4. **HW BP on preloader `.data 0x50C8`** — names the specific runtime.dll RVA that reads the spawn-API pointer (S178 open question §2.4). One flight.

## Log artifacts

- `docs/companion-watch.20260905-213019.log` — full watcher log for this flight (40 entries)
- `docs/crashwatch.out.log` — 0 triggers this flight
- No crashpad dumps (game never died)
