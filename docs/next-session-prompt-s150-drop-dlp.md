# Next session handoff — S150-drop DLP (drop-land-play combined arm)

**Prior session's last commit: `8f1e804`** (see `git log --oneline` on `dedicated-server-stub`).
Read this doc top-to-bottom before doing anything.

---

## COLD-START CONTEXT — what's done

The S150-drop track met its acceptance predicate on **2026-09-01**. Full record:
[docs/drop-sequence-status-s150.md](docs/drop-sequence-status-s150.md) §6.5–§6.16 (published
across commits `d8b7082 → 9ef4f29 → 2060cb8 → eb78d15 → 7f9e96b → eb8dae5 → 8f1e804`).

**The one-line summary:** first time in this project's history, a hero was landed on real
terrain via a driven drop chain and walked. Recipe: 7 sequential manual-map injections —
`gft → fo → sp → dropplane_b1only → droppod-pe-cdopoke → dismount-landstart → play-atlanding-walk`
— produced hero at `(-3206, 5070, 90)` on TrainingStart, then walking to `(-1960, 5070, 90)`,
Z=90 constant (ground-level locomotion).

**What that flight did NOT deliver** (still open, not blockers for this session):
- §6.13 IntroSequence timer blocker (would let pod DESCEND from cruise altitude rather than
  hero being teleported to landing).
- §6.9 `CallBPGuarded FFrame+0x80` OutParms primitive fix (would unblock every
  `FUNC_HasOutParms` UFunction project-wide).
- CO-OP vs AI acceptance predicate (`docs/coop-vs-ai-roadmap-s142.md` — WALL P + WALL E).

---

## THIS SESSION'S TASK — wire the drop-and-play chain into one arm

**Goal:** compose the last four sequential injections (`dropplane_b1only`, `droppod-pe-cdopoke`,
`dismount-landstart`, `play-atlanding-walk`) into ONE new arm `RM_DROPLANDPLAY`. Reduces the
flight from 7 injections to 4 (`gft + fo + sp + droplandplay`). Same behaviour, cleaner sequence,
better FK-31 budget (~54% → ~19% sitting-loss on independent binomial with historical ~27%
per-window rate).

**Prior session designed the arm** — see §1 below. This session's task is IMPLEMENT + FLY it,
not re-design.

---

## §1 — ARM DESIGN (from prior session's workflow `wf_9e890498-15c`, adversarially verified)

### Architecture: state machine across OnPI ticks

- **NOT** a refactor of the existing `Do*` functions — leaves them intact.
- **NOT** chained injection — that increases injection count, defeats the FK-31 win.
- **NOT** inline-in-one-hit — that would collapse 30–60s into one game-thread hit, deny
  per-hit settle.
- **IS**: one outer supervisor enum `g_dlpPhase = {DP=0, PD=1, DX=2, PL=3, DONE=4}` that
  dispatches to the existing `DoDropPlane` / `DoDropPod` / `DoDismount` / `DoPlay` on each
  game-thread hit.

**Precedent this design is safe:** `PdResolve` at `tutorial_launch.cpp:10119-10145` conditionally
calls `DpResolve()` + `DpCallBP(g_dpSpawnFn,...)` as fallback when no LokiDropShip exists —
proves cross-arm primitive calls are safely re-entrant. `DX` and `MOUNT` already share
`RdResolve()` + `g_rdPod`/`g_rdComp`/`g_rdPS`/`g_rdHero` — this IS the phase-to-phase handoff
pattern.

### State machine

| phase | name | dispatch | terminal criterion | measured cost (n=1 flight 4b) |
|---|---|---|---|---|
| 0 | DP | `DoDropPlane()` | DropShip census `0→1` | ~1–3s |
| 1 | PD | `DoDropPod()` | fresh `BP_DropPod_Tutorial_C`, PodTeamIndex==0, LokiRideable non-null | ~10–15s |
| 2 | DX | `DoDismount()` | `PlayersAttached.Num 0→1→0`, detach fault=no, hero moved | ~3–5s |
| 3 | PL | `DoPlay()` | `[PL] *** init complete: body=BUILT; camera + WASD active ***` then holds `KDLPPLAYHOLDMS` | ~15–30s + hold |

**Transition rule.** Each phase's sub-ladder advances its own `g_xxStep` each OnPI hit as
today. Each terminal case calls a NEW helper `SubladderComplete()` instead of setting
`g_done=1`:

```c
static void SubladderComplete() {
#if kRunMode == RM_DROPLANDPLAY
    g_dlpPhase++;
    g_dlpPhaseEnteredMs = GetTickCount();
    g_frameInit = FI_UNFIXED;      // RAII reset after DP (see R2)
#else
    g_done = 1;
#endif
}
```

