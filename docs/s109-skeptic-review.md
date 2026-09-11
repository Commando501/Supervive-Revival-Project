# S109 — adversarial review of the three S109 documents

**Date:** 2026-08-04 · **Role:** refute, not confirm. Default verdict when uncertain is *refuted*.
**Scope:** OFFLINE ONLY. No game launched, no injection, no live process. Nothing in
`.sentry-native/` or `Saved\Crashes` was modified — every file was opened `rb`/read-only.

**Documents under review**
1. `docs/s109-dump-forensics.md` (forensics agent)
2. `docs/s109-denominator-audit.md` (denominator agent)
3. `docs/s109-fk9-capture-durable.md` (coordinator)

**Instruments I used, and why they fail differently from the ones under review.**
I wrote a minidump reader from the MSDN `MINIDUMP_*` layouts (`skept_md.py` +
`t1_t3.py`/`t2_threadnames.py`/`t4_family.py`, scratchpad) that deliberately does **not** import
`tools/crashtri/mdctx.py`. Every stream is self-validated against its own declared header
(`SizeOfEntry`, `NumberOfEntries`, record counts) rather than against an assumed stride. All census
counts below come from **full enumerations** (`os.listdir` + `csv.DictReader` over every row) —
no `head`, no `tail`, no `head_limit` anywhere in the chain.

---

## Verdict summary

| # | target | verdict |
|---|---|---|
| T1 | `rip = runtime.dll + 1` | **CONFIRMED** — and better supported than the doc's own argument |
| T2 | 12-byte ThreadNames stride; tid 6104 ≠ GameThread | **CONFIRMED** by two independent methods |
| T3 | "this does not attribute the ~1–5 min tutorial death" | **CONFIRMED narrowly, OVER-CLAIMED as written** — one premise falsified, one MEASURED-for-2-of-6 |
| T4 | Family membership + the 3-dump "positive control" | **SPLIT** — family real; the control is **REFUTED** as evidence of shared cause |
| T5 | Retention retraction | **SPLIT** — "~3 min" retraction CONFIRMED; `state=2 ⇒ Pending` UNVERIFIED; rule PLAUSIBLE; **the shipped fix is safe either way** |
| T6 | Denominator audit | **arithmetic CONFIRMED throughout; two diagnoses REFUTED, one label self-contradictory, one internal number wrong** |

---

## T1 — `rip = 0x00007FFD3B400001` is `runtime.dll + 1` · **CONFIRMED**

### What I re-derived

**MEASURED — on-disk `G:\git\GAME BACKUPS FOR REVERSE ENGINEERING\SUPERVIVE\Loki\Binaries\Win64\runtime.dll`**
(67,511,496 B): `SizeOfImage = 0x4066000`, `NumberOfSections = 11`, `export dir rva=0 size=0`,
`AddressOfEntryPoint = 0x855440` (inside `packer1`, `0x7CF000..0x93E886`). Sections:
`.pdata .rwx packer0 packer1 packer2 .rsrc .reloc packer30 packer40 packer31 packer42`.
Every VA/VSize the forensics doc lists is exact.

**MEASURED — stream 16 corroborates, and its layout is self-validating.**
`SizeOfHeader=16, SizeOfEntry=48, NumberOfEntries=44804` ⇒ `16 + 44804·48 = 2,150,608` = the stream
size exactly. The fault region:

```
base=0x7FFD3B400000  size=0x7000   COMMIT  IMAGE  prot=PAGE_READONLY  ap=PAGE_EXECUTE_WRITECOPY
base=0x7FFD3B407000  size=0x1000   COMMIT  IMAGE  prot=PAGE_EXECUTE_READ
```

15 regions, `AllocationBase = 0x7FFD3B400000`, total span **exactly `0x4066000`**. The doc's
`PAGE_READONLY` claim, the `+0x7000` `EXECUTE_READ` neighbour and the `0x6FFF` miss distance are all
reproduced. The DEP reading is thus supported by two streams (6 and 16) plus the on-stack
`EXCEPTION_RECORD`.

### The attack, and why it fails

**Could the region be something else with a coincidentally similar layout?** No. Beyond the 11-section
match, there is corroboration from **an instrument neither S109 agent wrote**:

