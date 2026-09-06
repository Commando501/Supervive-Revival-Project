# Next-session handoff (S99) — VISIBLE hero SOLVED; finish animation + assess playability

Branch `dedicated-server-stub`. Continues S94–S98. **The hero body is now VISIBLE and MOVABLE in the force-open
tutorial (user-confirmed screenshot).** What remains is animation polish and an honest scoping of "game-ready
playable".

---

## PASTE-ABLE OPENING PROMPT

> Continue the SUPERVIVE tutorial work on branch `dedicated-server-stub`. Read first, in order:
> (1) `docs/next-session-prompt-s99.md` (this file), (2) `docs/session-94-visible-movable-hero.md` (tail = the S98
> solve), (3) memory `supervive-tutorial-launch-status` (tail = S98/S99).
>
> STATE: the tutorial has a VISIBLE Ronin body, WASD movement, a top-down camera, completable objectives and a
> walkable lesson chain. The S98 root cause of the long "invisible hero" hunt was **zero/flattened Scale3D**, now
> fixed in `DoSpawnPossess` and `BuildHeroBody`.
>
> GOAL: (a) verify/finish the idle-animation fix (built but NOT yet visually confirmed — the session crashed before a
> screenshot), (b) optionally add run-animation, (c) scope what "playable" can mean given abilities are GAS-gated.
>
> Do NOT re-open: the DS/blueprint-stub route (`OnObjectiveComplete` is `FUNC_BlueprintAuthorityOnly`, so a networked
> client can never complete objectives), the game's cosmetics controller (0 instances), DropPlane descent (faults),
> fog of war (disabled → no change), the "no SceneProxy" theory (retracted), or the cheat-spawn path (no
> `LokiPlayerCheats` instance exists).
>
> Env: elevated PS, **Steam must be running first**. Use the PowerShell tool (NOT Bash), `dangerouslyDisableSandbox:
> true` for launch/inject, `[System.IO.File]::Delete` for logs. ⚠ PowerShell `$pid` is read-only — use `$gpid`.
> Revert config to baseline when done.

---

## ★★★ THE S98 SOLVE — read this so you don't re-litigate it

**The hero and its body component were scaled to nothing.** Nothing was ever wrong with the mesh, materials,
component, registration, render proxy, fog of war, occlusion, or deploy — a zero-scale actor has correct coordinates,
working possession, working movement, a following camera, every flag set, and draws NOTHING.

| | was | now |
|---|---|---|
| hero actor (`DoSpawnPossess`) | `Scale3D (0,0,0)` | `(1,1,1)` |
| body component (`BuildHeroBody`) | `(1,1,0)` — flat | `(1,1,1)` |

### ⚠ THE OFFSET FACT (this is the trap — remember it)

`FTransform` in this build is the **16-byte-ALIGNED 0x60 layout**:

| field | offset |
|---|---|
| Rotation (FQuat4d) | `0x00` (0x20) |
| Translation | `0x20` (0x18 used + **8 pad**) |
| **Scale3D** | **`0x40 / 0x48 / 0x50`** (+8 pad) |

Proof: `xfsz = g_oBColl - g_oBXform = 0x70 - 0x10 = 0x60`.

The project's old idiom `g_xform+0x38/0x40/0x48` (L1062 *"scale 1 (NOT 0)"*, L2024, L2778, and `BuildHeroBody`'s
`T[7],T[8],T[9]`) actually writes **translation-pad, Scale.X, Scale.Y — leaving Scale.Z ZERO**, flattening everything
it "fixed". Live proof of that intermediate state: `RelativeScale3D = (1.000, 1.000, 0.000)`.

**Rule going forward:** never pass Scale3D through the `RelativeTransform` param. Write the component's
`RelativeScale3D` property directly (offset `+0x188`) and then call `SetWorldScale3D(1,1,1)`. That is what
`BuildHeroBody` now does.

---

## WHERE ANIMATION STANDS (the one open item)

### The sword needs NO socket work — confirmed

`SK_Ronin_Default_LOD1.uasset.names.txt` shows the skeleton carries `sword_01..04_m_jnt`, `hand_weapon01_l|r_jnt`,
`centralWeapon_*`, `spine03_weaponAttach01_m_jnt`. **The sword is part of the same skeletal mesh.** In BIND pose those
bones sit at rest, which is why the blade passes through the torso. **Any real pose fixes it** — the T-pose and the
sword placement are the same bug.

### AnimBP: tried, and it makes the body VANISH