Wire it at 3 sites: DP terminal (`tutorial_launch.cpp:7446`), PD advances
(`tutorial_launch.cpp:10914`), DX terminal (`tutorial_launch.cpp:14614`). PL has no terminal —
its FsHold timeout IS the outer mode's release.

**Between-phase settle.** No `Sleep()`. Each next-phase `Resolve()` already refuses cleanly
when the prior phase didn't produce its input:
- `PdResolve` refuses without LokiDropShip (`tutorial_launch.cpp:10147-10148`)
- `RdResolve` refuses without initialised pod (`tutorial_launch.cpp:13706`)
- `ResolveWakeMove` refuses without possessed hero (`tutorial_launch.cpp:12811`)

**The resolves themselves ARE the between-phase gates.** Game-thread `Sleep` blocks frames
(S140 T2 defect, `docs/s140-tier2-sentinel.md`).

**SEH policy.** The composed arm MUST NOT inherit `DoDropPlane`'s outer `__except` at
`tutorial_launch.cpp:7457-7461` (which sets `g_done=1` on ANY SEH). SpawnPlane's fault at
`rva 0x13495DD` is REPRODUCIBLE on this build (see §6.9), and the ship spawns anyway (statements
[6]..[9] execute BEFORE the fault at [10]). Wrap the DP sub-body call in a local `__except`
that LOGS and checks DropShip census `0→1` as the receipt for advancing.

**Failure handling.** HALT on any step-N success-criterion failure. Do NOT continue to N+1
with an unmet contract (would produce REFUSE cascade with unattributable markers). Record
`g_dlpFaultPhase` and skip to DONE so `DlpFinalReport` can attribute.

**ResetChainState() at Worker entry.** `g_dlpPhase = 0; g_dlpPhaseEnteredMs = GetTickCount();
g_dlpFaultPhase = -1;` — insurance against stale DLL state.

### Enum + build variant

- Add `RM_DROPLANDPLAY` after existing enum values at `tutorial_launch.cpp:260-264`.
- Variant name: `droplandplay`.
- `build.ps1` variant line — **DLP ONLY**, no other variant's build line changes:
  ```
  'droplandplay' = @('-DKRUNMODE=RM_DROPLANDPLAY',
                     '-DKFRAMEINIT=1',    # required for DP; RAII-scoped inside DP only
                     '-DKNOTELE=1',       # PL: prevent default KGROUNDX/Y/Z teleport
                     '-DKFLYMODE=1',      # PL: walking mode (matches play-atlanding-walk)
                     '-DKFSNAME=""',      # (verify against play-atlanding-walk's build line)
                     '-DKFAULTINFO=1', '-DKOUTPARMRET=1')
  ```
- Also add a `droplandplay-readonly` control variant if adopting the botspawn/mount pattern.
  Must be BYTE-DISTINCT from `droplandplay` — verify with `text_digest.py --dupes`.

---

## §2 — FILES TO MODIFY

| file | change | est. delta |
|---|---|---|
| `tools/sigbypass-mod/tutorial_launch.cpp` | add `RM_DROPLANDPLAY` enum; add `#if kRunMode == RM_DROPLANDPLAY` orchestrator block + `SubladderComplete()` helper + `DlpFinalReport()`; add supervisor globals; wrap 3 terminal `g_done=1` sites with `SubladderComplete()`; add outer Worker block near `:23969` doing FsArm → FsHold(KDLPPLAYHOLDMS) → FsDisarm → DlpFinalReport; add DP-local SEH wrapper (do-not-inherit); wire runtime `g_frameInit=FI_S80` RAII scope INSIDE DP entry only | **+120 to +200 lines** |
| `tools/sigbypass-mod/build.ps1` | add `droplandplay` (and optional `droplandplay-readonly`) variant | +5–10 lines |
| `tools/sigbypass-mod/text_digest.py` | audit-only, no code change | 0 |

