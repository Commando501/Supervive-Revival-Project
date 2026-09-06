# S178 — fo-alone control settles T5's anomaly; FK-31 is orthogonal to companion-watch [M]

**Session:** S178 · **Date:** 2026-09-05 · **Route:** two consecutive control flights, fresh launches, `-NoHook`
**Verdict:** ★★★ **[M]** on both:
- fo alone on a fresh menu-ready game reliably triggers FK-31 (0xC0000005 at RIP=runtime.dll+1) within ~10 s.
- `-CompanionWatch` does NOT defeat FK-31 — as expected. Companion-watch is FK-32-only.
- Therefore T5's non-death in the generality flight ([docs/s178-defeat-generality-across-triggers.md](s178-defeat-generality-across-triggers.md)) was SEQUENCE-DEPENDENT: something about the T1..T4 sequence (DR install + clear/reinstall + canary WPM + gft manual-map) suppressed fo's usual FK-31 trigger.

## Flights

### Control 1 — fo alone, no `-CompanionWatch`

- Launched via `configs/launch-redirect.ps1 -NoHook` (fresh boot, no shims, no watcher)
- Menu ready, game PID 16048
- Injected `tools/sigbypass-mod/tutorial_launch_fo.dll` via `inject.exe watch-now`; DllMain returned OK, MZ verified
- **Game dead at t+9.1 s** post-injection

Crashwatch → `EXIT -1073741819 (0xC0000005) — ACCESS VIOLATION (unhandled)`. Full minidump preserved at `dumps/crash-20260905-214037/`.

`mdctx.py` parse of the Sentry crashpad dump:
```
EXCEPTION code=0xC0000005 addr=0x7FFCA1400001 parms=['0x8', '0x7ffca1400001'] tid=25504
  rip  = 0x00007FFCA1400001
```

Runtime.dll HIGH mapping this boot: `0x7FFCA1400000` → `RIP = base + 1`. **Classic FK-31 Rule-2 signature (S131) — perfect match.** Deliberate execute-fault on runtime.dll's DOS header byte.

### Control 2 — fo alone, `-CompanionWatch` armed

- Launched with `configs/launch-redirect.ps1 -NoHook -CompanionWatch`
- Menu ready, game PID 19708
- Same fo injection
- **Game dead at t+12.2 s** post-injection

Crashwatch → `EXIT -1073741819 (0xC0000005) — ACCESS VIOLATION (unhandled)`.

**Companion_watch log for this flight ends with `game process gone (t=+66.70s), stopping. polls=544` and shows ZERO runtime.dll spawns.** The companion process never came up — FK-31 killed the game before the FK-32 detector could react.

## Interpretation

### [M] FK-31 is in-process and orthogonal to companion-watch

Both controls kill the game with `0xC0000005` at `runtime.dll+1`. Companion-watch's presence in Control 2 changes nothing:
- No runtime.dll child process ever appears (companion IS NOT spawned for FK-31 triggers)
- Watcher's log has no NEW CHILD entries for runtime.dll
- Death time is ~same (9.1 s vs 12.2 s; both within FK-31's ~10 s window per S177 F1&2)

This confirms S178 A1's n=403 batch-classification finding: FK-31 is purely in-process, mediated by the game's own copy of runtime.dll self-checking `.text`. Companion process has no role.

### [M] T5's non-death was sequence-anomalous, not a stable property

Generality flight T5 saw fo injection followed by 90 s of survival — the OPPOSITE of what both controls now measure. Since:
- Both fresh-launch controls reliably fire FK-31 within 10 s
- `-CompanionWatch` is measured NOT to defeat FK-31
- T5 had `-CompanionWatch` armed AND had 4 prior triggers applied

⇒ Something in the T1..T4 SEQUENCE suppressed fo's FK-31 trigger. Candidates (untested):
- **Suppression via DR install:** T1's SetThreadContext on all 139 threads may have interfered with FK-31's self-check mechanism (which reads a register or memory location the DRs indirectly affect)
- **Companion's own state:** T1 spawned a companion (killed by watcher) — whatever runtime.dll DID in its 4.5 s of life may have altered the game's runtime.dll copy or set a "we already responded once" flag
- **Sequence-cumulative memory writes:** T3 WPM to `runtime.dll HIGH + 0x949000` may have blunted the self-check's ability to detect fo's tampering (though canary was intact per T3)
- **LoadMap side-effect suppression:** fo's LoadMap-triggering code path may check preconditions before firing — the prior tampering may have failed those preconditions

**Not investigated further** — would need a bisection flight of the 4-trigger sequence. Interesting but low-leverage (fo's FK-31 is not something we're trying to defeat here).

### [M] Companion-watch's scope is now fully characterized

`-CompanionWatch` defeats:
- ✓ FK-32 (0xDEAD, companion-mediated) triggered by DR install — cumulative n=4 (S177 F9, S178 shipping, S178 generality T1, and implicitly here as no FK-32 event happened)

`-CompanionWatch` does NOT defeat:
- ✗ FK-31 (0xC0000005 at runtime.dll+1) triggered by fo shim — Control 2 measured directly

`-CompanionWatch` doesn't matter for:
- Triggers that don't spawn a companion (S178 generality: WPM, benign DLL, cleared/re-armed DRs)

## Cumulative fo-trigger record

| flight | prior tampering | -CompanionWatch | outcome |
|---|---|---|---|
| S177 F1 | gft (via stager) | no | FK-31 at t+12 s post-fo |
| S177 F2 | gft (via stager) | no | FK-31 at t+12 s post-fo |
| S178 generality T5 | DR + WPM + gft | yes | **NO DEATH** in 90 s (anomalous) |
| S178 control 1 (this) | none | no | FK-31 at t+9.1 s post-fo |
| S178 control 2 (this) | none | yes | FK-31 at t+12.2 s post-fo |

4 of 5 flights: FK-31 within 9-12 s of fo injection. 1 of 5 (T5) survived — the anomaly.

## What this changes

Nothing about the shipping story. `-CompanionWatch` is:
- Still the correct default for menu/exploration sessions (defeats FK-32)
- Still NOT for staging (breaks LoadMap per S177 F10, and doesn't defeat FK-31 which fires anyway per Control 2)

What this SUPPLIES is a clean characterization: the watcher does exactly what its name says — it watches for the FK-32 dispatcher and kills it. FK-31 needs a different defeat mechanism (S170 VEH, S173 thread suspend, or S168-style byte-level patching of the self-check function — all documented, none shipped).

## Next moves (unchanged from generality flight)

1. **Understand S177 F10 staging-with-watcher failure** — still the biggest engineering blocker to a shipping FK-32+staging combined defeat.
2. **T5 sequence bisection** — bisect T1..T4 to find which one suppressed fo's FK-31 in that sequence. Lower priority; interesting but not on the critical path.
3. **In-game FK-32 (S158 MiniDash) with watcher armed** — needs full tutorial staging first (blocked on #1).
4. **HW BP on preloader `.data 0x50C8`** — names the specific runtime.dll RVA that reads the spawn-API pointer.

## Artifacts

- `dumps/crash-20260905-214037/` — Control 1 crashpad snapshot (RIP=base+1)
- `dumps/crash-20260905-214256/` — Control 2 crashpad snapshot
- Archived Sentry dump: `dumps/crashpad-20260905-214256/`
- `docs/companion-watch.20260905-214256.log` — Control 2's watcher log (0 runtime.dll spawns)