Leaving the component's own `AnimClass` (`ABP_LokiHero_GenericRoot_EventDriven_C`) active — i.e. building with
`-DKANIMMODE=-1` so we don't override `AnimationMode` — produced **no body at all** (user-confirmed). It is
"EventDriven" and, with no GAS/character state in force-open, evaluates to a degenerate pose (collapsed bones → zero
bounds → culled). It did NOT crash. **Do not just "turn the AnimBP on".**

### Current approach: SingleNode + drive an AnimSequence ourselves (BUILT, NOT YET VERIFIED)

`BuildHeroBody` now loads an idle and calls `PlayAnimation(anim, bLooping=true)` (which sets SingleNode, assigns the
asset and plays, in one native call). Markers from the last live run — all "ok", but **the session crashed before a
screenshot**, so the visual result is UNKNOWN:

```
[PL] anim asset=0x126CE786600 (AnimSequence)
[PL] PlayAnimation(A_Ronin_Cosmetic_HeroSelect_Breathe, loop) ok
[PL] body built (animMode=1 tick=1 visible deferred=1)
```

Anim used: `/Game/Loki/Characters/Heroes/Ronin/Animation/Cosmetics/A_Ronin_Cosmetic_HeroSelect_Breathe`
(hero-select breathe/idle — self-contained, needs no gameplay state). Flags: `KPLAYANIM`, `KANIMPATH`, `KANIMNAME`.

**FIRST ACTION NEXT SESSION: relaunch and screenshot this.** If the idle plays and the sword sits in hand, animation
is done. If the body vanishes again, the AnimSequence is also collapsing the pose → fall back to `KPLAYANIM=0`
(T-pose but visible) and try a different anim (e.g. `A_Ronin_Cosmetic_HeroSelect_Intro`, or a locomotion anim under
`/Ronin/Animation/`). The full Ronin animation list is in `tools/extractor/out/allfiles.txt`
(`grep -i ronin allfiles.txt | grep /Animation/`).

### Run animation (optional next step)

Locomotion blending needs the AnimBP, which breaks rendering. A workable hack: in the per-hit `DoPlay` tick, call
`PlayAnimation(run_anim, loop)` when CMC velocity > 0 and `PlayAnimation(idle, loop)` when it is ~0. Crude but it
would animate movement without the AnimBP.

---

## ⚠ HONEST SCOPE: "game-ready playable" (abilities/attacks)

Right now the lesson chain is **WASD only**. Abilities/attacks run on **GAS**, and the force-open hero has
**no AttributeSet at all** (`attributeSet == 0x0`, verified live) because GAS is initialised during the
server-authoritative deploy this route cannot run. That is the same root condition that removed the cosmetics
controller, TeamState, FOW vision, and the `LokiPlayerCheats` object.

| goal | status |
|---|---|
| visible body | ✅ done (S98) |
| WASD movement + camera + stability | ✅ done (S94) |
| objectives + lesson chain | ✅ done (S93) |
| idle animation + sword in hand | 🔄 built, needs one screenshot |
| run animation | ⚠ achievable via the velocity-driven AnimSequence hack |
| **abilities / attacks** | ❌ GAS-gated — would require reconstructing ability-system init; a large, uncertain effort comparable to the whole deploy problem |

Don't promise ability play without first proving GAS can be initialised outside deploy.

---

## RECIPE (exact)

```powershell
# 0) ARM force-open: server/internal/interactive/interactive.go
#      forceTutorialMatch = true   AND   ConnectionDetails "address": ""
# 1) Steam MUST be running. Fresh game:
#    kill SUPERVIVE-Win64-Shipping ; [System.IO.File]::Delete("C:\Users\eastr\AppData\Local\SUPERVIVE\Saved\Logs\Loki.log")
& "G:\git\Supervive Revival Project\configs\launch-redirect.ps1" -NoHook   # background; Steam relaunches under a NEW pid
# 2) wait "TryUIReady SUCCESS" AND uptime >= 100s; resolve the LIVE pid (newest by StartTime)
# 3) inject in THIS ORDER (retry the whole launch if the game dies on fo — ~2 of 3 do):
#    >> RETRACTED 2026-07-27 (S106): "~2 of 3 do" is FALSE as a mechanism. DETERMINISTIC crashes --
#    >> two named signatures, byte-identical RVA chains across independent launches, both shim-caused,
#    >> both with compiled fixes. Retrying was the wrong response for ~15 sessions.
#    >> See docs/fk7-crash-settled.md (Step 0: three tutorial_launch DLLs on disk are A/B traps).
tools\inject\inject.exe mmap $gpid tools\sigbypass-mod\tutorial_launch_fo.dll        # wait for "WORLD UP"
tools\inject\inject.exe mmap $gpid tools\sigbypass-mod\gft_ready_fix.dll
tools\inject\inject.exe mmap $gpid tools\sigbypass-mod\tutorial_launch_sp.dll        # hero spawn (SCALE FIX lives here)
tools\inject\inject.exe mmap $gpid tools\sigbypass-mod\tutorial_launch_play.dll      # body + camera + WASD
# marker: docs\tutorial-launch-marker.txt   client log: C:\Users\eastr\AppData\Local\SUPERVIVE\Saved\Logs\Loki.log
```