**All new code MUST be gated under `#if kRunMode == RM_DROPLANDPLAY` at TU scope, including
string literals.** MEASURED hazard (`tutorial_launch.cpp:1119-1123`): an empty function-call
site — with NO change in `.text` size — moved play's `.text` digest `9bc10a4552c596e1 →
5dc37f819e641fdd`. Template: the `KOUTPARMRET` guard pattern at `tutorial_launch.cpp:1213-1223`.

---

## §3 — PRE-FLIGHT CHECKS (MANDATORY, IN ORDER)

Before FIRST flight, complete all of these. Halt if any fails.

### PF-1 (CRITICAL, unmeasured): DLL size vs manual-map threshold

The composed DLL's `.text` will be larger than any previously-successful manual-mapped DLL from
`tools/sigbypass-mod/build/tutorial_launch_*.dll`. This is the ONE unmeasured fundamental
unknown for the design.

```powershell
# Measure DLP against the largest historical
Get-ChildItem tools\sigbypass-mod\build\tutorial_launch_*.dll |
  Sort-Object Length -Descending | Select -First 5 | Format-Table Name,Length
```

If `droplandplay.dll` is significantly (>2x) larger than the largest historical successful
manual-map, investigate the manual-mapper (`tools/inject/mmap.go`) before flying. If comparable,
proceed. Record the size and the historical max in the flight's pre-registration.

### PF-2: Digest regression audit

```powershell
python tools\sigbypass-mod\text_digest.py --dupes tools\sigbypass-mod\build
```

Verify ZERO unexpected duplicate groups (`--dupes` clean, and no non-DLP variant collides with
`droplandplay`).

Byte-diff each existing regression-gated variant against its recorded `.text` sha256.
**⚠ USE THE CURRENT RECORDED DIGESTS — the prior workflow cited some stale values:**

| variant | CURRENT recorded digest | notes |
|---|---|---|
| `botai` | `5e47c13cf7f0a158` | S136, MUST NOT MOVE (dead-strip validator) |
| `play` | `9bc10a4552c596e1` | S123, MUST NOT MOVE (dead-strip validator) |
| `dropplane_b1only` | **`dcb19157cf45f9aa`** | POST-2060cb8 (was `5b4467b0105dec1a` pre-fix) |
| `droppod-pe-cdopoke` | **`283c1692a2135680`** | POST-2060cb8 (was `249a3cd2190eb334`) |
| `dismount-landstart` | **`62f257c191027ee3`** | POST-8f1e804 (was `0d5fa554edac53c5` pre-fix) |
| `dismount` | `0fe6d7ae1f26e16b` | POST-8f1e804 |
| `mount-ride` | `9b7f88af3210c438` | POST-2060cb8 |
| `mount-descend` | `c26e8831f45d7548` | POST-2060cb8 rebuild |
| `mount-phaseb` | `d69642beacc5e7a8` | POST-2060cb8 rebuild |

**If ANY of these move after your edit**, `#if kRunMode == RM_DROPLANDPLAY` isolation is
incomplete — add guards until byte-identical.

### PF-3: Record the DLP digest

Compute and record `droplandplay.dll` `.text` sha256[:16]. This becomes the new regression gate
for future sessions.

### PF-4: Elevated PowerShell + Steam running (standard)

### PF-5: Backup `docs/capture.log` if evidence still needed (`ags` may truncate on restart)

### PF-6: `forceTutorialMatch = true` in `server/internal/interactive/interactive.go`

Already set from prior session; verify with `Select-String "forceTutorialMatch\s*=" server/internal/interactive/interactive.go`. Rebuild `ags` if needed.

---

## §4 — FLIGHT RECIPE (reduced 7→4 injections)

```powershell
cd "G:\git\Supervive Revival Project"
# ELEVATED PowerShell. Steam must be running.

# 1. Launch backend + game, no default shims
.\configs\launch-redirect.ps1 -NoHook

# 2. In a second terminal, stage + inject DLP
.\configs\fk24-stage.ps1 -Probe tools\sigbypass-mod\build\tutorial_launch_droplandplay.dll -SkipProbe -Label dlp-flight1 -AllowStale
# ... wait for staging complete, then...
& tools\inject\inject.exe mmap <PID> tools\sigbypass-mod\build\tutorial_launch_droplandplay.dll
```

**Wait gates (do NOT skip; see `fk24-stage.ps1` discipline):**
- Wait for `Load map complete /Game/Loki/Maps/Tutorial/LVL_Tutorial` before proceeding past `fo`
- Wait for `[SP] done step=4` (in `docs/tutorial-launch-marker.txt` or the stager's copy
  `docs/fk24-stage-*-3-sp.txt`) before injecting DLP
- After DLP injects, monitor `docs/tutorial-launch-marker.txt` for the `[DLP] ...` phase headers

**Take dumpimage early** (per §6.10 recommendation, evidence survives mid-arm death):
```powershell
tools\usmapdump\usmapdump.exe dumpimage 'SUPERVIVE-Win64-Shipping.exe' dumps\s150-dlp-flight1-early
```

---