- `61C55551`'s UE `ModuleList` names **two** `runtime.dll` mappings — `0xFF760000 +0x4066000`
  **and** `0x7FF8F0400000 +0x4066000` — and that dump's fault address is `0x7FF8F0400001`,
  i.e. the named base **+1**. Its symbolicated `<CallStack>` reads literally
  `runtime_7ff8f0400000 / kernel32 / ntdll`.
- The `41cdafa3` dump contains hidden `MEM_IMAGE` allocations at **both** `0xFF760000`
  (span `0x4066000`, 10 regions) and `0x7FFD3B400000` (span `0x4066000`, 15 regions) — the *same
  two-mappings-of-0x4066000* shape UE named. Plus a third at `0x1F71BED0000`, one `READONLY` region
  of `0xA9E1000` = SUPERVIVE's `SizeOfImage` exactly.

So the naming does not rest on PE shape alone. **CONFIRMED.**

**Is "manually mapped, PEB-hidden" consistent with appearing in stream 16?** Yes, trivially, and there
is no tension: crashpad's `ModuleList` is built from the **PEB loader list**; `MemoryInfoList` is
built from **`VirtualQuery`**. An image absent from one and present in the other is exactly what an
unregistered section mapping looks like.

**Wording correction (mechanism, not conclusion):** `Type = MEM_IMAGE` with per-section protections
realised is a **kernel `SEC_IMAGE` section mapping** (`NtCreateSection(SEC_IMAGE)` +
`NtMapViewOfSection`), *not* a hand-rolled manual map — a manual mapper produces `MEM_PRIVATE`.
Say "mapped as an image section but never registered with the loader", not "manually mapped".

### Small errors in §5 (do not change the conclusion)

- `.rwx` is `XRW` on disk but maps live as **`PAGE_EXECUTE_READ`**, not `XRW`.
- *"none of the **2,384** pages of the fault image are in this dump"* — the image is `0x4066000/0x1000`
  = **16,486** pages. I verified **0 of 16,486** present. Substance right, arithmetic wrong.
- Verified alongside: **0 of 43,489** SUPERVIVE image pages present; `base+0x13454A0` (`ProcessInternal`)
  absent. The doc's stated blind spot is real and correctly stated.

### How load-bearing is it?

Less than the doc implies, which is good news. The downstream conclusions — *no game frames*,
*execute fault at the first instruction of a thread start routine*, *not FK-7* — hold for **any**
hidden image. The identification only names the **actor**. It happens to be solid anyway.

---

## T2 — 12-byte ThreadNames stride, and tid 6104 ≠ GameThread · **CONFIRMED**

### The stride, re-derived without assuming the count

**MEASURED.** Stream 24: size **1636**, and the stream's **own declared** `NumberOfThreadNames = 136`
(read from the file, not inherited from the ThreadList). ThreadList stream 3: size 6532,
`(6532−4)/48 = 136.000`, declared count 136, 136 distinct tids.

| stride | fits the stream? | tids present in ThreadList | name RVAs that resolve to a well-formed `MINIDUMP_STRING` |
|---|---|---:|---:|
| **12** | `4+12·136 = 1636` **exact** | **136 / 136** | **136 / 136** |
| 16 | `4+16·136 = 2180` **overruns by 544 B** | **0 / 136** | 34 / 136 (and overruns at entry 102) |

**⚠ A trap the forensics doc did not name, and which I checked because a wrong stride that produces
plausible output is this project's signature failure:** `4 + 16·102 = 1636` **also fits exactly**.
A 16-byte layout with `NumberOfThreadNames = 102` would have been size-consistent. It is excluded by
the declared count (136) and by the 0/136 tid match — not by the arithmetic alone. The doc reached the
right answer via an argument that would not have survived that alternative; the answer itself is safe.

### GameThread = 29236, by a method that never touches stream 24

**MEASURED.** Ranking all 136 threads by SUPERVIVE code/data pointers on their captured stacks:

```
1546  tid 29236   stack 327,680 B  (largest by 3.6x)  rip=ntdll+0x9DA74   6,664 B in use
 904  tid 13964   stack  45,056 B
 423  tid 13684   stack  86,016 B
 268  tid 26768   stack  24,576 B  rip inside the hidden runtime image
```

