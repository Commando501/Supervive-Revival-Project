# FK-31 and FK-32 — the two problems that outlived FK-7

**Opened 2026-08-08 (S112), when FK-7 was closed.**

FK-7 was *"the tutorial run dies within ~1–5 minutes."* Its cause is now measured, fixed and shipped
(`docs/s112-fk7-ab-results.md`): a standing `.text` patch of our own, **10/10 armed windows died with
it vs 3/36 without, Fisher p = 0.00000007**.

Two failure modes remain on the tutorial route. **Neither is FK-7** — each has a different mechanism,
a different lifecycle, and a different window — so they are split out rather than left keeping a
solved item nominally open. That framing is deliberate: leaving FK-7 "open" on these would repeat the
project's own recorded mistake of pooling distinct mechanisms under one label.

---

# FK-31 — the staging hazard *(now the dominant tutorial-route failure)*

> **Register framing** (`docs/ignorance-map-s101.md` is the canonical FK register, and its entries are
> FALSE KNOWNS): FK-31's false known is **"`fo`'s slot-285 `.rdata` `CustomLogin` patch is obsolete
> now that S107/S108 made the world load reliably"** — falsified below. The *open problem* it was
> meant to solve, the staging hazard, rides with it.

**MEASURED: 22 of 82 launches (27 %) die during staging**, before the probe DLL is injected at all.

### ⚠ FK-31 is NOT a re-filing of FK-26 — checked before opening this ID

FK-26 was *"the force-open dies silently ~2 of 3 launches **with no dump**"*, and it is **REFUTED**:
that "silent, dumpless" premise was an instrument blind spot (a census that enumerated only `UECC-*`
directories), and the deaths **do** write crashpad minidumps. FK-31 is the opposite situation — the
deaths are **measured, dumped and classified** (`OURS/protector`, 3 with exit `0xC0000005`). What is
open here is the **mechanism and its removal**, not whether the deaths are observable.

The observation overlap is real and is why the check was made; the ID is separate because the open
question is different.

## What is known

- Only `gft_ready_fix` and `tutorial_launch_fo` are resident when it happens.
- `gft_ready_fix` writes **no module image at all** (its only write is a heap flag), so the writer is
  **`fo`**.
- Every such death that left a dump classifies **`OURS/protector`** — `RIP == <runtime.dll base> + 1`,
  EXECUTE, `ExceptionInformation[0] == 8`. Three carry exit code `0xC0000005`.
- Deaths cluster around the map load (measured examples: T+0.5 s, T+3.4 s, and before it entirely).
- It is **arm-neutral** — it occurred at statistically indistinguishable rates across every probe and
  every hold length tested, which is why it could never explain any A/B result.

## The mechanism is CONFOUNDED and that is the whole problem

`fo` makes **two** module-image writes, and they are inseparable in every run ever flown:

| # | write | section | window |
|---|---|---|---|
| 1 | `ProcessInternal` prologue jmp | **`.text`** | ≤ 8 s, transient |
| 2 | slot-285 `CustomLogin` × 5 vtables | **`.rdata`** | ≤ 25.5 s |

S111 only ever measured `.text`. The claim that `.rdata` is also caught by the protector is an
**S61-era inference that has never been tested**.

## ⚠ `KNOLOGINVT` IS FALSIFIED — do not re-run it

The obvious experiment — drop the `.rdata` write and see if deaths fall — **was built and flown**
(`build.ps1 -Variant fo-nologinvt`, `.text b834ff93827654aa`). It does not work:

**4/4 launches died, 0/4 loaded the map**, every one with the exact fatal the S62 source comment
predicts: `LogSpawn: Warning: Login failed: ALokiGameMode::Login failed to Login` →
`Couldn't spawn player`. Fisher vs the `.rdata`-present baseline (13/51): **p = 0.0026**.

⇒ **The slot-285 patch is still load-bearing.** S62's stated purpose stands, and the S111 handoff's
speculation that S107/S108 had made it obsolete is **wrong**.
⇒ **The `.rdata` question cannot be answered by removal** — the route breaks before the question can
be asked.

## The next experiment (design, not just a flag)

