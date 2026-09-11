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

### S132 (2026-08-20) — one more instance, and ★ **it DID leave a dump**

**[M] One FK-31 staging death in five launches this session** (flight 4). Exit `0xC0000005`, only
`gft_ready_fix` + `tutorial_launch_fo` resident, probe never injected — the canonical shape.
Primary record: `docs/s132-dismount-settled.md` §6a-2.4.

★ **`crashwatch` caught it and `launch-redirect.ps1` archived a 41 MB crashpad minidump to
`dumps\crashpad-20260820-143225`.** Worth stating plainly because the *sibling* class (FK-32,
below) is the artifact-less one and the two get conflated: **FK-31 deaths are dumped**, which is
already what "What is known" records above, and this is one more confirmation rather than a new
property.

⚠⚠ **A pre-registered prediction that this run CANNOT test, recorded so nobody scores it.** The
crash-era `dump.exe` reads **`.text` 51.8 %** against a healthy client's **53.0 %**, which *looks
like* a refutation of *"a crash-era image holds MORE decrypted `.text`"*. **The comparison is NOT
matched:** it died at **141 s** having exercised far less game code than a client that had run the
whole staging + Route E + dismount chain. ⇒ **UNINTERPRETABLE for that hypothesis, not a
refutation.** A matched test needs two images taken at comparable uptime and comparable code
coverage.

⚠ **Denominator discipline — do not silently re-fit the headline.** S132's five launches were a
dismount campaign, not an FK-31 rate campaign, so pooling them into the 22/82 is not a controlled
statistic. The raw addition is 23/87 = 26 %, i.e. **materially unchanged**, and that is all it is
worth as an observation. The 27 % figure above stays as measured over the S112 corpus.

★ **And an offline lane the same day gave the `runtime.dll base + 1` fault a MECHANISM CLASS.**
S131 measured the kill address as constant per boot and named the target as `runtime.dll + 1`;
S132 read `runtime.dll` itself and found that **4,769 of its 18,580 functions end in a computed
`jmp <reg>`**, with targets carried as `movabs reg, -(ImageBase + target_RVA)` inside an MBA
polynomial. **[I] `live_base + 1` is the native output shape of that dispatch when the resolved
target RVA is 1 — or is 0 with the tail's `inc` applied.** ⇒ the kill need not be a bespoke crash
primitive at all; it is consistent with the protector's **ordinary flattened dispatch being handed
a null/poisoned target**, landing on its own read-only DOS header and faulting EXECUTE. That
matches every S131 measurement (`ExceptionInformation[0]==8`, READONLY/MEM_IMAGE page, per-boot
constancy). **Grade [I]** — the runtime `delta` term's storage is not identified, and a custom
fixup table in the encrypted `packer0` is an equally consistent alternative. Full record and
denominators: `docs/fk10-protector-identified.md` §6b.

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
| corpus count | 27 deaths | 2 instrumented (`s112c-trt-10`, `s112ship-06`) + 1 uninstrumented — **+1 in S132 ⇒ 3 instrumented** (see below) |
| trigger | a standing `.text` write | unknown |
| mechanism | ⚠ **OPEN** — what is [M] is the *fault signature* (`runtime.dll+1`, EXECUTE, `ExceptionInformation[0]==8`), not the mechanism. S132 gives it a **mechanism CLASS** only, graded **[I]** (see the S132 entry above). This row must not be read as "FK-31's mechanism is known" — the header above says the mechanism is exactly what is open | ★ **CLOSED S113 (FK-10)** — the protector calling `NtTerminateProcess(h, 0xDEAD)` at `runtime.dll` RVA `0x80f7f0`; see `docs/fk10-protector-identified.md` §6 and §6b. ⚠ the `NtTerminateProcess` *identity* is [I], not [M] — FK-10 §6b |

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

## S132 (2026-08-20) — a third instrumented instance, harvested exactly as prescribed

**[M] Flight 3 died with exit code `0x0000DEAD` during `play-atlanding`'s init**, on the **7th
injection into that one process**, at **395.3 s** elapsed. `crashwatch` was attached and polling at
50 ms and reports `MISSED: process exited before any crash marker was seen` —
**no dump, no UECC, no `handing control over to crashpad`**, i.e. the artifact-less signature above
reproduces exactly. Raw: `scratchpad/s132/evidence/f3-crashwatch-0xDEAD.log`. Context:
`docs/s132-dismount-settled.md` §6a-2.4.

⇒ **N = 3 instrumented, across three different builds and two sessions** (`s112c-trt-10` and
`s112ship-06` are both S112; this is the first outside it). Consequence for that
sitting: it is **VOID for the question it was flying** (hero playability at the landing point — no
`[PL] init complete` was ever printed), **not a negative result**.

★ **This cost nothing.** It is the "harvest it, don't spend launches on it" plan below working as
designed — the exit code came free from an instrument that was already permanent.

⚠ **Not established, and not tested here:** whether the 7-injections-into-one-process depth is
causal. It is a plausible dose variable (this project's whole hazard ladder is dose-shaped) but
S132 ran one such sitting, so it is **[S]**. Record injection depth on every future death; it is
free and it is the cheapest way this variable ever becomes testable.

## What is NOT established

⚠ **N = 2** *(as written 2026-08-08; **now N = 3** — see the S132 entry above, which does not change
the reasoning below)*. Reproducible across two different builds, non-random value, but two
observations. The claim "the two kill modes are mechanistically distinct" is **suggestive, not
established.**

★ **What HAS since been established is the MECHANISM, not the trigger** (S113, FK-10): the kill is
the protector executing `NtTerminateProcess(<handle from [this+0x10]>, 0xDEAD)` at `runtime.dll`
RVA `0x80f7f0`. S132 re-verified those bytes offline and found the **owning object** — that stub is
slot 4 of a 5-method vtable at `packer0` RVA `0x1831C0`, installed by a constructor at RVA
`0x7F86F0` which is the table's **only xref image-wide**. ⇒ **the constructor's call site is the
next thing to read, and it is the closest anything has come to FK-32's trigger.** See
`docs/fk10-protector-identified.md` §6b.
⚠ Grade honestly: the **bytes** are [M]; the **`NtTerminateProcess` identity** is inherited
annotation, not an offline measurement — the syscall number is decrypted at runtime and evaluates
to `0xFFFFFFFF` on disk, so the file alone only supports `Nt???(HANDLE, 0xDEAD)`. FK-10 §6b carries
the detail.

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