Build flags used for the current DLLs:

```
sp   : -DKRUNMODE=RM_SPAWNPOSSESS
play : -DKRUNMODE=RM_PLAY -DKANIMMODE=1 -DKPLAYANIM=1 -DKMESHTICK=1 -DKPUPYAW=-90
       -DKCAMUP=1000 -DKCAMBACK=550 -DKCAMPITCH=-58
       -DKCHEATSPAWN=0 -DKSMACTOR=0 -DKSTATICTEST=0 -DKTESTACTOR=0 -DKFOWKILL=0 -DKFOWATTR=0
compiler: C:\Users\eastr\AppData\Local\Programs\Swift\Toolchains\6.3.2+Asserts\usr\bin\clang++.exe
  clang++ -shared -O2 -D_CRT_SECURE_NO_WARNINGS <flags> tutorial_launch.cpp -o <out>.dll -lkernel32 -luser32
```

**Timing / capture:** body builds at ~195–205s uptime; sessions die ~230–260s. Screenshot with **Win+Shift+S or
Steam F12 — do NOT alt-tab.** The shim's resolve does many full 188k-object scans; trimming more of them buys a wider
capture window (already went 215s → 197s by gating the dead placeholder sweep and the GAS attr scan).

---

## VERIFICATION TOOLS (read-only RPM unless noted)

| tool | use |
|---|---|
| `tools/re/read_scale.py <PID> <objHex>` | RelativeLocation/Rotation/**Scale3D** of a SceneComponent — the fastest sanity check |
| `tools/re/poke_scale.py <PID> <compHex> [x y z]` | **write** RelativeScale3D live (`+0x188`) — fixed a RUNNING session with no relaunch |
| `tools/re/probe_comp.py` | component class/mesh/AttachParent/visibility |
| `tools/re/find_owner.py <PID> <BASE> <substr>` | live objects by name + class + Outer chain |
| `tools/re/proxy_census.py`, `prim_diff.py`, `proxy_stats.py` | the (retracted) proxy investigation — keep for method, not conclusions |
| `tools/re/scan_strings.py` | ASCII+UTF-16 pattern scan of `dumps/merged.dump.exe` |

---

## ELIMINATED — do not re-test

mesh/render data (loads healthy: Skeleton + 8 materials + LODInfo) · component construction (bare **and** the game's
`BP_Ronin_DefaultSKMeshComponent_C`) · component registration (`FinishAddComponent` ok) · actor spawn
(`FinishSpawningActor` returns a valid actor) · owner-hidden · placement/occlusion (tested at Z=2200 open air) ·
cloth/tick · **fog of war** (both FOW actors disabled → no change) · **GAS vision attrs** (no attribute set exists) ·
**cheat spawn** (no `LokiPlayerCheats` instance) · **"no SceneProxy"** (retracted — `+0x2B0` is not SceneProxy, and
the 400-sample test structurally excluded it).

## ⚠ METHODOLOGY LESSON (the most valuable thing here)

Three confident root-cause calls in a row — fog of war, "no SceneProxy", cheat-spawn — were **all wrong**, each built
on one suggestive signal instead of a controlled measurement. Two controls were themselves invalid (a **CameraActor**
is hidden in game by default; one test was compiled out and never ran). The real cause was a mundane scale bug that a
single direct read of the object's transform would have exposed in minutes.

**Read the actual state of the object before theorising about subsystems.** `read_scale.py` on the hero and the
component is now the first thing to run whenever something doesn't render.

## ENV AT HANDOFF

Config REVERTED to baseline (`forceTutorialMatch=false`, address `127.0.0.1:7777`). Game/ags stopped. All work
committed. `tutorial_launch_play.dll` on disk = the idle-animation build described above.