**Patch-then-immediately-restore.** Keep `CustomLogin` installed only across the instant `Login`
actually fires, instead of holding it for the whole ≤25.5 s deferred-travel window. That shrinks the
`.rdata` exposure without changing semantics, so it tests exposure *duration* — the variable S111
showed governs the `.text` hazard — rather than deleting a load-bearing behaviour.

If that also fails, the remaining clean approach is to express `CustomLogin` as a **heap** write, the
way `FsScan`/`FsThunk` did for RM_PLAY's `ProcessInternal` hook (`tools/sigbypass-mod/tutorial_launch.cpp`).
That is now a proven, worked pattern in this codebase.

---

# FK-32 — the `0x0000DEAD` artifact-less residual

> **Register framing:** FK-32's false known is **"the artifact-less death class is hangs —
> `Stall.RecordDump=false` configures them to leave nothing"** — falsified below. The *open problem*,
> the 3/36 residual, rides with it.

**MEASURED: 3 of 36 armed windows (8 %) still die with no module-image write anywhere.**

## Why this is a different animal from FK-7

| | FK-7 (closed) | FK-32 |
|---|---|---|
| exit code | **`0xC0000005`** (access violation) | **`0x0000DEAD`** |
| artifact | crashpad minidump, `runtime.dll+1`, EXECUTE | **none at all** — no dump, no UECC, no `handing control over to crashpad` |
| corpus count | 27 deaths | 2 instrumented (`s112c-trt-10`, `s112ship-06`) + 1 uninstrumented |
| trigger | a standing `.text` write | unknown |

## `0xDEAD` is not ours, and that is measured, not assumed

- `grep` over every shim source finds `0xDEAD` twice, both as **read** sentinels
  (`catalog_probe.cpp:191`, `tutorial_launch.cpp:3370`).
- There is **no `TerminateProcess` or `ExitProcess` call anywhere in the shim sources.**
- Our own harness kill was run as an explicit control: `Stop-Process -Force` and `.Kill()` both exit
  **`0xFFFFFFFF`**, not `0xDEAD`.

⇒ It is a deliberate silent termination by something that is not us.

## Why it matters beyond the tutorial

This **partially answers FK-8's own §7.2 item 2** (*"are the artifact-less terminations crashes or
`Stop-Process`?"* — **neither**), and it undermines the project's standing attribution of the
artifact-less death class to **hangs**. That attribution rested on `CrashReportClient.ini` setting
`Stall.RecordDump=false`, i.e. hangs being *configured* to leave nothing. At least some of those
deaths are not hangs at all — they are silent kills, and the exit code recovers them for free.

## What is NOT established

⚠ **N = 2.** Reproducible across two different builds, non-random value, but two observations.
The claim "the two kill modes are mechanistically distinct" is **suggestive, not established.**

## How to make progress cheaply

The instrument is already permanent — `configs/fk7-ab-run.ps1` holds an OS handle open across process
exit and records `exit_code` on **every** death, at zero marginal cost. So every future tutorial run
adds to this corpus whether or not anyone is studying it. Do not spend dedicated launches on FK-32
until N is larger; harvest it.

---

# What is deliberately NOT on this list

**"No shim-free tutorial run has ever been made."** This has been carried as a caveat for many
sessions. It is worth stating plainly that it is a **structural property of the force-open route, not
an outstanding task**: the tutorial map only opens *because* `fo` force-opens it, so a shim-free run
cannot exist on this route by construction. Removing that caveat requires the real match/travel flow
to work — a different workstream entirely (see the DS route notes).

Consequence: **8 % is our floor, not the game's rate**, and no amount of work on FK-31/FK-32 changes
that. A tutorial-specific game defect remains **unsupported** (0 qualifying dumps in 82 launches, 28/28
`OURS/protector`) and **unexcludable** on this route.

---

# Related, higher-value, and outside both

**The MENU route is unconverted.** `mainmenu_refresh_pi8`, `loadout_fix` and `missions_fix` all still
install transient `.text` prologue patches — S111 measured that trio at **33 % deaths per 320 s hold**.
`FsScan`/`FsThunk` in `tutorial_launch.cpp` is now a proven, shipped, worked example of replacing a
`ProcessInternal` `.text` hook with a 2-pointer heap write. Porting it would apply FK-7's fix to the
other half of the project, and it is the largest remaining win from this line of work.
