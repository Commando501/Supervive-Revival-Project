> ⛔ **FK-7 IS CLOSED (S112, 2026-08-08).** Any statement below that FK-7 is open, unverified, or needs a reproduce-then-repair run is **HISTORICAL**. Cause = our own standing `.text` patch (10/10 died with it vs 3/36 without, p = 7e-8); fixed, shipped, deployed. The remaining tutorial failures were split out as **FK-31 / FK-32** (`docs/fk31-fk32-successors.md`). Start at `docs/s112-fk7-ab-results.md`.

# S108 — name the ViewTarget writer, triage the new crash, close or re-scope FK-7

**Read this whole file before touching anything.** Everything below was measured live in S107
(2026-07-27) and is committed (`8e523ab`..`100a325` on `dedicated-server-stub`).

---

## 0. What changed in S107 — the thing that unblocks everything

**Getting into the tutorial is SOLVED.** It was never a shim problem: two fields were missing from
the backend's party/match documents. Both are now committed in
`server/internal/interactive/interactive.go` with the measurement in the comments.

1. **`FParty.State`** — `buildSoloParty` now serves `"state": "Default"` (+ `"clientVersion"`).
   `TryStartSoloMode` reads it at `PartyModel+0x558+0x18`; it read empty, so the call bailed **before
   any network egress**. Clean before/after from `capture.log`: pre-fix press = zero HTTP + zero log
   lines; post-fix press = `POST /party/parties/{id}/startSoloMode?mode=tutorialNew`.
   ⇒ **The START button was never broken.** The "live memory poke" in the FK-5 notes was a
   workaround for this missing field, not evidence the UI path was dead.

2. **`ConnectionDetails.address = ""`** (was `127.0.0.1:7777`) — **the keystone.** With the DS
   address the client arms a MatchID it can never reach, `/core-game/players` then reports a
   permanent non-empty MatchID, the client believes it is **already in a match** (presence blob
   reads `"a":"InMatch"`), and **every later START is a silent no-op**. Empty ⇒ it builds a valid
   `CoreGameMatchModel` and **parks** on the match loading screen.

This also closed the **S63/S64 "make it STAY"** frontier. The force-open used to revert to the lobby
in ~300 ms (`Client is ready to play` → `failed to get ULokiServerPlatformInstance` → `Browse` back)
purely because it ran with **no valid match model**. Injected into the parked state it does not revert.

### ★ THE RECIPE (this is how you get a world; do not improvise)

```powershell
# 1. ELEVATED PowerShell. Steam must already be running.
cd "G:\git\Supervive Revival Project"
.\configs\launch-redirect.ps1 -NoHook            # returns after launching; game keeps running

# 2. IN GAME: PLAY -> TUTORIALS -> BASIC TRAINING -> START.
#    The client PARKS on the "DROP IN, GEAR UP, AVOID THE STORM" loading screen. That is correct.

# 3. Then, into the live PID (get it with Get-Process SUPERVIVE-Win64-Shipping):
.\tools\inject\inject.exe mmap <pid> tools\sigbypass-mod\tutorial_launch_fo.dll   # login APPROVED
.\tools\inject\inject.exe mmap <pid> tools\sigbypass-mod\gft_ready_fix.dll
.\tools\inject\inject.exe mmap <pid> tools\sigbypass-mod\tutorial_launch_sp.dll   # spawn+possess
.\tools\inject\inject.exe mmap <pid> tools\sigbypass-mod\build\<the play/probe DLL>
```

Success looks like, in `docs\tutorial-launch-marker.txt`:
```
[VT]     custom-login INSTALL: 5 vtables slot285, stockLogin=0x… tramp=0x…
[LOGIN1] gm=BP_LokiGameMode_Tutorial_C PCClass=BP_LokiPlayerController_Dev_C err='(empty=approved)'
[SP]     gm=0x… pc=0x… startSpot=0x… heroClass=0x…      <- ALL FOUR non-zero
[SP]     done step=4 spawnedPawn=0x… cls=BP_HERO_Ronin_C
[PL]     *** init complete: body=BUILT; camera + WASD active ***
```