tid 29236 dominates on both pointer count and stack reservation. No other thread is a candidate.
The doc's figure of **104** is the count **at/above that thread's dump-time `rsp`** (live frames) —
I reproduce 104 exactly; the whole captured region holds 1546 (318 distinct). The definition should
be stated in the doc, but the number is right.

**tid 6104:** carries a ThreadNames entry with an **empty** string; 20,480 B stack. Of its 62
SUPERVIVE pointers, **6** lie between its dump-time `rsp` (`0x15F813EE78`) and the exception `rsp`
(`0x15F813F9B8`) — exactly the six the doc lists — and **56** lie *below* the dump-time `rsp`, i.e.
stale residue from the crash-reporting path that ran deeper on this thread and returned. **Zero** lie
at or above the exception `rsp`. Not the GameThread. **CONFIRMED.**

### One refuted MEASURED statement in §3

> *"Exactly **two** non-zero qwords above `rsp` in the whole 0x648-byte remainder of the stack"*,
> and the hexdump annotation *"`+0x040 .. +0x3FF` all zero"*.

**REFUTED — there are five.** Raw bytes from `rsp`:

```
+0x000  74 73 9a 3a fd 7f 00 00 ...      KERNEL32+0x17374
+0x030  91 cc 19 3b fd 7f 00 00 ...      ntdll+0x4CC91
+0x080  00 00 00 00 00 00 00 00  30 fb ff ff e8 04 00 00   <- +0x88 = 0x000004E8FFFFFB30
+0x090  30 fb ff ff d0 04 00 00  19 00 00 00 00 00 00 00   <- +0x90 = 0x000004D0FFFFFB30, +0x98 = 0x19
```

The doc asserted a range it did not print. The conclusion is unaffected — none of the three is a code
pointer — and in fact this **strengthens** §3: the same three constants appear at the same offsets in
all three walkable dumps (see T4).

---

## T3 — "this does not attribute the ~1–5 min tutorial death" · **CONFIRMED narrowly, OVER-CLAIMED as written**

### (a) "GameThread, RenderThread, RHIThread … were all healthy at the instant of death"

**Tagged MEASURED. It is not measured, and two of the three words are wrong.**

- **"at the instant of death"** — a crashpad dump is taken *during* exception handling, with all
  threads suspended. The dump samples the instant of the **dump**, not of the fault.
- **"healthy"** — what the dump shows is: `GameThread` at `ntdll+0x9DA74`, `RenderThread 0`
  (13684), `RHIThread` (30764) and `FAsyncLoadingThread` (13964) all at `ntdll+0x9D694`, using
  6,664 / 1,288 / 1,176 / 1,720 B of stack. Those are **ntdll wait stubs**. A thread blocked in a
  wait and a thread hung in a wait are indistinguishable in a dump. Supportable wording:
  **"alive, not faulted, blocked in an ntdll wait"**.

**★ The claim is nevertheless true — but on evidence the doc under-used.** From the session log:

- UE's `[NNN]` field is `GFrameCounter % 1000` and it **wraps** (`[982]` → `[  0]` at T+459.933).
  It advanced through **999 distinct frames in the 39.5 s** ending at T+490.72 (~25 fps).
- **Largest inter-line gap in the final 60 s = 0.068 s.** No stall, no ramp, no error burst.
- Two GameThread log lines at frame 781 are stamped `19:10:26.685` — **6 ms *after*
  `handing control over to crashpad`** at `19:10:26.679`. The game loop outlived the crash handoff.

Restate (a) on that basis. **⚠ Note the doc's own "frame counter advanced 772 → 778 across the last
258 ms" reads a mod-1000 counter as absolute.** It is correct here by luck; the same reading across a
wrap would be badly wrong.

### (b) "5 of the 6 fired ~3 s into startup, before any map loaded" · **MEASURED for 2 of 6; unsupported for 3**

| GUID | crash-dir `Loki.log` | span | `Load map complete` | dying in |
|---|---|---|---:|---|
| `61C55551` | 85,920 B | `21:28:08.948 → 21:28:11.814` = **2.87 s** | **0** | `FAssetRegistry` startup |
| `A55704B3` | 59,506 B | `08:40:06.432 → 08:40:09.261` = **2.83 s** | **0** | `LogD3D12RHI` feature probing |
| `064CE137` | **absent** | — | — | — |
| `62C094F1` | **absent** | — | — | — |
| `63AD699C` | **absent** | — | — | — |

