# Session 76 (cont.) — the DS ~2-min crash SOLVED (WorldSettings un-suppress) → stable MOVING fly-cam + PRE-DROP screen reached

## The deep-RE that cracked it
The DS session's recurring ~2-min crash was assumed to be the deploy-config feature-toggle wall
(`CursorCharacterAim`/`AttachAudioListenerToHero` "not ready" spam). **That was a red herring.** Parsing the
crash minidump (`tools/re/parse_minidump.py`) showed the real fault:

```
ExceptionCode=0xC0000005  ExceptionAddress=0x7FF8F0400001  params=['0x8', ...]   (0x8 = EXECUTE violation)
```

An **execute-AV at an unmapped garbage address** = the **S53/S54 "garbage-thread execute-AV"** — a half-hydrated
replicated actor spinning a stale callback into a thread. `usmapdump findptr <val>` → **0 hits**, so the pointer is
transient (not a stored field to null). S53 fixed its instance not by finding the pointer but by **un-suppressing a
replica on the stub** so it hydrates fully.

## The fix (S53 pattern)
`unreal-stub/.../LokiNetDriver.cpp` `IsClassNetCacheDivergent` still suppressed `AHUD`, `ASpectatorPawn`,
`AWorldSettings`. The stub log confirmed the one stock replicated actor it actually dropped was
**`WorldInfo_1 (WorldSettings)`** → its client replica spawns but never gets a property bunch (S53's exact
signature). **Removed `AWorldSettings` from the suppression set** (like the S71 `ADefaultPawn` un-suppress; stock
UE5.4 class + `NetworkChecksumMode=None` tolerates any residual schema diff). Rebuilt `Build.bat LokiEditor` (66s
incremental).

## ★★★ RESULT — the crash is GONE; stable MOVING fly-cam achieved ★★★
- **Bare client (no shim): stable 5+ min** past the old ~2-min crash point (was 100% fatal before).
- **Free-cam injected (`ds_hybrid` `MODE_FREECAM`): ran 187,000 frames** — spawned an `ACameraActor`,
  `SetViewTargetWithBlend`'d the view to it, and the `K2_SetActorLocation` puppet **moved it (WASD)** far out
  (to ~124210, 49084, 271400) with the session holding together. **A stable, controllable, moving camera over
  the live SUPERVIVE tutorial world — the Route D goal.** (Overlay reveal `WBP_UI_MatchTransition`, camera
  spawn/retarget/puppet all in `ds_hybrid.cpp`.)
- WorldSettings replicated cleanly to the client (no "Invalid replicated field", no schema reject).

## ★ NEW MILESTONE — the client reached the PRE-DROP hero screen ★
With the crash gone the client's own match flow **advanced past the loading/dead-spectator state into the real
pre-drop screen** (hero **BRALL**, "DROP LEADER", Reviver role, emote wheel) — a hero assigned, the actual
pre-match lobby. Never reached before over any route. (Trigger unclear — appeared during the free-cam run;
possibly the stable session + hydrated state let the client's match-ready check pass.)

## NEXT WALL — the whack-a-mole continues one stage deeper
Advancing to pre-drop engaged the **next** half-hydrated replica → **another garbage-thread execute-AV**
(`0x7FF90E000001` — same signature, different value). So each replica-fix advances the client one match stage.
Open question for the next step: is the pre-drop crash (a) another half-hydrated replica (fixable the same way),
or (b) the **in-match anti-tamper** reacting to the injected shim — external RPM to the game got **blocked** the
moment the match went "real" (the preloader anti-tamper waking up), so the pre-drop crash may be its response to
injection, not a replica. Discriminator: does a **bare client (no injection)** reach pre-drop and crash on its own?

## Reusable / durable
- **The WorldSettings un-suppress** (committed) — the durable fix; stabilizes the DS session past ~2 min.
- `ds_hybrid.cpp` `MODE_FREECAM` (spawn CameraActor + SetViewTargetWithBlend + K2_SetActorLocation puppet),
  `MODE_SPECTATOR_CAM` (overlay reveal + velocity puppet), `MODE_DEBUGCAM` (EnableDebugCamera — blocked: no
  CheatManager in shipping). Resolve offsets by reflection (PropOffsetOnClass), heap-guarded writes.
- Crash triage: `parse_minidump.py <newest .dmp>` → `0x8`+unmapped-execute addr = the garbage-thread AV;
  `usmapdump findptr` to test if the pointer is stored (it's transient here).
- Anti-tamper note: external ctypes RPM works pre-match but is **blocked in-match** — drive via in-process shims.