⚠ **Traps, all hit in S107:**
- `RM_PLAY` and `RM_SPAWNPOSSESS` are **continuation** modes — they attach to an already-running
  tutorial and `return 0` before the force-open block. `-Hook <play dll>` alone **cannot work**
  (S107 wasted a launch on this). `ResolveSpawnPossess` is **one-shot, no retry loop**, so inject it
  only once the world is genuinely up. `[SP] gm=0x0 pc=0x0 startSpot=0x0 heroClass=0x0` = the world
  is gone; do not proceed.
- The marker file is **truncated on every injection**. Copy it off after each stage or you lose the
  earlier shim's output.
- Restarting `ags` mid-session forces the client through a **re-login** (`LVL_Login` → lobby, ~40 s).
  It also clears the armed `SoloMode` (`json:"-"`), which is the cure for a stuck phantom match.

---

## 1. TASK ONE — `wprobe2`: name the writer (FK-24)

**Goal:** identify what writes `0x01` into the low byte of `APlayerCameraManager->ViewTarget.Target`
at `+0x420`. Full brief: `docs/fk24-writer-probe.md`. Mechanism detail: `docs/fk7-crash-settled.md`.

**Why `wprobe2` and not `wprobe`:** S107 ran the DR build. It armed cleanly —
`arm sweep#1 threads=128 armedOK=128 dr7ReadbackZero=0 failGet=0 failSet=0` — and then:

```
[WP] selftest *** FAIL: no trap 8000 ms after arming (selfPhase=0) -- the watchpoint is VOID on the
     game thread. READ NOTHING ELSE IN THIS RUN AS A NEGATIVE. ***
[WP] *** W2: 1 thread(s) had our Dr7 bits CLEARED BY SOMETHING ELSE since the last sweep (the packer
     polls DR). Coverage for that window is VOID, not negative. ***
```

That is the anticipated void condition, and the escalation rule is explicit: **escalate to `wprobe2`
on a VOID verdict, never on a clean negative.** `wprobe2` is `KWPROBE=2` — a process-wide
`PAGE_READONLY` write trap on the 4 KB page holding `&Target`. Process-wide means the packer's
per-thread DR polling cannot defeat it.

```
tools\sigbypass-mod\build\tutorial_launch_play_wprobe2.dll
```

**Before you spend a launch:**
- Rebuild it (`.\tools\sigbypass-mod\build.ps1 -Name tutorial_launch -Variant play-wprobe2`) and
  verify with `verify_dll.py`: zero `__CxxFrameHandler`/`_CxxThrowException`, distinct `.text` hash.
- ⚠ Consider building a **`play-wprobe2-v66`** variant (`-DKPUPYAW=-90`). S107 established the four
  camera crash dumps show `POV.Rotation == (-66,-90,0)`, which needs `KCAMPITCH=-66` (the *source*
  default) **and** `KPUPYAW=-90` (**not** the source default 0.0). Neither the plain source build nor
  the S99 flag-set reproduces that POV — the crashing vintage was an intermediate. The probe logs
  the live POV, so **verify the vintage match in-run rather than assuming it**.
- **Read the instrument before the result.** Gate on `selftest *** PASS ***`. No PASS ⇒ the sitting
  is VOID; stop and fix the instrument rather than burning launches.
- The bug fires roughly **1-in-2 to 1-in-3 per launch**, so a quiet run is **not** evidence.
  Budget ≥4 launches; each still reports whether the instrument worked.

**What a hit gives you:** the writing thread, `module+RVA`, 64 live instruction bytes (capturable
even from a never-decrypted page — the CPU just executed it), the store width **from hardware**, and
which register held the PCM (separating "aimed at this field" from a type confusion). Resolve the RVA
offline afterwards with `python tools\strxref\strxref.py func 0x<rva>`.