**Blind spot, stated next to the negative:** for the three logless members the *only* timing datum is
`SecondsSinceStart = 0` — and **the two logged members also read 0** while their logs span 2.8–2.9 s.
So in this family `SecondsSinceStart=0` carries **no elapsed-time information whatsoever**; it is a
family *field*, not a *clock*. I cannot bound when those three died.

**⚠ REFUTED as stated:** *"Dates span 2026-06-26 → 2026-07-19, all **before the tutorial route
existed** (S107/S108, August)."* `tools/sigbypass-mod/tutorial_launch.cpp` was **added 2026-07-09**
(`ccdb847`); `docs/session-61-tutorial-match-setup.txt` and `docs/tutorial-launch-cmd.txt` landed
2026-07-11 (`a91a61c`). `61C55551` (07-10) and `A55704B3` (07-19) **postdate** the tutorial shim.
Drop the date argument entirely — it is not needed.

**Defensible restatement:** *"At least 2 of the 6 are MEASURED to have died before any map loaded, on
the ordinary launch path. The family therefore occurs without a tutorial world. Three more cannot be
placed in time at all."* That still carries the conclusion; the "5 of 6 at ~3 s" version does not.

### (c) Does 487.3 s / 341.7 s-post-map rule out a tutorial-correlated cause?

**No — and to its credit the forensics doc does not claim it does** (§6b: *"n=1 and undetermined"*).
What is ruled out: this faulting thread being one of the game's, and the three named crash families.
What is **not** ruled out: that something the tutorial run did (shim injection, world load, the
force-open) provoked the protector into spawning the thread. §9's headline sentence is fine if read
as *"this death is not an instance of FK-7 Family A/B or the S108 family, and no game code is on the
faulting stack"*; it is over-claimed if read as *"the tutorial route had nothing to do with it"*.

**Blind spot to record next to the whole of §9:** 0 of 43,489 SUPERVIVE image pages are in the dump,
so nothing about our hooks, a `.text` patch, or a tamper trip is visible in either direction.

**Verdict:** the operational consequence — *a sitting that dies must be checked against this signature
before its death is spent as FK-7 evidence*, and *the `play-nostatictest` arm has still never been
observed to die of FK-7* — **survives intact**. Both are the right calls.

---

## T4 — Family membership and the "positive control" · **SPLIT**

### The coordinator's "all five are zero-byte dumps" is **REFUTED**; the forensics correction is right

**MEASURED, full disk enumeration.** 0-byte / absent `UEMinidump.dmp`: `064CE137`, `62C094F1`,
`63AD699C`, `83E3410A`, `858B6F07`, `EBFECFE7`, `_0000` = **7**. `61C55551` = **13,631,799 B**,
`A55704B3` = **13,264,110 B**. Three of the five, not five.

### The 3-dump register/stack identity is **NOT a control** · **REFUTED as evidence of a shared cause**

Every equality the doc lists is **forced** by "the thread faulted at the first instruction of a start
routine reached through the standard `RtlUserThreadStart → BaseThreadInitThunk` path". My own
measurement makes this unavoidable — the shared state goes *further* than the doc reported:

| | `41cdafa3` | `61C55551` | `A55704B3` |
|---|---|---|---|
| `rax rcx rsi r12–r15` | 0 | 0 | 0 |
| `rdi == rsp` | ✔ | ✔ | ✔ |
| `rbx == r10` | ✔ | ✔ | ✔ |
| **`rbp`** | **`0x537AC9E1`** | **`0x537AC9E1`** | **`0x537AC9E1`** |
| **`r11`** | **`0x95654773B3BC`** | **`0x95654773B3BC`** | **`0x95654773B3BC`** |
| `[rsp]`, `[rsp+8..0x2F]`, `[rsp+0x30]` | k32+0x17374 / 40 B zero / ntdll+0x4CC91 | same | same |
| **`[rsp+0x88/0x90/0x98]`** | `4E8FFFFFB30 / 4D0FFFFFB30 / 0x19` | **identical** | **identical** |
| `rdx`, `rbx/r10`, `r8`, `r9` | **all different across the three** | | |