## §5 — PRE-REGISTERED SUCCESS CRITERIA

Write a pre-registration file `docs/dlp-flight1-PREREGISTERED.txt` BEFORE launch. Copy these
receipts verbatim into it:

**Unified marker stream (mirrors flight 4b's four separate markers, one file):**

```
[DLP] === PHASE 0: DP (dropplane_b1only) ===
[DP]  ... (existing DP marker output through to terminal)
[DP]  B1 SpawnPlane AFTER: FAULTED (SEH-captured) rva=0x13495DD    <- EXPECTED per §6.9
[DLP] DP: DropShip census 0->1 : PASS, advancing to PD
[DLP] === PHASE 1: PD (droppod-pe-cdopoke) ===
[PD]  ... (existing PD marker output)
[DLP] PD: BP_DropPod_Tutorial_C count +1 PodTeamIndex=0 LokiRideable=0x... : PASS, advancing to DX
[DLP] === PHASE 2: DX (dismount-landstart, KDXLANDING=2) ===
[DX]  cand[0] ps=... cls=LokiPlayerState_HeroAffiliated | GATE5 UNMEASURED -> SKIP
[DX]  cand[1] ps=... cls=BP_LokiPlayerState_C | GATE5 PASS | GATE6 PASS
[DX]  picked cand[1] ... hero=... 'BP_HERO_Ronin_C'
[DX]  D3 detach(PS in array) AFTER: fault=no
[DX]  hero before=(0.0, 0.0, 13240.0)  after=(-3206.4, 5070.5, 138.0)
[DLP] DX: hero moved to landing coord : PASS, advancing to PL
[DLP] === PHASE 3: PL (play-atlanding-walk) ===
[PL]  ... (existing PL marker output)
[PL]  *** init complete: body=BUILT; camera + WASD active ***
[ANIM] PlayAnimation(run, loop) ok
[ANIM] PlayAnimation(idle, loop) ok
[DIAG] hero=(-3206,5070,90) ...   <- landed and settled
[DIAG] hero=(-1960,5070,90) ...   <- WALKED, Z stayed 90
[DLP] === COMPLETE (or hold expired) ===
```

**Terminal success:** hero coord `(~-1960, 5070, 90)` or thereabouts (X moves, Z stays 90).
Matches flight 4b's measured behavior.

**Terminal fault:** `[DLP] === FAULT at phase N (name) ===` prominently, plus
`g_dlpFaultPhase` value in the final report.

---

## §6 — KNOWN RISKS + FALLBACKS

| # | Risk | Signal | Mitigation | Fallback if triggered |
|---|---|---|---|---|
| R1 | **DLL size** | `.text` significantly > all historical | measure before flight | investigate `mmap.go` before flying |
| R2 | **KFRAMEINIT wrong-scope cascade** | PL's `WireAbilitySystem` differs from historical | RAII scope `g_frameInit=FI_S80` at DP entry, `FI_UNFIXED` at DP exit | audit `g_frameInit` at fault call site |
| R3 | **DP `__except` kills recipe** | `[DP] SpawnPlane FAULTED` → immediate `g_done=1`, no PD/DX/PL | local `__except` around DP sub-body; DropShip census IS the receipt | if census stays 0, fault was consequential; halt with `g_dlpFaultPhase=0` |
| R4 | **Regression blast radius** | `--dupes` shows any existing arm at new hash | every new fn/literal gated under `#if kRunMode == RM_DROPLANDPLAY` | add guards until byte-identical to recorded gates |
| R5 | **Stale globals across sub-arms** | sub-arm reads stale ptr, prints nonsense | audit each Resolve() (write-before-read) | `ResetChainState()` at Worker entry |
| R6 | **KNOTELE/KFLYMODE drift** | hero ends at `(-65,-1770,393)` instead of landing coord | build.ps1 DLP line must include `-DKNOTELE=1 -DKFLYMODE=1` | rebuild + verify |
| R7 | **RdResolve timing** | DX finds no pod / wrong pod | call RdResolve AT the PD→DX transition, not at arm setup | halt with `g_dlpFaultPhase=2` |
| R8 | **Failed-run attribution** | "everything mostly ran" ambiguity | DlpFinalReport prints `g_dlpFaultPhase` + per-phase sub-headers | fix report format |
| R9 | **FK-31/FK-32 budget** | none — WIN vs sequential (54% → 19% sitting-loss) | n/a | n/a |
| R10 | **Pod position drift** | none — combined arm reduces variance vs sequential | n/a | n/a |

---

## §7 — DO-NOT-REGRESS RULES

- **Do NOT** restore DoDropPlane's outer `__except` set-g_done semantics inside the composed arm (R3).
- **Do NOT** skip PF-1 (DLL-size measurement) — this is the one unmeasured fundamental unknown.
- **Do NOT** set `KFRAMEINIT=1` globally without the RAII scope (R2).
- **Do NOT** flip `KNOTELE`/`KFLYMODE` defaults for other variants (only DLP build line changes).
- **Do NOT** `tee` over an evidence file after client death (S137 lesson).
- **Do NOT** trust `.text` size alone — diff the SHA (repo rule).
- **Do NOT** bank on this working first flight — pre-register in
  `docs/dlp-flight1-PREREGISTERED.txt` BEFORE launch.
- **Do NOT** add RM_MOUNT — DX's own `PlayersAttached` append IS the atomic mount for the
  immediately-following detach. Document this in the orchestrator's leading comment so a
  successor knows why RM_MOUNT is absent.
- **Do NOT** read the marker mid-run to declare success — wait for `[DLP] hold expired,
  disarming` or an explicit fault line (S135 lesson: wait for `[BS] done`).
- **Do NOT** promote DLP to the default `.\configs\launch-redirect.ps1` set. Still a
  DIAGNOSTIC arm using authority-only entry points via S55 primitive + one CDO poke via play's
  own scope. Not a shipping fix.

---

## §8 — AFTER THE FLIGHT

If success:
1. Preserve marker: `Copy-Item docs/tutorial-launch-marker.txt docs/dlp-flight1-final-marker.txt`
2. Take late dumpimage: `usmapdump.exe dumpimage ... dumps\s150-dlp-flight1-success`
3. Terminate cleanly: `Get-Process SUPERVIVE-Win64-Shipping,ags | %{ $_.Kill() }`
4. Update `docs/drop-sequence-status-s150.md` with §6.17 flight result
5. Commit — this is a code + doc commit, same clean-scope discipline as prior session

If fault:
1. Preserve marker + late dumpimage as above
2. Read the `[DLP] FAULT at phase N` line + `g_dlpFaultPhase` — that's your localization
3. Design a targeted next step based on the specific failure mode (§6's table)
4. Do NOT re-fly without diagnosing — each armed window costs an FK-31 sitting-loss risk

---

## §9 — RESERVE TARGETS (if this succeeds, or as parallel work)

In priority order per prior session:
1. **§6.13 IntroSequence timer blocker** — offline transcribe `OnIntroSequenceFinished`'s AS
   body (LokiDropPod.as ~L4088-4104) and enumerate all gates on the leader-pod branch.
   Localizes H1/H2/H3 (see §6.13).
2. **§6.9 CallBPGuarded FFrame+0x80 primitive fix** — allocate `FOutParmRec` chain from
   UFunction's `CPF_OutParm` children. Unblocks every `FUNC_HasOutParms` UFunction
   project-wide. Long-term win.
3. **CO-OP vs AI acceptance predicate** — `docs/coop-vs-ai-roadmap-s142.md` (WALL P + WALL E).
   Separate track from S150-drop.

---

## §10 — KEY FILES + POINTERS

- Design source: `docs/drop-sequence-status-s150.md` §6.5-§6.16 (canonical state of the drop track)
- CLAUDE.md drop section: `CLAUDE.md` at the "Before touching anything drop- / deploy-" heading
- Flight-4b evidence: `docs/mount-flight-4b-final-marker.txt` (gitignored, 15,903 bytes),
  `dumps/s150-mount-flight-4b-success/` (gitignored)
- The proven arms (all built + verified in prior session):
  - `tools/sigbypass-mod/build/tutorial_launch_dropplane_b1only.dll` (`dcb19157cf45f9aa`)
  - `tools/sigbypass-mod/build/tutorial_launch_droppod_pe_cdopoke.dll` (`283c1692a2135680`)
  - `tools/sigbypass-mod/build/tutorial_launch_dismount_landstart.dll` (`62f257c191027ee3`)
  - `tools/sigbypass-mod/build/tutorial_launch_play_atlanding_walk.dll` (`944a27728053359e`)
- Injector: `tools/inject/inject.exe`
- Staging script: `configs/fk24-stage.ps1`
- Launcher: `configs/launch-redirect.ps1`
- Text-digest audit: `tools/sigbypass-mod/text_digest.py`

**When in doubt:** re-read [docs/drop-sequence-status-s150.md](docs/drop-sequence-status-s150.md)
§6.16 (the mount-flight-4b success record) — it names every offset, every digest, every
receipt that this DLP arm must reproduce.