⚠ **The retracted criterion — do not re-introduce it.** `delta = live − corrupt` is *arithmetically
forced* to `+0x3F` whenever byte 0 becomes `0x01` (live low byte is `0x40` in 3/3, including a clean
control). It discriminates **nothing**, and it had been built into the fix's own instrumentation
where it would have printed `delta=+63 lowbyte=0x01` and been read as confirmation. Report the
**writer's identity**, never a property of the written value.

---

## 2. TASK TWO — triage the new crash dump

S107 produced the **first crash on the fixed build** (`KVTGUARD` + `KGCROOT` + `KXFORMFIX` +
`KTESTACTOR=0`):

```
dump : %LOCALAPPDATA%\SUPERVIVE\Saved\Crashes\UECC-Windows-166396E24F5A36C5727032B196D739EA_0000
when : 2026-08-04 03:49:20 game time  (~90 s after the probe's init completed)
base : 0x7FF6EAA10000
RVAs : 35aa803 3ed1a7f 3ed8642 f96a8e f9ce6a 3eeedd4 3ef3e65 39c76c6 37f8b8c 4028924 403005f
       40300da 4030f6c 4039696 751ef62
```

Against the FK-7 families: **shares only the tail frame `37f8b8c`** with the GameThread family;
nothing with the worker family. **`3c5dc52` (`CalcCamera`) and `3c5d255` are ABSENT** — the FK-7
camera signature did **not** recur. That is *consistent* with the vtguard working, but **one dump
cannot prove it** and this is a different crash needing its own triage.

Also in that run, caught and survived via SEH (anim swapping self-disabled, session continued):
```
[NULL] fatal 0xC0000005 RIP=0x7FF6EB9F2420 rva=0xFE2420 access=READ addr=0x3000000003
[ANIM] PlayAnimation(A_Ronin_Cosmetic_HeroSelect_Breathe, loop) FAULTED -> anim swapping DISABLED
```
`addr=0x3000000003` and `RAX=3000000000 / RBX=3000000030 / RDX=3000000030` look like a **tagged or
shifted pointer**, not a null deref. Worth its own look — it may be the same class of bug as the
one-byte `ViewTarget` corruption.

**Tools:** `tools/crashtri/` — `harvest.py` (census + family classification over all 87 dumps),
`mdctx.py <dump>` (exception record + full `CONTEXT_AMD64`), `deadobj.py <dump>`,
`ptrhunt.py <dump> 0x<ptr>`. Then `strxref func 0x<rva>` and `vtables.py who|slotof` to name frames.

**Deliverable:** name the frames, classify the family (new? a variant of A/B?), and state plainly
whether the vtguard prevented Family B or merely wasn't exercised.

---

## 3. TASK THREE — close or re-scope FK-7

FK-7 is **OPEN**, verdict **DO-NOT-CLOSE**, for one reason: **zero live runs of the fix exist that
reproduce-then-repair.** See `docs/fk7-crash-settled.md` §0 (governing) and
`memory/supervive-tutorial-crash-fk7.md`.

The verification run, in order — **a quiet run is VOID, not a pass**:

- **Run 0** — `play` vs `play_testactor`; `grep -c LogChaosCloth Loki.log` → expect **0 vs 1**.
  Needs no crash, no marker, no surviving session, and it changes what the later A/B means.
- **Runs 1–2** — `play-novtguard`, hold to T+220 s, as a **MANDATORY positive control**: prove this
  build vintage reproduces the crash *at all*. The four camera dumps span three vintages and the
  sub-family split correlates perfectly with commit `a8d23f2`, so this is genuinely unknown. **If the
  controls are quiet the sitting is void and Runs 3–4 must not be read as a pass.**
- **Runs 3–4** — `play`, hold to T+300 s. Every criterion gates on the guard's own
  `[VTG] *** INVALID` detection line, **not on survival**. A quiet run without it is void, not a repair.

**Legitimate outcomes:** FK-7 CLOSED (reproduce + repair, both observed); or CLOSED-WITH-SPLIT; or
still OPEN with the residue named. Do **not** close on "the guard stops the symptom" — FK-7's
original sin was a mechanism claim made without opening a crash, and closing on the guard alone
repeats it one level up. The **writer** (FK-24) is a separate item and does not block closure.