Two *non-zero constants* (`rbp`, `r11`) plus three constant stack qwords repeating byte-for-byte
across three launches on three ASLR bases means the values are **deterministic OS thread-start
residue**, not per-crash computation. The registers that *would* carry a shared computation are
precisely the ones that differ. So the "**seven independent equalities**" are **one fact — a virgin
thread-entry frame — counted seven times**. §3 of the forensics doc says exactly this
("thread-entry ABI state, not a computation in flight") and then §6b Ask 2 contradicts it.

The correct strength: *all three are thread-start faults*. That is enough to **reject the
import-trampoline hypothesis** (which the doc does, correctly, on stack geometry) but it is **not**
independent corroboration of a shared cause.

### What actually carries the family — and it does, well

The real discriminator is `fault address == base of a hidden 0x4066000-span MEM_IMAGE allocation, + 1`,
plus UE naming the module for two of them. Graded membership:

| GUID | evidence | grade |
|---|---|---|
| `41cdafa3` | 11-section PE match + the `0xFF760000`/high-base twin shape | **CONFIRMED** |
| `61C55551` | UE `ModuleList` names `runtime.dll @0x7FF8F0400000`; `<CallStack>` = `runtime_7ff8f0400000` | **CONFIRMED** |
| `A55704B3` | UE `ModuleList` names `runtime.dll @0x7FF90E000000`; `<CallStack>` = `runtime` | **CONFIRMED** |
| `62C094F1`, `63AD699C` | same ntdll base `0x7FF8F01D0000` **and** same fault `0x7FF8F0400001` as `61C55551`, where the module is named at that base | **strong** |
| `064CE137` | `0x7FFB9EE00001` — address shape only; no dump, no log, no corroborating base | **PLAUSIBLE, not established** |

**Also imprecise:** *"UE's own minidumps from **two earlier launches** list `runtime.dll @0xFF760000`
**and** `@0x7FF8F0400000`"* — **one** dump (`61C55551`) lists both; `A55704B3` lists a single mapping
at `0x7FF90E000000`. That sentence is the one the identification leans on, so it should be exact.

---

## T5 — the retention retraction · **SPLIT**

### The struct decode — offsets **CONFIRMED**, and the record is 56 bytes, not 48

I re-derived the layout from the raw bytes without assuming crashpad's header. The string table
**self-validates the offsets**:

```
MetadataFileHeader : magic 'DAPC'  version 1  num_records 1  padding 0
record (56 B):
  uuid                       41cdafa3-ceff-4d83-8d11-69fa9b75b54a
  file_path_index      = 0     -> "41cdafa3-…-69fa9b75b54a.dmp\0"   (41 bytes)
  id_index             = 41    -> "041de361-5d80-49b3-898a-91c174799b3a\0"
  creation_time        = 1785870627   (14:10:27 local)
  last_upload_attempt  = 1785870629   (14:10:29 local, crash + 2 s)
  upload_attempts      = 1
  state                = 2
  upload_explicitly_requested = 1, padding[7]
16 + 56 + 41 + 37 = 150 = file size, exact.
```

`id_index = 41` is *precisely* the byte length of the first string. That single coincidence pins the
two index fields and therefore the whole offset layout. `settings.dat` likewise:
magic `sdPC`, version 1, **options `0x1` (uploads enabled)**, `last_upload_attempt = 1785870629`.
Every value the coordinator reports sits at the right offset. **CONFIRMED.**

### `state = 2 ⇒ Pending` · **UNVERIFIED — and at least as likely to mean `Completed`**

The *value* is 2; its *meaning* depends on crashpad's `ReportState` enum ordering, which is not cited
anywhere and which I could not source offline (no crashpad/sentry-native source on this machine;
`crashpad_handler.exe` exists at `Engine/Plugins/SentrySDK/Binaries/Win64/` but an enum is not a
string). The two orderings in circulation give opposite answers:

- `{kPending=0, kUploading=1, kCompleted=2}` ⇒ **state 2 = Completed = the upload SUCCEEDED**
- `{kNew=0, kPending=1, kUploading=2, kCompleted=3}` ⇒ state 2 = Uploading (contradicted by
  `upload_attempts` already being 1, which stock crashpad increments only after an attempt concludes)

**A near-miss worth recording so nobody re-runs it.** In stock crashpad a non-empty `id` is written
only by `RecordUploadComplete`, so `id_index → "041de361-…"` looked like proof of a successful upload.
It is not: **`041de361-5d80-49b3-898a-91c174799b3a` is the client-side `event_id`**, already present
in `__sentry-event` (`event_id` field, MessagePack) *before* any upload. Sentry-native pre-seeds it.
Neutral evidence.

⇒ The sentence *"one upload was attempted two seconds after the crash **and did not complete**"* is
**PLAUSIBLE-BUT-UNPROVEN**.

### "The ~3 minutes was an observation interval" · **CONFIRMED**

Reproduced independently from `Saved\Logs` line-1 stamps (local) + terminal-key counts:

```
02:07:09 -> died 02:10:53 (crashpad)  relaunch 02:12:15
02:12:15 -> died 02:17:15 (crashpad)  relaunch 02:19:58   <-- inside the S108 skeptic's 02:17:16..02:20:11 gap
02:19:58 -> died 02:22:30 (crashpad)  relaunch 13:55:47
13:55:47 -> died 14:01:07 (crashpad)  relaunch 14:02:15
14:02:15 -> died 14:10:26 (crashpad)  NO relaunch          <-- the report survived 65+ min
```

The S108 window does contain a relaunch. The "~3 minute retention window" figure is correctly
retracted. **CONFIRMED.**

### "The next launch clears it" · **PLAUSIBLE-BUT-UNPROVEN — a successful upload explains the four cleared reports equally well**

The four cleared reports were **never observed between their crash and the next launch**. The only
mid-window observation in the whole record is the S108 one at **02:17:16 — crash + 1 s**, i.e.
*before* the crash+2 s upload attempt. So the data cannot distinguish:

- (A) uploads fail → reports sit → a launch clears the database; or
- (B) uploads succeed → crashpad removes them → the relaunch correlation is incidental.