Artifact set (six single-variable controls, distinct `.text` hashes, `play` unchanged):
`play`, `novtguard`, `nogcroot`, `nopimutex`, `noxformfix`, `testactor` — plus the `wprobe*` builds.
⚠ **`play_noxformfix` matches `play` in size AND `.pdata` count by design — only the `.text` hash
separates them.** Known defect left in deliberately: `s_tries` never resets and latches the guard off
after enough teardowns; it is function-scoped inside `VtResolve` and needs promoting to file scope
before the second run.

---

## 4. Subagents — cap of 3, and what they are for

**Hard cap: 3 agents total for the session.** The live work (launching, injecting, reading markers)
is **serial and must stay on the main thread** — it is one game process and one marker file, and
parallel agents would race each other. Spend the three on *offline* work that runs while a launch is
in flight or after it:

| # | Use it for | Not for |
|---|---|---|
| 1 | **Crash triage** (Task 2) — parse the new dump, name the frames, classify the family | anything touching the running game |
| 2 | **Adversarial verification** of whatever Task 1 or 3 concludes — the highest-value slot, given nine instrument-artifact errors in S107 | producing the conclusion it is meant to check |
| 3 | Hold in reserve: the `rva → function` sweep after a probe hit, or the `s_tries` fix + rebuild | speculative exploration |

Do **not** spend an agent re-deriving what is already written down — `docs/coverage-audit-s101.md`,
`docs/ignorance-map-s101.md` and the six `fk*-settled.md` files exist precisely so nobody re-does that.

---

## 5. ★ The rule that matters most

Nine claims in S107 were the **same error shape**: an instrument's blind spot recorded as a
structural property of the game.

| instrument | artifact | what got recorded | truth |
|---|---|---|---|
| reflection-only property walk | sees only UPROPERTYs | "the legacy input path doesn't exist" | no `UPROPERTY` macro at all in UE 5.4 |
| non-zero-**byte** coverage metric | counts bytes, not pages | "`.rdata` is 63% readable, structural" | 99.64% readable; the gap is padding |
| ASCII-only string scan | misses UTF-16 | "the packer encrypts module strings" | ~87,851 UTF-16 strings were invisible |
| `_AS`-suffix grep | matches only shadowing classes | "the script layer is thin — accept the ceiling" | 110 classes, ~8× undercount, ~26 sessions |
| an xref queried at +88 into a string | wrong start offset | "that code never ran" | 4 references, live function |

**Two of the nine were committed during the audit built to catch them**, one inside the FK-24
instrumentation itself. So:

- Write the instrument's blind spot **next to** every negative result. "No hits" means nothing
  without "scanned ASCII only, module range only, len≥6".
- **Run a positive control** before believing an absence. `tools/re/input_watch.py` still hardcodes
  `+0x418/+0x430` with no positive control anywhere in the record — if those offsets are wrong,
  every "input doesn't reach the pawn" reading in the project is void.
- A true statement about **one artifact** is not a statement about a **technique**.
- When a census returns a suspiciously round or small number, **question the key you grepped for**
  before believing the number.

See `memory/supervive-instrument-artifact-pattern.md` and
`memory/supervive-read-the-shipped-artifacts-first.md`.

---

## 6. Housekeeping

- Branch `dedicated-server-stub`. S107 committed as six area-split commits `8e523ab`..`100a325`.
  Nothing pushed.
- **`ags` must be running** for any live work (`server/ags.exe`, or just use `launch-redirect.ps1`).
  If you rebuild `ags`, re-append `certs/root.crt` to the game's `cacert.pem` — but note that
  restarting `ags` *manually* (not via the launcher) preserves the certs, because the launcher
  **wipes the certs dir** at line 185.
- `CLAUDE.md` still lags — it does not yet describe the recipe in §0. Updating it is a reasonable
  end-of-session task once the above lands.