`s109-fk9-capture-durable.md` §6 states this honestly. §0 and §2 do not (*"The report is cleared by
the next game launch"*, *"there is no retention window"*), and `s109-denominator-audit.md` claim 22
adopts it as **MEASURED**. That adoption should be downgraded.

**★ One thing the artifact *does* settle, and the doc has backwards.** Whatever `state=2` means, this
report **was not deleted for 65+ minutes after its single upload attempt**. Therefore §5's residual-risk
sentence — *"If an upload ever **succeeds**, the report is deleted ~2 s after the crash. No pre-launch
sweep, no post-exit sweep, and no filesystem watcher can outrun that"* — is unsupported, and is
arguably refuted by this very dump under reading (B). It should be softened to *"deletion timing after
a successful upload is unknown; the one observed report survived 65 min after its attempt."*

### **Is the shipped fix safe even if the rule is wrong? YES — and this is the question that matters**

**MEASURED.** `configs/archive-crashdumps.ps1` contains **only `Copy-Item`** (lines 149, 167) — no
`Remove-Item`, no `Move-Item`, no `Clear-*`. `configs/launch-redirect.ps1` calls it twice: line **298**
(pre-launch) and line **410** (post-exit, `-Label postexit`). It never mutates a database it does not
own, and it warns loudly rather than reassuring when a death left no report.

Under **every** hypothesis — upload fails / upload succeeds / launch clears / something else clears —
the worst outcome is an empty archive plus that warning. What the retention rule actually changes is
the **expected yield**, not safety: if uploads sometimes succeed and reap, the post-exit sweep will
often come up empty and the §5 mitigation (hosts-redirect `o566896.ingest.sentry.io`) moves from
optional to necessary. **Ship it; the mechanism claim can stay open.**

---

## T6 — the denominator audit · arithmetic **CONFIRMED**, two diagnoses **REFUTED**

### Everything I recomputed from disk and the CSV agrees

| audit claim | my recount | ✓ |
|---|---|---|
| 88 crash dirs = 87 `UECC-*` + `_0000` | 88 / 87 / `_0000` | ✔ |
| 7 with 0-byte or absent `UEMinidump.dmp` | 7 (6 `UECC-*` + `_0000`) | ✔ |
| 81 non-empty dumps | 81 | ✔ |
| census = 87 rows = 86 `UECC-*` + `_0000`; `FED1F952` on disk but absent from the CSV | exact | ✔ |
| `88 − 1 − 2 = 85`; `85 − 6 = 79` | 85 / 79 | ✔ |
| 5/79 = 6.3 %, 4/79 = 5.1 %, 5/86 = 5.8 % | 6.33 / 5.06 / 5.81 % | ✔ |
| 13 rows empty `chain`; the `base=0x0` set is the **same set** | verified as sets, not counts | ✔ |
| 74 rows carry frames; 73 excluding `166396E2` | 74 / 73 | ✔ |
| "68 % of chained crashes are repeats" = 50/73 | 50 of 74 in repeated chains (67.6 %) | ✔ |
| only 7 of the 13 have 0-byte dumps; the other 6 are `154E12A5, 298DDD37, 61C55551, 8C3ECC71, A55704B3, B84A0661` | name-for-name | ✔ |
| Fisher one-sided p = 0.152 | `C(10,7)/C(12,7) = 120/792 = 0.1515`; the audit's `C(5,2)/C(12,2)=10/66` is the equivalent formulation | ✔ |
| §4 probe-dump table | `166396E2` mtime 08-03 22:49:20, `0x80000004`, secs 2550; `FED1F952` mtime 08-04 01:57:52, AV **writing** `0x2bd733eaee0`, secs 572 | ✔ |
| §5 ten-session window: 2 critical-error + 7 crashpad + 1 neither | reproduced from `Saved\Logs` line 1 + whole-file key counts | ✔ |
| 12 deaths / 1 clean exit (`Loki_2.log`, `LogExit: Exiting.` = 1) | ✔ | ✔ |
| census newest row 2026-08-03 (stale) | 2026-08-03 22:49:21 (`166396E2`) | ✔ |

No count anywhere in my chain came from a truncated read.

### **REFUTED — `base=0x0` is NOT a "`harvest.py` parse failure"**

`tools/crashtri/harvest.py:32-34`:

```python
frames = parse_pcallstack(tag(d, "PCallStack"))
game   = [f for f in frames if f[0].lower().startswith("supervive")]
base   = game[0][1] if game else 0
```

**`harvest.py` never opens a minidump.** It reads `CrashContext.runtime-xml` only. `base=0x0` is the
documented behaviour of a tool whose input — the symbolicated `<PCallStack>` — genuinely contains no
SUPERVIVE frames. Calling it a *parse failure* and tagging that **"MEASURED — this one is a fresh
instrument artifact"** is itself an instrument-artifact-shaped error: a true observation about a
column generalised into a false claim about the tool. **`s109-dump-forensics.md` §6b has the correct
version** (*"harvest.py derives base from SUPERVIVE frames in the XML, and there are none"*).
The remediation in §6.4(c) is still worth doing; only the diagnosis is wrong.

### **Self-contradictory — "85 crash dirs unclassifiable forever"**

The arithmetic (`2/87 = 2.3 %`, `87 − 2 = 85`) is right. The **label is wrong and contradicts the
audit's own §1.4**, which concludes: *"a `UECC-*` dir is positive proof that the death did NOT go
through crashpad."* All 85 have a `UECC-*` dir. They are therefore **classified — as non-crashpad
deaths.** §1.3's *"the crashpad channel is unmeasurable for them, **in either direction**"* is
directly falsified by §1.4.

What is genuinely unrecoverable is the **count of additional dir-less deaths** that occurred alongside
them — a missing-denominator problem, not an unclassifiable-numerator one. That distinction matters:
the first framing makes the historical corpus sound worthless; the correct one leaves it valid
"as far as it goes", which is what §1.4 actually establishes.

### **Wrong number — deaths total**

§2.2 and §2.4: *"TOTAL process deaths with surviving evidence **≥ 97**"* (87 + 7 + 3), *"genuine game
deaths ≥ 95"*. Claim register **#18: "All-time deaths ≥ 98"**. **97 is right**; 98 is an error in the
register.

### **PLAUSIBLE-BUT-UNPROVEN — `_0000` as "a crash of the crash reporter"**

Solid: `ProcessId=0`, `SecondsSinceStart=0`, empty `EngineVersion`/`ExecutableName`/`CommandLine`/
`BaseDir`, `CrashGUID=_0000`, 0-byte dump. Excluding it from **dump-content** denominators is right
regardless.

Against the characterisation: its 509-byte `Loki.log` is **not** "the CrashReportClient's own log" in
any recognisable sense — it is UE pre-`Log file open` pak/IoStore text mounting
`../../../Loki/Content/Paks/global.utoc`; `GameName = UE-Loki`; `ErrorMessage` faults at
`0x00007ff6823657d0`, inside the range where `SUPERVIVE-Win64-Shipping` loads; and its `PCallStack` is
a 2-frame thread-start pair whose `KERNEL32 0x00007ff8efd40000 + 17374` base is the **same kernel32
base as `61C55551`**. A more parsimonious reading is *"a crash context written with almost no state,
very early"*. Only the **death-count** exclusion (85 vs 86) rests on the contested claim.

---

## Cross-document contradictions

1. **`base=0x0` diagnosis** — audit §3.4 "a `harvest.py` **parse failure**" **vs** forensics §6b
   "`harvest.py` derives `base` from SUPERVIVE frames in the XML, and there are none".
   **Forensics is right** (source read).
2. **Zero-byte family dumps** — coordinator "all five are zero-byte" **vs** forensics "three of five".
   **Forensics is right** (disk verified).
3. **Deaths total** — audit §2.2/§2.4 "**≥ 97**" **vs** audit claim register #18 "**≥ 98**". 97.
4. **Classifiability of the 85** — audit §1.3 "unmeasurable in either direction" **vs** audit §1.4
   "a `UECC-*` dir proves the death was not a crashpad death".
5. **Status of the retention rule** — fk9 §6 "does not prove the launch-clears rule by direct
   experiment" **vs** fk9 §0/§2 flat assertion **vs** audit claim 22 "MEASURED (elsewhere), adopted
   here". Three different confidence levels for one claim.
6. **★ The retracted crashpad-key claim is still in the body of the document that retracts it.**
   `s109-dump-forensics.md` §7 opens with a correct RETRACTION, then twenty lines later still prints
   the grep table row `handing control over to crashpad | **0** | see below`, still prints the
   ⚠ paragraph *"`handing control over to crashpad` does NOT appear … `CLAUDE.md`'s note is
   **incomplete**"*, and §10 follow-up 3 still says *"The `handing control over to crashpad` tell is
   incomplete — add the … variant"*. **Verified ground truth:** the session log contains the key
   exactly **once**, at line 52508 of 52511, with two lines after it; `flushing session and queue
   before crashpad handler` also **once**; `=== Critical error: ===` **zero** times.
   `CLAUDE.md`'s tell needs no amendment; the *observation* that `flushing…` survives attachment
   truncation is right and worth keeping.
7. **`s109-dump-forensics.md` §7 timeline** labels `Sentry HandleBeforeCrash End` "(final line)".
   It is not: four Sentry lines follow it — including `handing control over to crashpad` at
   `19:10:26.679` — plus two `GameFeatureToggles` lines at `19:10:26.685`. In the same section that
   retracts a truncation error.
8. **"104 SUPERVIVE stack pointers" (GameThread)** is correct but undefined — it is the count
   *at/above the thread's dump-time `rsp`*. The whole captured stack holds 1546 (318 distinct).
   State the definition or the next reader will fail to reproduce it.

---

## The single most dangerous surviving claim

> **`s109-dump-forensics.md` §6b, tagged MEASURED: "five of the six members fired **before any map
> loaded**, on the ordinary launch path, **weeks before the tutorial route existed**."**

It is the sole evidential basis for "Family R is a process-lifetime hazard, not a tutorial signature",
which is in turn what tells the project to stop looking at this death — and:

- it is **MEASURED for 2 of 6** (`61C55551`, `A55704B3`, both with `Load map complete = 0`);
- for the other **3** there is **no log at all**, and their only timing datum, `SecondsSinceStart = 0`,
  is shown by the *same document's own two logged members* to be uninformative (they read 0 at 2.9 s);
- the "weeks before the tutorial route existed" half is **falsified** — `tutorial_launch.cpp` was
  added 2026-07-09, before two of the six.

The conclusion survives on the two measured instances. The sentence does not. Rewrite it before it is
quoted, because "5 of 6, weeks before" is exactly the kind of round, confident census this project
has been burned by, and the next reader will not re-open the crash dirs to check.

**Runner-up, and the one most likely to actually bite:** contradiction #6 — the retracted
`handing control over to crashpad` false negative still standing as MEASURED in §7's grep table and in
§10's follow-up list. Someone will "fix" a death-detector that is not broken.
