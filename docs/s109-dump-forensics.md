# S109 — forensics on the preserved Sentry/crashpad minidump `41cdafa3`

**Artifact:** `dumps/s109-sentry-20260804-1410/reports/41cdafa3-ceff-4d83-8d11-69fa9b75b54a.dmp`
(43,804,912 B) + its own `Loki.log` (7,409,557 B) + `__sentry-event` (3,041 B).
**Provenance (given, not re-derived):** the death of the `play-nostatictest` bisect arm from S108b —
the run `docs/s108b-ksmactor-bisect.md` §2 records as **unattributed**.
**Date of analysis:** 2026-08-04. Every claim below is tagged **MEASURED** or **INFERRED**.
Tools: `tools/crashtri/mdctx.py` (read-only) + four throwaway scripts driving its `MD` parser.
No cdb/WinDbg on this machine. The dump was opened `rb` only and is unmodified.

---

## 0. The verdict in four lines

1. **MEASURED — the frame chain contains ZERO SUPERVIVE frames.** The faulting thread's stack is a
   virgin thread-entry frame. In `harvest.py`'s `chain` column this crash's value is the **empty
   string**.
2. **MEASURED — the fault PC is `runtime.dll + 1`**, i.e. byte 1 of the DOS header of SUPERVIVE's
   manually-mapped, PEB-hidden 64.4 MB protection runtime, on a `PAGE_READONLY` page. DEP execute fault.
3. **MEASURED — this is not a new family.** It is the **6th** instance of a signature already sitting
   in the corpus (5 prior `UECC-*` crashes), which `harvest.py` is structurally blind to because it
   classifies by SUPERVIVE RVA chain and this family has none.
   ⚠ **CORRECTED (skeptic T4):** membership is **NOT** proven by the shared register/stack state.
   That state (`rax=rcx=rsi=r12–r15=0`, `rdi==rsp`, `[rsp]=KERNEL32+0x17374`, and even the identical
   non-zero `rbp`/`r11`) is **deterministic OS thread-start residue** — it is what *every* freshly
   created x64 thread looks like, so it shows only that all six are thread-start faults. The
   "seven independent equalities" were one fact counted seven times. What actually carries the family
   is **fault PC == `<image base> + 1` of `runtime.dll`**, plus UE's own ModuleList naming `runtime`
   in the walkable members. Grading: `41cdafa3` / `61C55551` / `A55704B3` **confirmed**;
   `62C094F1` / `63AD699C` strong; `064CE137` shape-only.
   ⚠ **CORRECTED (skeptic T3b):** "5 of the 6 fired before any map loaded, weeks before the tutorial
   route existed" is **measured for 2**, and the date half is **falsified** (`tutorial_launch.cpp`
   predates two of them). See the banner at §6b. The surviving claim: the family is **not
   tutorial-exclusive**, so co-occurrence with the tutorial is circumstantial.
4. **INFERRED (high confidence) — this death does NOT attribute the ~1–5 minute tutorial death.**
   It attributes the death of *this one run* to the protection runtime (`runtime.dll`) starting a
   thread at a deliberately-or-systematically bogus address. The game's own code is not on the stack.
5. **★ MEASURED (added §11) — there is a SECOND packer family, and together they are ~13 % of the
   corpus.** Walking the 6 chainless-but-parseable dumps confirmed family A directly (UE's own
   ModuleList *names* `runtime.dll` in `61C55551` and `A55704B3`, closing the PE-shape inference the
   skeptic flagged), and turned up a previously unrecorded family B: **6 crashes executing at
   `<64 KB-aligned base> + 0x205D` in memory that is not mapped at all.** Both are control transfer
   into a packer mapping with **zero** game frames. **A + B = 11 of 87 census rows (12.6 %), + the
   crashpad dump = 12 known, and all of it should be excluded from FK-7 analysis.**
   ⚠ And a third census artifact: `frame0mod` for these rows (`ntdll`, `mdnsNSP`) is **UE's
   nearest-module guess and is SPURIOUS** — `modof()` resolves them to no module at all.

---

## 1. Instrument check first

**MEASURED.** `mdctx.py` parses the dump. Streams present:
`[3, 4, 5, 6, 7, 12, 14, 15, 16, 24, 1129316353]` — ThreadList, ModuleList, MemoryList, Exception,
SystemInfo, HandleData, UnloadedModuleList, MiscInfo, **MemoryInfoList**, **ThreadNames**, and one
crashpad-private stream. 723 memory ranges, 40.90 MB. 221 modules. SUPERVIVE base `0x7FF6EAA10000`,
SizeOfImage `0xA9E1000`.

**Two offset traps found and corrected — do not trust the documented layouts here:**

| stream | documented | actual in this dump | how I caught it |
|---|---|---|---|
| 24 ThreadNames | `MINIDUMP_THREAD_NAME` = `{ULONG64 ThreadId; RVA64 Rva;}` = **16 B** | **12 B** (`u32 tid`, `u32 rva`) | stream size 1636; `4+16·136 = 2180` **overruns**, `4+12·136 = 1636` is exact, and the 12-B parse matches **136/136** tids against the ThreadList. **MEASURED.** |
| 3 ThreadList | — | `mdctx.py`'s offsets (Tid@0, Teb@16, Stack@24, Ctx@40) are correct | cross-validated: every thread's `rsp` from its context falls inside its own declared stack range |

The brief's warning about `tools/re/parse_minidump.py` having wrong thread offsets is separate and
was not used. **This is exactly the class of error that would have produced a confident wrong answer**
— a 16-byte ThreadNames walk reads past the stream into the module list and invents thread names.

**Blind spot of this dump, stated up front:**
**MEASURED — zero (0 / 43,489) pages of SUPERVIVE's own image are present in the dump.** Crashpad
captured thread stacks and some heap, not module images. Consequences:
- I **cannot** check whether any of our `.text` hooks (`ProcessInternal` at `base+0x13454A0` etc.)
  were resident at crash time. Probed 7 known offsets; all `(NOT IN DUMP)`.
- I **cannot** disassemble `KERNEL32+0x17374` to *prove* it is `BaseThreadInitThunk`; that
  identification rests on frame geometry (§3) plus an independent cross-dump control (§6).

---

## 2. The exception

**MEASURED**, from stream 6:

```
EXCEPTION code=0xC0000005 addr=0x7FFD3B400001 parms=[0x8, 0x7ffd3b400001] tid=6104
rax=0 rcx=0 rdx=0x7378BF7888CA3EAA rbx=0xF17175D21AD37204
rsp=0x15F813F9B8 rbp=0x537AC9E1 rsi=0 rdi=0x15F813F9B8
r8=0xAAD340C414200EA8 r9=0xF5422C22166F00F1 r10=0xF17175D21AD37204 r11=0x95654773B3BC
r12=r13=r14=r15=0    rip=0x00007FFD3B400001
```

`parms[0] == 8` ⇒ **execute** access violation (0=read, 1=write, 8=DEP/execute). `rip == fault addr`.

**MEASURED, independent corroboration inside the dump.** A textbook `EXCEPTION_RECORD` is laid out on
the faulting thread's own stack by the dispatcher, and it agrees field-for-field:

```
0x15F813F770: 0x00000000C0000005   ExceptionCode (+ flags 0)
0x15F813F778: 0                    ExceptionRecord (no nested)
0x15F813F780: 0x00007FFD3B400001   ExceptionAddress
0x15F813F788: 0x0000000000000002   NumberParameters
0x15F813F790: 0x0000000000000008   Information[0]  <- execute
0x15F813F798: 0x00007FFD3B400001   Information[1]
```

**MEASURED — region protection at the fault address** (stream 16, MemoryInfoList):

```
base=0x7FFD3B400000  size=0x7000  state=COMMIT  Type=IMAGE
prot=PAGE_READONLY   AllocationProtect=PAGE_EXECUTE_WRITECOPY  allocbase=0x7FFD3B400000
```

Not executable ⇒ the DEP reading is confirmed by a second stream, not just by `parms[0]`.
The **next** region up, `+0x7000 (0x1000 B)`, *is* `PAGE_EXECUTE_READ`. So the target missed the first
executable byte of the image by exactly `0x6FFF`.

---

## 3. The frame chain

**MEASURED.** Faulting thread `tid=6104`, stack region `0x15F813B000 .. 0x15F8140000` (20,480 B
captured), `rsp = 0x15F813F9B8` — **0x648 bytes below the top of the stack**. Raw dump from `rsp`:

```
+0x000  74 73 9a 3a fd 7f 00 00 00 00 00 00 00 00 00 00   -> 0x00007FFD3A9A7374
+0x010  00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
+0x020  00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
+0x030  91 cc 19 3b fd 7f 00 00 00 00 00 00 00 00 00 00   -> 0x00007FFD3B19CC91
+0x040 .. +0x087  all zero
+0x088  30 fb ff ff e8 04 00 00 30 fb ff ff d0 04 00 00   -> 0x000004E8FFFFFB30, 0x000004D0FFFFFB30
+0x098  19 00 00 00 00 00 00 00 ...                       -> 0x0000000000000019
+0x0A0 .. +0x647  all zero
```

⚠ **CORRECTED after adversarial review (S109 skeptic, T2).** The original text claimed
*"+0x040 .. +0x3FF all zero"* and *"exactly two non-zero qwords"*. **Both are wrong**, and the range
was asserted over bytes that were never printed. Re-measured over the **full** `rsp`→stack-top extent
(0x648 bytes, all present in the dump): there are **five** non-zero qwords, not two.

The conclusion is unchanged, and is in fact better stated by the corrected fact — **exactly two of
the five resolve inside any loaded module**, and they are precisely the thread-entry return pair:

| slot | value | resolves to |
|---|---|---|
| `[rsp+0x00]` | `0x00007FFD3A9A7374` | `KERNEL32.DLL+0x17374` (base `0x7FFD3A990000`) |
| `[rsp+0x08 .. +0x2F]` | 40 bytes, **all zero** | the `sub rsp,28h` shadow/home space |
| `[rsp+0x30]` | `0x00007FFD3B19CC91` | `ntdll.dll+0x4CC91` (base `0x7FFD3B150000`) |
| `[rsp+0x88]` | `0x000004E8FFFFFB30` | no module — non-pointer scratch |
| `[rsp+0x90]` | `0x000004D0FFFFFB30` | no module — non-pointer scratch |
| `[rsp+0x98]` | `0x0000000000000019` | no module — small integer |

The three extra values are not code addresses and cannot be return addresses, so the frame count and
every downstream conclusion stand. **Zero SUPERVIVE frames** remains exact.

**INFERRED (forced by the geometry).** That is the canonical x64 thread-start frame:
`ntdll!RtlUserThreadStart` → `call kernel32!BaseThreadInitThunk` (pushes 8 B) →
`BaseThreadInitThunk: sub rsp,28h` → `call <start routine>` (pushes 8 B). Entering the start routine,
the return address into kernel32 sits at `[rsp]`, the 0x28 of home space follows, and the return
address into ntdll sits at `[rsp+0x30]`. `8 + 0x28 = 0x30`, byte-exact.

⇒ **The thread had executed zero instructions of its start routine.** The fault is the *first
instruction fetch* at the start address. **The thread's start address was `0x7FFD3B400001`.**

### Chain in the corpus format (`harvest.py` `chain` column = SUPERVIVE RVAs)

```
chain = ""          (0 game frames)
```

### Chain in module terms (what a symbolicating debugger would print)

```
#0  runtime.dll + 0x1        <- fault PC, DEP execute on a PAGE_READONLY page
#1  KERNEL32.DLL + 0x17374   <- BaseThreadInitThunk
#2  ntdll.dll   + 0x4CC91    <- RtlUserThreadStart
```

**Blind spot / what I searched.** I walked every 8-byte-aligned qword from `rsp` to the top of the
thread's captured stack (`0x15F8140000`) and tested each against `[SUPERVIVE base, base+0xA9E1000)`.
Zero hits. I *also* walked the region **below** `rsp` down to the dump-time `rsp` (`0x15F813EE78`) —
that is exception-dispatch scratch written *after* the fault, and it does contain 6 SUPERVIVE
pointers (`7059d30 7059e0e 7059000 …`, plus one page address `1345000`). **Those are not call frames
and must not be entered into the census** — they are the crash-reporting path (§4), and building a
"chain" out of them would be exactly the instrument artifact this project keeps committing.

### Hypothesis explicitly TESTED AND REJECTED

The brief proposed: *a mis-computed VMProtect/Themida import trampoline (`real = C2 ^ ROL64(C1+M,0x33)`)
jumping to a bad target.* The high-entropy `rdx/r8/r9/r11` and `rbx == r10` do look like that.
**REJECTED (MEASURED).** An import-stub misjump faults *inside or from* the stub, leaving the real
call stack beneath it. Here the stack below the entry frame is empty and the frame above is the OS
thread-start pair. Nothing called this; the OS entered it. The garbage registers are simply whatever
`ntdll`'s thread-start path left in them — and §6 shows the *same* registers are zero/garbage in the
same pattern across three independent crashes, i.e. they are the thread-entry ABI state, not a
computation in flight.

---

## 4. Which thread faulted — and which threads exist

**MEASURED.** 136 threads. ThreadNames (12-byte entries, §1) resolves **73** names.

- **`tid = 6104` is UNNAMED** — it carries a ThreadNames entry with an empty string. It is not a UE
  thread. **It is NOT the GameThread.**
- **`GameThread = tid 29236`** — alive at dump time, parked in `ntdll+0x9DA74`, 104 SUPERVIVE stack
  pointers.
- `RenderThread 0 = 13684`, `RHIThread = 30764`, `FAsyncLoadingThread = 13964`, `IoDispatcher = 31632`,
  `sentry-http = 32736`, etc. — all alive.
- **MEASURED — five threads have `rip` inside the hidden protection image** (§5): tids **9996, 26768,
  35484, 40160, 40484**. `tid 6104` is a *sixth* association: its start address is in that image.
- `tid 26768` (runtime.dll `packer30`) carries **268 SUPERVIVE pointers / 129 distinct RVAs**
  (`0xB9E1F0 … 0xA0578B0`, `f7ec20` repeated 55×) — a protector thread walking game structures.
  *INFERRED, low confidence:* a scanner. Not pursued; the RVAs are mostly above the known `.text`
  range so it is likelier walking data than hashing code.

At dump time `tid 6104` itself sits at `ntdll+0x9DC94` with `rsp = 0x15F813EE78` — i.e. **below** the
exception `rsp`, inside the handler chain, waiting on crashpad.

**MEASURED — the exception was dispatched through the protector's own handlers.** Return addresses on
the post-fault scratch, in order: `runtime.dll+0x8FA376`, `+0x87CD3E`, `+0x8AEA87`, `+0x8D9040/82`
(all in section `packer1`), `+0x1295B65` (`packer30`), then `SUPERVIVE+0x7059D30 / +0x7059E0E`,
`KERNELBASE`, `ntdll`. **INFERRED:** that is the packer's vectored/unhandled exception filter — the
same filter `CLAUDE.md` documents as eating C++ exceptions — running before UE's.

**Blind spot:** thread-list *order* is not usable as creation order. `tid 6104` is at index 2 of 136
(right after `GameThread` and the runtime.dll thread `9996`), which naively reads as "created early".
That contradicts the forced conclusion of §3 (a thread cannot idle at its first instruction for 8
minutes), so crashpad's enumeration order is simply not creation order. **I state the ordering as a
non-discriminating observation, not evidence.**

---

## 5. What is at `0x7FFD3B400000` — identified

**MEASURED.** The fault target lies in a **hidden image**: `Type = MEM_IMAGE`, `AllocationBase =
0x7FFD3B400000`, committed span `0x4066000` (64.40 MB), **absent from the dump's 221-entry module
list**. It sits *above* `ntdll.dll` (the highest loaded module, ending `0x7FFD3B349000`) — which is
why `mdctx.py` printed no `fault PC = mod+off` line, and why UE's own symbolication mis-attributes it
to `ntdll` (§6).

Three hidden images exist in total (of 223 IMAGE allocations):

| allocbase | span | shape |
|---|---|---|
| `0x00000000FF760000` | `0x4066000` | 10 regions; `+0x7000` still `EXECUTE_WRITECOPY` |
| `0x00007FFD3B400000` | `0x4066000` | 15 regions; `+0x7000` realized to `EXECUTE_READ` ← **fault target** |
| `0x000001F71BED0000` | `0xA9E1000` | **one** `READONLY` region; size **== SUPERVIVE's SizeOfImage exactly** |

### Identification: `Loki/Binaries/Win64/runtime.dll`

**MEASURED** — on-disk `runtime.dll` is 67,511,496 B with `SizeOfImage = 0x4066000` and 11 sections.
Every section VA/size matches the observed region layout:

| section | file VA / VSize | observed region at `0x7FFD3B400000` |
|---|---|---|
| headers + `.pdata` | `0x1000 / 0x56E8` | `+0x0  0x7000  READONLY` |
| **`.rwx`** | `0x7000 / 0x1000` (XRW) | `+0x7000  0x1000  EXECUTE_READ` |
| `packer0` | `0x8000 / 0x7C7000` (R) | `+0x8000  0x7C7000  READONLY` |
| `packer1` | `0x7CF000 / 0x16F886` (XR) | `+0x7CF000  0x170000  EXECUTE_READ` |
| `packer2` | `0x93F000 / 0xC010` (RW) | `+0x93F000  …  RW/WRITECOPY` |
| `.rsrc` + `.reloc` | `0x94C000 / 0x92DA60` (R) | `+0x94C000  0x930000  READONLY` |
| `packer30` | `0x127C000 / 0x22D344` (XR) | `+0x127C000  0x22E000  EXECUTE_READ` |
| `packer40` | `0x14AA000 / 0x75330` (RW) | `+0x14AA000  0x76000  WRITECOPY` |
| `packer31` | `0x1520000 / 0x2A48628` (XR) | `+0x1520000  0x2A49000  EXECUTE_READ` |
| `packer42` | `0x3F69000 / 0xFC5DC` (RW) | `+0x3F69000  0xFD000  WRITECOPY` |

Also **MEASURED:** `runtime.dll` has **no export directory** (`export dir rva=0, size=0`) and
`AddressOfEntryPoint = 0x855440` (inside `packer1`). Its loader, `preloader.dll` (26,824 B), **is** in
the module list at `0x7FFD23200000`. This matches `docs/ignorance-map-s101.md` FK-10 exactly
(`packer0..packer42` + `.rwx`, no exports, self-identifies as `packer/3.3.1`).

**MEASURED, independent confirmation:** UE's own minidumps from two earlier launches list
`runtime.dll @0xFF760000 +0x4066000` **and** `runtime.dll @0x7FF8F0400000 +0x4066000` in their
`ModuleList` — the same two-mappings-of-`0x4066000` shape, named. (`ignorance-map-s101.md:929` already
recorded this pair; nothing here contradicts it.)

**MEASURED — none of the 2,384 pages of the fault image are in this dump.** I cannot read the bytes at
`0x7FFD3B400001` (they are `4D 5A …` on disk) or disassemble any protector code from this artifact.

### The third hidden image

**MEASURED:** `0x1F71BED0000`, `Type=IMAGE`, a *single* `PAGE_READONLY` region of `0xA9E1000` —
byte-identical in size to SUPERVIVE's own `SizeOfImage`. That is the shape of a
`SEC_IMAGE_NO_EXECUTE` / `LOAD_LIBRARY_AS_IMAGE_RESOURCE` mapping of the game's own executable.
**INFERRED (moderate confidence):** a pristine reference copy of the game image — what a code-integrity
comparator needs. **Alternative not excluded:** UE/CEF map the exe read-only for resources.
Zero pages of it are in the dump, so I cannot check its contents.

### Why the address is `base + 1`, and why that matters

**MEASURED:** the offset is exactly `+1`, and (§6) it is exactly `+1` in **all six** instances across
**four different ASLR bases**.

**INFERRED (high confidence):** the value is *derived from the image base*, not random. A misjump that
computed a garbage 64-bit target would not land on `base+1` six times. `HMODULE | 1` is the Windows
tag for a `LOAD_LIBRARY_AS_DATAFILE` handle (`|2` = `AS_IMAGE_RESOURCE`), so a tagged module handle
used where an `LPTHREAD_START_ROUTINE` was expected — or a resolved RVA of 1 — both produce this
exactly.

**What I cannot separate:** *deliberate anti-tamper self-kill* vs *a systematic defect in the
protector's own thread-spawn path*. Both predict an exact, reproducible `base+1`. See §8.

---

## 6. Cross-dump positive control — the signature is already in the corpus

The corpus already holds this crash. `harvest.py` cannot see it: it classifies by
`chain = SUPERVIVE RVAs`, and this family has none, so all five land in the
`(no game frames)` bucket alongside unrelated `mdnsNSP` noise.

**MEASURED — tight key** (`ErrorMessage` fault address ending `0001` **or** `<CallStack>` containing
`runtime`), over all 88 `CrashContext.runtime-xml` in `%LOCALAPPDATA%\SUPERVIVE\Saved\Crashes`:

| GUID | date | `secs` | fault address | UE `<CallStack>` | log span |
|---|---|---:|---|---|---|
| `064CE137…` | 2026-06-26 01:24 | 0 | `0x00007ffb9ee00001` | (blank) | (no log) |
| `63AD699C…` | 2026-07-08 22:05 | 0 | `0x00007ff8f0400001` | (blank) | (no log) |
| `62C094F1…` | 2026-07-09 02:00 | 0 | `0x00007ff8f0400001` | (blank) | (no log) |
| `61C55551…` | 2026-07-10 16:28 | 0 | `0x00007ff8f0400001` | **`runtime_7ff8f0400000 / kernel32 / ntdll`** | 2.9 s, frame 0 |
| `A55704B3…` | 2026-07-19 03:40 | 0 | `0x00007ff90e000001` | **`runtime / kernel32 / ntdll`** | 2.8 s, frame 0 |
| **`41cdafa3` (this dump)** | 2026-08-04 14:10 | **491** | `0x00007ffd3b400001` | (crashpad; no XML) | **491 s, frame 778** |

Their `<PCallStack>` is `ntdll 0x… + <off>0001   KERNEL32 0x… + 17374` — UE attributes frame 0 to
`ntdll` because ntdll is the nearest module *below* the hidden image, the same artifact `mdctx.py`
would have produced. Its symbolicated `<CallStack>` gets it right and **names `runtime`**.

**MEASURED — three-dump register/stack identity** (`mdctx.py` on this crashpad dump + the two UE
`UEMinidump.dmp` files; *different dumper, different launches, different ASLR bases*):

| | `41cdafa3` (crashpad) | `61C55551` (UE) | `A55704B3` (UE) |
|---|---|---|---|
| fault addr | `0x7FFD3B400001` | `0x7FF8F0400001` | `0x7FF90E000001` |
| = runtime.dll base + | **1** | **1** | **1** |
| `parms` | `[0x8, addr]` | `[0x8, addr]` | `[0x8, addr]` |
| `rax rcx rsi r12 r13 r14 r15` | all **0** | all **0** | all **0** |
| `rbx == r10` | **true** | **true** | **true** |
| `rdi == rsp` | **true** | **true** | **true** |
| `[rsp]` | `KERNEL32+0x17374` | `kernel32+0x17374` | `kernel32+0x17374` |
| `[rsp+8..0x2F]` | 40 B zero | 40 B zero | 40 B zero |
| `[rsp+0x30]` | `ntdll+0x4CC91` | `ntdll+0x4CC91` | `ntdll+0x4CC91` |
| SUPERVIVE frames | **0** | **0** | **0** |

Identical to the byte across three ASLR eras. This is as clean a family identification as the corpus
has, and it retroactively validates the §3 walk with an instrument I did not write.

**MEASURED, and it explains an instrument discrepancy:** UE's minidumps *list* `runtime.dll` in their
module list; crashpad's does not. **INFERRED (moderate):** `MiniDumpWriteDump` enumerates the PEB
loader list; the five UE-side deaths all occurred **~3 s into startup** (frame `[  0]`, log spans 2.8
and 2.9 s), before the protector unlinks itself; ours occurred at **T+491 s**, long after. Same image,
different visibility, because of *when* the process died — a clean instrument-artifact explanation for
"the module list disagrees".

**⚠ A loose key I tried and discarded, recorded so nobody repeats it:** grepping `<PCallStack>` for
`+ 17374` matches **85 of 88** crashes, because `BaseThreadInitThunk` is the bottom frame of nearly
every thread. It is not a discriminator. The discriminating key is *frame 0 ending in `0001` with no
SUPERVIVE frames*, or `<CallStack>` naming `runtime`.

---

## 6b. Membership test against the five prior crashes — and a premise that needs correcting

A mid-task lead from the main thread flagged these same five census rows (`frame0` ending `00001`,
`base=0x0`, empty `chain`) and asked whether our dump is a member or merely shares an address shape.
I had reached the same five independently (§6). Answering the three asks directly.

### Correction: two of the five DO have parsed minidumps

**MEASURED — the premise "these dirs contain a zero-byte `UEMinidump.dmp` … nobody ever had a dump to
walk" is true for three of the five, not all five:**

| GUID | `UEMinidump.dmp` |
|---|---:|
| `064CE137…` | **0 B** |
| `62C094F1…` | **0 B** |
| `63AD699C…` | **0 B** |
| **`61C55551…`** | **13,631,799 B** |
| **`A55704B3…`** | **13,264,110 B** |

The 7 zero-byte dumps on disk are `064CE137`, `62C094F1`, `63AD699C`, `83E3410A`, `858B6F07`,
`EBFECFE7`, `_0000` — only three of which are in this family; the other four are the unrelated
`mdnsNSP` group. Those two 13 MB dumps are what made §6's three-way register/stack control possible,
and they are why the family identification is not resting on a shared address shape at all.
So: **our dump is not the first member with memory attached — it is the third, and the only one that
is mid-run rather than at startup.** (The `base=0x0` census column is still explained as the lead
says: `harvest.py` derives `base` from SUPERVIVE frames in the XML, and there are none.)

### Ask 1 — `CrashContext.runtime-xml` field comparison (all MEASURED)

| field | all five prior | `41cdafa3` (this dump) |
|---|---|---|
| exception code | `EXCEPTION_ACCESS_VIOLATION` (`0xC0000005`) | `0xC0000005` |
| fault address | `…e00001` / `…400001` ×3 / `…000001` | `0x7FFD3B400001` |
| `parms[0]` execute flag | not in the XML; **`0x8` MEASURED in the two real minidumps** | `0x8` |
| `PCallStackHash` | `DA39A3EE5E6B4B0D3255BFEF95601890AFD80709` (**all five**) | n/a (crashpad, no XML) |
| `EngineVersion` | `5.4.3-0+UE5` (all five) | `5.4.3-0` |
| `BuildVersion` | `UE5-CL-0` (all five) | `release2.4.live-156430-shipping` |
| `BuildConfiguration` | `Shipping` | `Shipping` |
| `CrashType` / `IsEnsure` / `IsAssert` | `Crash` / `false` / `false` | `Crash` / `false` / `false` |
| `SecondsSinceStart` | **`0`** (all five) | **`491`** |
| `CrashingThreadId` | absent | `"0"` |
| SUPERVIVE frames | **0** (all five) | **0** |

`DA39A3EE5E6B4B0D3255BFEF95601890AFD80709` is **`sha1("")`** — UE hashed an empty call stack.
**Caveat, MEASURED:** that hash covers **12** of 88 crashes, not 5 — it also tags the `mdnsNSP` group.
It means "UE produced no symbolicated frames", so it is *necessary but not sufficient* as a Family-R key.

### Ask 1b — what the game was doing (MEASURED)

- **None of the five had loaded any map.** Both surviving `Loki.log`s contain **zero**
  `Load map complete` lines and end at frame `[  0]`: `61C55551` spans 2.9 s (`21:28:08.948 →
  21:28:11.814`, dying in `FPipelineCacheFile` / `FAssetRegistry` startup), `A55704B3` spans 2.8 s
  (`08:40:06.432 → 08:40:09.261`, dying in `LogD3D12RHI` feature probing).
- Dates span **2026-06-26 → 2026-07-19**, all *before* the tutorial route existed (S107/S108, August).
- Three of the five carry our `-ini:…localhost:8080` redirect command line; two read
  `CommandLineRemoved`.
- Ours: `LVL_Tutorial` fully loaded 341.7 s earlier, frame 778, mid-session.

### Ask 2 — member, or superficial address shape? **MEMBER. Established, not inferred from shape.**

The address shape is the *weakest* evidence available and I did not rely on it. What settles it:

1. **MEASURED — the module is named, twice, by an instrument I did not write.** UE's own minidumps for
   `61C55551` and `A55704B3` list `runtime.dll @0xFF760000 +0x4066000` and `runtime.dll
   @0x7FF8F0400000 +0x4066000` in their `ModuleList`, and `61C55551`'s symbolicated `<CallStack>`
   reads literally **`runtime_7ff8f0400000 / kernel32 / ntdll`**. In our dump the same image is
   identified independently by an exact 11-section PE match against `Loki/Binaries/Win64/runtime.dll`
   (§5). Same module, same `+1`.
2. **MEASURED — byte-identical machine state** across three dumps, two dumpers, four ASLR bases:
   `parms=[0x8,addr]`; `rax=rcx=rsi=r12=r13=r14=r15=0`; `rbx==r10`; `rdi==rsp`;
   `[rsp]=KERNEL32+0x17374`; `[rsp+8..0x2F]` = 40 zero bytes; `[rsp+0x30]=ntdll+0x4CC91`; zero
   SUPERVIVE frames (§6 table). Seven independent equalities is not a coincidence of shape.

### Ask 2b — why `0x7FF8F0400001` recurs three times

The lead is right that repeated exact addresses are not ASLR-randomised garbage — and that is
precisely the point. **MEASURED:** `0x7FF8F0400000` is `runtime.dll`'s *image base* in those launches
(UE's module list says so outright). It repeats because a **load address** repeats, not because a
computation repeats. `runtime.dll` is manually mapped by `preloader.dll`, so its base is chosen by the
packer's own mapper, not by the loader's ASLR draw; the `0xFF760000` twin repeats across launches too.
The `+1` is the invariant; the base is whatever that launch mapped.

**Therefore the obfuscated-import-trampoline alternative (`real = C2 ^ ROL64(C1+M,0x33)`) is REJECTED
for the whole family, on three independent grounds:**
- **Stack geometry** (§3): the faulting stack is a virgin OS thread-entry frame with the exact `0x30`
  `BaseThreadInitThunk` gap and nothing beneath. A trampoline misjump faults *from* a call site and
  leaves that call stack behind. All three walkable dumps show the same empty entry frame.
- **Arithmetic**: an XOR/ROL misfire lands on a uniformly random 64-bit value. Landing on
  `image_base + 1` — with `image_base` varying across launches — six times running is not a
  mis-computation; it is a value *derived from* the base.
- **Register state**: the "high-entropy" `rdx/r8/r9/r11` that motivated the trampoline reading are the
  *same shape* in all three dumps while `rax/rcx/rsi/r12–r15` are *uniformly zero* in all three. That
  is thread-entry ABI residue, not a computation in flight.

### Ask 3 — the family is NOT tutorial-route-exclusive, and this weakens the attribution further

> ## ⚠ CORRECTED after adversarial review (S109 skeptic, T3b). **This was the most over-claimed
> sentence in the document, and it is the one that tells the project to stop looking here.**
>
> The original read: *"MEASURED: five of the six members fired before any map loaded, on the ordinary
> launch path, weeks before the tutorial route existed."* Two halves of that are wrong:
>
> * **"five of six" is MEASURED for only TWO.** `61C55551` (2.87 s) and `A55704B3` (2.83 s) have logs
>   showing `Load map complete = 0`. The other three (`064CE137`, `62C094F1`, `63AD699C`) have **no
>   log at all** — their only datum is `SecondsSinceStart = 0`, which is **proven uninformative**:
>   both logged members *also* read 0 while actually being 2.9 s in.
> * **"weeks before the tutorial route existed" is FALSIFIED.** `tools/sigbypass-mod/tutorial_launch.cpp`
>   was added **2026-07-09** — *before* `61C55551` (07-10) and `A55704B3` (07-19). The date argument
>   runs the wrong way and must not be used.
>
> **The conclusion survives on the two measured instances; the sentence does not.** Supportable
> wording: *two independently-logged members of Family R fired ~2.9 s into startup with no map
> loaded, on runs that were not tutorial sittings — so the family is not tutorial-exclusive, and
> co-occurrence with the tutorial is circumstantial.* Everything below follows from that weaker
> claim; nothing downstream needed to change.

**MEASURED for 2 of 6, INFERRED for the rest (see banner):** two members fired **before any map
loaded**, on the ordinary launch path, on runs that were not tutorial sittings. Family R is
therefore **not a tutorial-route-exclusive signature**. Consequences:

- It **cannot** be read as "the tutorial route provokes this".
- It weakens, rather than supports, any claim that this death attributes the ~1–5 min tutorial death.
  §9's conclusion stands and is now better supported: the co-occurrence with the tutorial is
  circumstantial.
- It also weakens the deliberate-anti-tamper reading of §8 (5/6 fired ~3 s in, before any shim,
  before the force-open), and correspondingly strengthens the systematic-defect reading. §8's verdict
  — mechanism and actor established, motive not — is unchanged, but the balance shifts toward defect.
- **Our instance is the outlier**: the only mid-run member (T+491 s vs `SecondsSinceStart=0` ×5), and
  the only one with 40.9 MB of memory. Whether "mid-run" is a different trigger or the same hazard
  sampled later is **n=1 and undetermined**.

---

## 7. The run's own `Loki.log`

> ### ⚠ RETRACTION — and the source it came from
>
> **An earlier revision of this section claimed, tagged MEASURED, that `handing control over to
> crashpad` does NOT appear in this run's log, and used that to call `CLAUDE.md`'s "clean tell"
> incomplete. That claim is WRONG and is RETRACTED. `CLAUDE.md`'s tell is correct and needs no
> amendment.**
>
> **Cause (MEASURED, byte-exact, verified by me):** the bundled Sentry attachment is a **truncated
> prefix** of the session log.
>
> ```
> attachments/41cdafa3-…/Loki.log                    7,409,557 B   <- what the brief supplied
> C:\Users\eastr\AppData\Local\SUPERVIVE\Saved\Logs\Loki.log   7,412,142 B   <- the real session log
> delta                                                  2,585 B
> attachment is a byte-exact PREFIX of the session log:  True
> ```
>
> The missing 2,585 bytes are the terminal block, and they contain
> `[19.10.26:679][781]LogSentrySdk: handing control over to crashpad`. Grepping the attachment for
> that key returns 0 **by construction**. It was a false negative guaranteed by the instrument, and
> I recorded it as a property of the game — **the project's dominant error mode**
> (`memory/supervive-instrument-artifact-pattern`), committed in this document.
>
> Everything else extracted from the attachment remains valid (it is a byte-exact prefix); only the
> tail was missing. **All terminal-block analysis below is redone against the session log**
> (51,624 stamped lines; the attachment held 51,604 of them).
> **Rule for anyone reading this later: never mine a Sentry/crashpad attachment log for terminal
> behaviour. Use `Saved\Logs\Loki.log` while the session has not rotated.** The same defect was
> independently found in the bundled logs inside the `UECC-*` crash dirs.

**MEASURED** timeline:

| event | timestamp (UTC) | T+ (from first log stamp) |
|---|---|---|
| first stamped line | `19:02:15.420` | 0 |
| process create (MiscInfo `createtime`) | `19:02:13` | — |
| Sentry session start | `19:02:19.347` | — |
| `Load map complete /Game/Loki/Maps/LVL_Login` | `19:02:21.408` | 6.0 s |
| `Load map complete …/LVL_LobbyV2_Persistent` | `19:02:30.883` | 15.5 s |
| `LoadMap: …/Tutorial/LVL_Tutorial?game=BP_LokiGameMode_Tutorial_C` | `19:04:38.488` | 143.1 s |
| **`Load map complete /Game/Loki/Maps/Tutorial/LVL_Tutorial`** (6.42 s LoadMap) | `19:04:44.912` | **149.5 s** |
| last non-Sentry line (`Wallet balance: vp, 2004`) | `19:10:04.335` | 468.9 s |
| `LogSentrySdk: flushing session and queue before crashpad handler` | `19:10:26.573` | **491.2 s** |
| `Sentry HandleBeforeCrash End` (final line) | `19:10:26.579` | 491.2 s |

⇒ **MEASURED: the tutorial world lived 341.7 s (5 min 42 s) after `Load map complete`.**
Sentry: 487.332 s of process; UE crash context: `SecondsSinceStart = 491`. All consistent.

**MEASURED — greps and their exact keys:**

| key | hits (session log) | note |
|---|---:|---|
| **`handing control over to crashpad`** | **1** — `[19.10.26:679][781]` | present. Absent from the truncated attachment only. |
| `crashpad` (any case) | 4 | 2 at startup, plus `flushing session and queue before crashpad handler` and the hand-off |
| `Fatal` / `Assertion` / `Exception` / `AccessViolation` | **0 / 0 / 0 / 0** | no UE-side fatal, no assert |
| `anticheat` / `EasyAnti` / `BattlEye` / `Denuvo` / `VMProtect` / `Themida` / `integrity` | **0** each | |
| `[PL]` `[SP]` `[ANIM]` `[DIAG]` `[NULL]` `[SMA]` `[SMT]` `[FO]` `[GFT]` | **0** each | expected — the shims write `docs/*-marker.txt`, never `Loki.log`. Not evidence of absence. |
| `feature toggles were not ready` | **49,400** | see §7b |

**MEASURED — the terminal sequence, from the session log:**

```
[19.10.26:573][778] LogSentrySdk: flushing session and queue before crashpad handler
[19.10.26:573][778] LogSentrySdk: Verbose: invoking `on_crash` hook
[19.10.26:573][778] LogSentrySdk: Sentry HandleBeforeCrash Begin
[19.10.26:579][778] LogSentrySdk: Sentry HandleBeforeCrash End
[19.10.26:591][779] LogTemp: Error: …AttachAudioListenerToHero…            (×2)
[19.10.26:591][779] LogSentrySdk: Screenshot attachment is disabled in plugin settings.
[19.10.26:605][779] …FudgeMantlingSouth… ×2   [:612][779] …CursorCharacterAim… ×2
[19.10.26:635][779] …AttachAudioListenerToHero… ×2
[19.10.26:647][780] …FudgeMantlingSouth… ×2   [:654][780] …CursorCharacterAim… ×2
[19.10.26:673][780] …AttachAudioListenerToHero… ×2
[19.10.26:679][781] LogSentrySdk: Verbose: sending envelope
[19.10.26:679][781] LogSentrySdk: Verbose: serializing envelope into buffer
[19.10.26:679][781] LogSentrySdk: handing control over to crashpad
[19.10.26:685][781] LogTemp: Error: …FudgeMantlingSouth…                   (×2)  <- AFTER the hand-off
```

### ★ The terminal block independently corroborates §4: the GameThread was NOT the faulting thread

**MEASURED.** The frame counter advances **778 → 781** *during* the crash hand-off, and **two log
lines are emitted after `handing control over to crashpad`**. The game thread kept ticking for
~112 ms across ~3 frames while the crash handler ran on another thread.

**INFERRED (high confidence).** A fault *on* the GameThread freezes it inside the exception
dispatcher; it cannot advance frames or log. Continued frame advance during crash handling is only
possible if the faulting thread is a different one. That is an independent confirmation, from the log
alone, of the dump's finding that the faulting thread is the unnamed `tid 6104` and not `GameThread
= tid 29236` — reached by a wholly separate instrument.

**MEASURED — no degradation before death.** Non-spam lines in the last 5 minutes are ordinary:
level-streaming `AddToWorld`, navmesh `oversized dirty area` warnings, `RemoveUnreachableObjects`, and
a ~60 s `LogMessenger` heartbeat/reconnect cycle against our own backend. No error burst, no ramp. The
process was ticking normally at ~27 fps and then stopped existing (§7b).

**MEASURED — the shim was alive at death.** `docs/fk24-run-nostatictest1.txt` (this run's copied
marker, 32,662 B) ends mid-loop with `[DIAG] hero=(-8,-1855,468) … cam=(-8,-626,3228)` /
`[FOW] RegisterFogOfWarPrimitive(re-assert) ok`, with **no** `[NULL]` fault and no `[ANIM] FAULTED` —
consistent with S108b's finding that `KSTATICTEST=0` removes the self-inflicted AV. The staged marker
copies `docs/fk24-stage-nostat1-{1..4}*.txt` are timestamped 14:01–14:05 local, inside this run's
window, confirming artifact/run identity.

---

## 7b. The `ULokiGameFeatureToggles` error storm: **NOISE**, not a cause and not a symptom of dying

The coordinator asked this explicitly. Answer: **background noise, present at full intensity from the
moment the tutorial map loaded, 341.7 s before death, with no terminal escalation.** All MEASURED,
against the session log.

**Rate against wall clock and against frames** (windows anchored on `Load map complete`):

| window | lines | toggles | frames | toggles/s | **toggles/frame** |
|---|---:|---:|---:|---:|---:|
| `T_map +0 … +30 s` | 6,240 | 6,012 | 819 | 200.4 | **7.34** |
| `+30 … +60` | 4,721 | 4,710 | 785 | 157.0 | **6.00** |
| `+60 … +120` | 7,583 | 7,462 | 1,000 | 124.4 | **7.46** |
| `+120 … +180` | 9,213 | 9,200 | 1,000 | 153.3 | **9.20** |
| `+180 … +240` | 8,542 | 8,530 | 1,000 | 142.2 | **8.53** |
| `+240 … +300` | 8,122 | 8,106 | 1,000 | 135.1 | **8.11** |
| `+300 … +330` | 3,519 | 3,508 | 746 | 116.9 | **4.70** |
| **FINAL 10 s** | 1,580 | 1,572 | 263 | 142.9 | **5.98** |
| **FINAL 5 s** | 778 | 770 | 129 | 128.3 | **5.97** |
| **FINAL 1 s** | 162 | 154 | 27 | 77.0 | **5.70** |

The terminal rate (5.98/frame, 142.9/s) is **below** the run's own peak (9.20/frame at `+120…+180 s`)
and below the opening window (7.34/frame). **There is no ramp, no burst, and no terminal escalation.**

**Onset:** first occurrence at `T+148.5 s`, which is **1.0 s *before*** `Load map complete
/…/LVL_Tutorial` — i.e. it begins *during* the 6.42 s `LoadMap`, not at any later trigger. It then
accounts for **49,400 of 51,624 stamped lines (95.7 %) of the entire session log**.

**Composition is stable**, which rules out "a new failing subsystem joined at the end":

| window | keys |
|---|---|
| first 60 s | `AttachAudioListenerToHero` 30 %, `CursorCharacterAim` 30 %, `DeadSpectatorCameraLock` 20 %, `FudgeMantlingSouth` 20 %, `BigHead` ×2 |
| mid (150–210 s) | `FudgeMantlingSouth` 38 %, `AttachAudioListenerToHero` 38 %, `CursorCharacterAim` 24 % |
| **final 10 s** | `CursorCharacterAim` 33 %, `AttachAudioListenerToHero` 33 %, `FudgeMantlingSouth` 33 % — an exact 3-way split, each logged twice per frame |

**Frame rate was flat to the last frame** (distinct frame indices per 10 s window): 29.2, 30.0, 26.2,
27.6, 27.6, 27.3, 27.2, 27.0, 26.7, 26.6, **26.6** at `T_map+330`. No slowdown approaching death.

> ⚠ **An artifact in my own table, flagged rather than published.** The naive `T_map+340` bucket reads
> "47 frames / 10 s ≈ 4.7 fps" and looks like a terminal stall. It is not: the run ends at
> `T_map+341.7`, so that bucket holds only **1.7 s** — 47 frames in 1.7 s = **27.6 fps**, dead on the
> run average. A truncated final bucket is not a stall. (The one genuine hitch, 3.3 fps at
> `T_map+60`, is a level-streaming pause 280 s before death.)

**Verdict.** Not a cause: it is not an exception, the process survived 341.7 s of it at full rate, and
`ULokiGameFeatureToggles::Get` returning a default cannot spawn a thread at `runtime.dll+1`. Not a
symptom of dying: the terminal rate is *lower* than mid-run and the composition is unchanged. It is a
**pre-existing consequence of the force-open route** — the tutorial world is entered without the
normal flow that marks feature toggles ready — and it is loud (95.7 % of all log lines) but inert.
**Saying so is the finding**: it removes the most visually obvious feature of this log from the
candidate-cause list, and it means any future sitting can ignore the storm rather than chase it.

*Actionable side-effect, not a crash lead:* at ~6–9 formatted log lines per frame, the storm is a real
I/O tax and it inflates every log 20× (49,400 of 51,624 lines). If `gft_ready_fix` can be made to
actually satisfy this gate, future tutorial logs become readable and `FAsyncWriter_Loki` stops
churning.

---

**MEASURED — `__sentry-event`** (MessagePack, decoded with a hand-rolled reader): no stack trace, as
stated. Useful fields: `level=fatal`; `BuildVersion=release2.4.live-156430-shipping`; UE `5.4.3-0`;
sentry-native `0.7.6`; `Crash Type=Crash`, `IsAssert=false`, `IsEnsure=false`;
**`Crashing Thread Id: "0"`**; `Seconds Since Start: 491`; `Crash GUID:
UECC-Windows-EE05D2854EA1B732FA93E090DE045227`; breadcrumbs = the three `PostLoadMapWithWorld` events
only. **MEASURED:** no `UECC-Windows-EE05D285…` directory exists in `Saved\Crashes` — the GUID was
minted but the UE-side crash folder was never written (the crashpad path took over).
**INFERRED:** `Crashing Thread Id: 0` is UE failing to attribute a fault on a thread it never created
— consistent with §4.

---

## 8. Classification

### Against FK-7 Family A (worker-thread animation UAF)
`docs/fk7-crash-settled.md` §3: chain `3495973 3405f13 3691a72 3691704 367b462 f84697 …`, 194–201 s,
faulting on a freed animation object with a free-list link at `+0x00`.
**NOT THIS.** Our chain is empty; no worker thread faulted; no freed object is on the stack; the fault
is an *execute* fault, Family A is a *read*.

### Against FK-7 Family B (GameThread camera, one-byte overwrite at `ViewTarget.Target+0x420`)
`docs/fk7-crash-settled.md` §2: two sub-chains, `3c5dc52 3c5d255 3c34b22 3c596b3 …` and
`12c7e2d 3c2adb9 3c34b0c 3c596b3 …`, 173–194 s, on the **GameThread**.
**NOT THIS.** The GameThread (`tid 29236`) is alive and parked at dump time. Our faulting thread is
unnamed, has no game frames, and the fault is an execute fault, not a deref of a corrupted pointer.

### Against the S108 "new family"
`docs/s108-crash-triage.md`: chain
`f96a8e f9ce6a 3eeedd4 3ef3e65 39c76c6 37f8b8c 4028924 403005f 40300da 4030f6c 4039696 751ef62`
(tail = `FEngineLoop::Tick` / `EngineTick`).
**NOT THIS.** Twelve SUPERVIVE frames vs our zero, and an `FEngineLoop::Tick` spine vs our
`RtlUserThreadStart` spine. No overlap of any kind.

### Verdict: **(d) something else entirely — but not novel**

**It is `runtime.dll+1`, a pre-existing corpus family of 6 (§6) that the census cannot represent.**
Proposed name for the census: **Family R**. Suggested key for `harvest.py`:
*frame 0 with no module match and address `≡ 1 (mod 0x1000)`, zero SUPERVIVE frames* — or simply
`<CallStack>` containing `runtime`.

### Deliberate anti-tamper kill, or protector defect? — weighed

The brief asked this directly. **INFERRED, and I am deliberately not resolving it:**

*Supporting deliberate:*
- **MEASURED** — the offset is exactly `+1` across 6 crashes / 4 ASLR bases. Reproducible to the byte.
- **MEASURED** — the dying code is the protector; the game contributes nothing.
- **MEASURED** — the protector keeps a pristine read-only `SEC_IMAGE` mapping of the game's own exe
  (§5) and runs ≥5 dedicated threads.
- **Documented elsewhere** — `preloader.dll` ships `PACKER_CRASH_AT` and `Conflicting software
  detected!`, and `SUPERVIVE-Diagnoser.exe` names *"debuggers, injectors, cheats"*
  (`docs/ignorance-map-s101.md` C7). Spawning a thread at a non-executable address is a recognised
  deniable self-kill in this protector family.
- **MEASURED** — the death left no trace in `Loki.log` and UE could not attribute it
  (`Crashing Thread Id: 0`). Deniability is what a designed kill buys.

*Supporting defect, or at least not-yet-deliberate:*
- **MEASURED** — `487 s ≠ 285 s`. The project's documented code-integrity kill lands at ~285 s
  (`CLAUDE.md`); the catalog-check window is "~3–5 min". 8.2 minutes matches neither.
- **MEASURED** — I cannot show a `.text` patch was resident: **zero SUPERVIVE image pages are in the
  dump** (§1). There is no evidence of tamper in this artifact, only opportunity.
- **MEASURED** — 5 of the 6 instances fired at **~3 s into startup**, before the tutorial, before any
  probe, on the ordinary launch path. If this were the integrity kill responding to our shims, the
  startup cluster is unexplained. A single systematic defect (tagged `HMODULE` passed as a start
  routine) explains all six without invoking detection at all.
- **MEASURED, base rate is unknown** — n=1 for the mid-run variant, and the corpus contains **no
  clean, un-instrumented 8-minute run** to compare against. I cannot say `runtime.dll` does not do
  this on a stock launch.

**My call: the evidence establishes the mechanism and the actor, not the motive.** Confidence that
`runtime.dll` started the thread and that this killed the process: **high**. Confidence that it was a
*tamper response*: **low-to-moderate, and unsupported by anything in this artifact.** Recording it as
"the anti-tamper kill" would be precisely the instrument-artifact move
(`memory/supervive-instrument-artifact-pattern`): a true fact about one dump generalised into a claim
about a mechanism.

**The cheapest experiment that separates them**: one launch with `-NoHook`, no injection, left idle
for ≥10 minutes, watching for a `runtime.dll+1` death. If it fires, it is a defect and FK-7 work
should ignore it entirely. If 3–4 such runs stay clean while instrumented runs die this way, the
tamper reading gets its first real support. **Zero backend changes, zero code.**

> ## ★ RUN 1 PERFORMED — 2026-08-04 16:38, and it did NOT separate them
>
> `.\configs\launch-redirect.ps1 -NoHook` · no shims · `forceTutorialMatch = false` · idle at the
> menu. Predictions were registered **before** launching, so the result cannot be read backwards.
>
> **MEASURED — the run SURVIVED 33.8 minutes = 4.2× the reference death's 487.3 s**, and was still
> alive and healthy when observation stopped:
>
> | | value |
> |---|---|
> | maps loaded | `LVL_Login` → `LVL_LobbyV2_Persistent` (menu reached normally) |
> | threads | **120**, flat over the whole run (the crashed run's dump had ~136) |
> | working set | 977 MB at 17 min → **451 MB** at 34 min (falling; no leak) |
> | `handing control over to crashpad` | **0** |
> | `flushing session and queue` / `Critical error` / `Fatal` / `RequestExit` | **0 / 0 / 0 / 0** |
> | new crashpad report | **0** |
> | new `UECC-*` dir | **0** |
>
> **This is the WEAK outcome, exactly as pre-registered, and it does NOT support the tamper reading.**
> Three reasons, all of which must travel with the result:
> 1. **n = 1.** The plan called for 3–4 clean runs; one is not a base rate. Two family members fired
>    ~2.9 s into ordinary startups, so the hazard is *sporadic* — a single quiet window is expected
>    even under the defect hypothesis.
> 2. **CONFOUNDED.** "No shims" arrived bundled with "no tutorial". The activity gap is large:
>    **607 KB of log in 17 min here vs 7.4 MB in 8 min** for the crashed run. This process is doing
>    far less work. (Thread count is comparable, so it is not a trivial-process comparison — but it
>    is not a matched one either.)
> 3. **There may be NO shim-free family member to compare against.** `61C55551` (07-10) and
>    `A55704B3` (07-19) date from a period when the launcher injected by default, so the corpus may
>    contain zero confirmed un-instrumented instances. This run did not produce one.
>
> **What it DOES establish (MEASURED):** the `runtime.dll+1` death is **not certain per process
> lifetime**. A clean run can pass both the ~2.9 s startup window and the 487 s mid-run window
> without it. That kills "every process eventually hits this" and confirms the family is sporadic.
>
> *(Incidental: the only errors in the whole run are Vivox voice login failing with
> `Access Token Service Unavailable` — that backend is dead too. It is not fatal and is unrelated.)*
>
> ---
>
> ## ★★ RUNS 2–4 PERFORMED — the base rate exists now, and it is lopsided
>
> Driver: `scratchpad/idle-runs.ps1`, protocol held identical to run 1. Each run launched, held
> 900 s, then terminated with `Stop-Process -Force`. **MEASURED:**
>
> | run | outcome | uptime | log | crashpad key / flush / fatal / crit | reports before→after |
> |---|---|---:|---:|---|---|
> | 1 | SURVIVED (killed) | **2460 s** (41.0 min, 5.05×) | 885 KB | 0 / 0 / 0 / 0 | 1 → 0 *(the purge, §7 of the capture doc)* |
> | 2 | SURVIVED (killed) | 905 s (15.1 min, 1.86×) | 476 KB | 0 / 0 / 0 / 0 | 0 → 0 |
> | 3 | SURVIVED (killed) | 904 s (15.1 min, 1.86×) | 536 KB | 0 / 0 / 0 / 0 | 0 → 0 |
> | 4 | SURVIVED (killed) | 904 s (15.1 min, 1.86×) | 471 KB | 0 / 0 / 0 / 0 | 0 → 0 |
>
> **4 of 4 clean runs survived. 5,173 s = 86.2 min of clean process lifetime, ZERO deaths of any
> kind.** Control check: terminating by `TerminateProcess` raises no exception, and indeed **no run
> produced a crashpad report** — so killed runs did not contaminate the count.
>
> ### The contrast with the same day's instrumented runs
>
> Same machine, same build, same day (**MEASURED**, from `Log file open` + last-activity timestamps):
>
> | configuration | exposure | deaths |
> |---|---:|---:|
> | instrumented + force-open tutorial | 1,487 s (24.8 min) over 5 sessions | **5** |
> | clean `-NoHook`, menu-idle | 5,173 s (86.2 min) over 4 runs | **0** |
>
> Instrumented hazard ≈ 1 death per 297 s. Applied to 5,173 s that predicts **≈ 17 deaths**;
> we observed **0**. Poisson `P(0 | λ=17.4) ≈ 3 × 10⁻⁸`. The clean runs also each passed the **~2.9 s
> startup window** that killed two family members, four times over.
>
> ⇒ **INFERRED (now well-supported): the deaths are provoked by the instrumented / tutorial
> configuration, not by process lifetime.** "Every process eventually hits this" is dead. The
> forensics §8 lean toward *systematic protector defect* is **weakened**; the tamper-response reading
> gets its first real support.
>
> ### ⚠ What is STILL not established — the confound is unbroken
>
> **Which variable does it.** "No shims", "no tutorial" and "far less work" are perfectly confounded:
> every clean run sat at the menu. And note the death side is weaker than it looks — **only 1 of those
> 5 instrumented deaths is confirmed `runtime.dll+1`** (`41cdafa3`); the other 4 had their dumps
> purged by the next launch before FK-9 was fixed, so their causes are simply unknown. The honest
> statement is *"the instrumented tutorial configuration dies and the clean menu configuration does
> not"* — which is useful, and is not the same as attributing the family.
>
> ### The next experiment, and it is the discriminator
>
> **Default launch (full shim set) idled at the menu, 15 min × 3.** This separates shims from tutorial,
> which run 1–4 cannot. If those die → the shims provoke it. If they survive → it is the
> tutorial/world, and the shims are exonerated. Note that "tutorial without shims" is **not**
> constructible — the force-open *is* a shim — so this is the only available split. Same cost, ~50 min.

---

## 9. Attribution — the direct answer

**Does this death attribute the ~1–5 minute tutorial death? NO.**

- **MEASURED:** the faulting thread has **zero SUPERVIVE frames**. Nothing in the game — not the
  camera, not the animation path, not the shim, not `FEngineLoop::Tick` — is on the stack.
- **MEASURED:** the GameThread, RenderThread, RHIThread and the shim's `[DIAG]` loop were all healthy
  at the instant of death; frame rate was flat at ~27 fps to the last frame (§7b), and the GameThread
  **kept advancing frames 778→781 during the crash hand-off** — which by itself proves the fault was
  not on it (§7).
- **MEASURED:** the one loud feature of the log — 49,400 `ULokiGameFeatureToggles` errors, 95.7 % of
  all lines — is **noise**: it starts 1.0 s *before* the tutorial map completes, runs at 4.7–9.2 per
  frame for 341.7 s, and its terminal rate (5.98/frame) is *below* its mid-run peak (§7b).
- **MEASURED:** it is FK-7-adjacent only in wall-clock (341.7 s after map load, at/just past the top
  of the "1–5 min" band). Chain, thread, fault type and faulting module all differ from every named
  family.

**What it DOES attribute:**

1. **The `play-nostatictest` arm's death is now attributed** — closing the S108b §2 open item. It died
   because `runtime.dll` started a thread at `runtime.dll+1`. It did **not** die of FK-7, and its
   >301 s survival (actually 341.7 s post-map-load) was **not** cut short by a game bug. **S108b's
   "with n=1 per arm, survival time is dominated by something else" is now named: at least for this
   arm, the something else is the protector.**
2. **A previously-invisible corpus family is named** — 6 crashes, byte-identical signature,
   structurally unrepresentable in `crash_census.csv`.
3. **A live confounder for every future FK-7 sitting** — any run may be terminated by `runtime.dll+1`
   at an arbitrary time with no game frames and no UE crash folder. A sitting that dies must be
   *checked* against this signature before its death is spent as FK-7 evidence.

**Practical consequence for the next sitting:** the `play-nostatictest` / current-`play` arm has
**still never been observed to die of FK-7**. Its one recorded death is not a game crash. Whether the
`SpawnActorCls` `Scale3D.Z` fix works remains, as `memory/supervive-tutorial-crash-fk7` says,
**DO-NOT-CLOSE — zero live reproduce-then-repair runs exist.** This dump does not move that verdict
in either direction; it removes a data point that was quietly being counted as one.

---

## 10. Follow-ups worth the time (not done here)

1. **`harvest.py`: add a Family-R key.** It currently buckets these as `(no game frames)` next to
   unrelated `mdnsNSP` noise. Also: `crash_census.csv` is stale (newest row 2026-08-03) and, being
   `UECC-*`-only, is blind to every crashpad death — including this one.
2. **Do not feed the `f96a8e…` / camera / anim chains anything from this dump.** Its 6 SUPERVIVE
   pointers are post-fault handler scratch.
3. **Never mine a Sentry/crashpad *attachment* log for terminal behaviour** — it is a truncated
   prefix (2,585 B short here) and drops the crash-defining tail. The same defect affects the bundled
   logs in the `UECC-*` dirs. `CLAUDE.md`'s `handing control over to crashpad` tell is **correct**;
   an earlier revision of this document wrongly called it incomplete (retraction banner in §7).
4. **The 60-second `LogMessenger` heartbeat-timeout/reconnect cycle** (4× in this run) is a backend
   keepalive gap, unrelated to the crash, and cheap to fix.
5. **The `-NoHook` idle-run experiment** in §8 is the only thing that separates "deliberate" from
   "defect", and it is nearly free.

---

## 11. ★ The free lead, taken: the chainless bucket is TWO packer families, not junk

Follow-on from the denominator audit's corrected diagnosis (`base=0x0` means *no SUPERVIVE frame in
the callstack*, not a parse failure). The 13 chainless census rows were flagged as unexamined
candidates. **All 6 with walkable minidumps have now been walked.** Every claim here is MEASURED via
`tools/crashtri/mdctx.py`.

They are **not one phenomenon**. They split cleanly into two families plus two singletons:

### A. `<image base> + 1` — the `runtime.dll` family (5 in census, 6 with the crashpad dump)

`064CE137` · `61C55551` · `62C094F1` · `63AD699C` · `A55704B3` (+ `41cdafa3`, crashpad)

**Direct module attribution, which the crashpad dump could not give us:** in the two walkable
members the UE dump's ModuleList *names the module*, so `modof()` resolves the fault PC outright:

```
61C55551   pc=0x7FF8F0400001   parm0=0x8 (EXECUTE)   -> runtime.dll + 0x1
A55704B3   pc=0x7FF90E000001   parm0=0x8 (EXECUTE)   -> runtime.dll + 0x1
```

This closes the identification the skeptic flagged as resting on PE-shape inference: the family is
`runtime.dll+1`, named by the OS's own module list, at two different ASLR bases.

### B. `<64 KB-aligned base> + 0x205D` — a SECOND, previously unrecorded family (6)

`298DDD37` · `83E3410A` · `858B6F07` · `8C3ECC71` · `B84A0661` · `EBFECFE7`

```
298DDD37   pc=0x1C9C9A0205D   pc-0x205D = 0x1C9C9A00000   64 KB aligned   parm0=0x0
8C3ECC71   pc=0x1856CA8205D   pc-0x205D = 0x1856CA80000   64 KB aligned   parm0=0x0
B84A0661   pc=0x267E7A9205D   pc-0x205D = 0x267E7A90000   64 KB aligned   parm0=0x0
```

MEASURED in all three: `rip == fault address` (executing there), `modof()` = **NONE** for both the PC
and the computed base, and subtracting the constant `0x205D` lands on a **64 KB-aligned** address —
the granularity of a `VirtualAlloc`/section mapping. So this is `<hidden mapping> + 0x205D`, a fixed
offset into a variably-based private region.

**`parm0 = 0x0` (read), not `0x8`** — the distinction matters: family A executes on a page that is
mapped but **NX** (a DEP violation), family B fetches from an address that is **not mapped at all**.

### The two are siblings, and neither is a game bug

Both are **control transfer into a packer-managed mapping that cannot be executed**. Neither has a
single SUPERVIVE frame on the stack. Together:

**11 of 87 census rows = 12.6 % of the UECC corpus — plus the crashpad dump = 12 known.**

⇒ **That ~13 % should be excluded from FK-7 analysis entirely.** It is protector control flow, not
game code, and it was previously invisible because `harvest.py` classifies by SUPERVIVE RVA chain and
these have none.

### ⚠ A third instrument artifact in the census, found on the way

`frame0mod` is **UE's nearest-module guess, and for both families it is SPURIOUS.** MEASURED:
`modof()` resolves these fault addresses to **no loaded module at all**, yet the census confidently
labels family A `ntdll` (5 rows) and family B `mdnsNSP` (6 rows). `mdnsNSP` is Bonjour's Winsock
name-service provider and has nothing to do with any of this.

**Do not read `frame0mod` as an attribution for chainless rows.** Anyone grepping the census for
"crashes in ntdll" or "crashes in mdnsNSP" is reading a guess, and the census offers no marker
distinguishing a resolved module from a guessed one.

### Remaining singletons (not either family)

* `154E12A5` — `pc = 0x0`, `parm0 = 0x8`: an **execute at NULL**. Same *class* (bad control transfer)
  but not a packer mapping. This is the audit's "ANIM crash".
* `_0000` — `pc = 0x2C5D0641C47`, zero-byte dump, `frame0mod=Unknown`; unresolved, and its status as a
  game death is disputed (see the denominator audit §2).

---

## 12. ★★★ DISCRIMINATOR RESULT — the shims provoke it, and BOTH families reproduce at the menu

**2026-08-04 18:17–18:20.** Default launch (full shim set), `forceTutorialMatch = false`, idle at the
**menu** — no tutorial, no world. Protocol otherwise identical to the clean runs. Driver:
`scratchpad/shim-runs.ps1`.

### 3 of 3 died

| run | outcome | died at | shims confirmed active | crashpad key | dump |
|---|---|---:|---|---:|---|
| shim 1 | **DIED** | ~65 s | all 6 | 0 | **none** |
| shim 2 | **DIED** | **~23 s** | catalog-store-fix | 1 | `3e17e732` (5.4 MB) |
| shim 3 | **DIED** | ~37–41 s | 3 | 1 | `590cfd83` (43.7 MB) |

⚠ **Driver bug, corrected here:** run 2's summary line reads `uptime=0s`. `$elapsed` is not recomputed
on the death path out of the positive-control loop. Real figure from timestamps: process started
18:18:36, crashpad flush 18:18:59 ⇒ **~23 s**. Do not quote the 0.

**Positive control passed on every run** — shim markers (all 15 days stale beforehand) were rewritten
after each launch, so these are genuinely instrumented runs, not clean runs wearing a label.

### The contrast is now clean, and it is the whole answer

| configuration | tutorial? | shims? | exposure | deaths |
|---|---|---|---:|---:|
| clean `-NoHook`, menu-idle | no | **no** | 5,173 s (86.2 min), 4 runs | **0** |
| **shims, menu-idle** | **no** | **yes** | ~129 s, 3 runs | **3** |
| instrumented + force-open tutorial | yes | yes | 1,487 s (24.8 min), 5 sessions | 5 |

⇒ **MEASURED: the tutorial is NOT required. The shims are sufficient.** The confound that survived
runs 1–4 is broken: holding "menu-idle" fixed and toggling only the shims flips the outcome from
0/4 deaths to 3/3 deaths, and the shim runs die **an order of magnitude faster** (23–65 s vs 86 min
of clean survival). Every death is far short of the documented ~285 s integrity-check window.

### ★ Both families reproduced — on demand, at the menu

```
shim run 2  3e17e732:  rip = 0x7FFD3B400001   parm0=0x8 EXECUTE/DEP   NO module
                       chain = EMPTY (zero SUPERVIVE frames)
                       stack = KERNEL32+0x17374, ntdll+0x4CC91   <- thread-entry pair
            => FAMILY A, and note the address is BYTE-IDENTICAL to the reference
               tutorial death 41cdafa3. Different process, different session, same
               fault address — confirming the family is carried by a recurring LOAD
               ADDRESS (the packer's mapper is deterministic), not by a computation.

shim run 3  590cfd83:  rip = 0x1C835EC205D    parm0=0x0 READ (unmapped)  NO module
                       0x1C835EC205D - 0x205D = 0x1C835EC0000  (64 KB aligned)
            => FAMILY B — the family discovered offline in §11, now caught live.
```

**★ And run 3 is a first: a Family B death WITH SUPERVIVE frames on the stack —
`chain = 888cee8 8831758`.** Every one of the six corpus members of Family B is chainless. This is
the first specimen that carries game frames, i.e. the first one that can be tied to a call site.
Neither RVA appears in FK-7 Family A (`3495973 3405f13 3691a72…`), Family B (`3c5dc52…`/`12c7e2d…`)
or the S108 family — it is a new chain. **That is the next lead, and it is free.**

### What this does and does not say

* **DOES:** our instrumentation — injection and/or shim behaviour — provokes both packer families,
  reliably and within a minute, with no tutorial involved. FK-7 work must treat instrumented-run
  deaths as suspect by default.
* **DOES NOT** distinguish **the act of manual-mapping a DLL** from **what the shims then do**. Both
  are "our modifications", and the clean arm skipped both (`-NoHook` also skips `inject.exe`).
  Separating them needs a run that injects a **do-nothing** DLL. That is the next experiment, and it
  is cheap.
* **DOES NOT** let shim count be read as a dose: the "shims active" column is a lower bound sampled at
  death, so it rises with lifetime by construction. Run 1 lived longest *and* shows all six. Reading
  that as "more shims = slower death" would be backwards causality from a sampling artifact.
* ⚠ **Run 1 died with NO crashpad artifact and no handoff line** — a genuine "neither artifact" death,
  the class the denominator audit found and sized at 3. Its cause is unrecorded.

---

## 13. ★★★ NOOP-CANARY — manual-mapping is EXONERATED; it is shim BEHAVIOUR

**2026-08-04 18:52–19:37.** §12 proved our instrumentation provokes the packer deaths, but could not
say whether the culprit was **the act of manual-mapping a DLL** or **what the shims subsequently do**
— `-NoHook` skips both. This isolates the first.

`tools/sigbypass-mod/noop_canary.cpp` → `build/noop_canary.dll`: mapped by the **identical** mechanism
(`launch-redirect.ps1 -Hook`, i.e. `inject.exe watch-now`, manual map, same as every real shim), and
then does **nothing** — no hook, no `.text` patch, no thread, no native call, no page-protection
change. Its whole body is one appended marker line. Verified before use: valid x64 PE32+,
`IMAGE_FILE_DLL`, entry point `0x14E0`, **imports only `KERNEL32.dll`** (no CRT), and **zero** C++
exception machinery (`__CxxFrameHandler3` / `_CxxThrowException` / `__cxa_throw` / `_purecall` all
absent — scanned as raw bytes, see the trap below).

### 3 of 3 SURVIVED the full hold

| run | outcome | uptime | DLL mapped | crashpad key | reports |
|---|---|---:|---|---:|---|
| noop 1 | **SURVIVED** | 900 s | **yes, t+5 s** | 0 | 2 → 0 *(pre-launch sweep took both, then the launch purged)* |
| noop 2 | **SURVIVED** | 900 s | **yes, t+5 s** | 0 | 0 → 0 |
| noop 3 | **SURVIVED** | 900 s | **yes, t+5 s** | 0 | 0 → 0 |

**Positive control passed on all three** — `docs/noop-canary-marker.txt` grew by exactly one line per
run, three distinct pids at three distinct load addresses:

```
[NOOP] mapped 2026-08-04 18:52:20.457  pid=39196  self=0x1522DA90000  exe=0x7FF7E3CB0000
[NOOP] mapped 2026-08-04 19:07:32.588  pid=44636  self=0x1E074030000  exe=0x7FF7E3CB0000
[NOOP] mapped 2026-08-04 19:22:46.509  pid=44844  self=0x14FE5D90000  exe=0x7FF7E3CB0000
```

A run whose marker did not grow would have been scored **VOID**, not SURVIVED — because `-Hook`
injects one DLL and no secondaries, so a silent mapping failure degenerates into a *clean* run.

### The three-arm result

| arm | mapped DLL? | shim behaviour? | exposure | deaths |
|---|---|---|---:|---:|
| clean `-NoHook` | no | no | 5,173 s (86.2 min), 4 runs | **0** |
| **noop canary** | **YES** | **no** | **2,700 s (45.0 min), 3 runs** | **0** |
| full shim set | yes | **yes** | ~129 s, 3 runs | **3** |

⇒ **MEASURED: manual-mapping alone does NOT provoke the packer.** 45 minutes of a DLL resident in the
process, mapped by the exact injection path the project uses, zero deaths — while the same injection
path carrying real shims kills the process in 23–65 s. **The injection technique is exonerated; the
cause is what the shims DO.** Combined non-shim exposure is now **131.2 min / 0 deaths** against
**~129 s / 3 deaths** with shims.

### ★ The next bisect, and it is single-variable

The default set is `catalog_store_fix` (primary) + `mainmenu_refresh_pi8`, `catalog_pick_fix`,
`loadout_fix`, `missions_fix`, `battlepass_adopt_fix` (secondaries).

**`catalog_store_fix` is the prime suspect on two independent grounds:**
1. It is the **only** shim in the default set that **writes to the game's `.text`** — the
   self-restoring `jz`-NOP, plus an AssetManager scan and a CatalogEntry poke.
2. In §12's shim run 2 — the fastest death at **~23 s** — it was the **only** shim confirmed active.

**Test: `-Hook catalog_store_fix.dll` alone (no secondaries), menu-idle, 15 min × 3.** Same harness,
one variable. Dies → the `.text` patch or its scan is the mechanism, and that is a *fixable* bug
rather than a property of the game. Survives → the cause is in the PI-hooking secondaries, and the
next split is `mainmenu_refresh_pi8` vs the rest.

### ⚠ Instrument trap hit and corrected while building this

My first exception gate ran `strings -a build/noop_canary.dll | grep -qF __CxxFrameHandler3`.
**`strings` is not installed on this machine.** The pipeline produced nothing, `grep -q` failed, and
the gate printed **"absent (good)" for all four symbols without ever executing** — a missing tool
issuing a clean bill of health. Re-done as a raw byte scan in Python, which is tool-independent.
Caught before it mattered, but it is the same shape as S109-b/c and is now the fourth instance today.
**A gate that cannot fail is not a gate.**

---

## 14. ★★ `catalog_store_fix` ALONE is EXONERATED — the killer is in the SECONDARIES

**2026-08-04 19:43–20:29.** Single-variable bisect of §12's result. `-Hook` the launcher's own
`catalog_store_fix.dll` (`sha256 fe937ac3…` — **not** the `build/` copy, which is a different binary
at `c1e4a6e4…`), no secondaries, menu-idle, 900 s hold.

| run | outcome | uptime | shim active | crashpad key | reports |
|---|---|---:|---|---:|---|
| csf 1 | **SURVIVED** | 900 s | yes, t+5 s | 0 | 0 → 0 |
| csf 2 | **SURVIVED** | 900 s | yes, t+5 s | 0 | 0 → 0 |
| csf 3 | **SURVIVED** | 900 s | yes, t+5 s | 0 | 0 → 0 |

Positive control passed on all three: the marker's mtime advanced past each run's gate
(18:19:40 → 19:44:35 → 19:59:49 → 20:14:xx). Gated on **mtime, not line count**, because this shim's
marker opens `CREATE_ALWAYS` and truncates (FK-25).

### The four-arm picture

| arm | mapped DLL | writes game `.text` | PI hook | exposure | deaths |
|---|---|---|---|---:|---:|
| clean `-NoHook` | no | no | no | 86.2 min, 4 runs | **0** |
| noop canary | yes | no | no | 45.0 min, 3 runs | **0** |
| **`catalog_store_fix` alone** | yes | **YES** | no | **45.0 min, 3 runs** | **0** |
| full shim set | yes | yes | **YES ×3** | ~129 s, 3 runs | **3** |

⇒ **MEASURED: the prime suspect is wrong.** The self-restoring `jz`-NOP, the AssetManager scan and
the CatalogEntry poke run for 45 minutes across 3 launches without a single death. **Writing the
game's `.text` is not, by itself, what provokes the packer.** Non-lethal exposure is now
**176.2 min / 0 deaths** against **~129 s / 3 deaths** for the full set.

**This also retires the §12 inference it was built on.** Shim run 2 died at ~23 s with
`catalog_store_fix` the only shim *confirmed active*, which is what nominated it. That column was a
lower bound sampled at death — §12 said so explicitly — and the caveat is now vindicated: the
secondaries inject from a detached helper that waits for the primary to settle, so at 23 s one may
have been mapped and simply not yet have written its marker. **Do not read "shims confirmed active"
as "shims present."**

### ★ The next suspect was already flagged in this repo, unvalidated, for a month

The remaining variables are the five secondaries: `mainmenu_refresh_pi8`, `catalog_pick_fix`,
`loadout_fix`, `missions_fix`, `battlepass_adopt_fix`. **Three of them are `ProcessInternal`
hookers** — `pi8`, `loadout_fix`, `missions_fix` — and each writes a 5-byte `jmp` into `PI`'s
prologue, transiently, serialized through `Local\SuperviveMissionsPIHook`.

`CLAUDE.md:156` has carried this since **2026-07-10**, and it has never been discharged:

> **VALIDATION PENDING:** the default set now runs THREE PI-hookers in one launch (`pi8` +
> `loadout_fix` + `missions_fix`). Each pair has been validated live … **but the full triple has not
> yet had a confirmation launch.** The shared-mutex + transient-install design is N-way safe *by
> construction* and contention is low, but do one validation pass when the game is free. **If the
> triple ever misbehaves, `-NoMissions` / `-NoLoadout` isolate it.**

Every launch in §12 ran that unvalidated triple. "N-way safe by construction" is an argument, not a
measurement — and CLAUDE.md's own warning names the isolation flags to use.

### The next test, single-variable, using the documented flags

**`launch-redirect.ps1 -NoMissions -NoLoadout`, menu-idle, 15 min × 3.** That drops two of the three
PI-hookers, leaving `pi8` alone (plus `catalog_pick_fix` and `battlepass_adopt_fix`, neither of which
hooks PI).

* **survives** → PI-hooker **multiplicity** is implicated, the month-old warning is vindicated, and
  the fix is a scheduling/serialisation bug in our own code — the best possible outcome, because it
  is ours to fix.
* **dies** → a single PI hook, or `catalog_pick_fix` / `battlepass_adopt_fix`, is sufficient; split
  again from there.

⚠ Whatever the result, the FK-7 consequence from §12 stands and strengthens: **every tutorial sitting
in the record ran the full default set**, i.e. the unvalidated triple. Tutorial deaths attributed to
the game may be this.

---

## 15. ★★ DOSE-RESPONSE across shim load — ⚠ SEE THE CORRECTION BANNER: it is NOT the PI hook

**2026-08-04 20:33–21:19.** `launch-redirect.ps1 -NoMissions -NoLoadout` —
the isolation flags `CLAUDE.md:156` itself names. Resulting set:
`catalog_store_fix` + `pi8` + `catalog_pick_fix` + `battlepass_adopt_fix` = **one** PI hooker
instead of three. Menu-idle, 900 s hold, 3 runs.

**Result: NOT a clean survival — 2 survived, 1 DIED at 55 s.**

| run | outcome | uptime | active (all 4 expected) | **forbidden active** | dump |
|---|---|---:|---|---|---|
| pi1 1 | SURVIVED | 906 s | 4 @ t+41 s | **none (good)** | — |
| pi1 2 | SURVIVED | 901 s | 4 @ t+5 s | **none (good)** | — |
| pi1 3 | **DIED** | **55 s** | 4 @ t+5 s | **none (good)** | `673de738` (43.4 MB) |

**Both halves of the two-sided control passed on every run:** all four included shims activated, and
`loadout_fix` / `missions_fix` **never** activated — so the exclusion flags genuinely worked and these
runs are the configuration intended. A survival with a silently-ignored flag would have sent this
bisect down the wrong branch.

### The dose-response

| arm | PI hookers | runs | exposure | deaths | 1 death per |
|---|---:|---:|---:|---:|---:|
| clean `-NoHook` | 0 | 4 | 5,173 s | 0 | — |
| noop canary (inert) | 0 | 3 | 2,700 s | 0 | — |
| `catalog_store_fix` alone | 0 | 3 | 2,700 s | 0 | — |
| **`-NoMissions -NoLoadout`** | **1** | 3 | **1,862 s** | **1** | **1,862 s** |
| **full default set** | **3** | 3 | **129 s** | **3** | **43 s** |

**Pooled PI=0: 10,573 s (2.94 h) with ZERO deaths.**

* If the PI=1 hazard held in the PI=0 arms, expected **5.68** deaths; observed **0**.
  `P(0 | λ=5.68) = 0.0034`.
* If the PI=1 hazard held in the PI=3 arm, expected **0.069** deaths; observed **3**.
  `P(≥3 | λ=0.069) = 5.3 × 10⁻⁵`.

⇒ **MEASURED: introducing a `ProcessInternal` hooker introduces lethality (p ≈ 0.003), and going from
one to three multiplies the hazard ~43×** (1 per 1,862 s → 1 per 43 s), p ≈ 5×10⁻⁵. Monotone across
0 → 1 → 3. `CLAUDE.md:156`'s month-old "the full triple has never had a confirmation launch" is
**vindicated, and understated** — the triple is not merely unvalidated, it is ~43× worse than one.

**But the correct reading is a RATE, not a switch.** One PI hooker is *not* safe; it is *slow*. Two of
three runs surviving 15 minutes is exactly what a 1-per-1,862 s hazard looks like. **Anyone who ran
`-NoMissions -NoLoadout` twice and called it clean would have been wrong** — which is precisely why
this arm needed n≥3.

### The dump: Family A, and the SAME address a third time

```
673de738   rip = 0x7FFD3B400001   parm0=0x8 EXECUTE/DEP   no module   chain EMPTY
           stack = KERNEL32+0x17374, ntdll+0x4CC91
```

`0x7FFD3B400001` is now the fault address in **three independent deaths** — the reference tutorial
death `41cdafa3`, shim run 2 `3e17e732`, and this. Three processes, three sessions, one address.
That is the recurring **load address** of `runtime.dll`, confirming §12's reading yet again.

### ⚠ What is still confounded — stated because it changes the next test

The PI=1 arm added **three** shims to the `catalog_store_fix` baseline, not one: `pi8`,
`catalog_pick_fix` and `battlepass_adopt_fix`. `pi8` is the only PI hooker among them and is the
prime suspect on mechanism, **but it is not isolated.** The lethality could belong to
`catalog_pick_fix` or `battlepass_adopt_fix`.

**Next test: `-Hook mainmenu_refresh_pi8.dll` alone, menu-idle.** ⚠ Power matters here — at
1 per 1,862 s, three 15-minute runs expect only ~1.5 deaths, so **3 runs cannot distinguish "lethal"
from "safe"**. This arm needs **≥6 runs** (or longer holds) to be worth running at all. Budget ~1.5 h.
Scoring it on 3 runs would repeat the error this section just documented.

---

## 16. ⚠⚠ CORRECTION TO §15 — "PI hookers 0/1/3" counted SHIMS, not INSTALLED HOOKS

Found 2026-08-04 21:05, while designing the `pi8`-alone arm — i.e. **the next experiment caught the
error in the last one.** §15's arithmetic is right and its headline is wrong.

**MEASURED, from the shim sources.** Whether a PI-hooking shim actually writes the 5-byte `jmp` into
`ProcessInternal`'s prologue *while idle at the menu* differs per shim:

| shim | installs the PI hook at menu-idle? | evidence |
|---|---|---|
| `mainmenu_refresh_pi8` | **NO** | `InstallHook()` is reached only via the pick/`desired` path. Its own marker says `[3] hook built. Open HUNTERS + click a hunter.` No click ⇒ no install. |
| `loadout_fix` | **YES** | `Sleep(4000); HookLock(); if(!InstallHook()){… "[3] FAIL InstallHook" …}` — unconditional init step. |
| `missions_fix` | **YES** | `ApplyOnce()` → `HookLock(); if(!InstallHook())…`, the fetch-driven rebuild/swap. |

Re-labelling §15's arms by **hooks actually installed**, not shims present:

| arm | shims called "PI hookers" | **PI hooks actually installed** | exposure | deaths |
|---|---:|---:|---:|---:|
| clean / noop / `csf` alone | 0 | **0** | 10,573 s | 0 |
| `-NoMissions -NoLoadout` | 1 (`pi8`) | **0** — `pi8` never arms without a click | 1,862 s | **1** |
| full default set | 3 | **2** (`loadout_fix` + `missions_fix`; `pi8` idle) | 129 s | 3 |

### What this changes

**RETRACTED: "the `ProcessInternal` hook is the mechanism."** The `-NoMissions -NoLoadout` arm
installed **zero** PI hooks and still killed the process at 55 s. An installed PI hook is therefore
**not necessary** for a death, and §15's title claimed otherwise.

**What SURVIVES, unchanged:** the numbers, the monotone dose-response, and both p-values. Adding shim
load to `catalog_store_fix` introduces lethality (`p ≈ 0.0034`) and more of it is ~43× worse
(`p ≈ 5×10⁻⁵`). The **dose is shim activity** — worker threads, symbol resolution, polling,
thread-suspending writes — **not specifically PI-prologue patching.**

**And the `.text` story gets sharper, not weaker.** §14 already showed `catalog_store_fix`'s
self-restoring `jz`-NOP is harmless over 45 min. Now the deadliest arm is the one where two shims
*additionally* patch PI's prologue — but the 1-death arm patched no game code at all beyond
`catalog_store_fix`'s. **Writing game `.text` is neither necessary nor sufficient.**

### The error, named

I labelled the arms by **shim identity** and then read that label as a **mechanism**. The label was
accurate ("`pi8` is a PI-hooking shim") and the inference from it was false ("therefore a PI hook was
installed"). That is the project's signature failure mode in its purest form — same shape as
`base=0x0` earlier today, and the fifth instance in this session. Filed to
`memory/supervive-instrument-artifact-pattern`.

**Method note that would have caught it immediately:** none of these arms ever measured whether a
hook was installed — only which DLL was loaded. The `pi8`-alone driver now greps its marker for
`[armed]` and reports `armedPIhook=N`, so the claim is measured rather than assumed. **A variable you
have not instrumented is not a variable you have controlled.**

### Consequence for the running experiment

The `pi8`-alone arm (6 runs, launched 21:10) is still the correct next isolation — it splits `pi8`
from `catalog_pick_fix` and `battlepass_adopt_fix` — but it is **not** a test of the PI hook, and must
not be written up as one. At menu-idle `pi8` will load, resolve, poll, and never arm. Expect
`armedPIhook=0` on every run; if any run reports otherwise, something triggered a pick and that run
needs separate treatment.

---

## 17. `mainmenu_refresh_pi8` alone — 6 runs, 0 deaths, and §16's prediction MEASURED

**2026-08-04 21:10–22:41.** `-Hook mainmenu_refresh_pi8.dll` (`sha 35e43f8d…`, the injector's copy,
not `build/`'s `396e669a…`), no secondaries, menu-idle, 900 s hold, **6 runs** — sized so the arm has
power against the 1-per-1,862 s hazard rather than repeating §15's under-powered mistake.

**Result: 6 of 6 SURVIVED.** Zero deaths, zero crashpad reports, launch stamps exactly 15:15 apart
(21:10:13 → 22:26:28), confirming every run held the full 900 s.

### ★ §16's prediction was measured, not assumed

The driver greps the marker for `[armed]`. Every run:

```
run 1..6   armedPIhook = 0     [3] hook built = 1     (75-83 marker lines each)
```

`pi8` loaded, resolved 4 subjects and 3 handler fns, **built** its hook — and **never armed it**,
exactly as §16 predicted from the source (`[3] hook built. Open HUNTERS + click a hunter.`).
**This arm therefore contains ZERO installed PI hooks over 90 minutes**, and it is the first arm in
the series where that was *measured* rather than inferred from which DLL was loaded.

### Where the numbers stand

| arm | exposure | deaths | 1 death per |
|---|---:|---:|---:|
| clean `-NoHook` | 5,173 s | 0 | — |
| noop canary (inert) | 2,700 s | 0 | — |
| `catalog_store_fix` alone | 2,700 s | 0 | — |
| **`mainmenu_refresh_pi8` alone** | **5,400 s** | **0** | — |
| `csf`+`pi8`+`pick`+`battlepass` | 1,862 s | 1 | 1,862 s |
| **full default set** | 129 s | 3 | **43 s** |

**Pooled zero-death exposure: 15,973 s = 4.44 hours.**

⚠ **Stated honestly: this does NOT reach significance.** If the 1-death arm's hazard held here,
expected 2.90 deaths, observed 0 → `P(0 | λ=2.90) = 0.055`. Suggestive, just short of 0.05.
**`pi8` is not exonerated, it is un-implicated.** Saying more than that would be the §15 error again.

### What is now cornered

`catalog_store_fix` alone: clean. `pi8` alone: clean. Yet `csf` + `pi8` + `catalog_pick_fix` +
`battlepass_adopt_fix` killed once in 31 minutes. ⇒ **the lethality in that arm belongs to
`catalog_pick_fix`, `battlepass_adopt_fix`, or an interaction** — none of which has been tested alone.

### ★ The next experiment should run at the HIGH-hazard end, not this one

Bisecting further down here costs ~1–2 h per arm for a marginal p-value. The full set dies at
**1 per 43 s** — ~43× faster — so **subtract one shim at a time from the FULL set** and each arm
resolves in minutes:

| arm | drops | leaves | expected |
|---|---|---|---|
| `-NoLoadout` | `loadout_fix` (installs a PI hook) | `missions_fix` still hooks | fast death ⇒ `loadout_fix` not required |
| `-NoMissions` | `missions_fix` (installs a PI hook) | `loadout_fix` still hooks | fast death ⇒ `missions_fix` not required |
| `-NoPasses` | `battlepass_adopt_fix` | both PI hookers remain | fast death ⇒ battlepass not required |

Each arm: 15-minute cap, but a positive result should land in **under a minute**, so 3 runs ≈ 5–10 min
rather than 45. **Subtractive-at-high-hazard is strictly more informative per minute than
additive-at-low-hazard**, and it directly tests the two shims that *actually install PI hooks* —
which, per §16, no arm has yet isolated.

### ⚠ Driver defect in this run, and what it cost

The per-run summary lines are **absent** from `pi8-runs-summary.txt`: I patched the format string to
add `armedPIhook={12}` while supplying only 11 arguments, so every `-f` threw
`Error formatting a string: Index … must be … less than the size of the args array` (18 occurrences).
**No data was lost** — outcomes were recovered from the console markers, the launch-interval spacing
and the copied per-run markers, all of which agree. But the summary file for this arm is empty and
should not be read as "no runs happened". Fix before reuse: `{12}` → `{10}`.

---

## 18. ★★★ SUBTRACTIVE SWEEP — and the real discriminator is the INJECTION WINDOW, not the shim

**2026-08-04 22:56–23:17.** Full default set minus exactly one shim, 300 s hold × 3 per arm. Chosen
because the full set dies at 1-per-43 s, so an arm that keeps the fast kill shows it in minutes.

| arm | drops | outcomes | exposure | deaths | 1 per |
|---|---|---|---:|---:|---:|
| `-NoLoadout` | `loadout_fix` | S / **D@20 s** / S | 628 s | 1 | 628 s |
| **`-NoMissions`** | `missions_fix` | **D@35 s / D@25 s / D@30 s** | **90 s** | **3** | **30 s** |
| `-NoPasses` | `battlepass_adopt_fix` | S / **D@51 s** / S | 655 s | 1 | 655 s |
| *(full set, ref)* | — | D/D/D | 129 s | 3 | 43 s |

The dropped shim's marker **never advanced in any of the 9 runs**, so every exclusion took.

**MEASURED: dropping `missions_fix` does NOT reduce lethality** — 3/3 at 25–35 s, if anything faster
than the full set. **Dropping `loadout_fix` or `battlepass_adopt_fix` cuts the hazard ~21×**
(1-per-30 s → 1-per-628/655 s). Rate-ratio test, exposure-adjusted:
`P(≥3 of 5 events landing in NoMissions | exposure share 0.066) = 0.0025`.

### ★ The observation that reframes the whole series

`docs/inject-secondaries.log` gives the injection timeline — **MEASURED**:

```
T+0 s    game process up
T+20 s   "primary catalog_store_fix installed+unhooked - safe to inject secondaries"
T+20 s   inject pi8 → T+24 s pick → T+27 s loadout → T+30 s missions → T+33 s COMPLETE
```

Now every death ever recorded in this series, by uptime:

```
20 s  23 s  25 s  30 s  35 s  41 s  51 s  55 s  65 s
```

**Not one death has ever occurred before T+20 s — the exact moment secondary injection begins.**
The earliest death (20 s) lands on the first injection; the cluster 20–35 s sits inside the 13-second
window in which four DLLs are manual-mapped back to back.

And the complementary half:

| arms that never run the detached secondary sequence | exposure | deaths |
|---|---:|---:|
| clean `-NoHook`, noop canary, `csf` alone, `pi8` alone | **15,973 s = 4.44 h** | **0** |

⇒ **Every death in the series happened at or after the secondary-injection window, and no arm that
skips that sequence has ever died** — across four and a half hours. That is a sharper discriminator
than any single shim's identity, and it also explains why the `active=[csf]` column reads bare on the
fastest deaths: **those runs died *during* injection, before the secondaries could write markers.**

⚠ **Consequence for how these arms must be read: this is intention-to-treat.** We know which *flag*
was passed; for deaths at 20–35 s we cannot confirm which secondaries had finished mapping. The arm
comparison stays valid (same harness, flag is the only difference), but "shim X was present at death"
is **not** established for the fast deaths.

### The dumps: both families, and Family A a fourth time

```
sub-NoMissions-1  e7d14df5   pc=0x14BA020205D   parm0=0x0  -> FAMILY B
sub-NoMissions-2  5e4cce11   pc=0x1830F7C205D   parm0=0x0  -> FAMILY B
sub-NoMissions-3  d9a2e984   pc=0x7FFD3B400001  parm0=0x8  -> FAMILY A
sub-NoPasses-2    2b109408   pc=0x2154F6C205D   parm0=0x0  -> FAMILY B
```

3 of 4 are Family B. `0x7FFD3B400001` is now the fault address in a **fourth** independent death.
Both families are produced by the same trigger, which argues they are two faces of one protector
response rather than two unrelated bugs.

### Why "which shim" may be the wrong question

`-NoPasses` keeps **both** PI hookers (`loadout` + `missions`) and is ~21× *safer* than `-NoMissions`,
which keeps only one. That does not fit any story where a particular shim's behaviour is the cause,
and it is the third result pointing the same way (§16, §17). Combined with the timing, the better
model is: **hazard is driven by the burst of manual-maps and the concurrent activity it kicks off,
and shim identity mostly changes how much activity lands inside that window.**

### Next, in priority order

1. **Space the injections out.** Same five shims, but inject with e.g. 60 s gaps instead of 3 s.
   If deaths vanish, the cause is *burst rate*, and the fix is a one-line change to
   `inject-secondaries.ps1` — no shim rewrite. **Cheapest and highest-value test remaining.**
2. **Inject two inert noop canaries back to back**, replicating the burst with zero shim behaviour.
   Separates "rapid mapping" from "what the mapped code does" — the §13 canary tested one DLL only.
3. Only then bisect shim identity further; at n=3/arm the current arms cannot separate interaction
   models.

---

## 19. ★★★ Spacing the injections collapses the hazard — ⚠ SEE §20: "eliminates" IS TOO STRONG

**2026-08-04 23:24 – 2026-08-05 00:20.** Identical full default set, menu-idle, but
`-InjectGapSeconds 60`, so the secondaries land at ~T+20 / 80 / 140 / 200 / 260 instead of packed
into T+20..T+33. Hold 600 s × 5 runs.

| run | outcome | uptime | injections | **observed gaps** | shims active |
|---|---|---:|---:|---|---|
| 1 | **SURVIVED** | 603 s | 5 | **[60,60,61,60]** | all 6 |
| 2 | **SURVIVED** | 603 s | 5 | **[60,60,60,60]** | all 6 |
| 3 | **SURVIVED** | 603 s | 5 | **[60,60,60,60]** | all 6 |
| 4 | **SURVIVED** | 604 s | 5 | **[60,60,60,60]** | all 6 |
| 5 | **SURVIVED** | 602 s | 5 | **[60,60,60,60]** | 5 of 6 |

**TOTAL: 3,015 s exposure, 25 injections, ZERO deaths.**

| | stock 3 s gap | spaced 60 s gap |
|---|---:|---:|
| exposure | 129 s | **3,015 s** |
| injections | 12 | **25** |
| deaths | **3** | **0** |

* **per-INJECTION model** (the harder test — same number of maps, just spread out): expected
  **6.25** deaths, observed 0 → `P(0 | λ=6.25) = 0.0019`.
* per-second model: expected 70.1, observed 0 → `P ≈ 3×10⁻³¹`.

⇒ **MEASURED: the burst rate of manual-maps dominates the hazard, not any shim's identity or
behaviour.** ⚠ **But see §20 — a later 12-run sweep found the residual hazard is NOT zero, and
this arm's clean sweep was luck-consistent (it expected ~1 death at the pooled spaced rate).**

**The treatment was verified on every run** — the driver parses `inject-secondaries.log` and measures
the actual spacing; all five runs show 60 s gaps. A silent fallback to the 3 s default would have
looked like a failed treatment rather than an un-applied one, which is the most expensive way this
test could have been wrong.

**And the shims still work.** All six markers advanced (5 of 6 on run 5 — `pi8`'s marker lagged the
sample; it was injected, per the log). This is not "disable the shims to stop the crashes" — it is
**the full functional set AND stability**, which is the outcome that actually matters.

### Where the whole series lands

| arm | exposure | deaths | 1 per |
|---|---:|---:|---:|
| clean `-NoHook` (no injection sequence) | 5,173 s | 0 | — |
| noop canary ×1 | 2,700 s | 0 | — |
| `catalog_store_fix` alone | 2,700 s | 0 | — |
| `pi8` alone | 5,400 s | 0 | — |
| **SPACED full set (60 s)** | **3,015 s** | **0** | — |
| `csf`+`pi8`+`pick`+`bp` (3 s) | 1,862 s | 1 | 1,862 s |
| `-NoLoadout` (3 s) | 628 s | 1 | 628 s |
| `-NoPasses` (3 s) | 655 s | 1 | 655 s |
| **full set (3 s)** | 129 s | 3 | **43 s** |
| **`-NoMissions` (3 s)** | 90 s | 3 | **30 s** |

**Zero-death exposure across all clean arms: 18,988 s = 5.27 hours.** Every death in the entire
series occurred in an arm using the **3 s** gap.

### The fix

`configs/inject-secondaries.ps1` gained `-GapSeconds` (default **3**, i.e. behaviour unchanged unless
asked); `configs/launch-redirect.ps1` passes it through as `-InjectGapSeconds`. Verified end-to-end
before use: the launcher builds `-GapSeconds 60` and the injector binds it.

**Recommendation, and it is a judgement call the user should make:** flipping the default 3 → 60
costs **~4.3 min** before the store/roster/missions/passes are all live, versus ~35 s today. That is a
real usability cost for a real stability gain. Options:
1. **Leave the default at 3, use `-InjectGapSeconds 60` for long sittings** — no regression risk, opt-in.
2. **Flip the default to 60** — safest, slowest menu.
3. **Find the knee** — bisect the gap (20 s? 30 s?) for ~1 h of runs, and get most of the stability
   at a fraction of the wait. 60 s was chosen to be decisive, not minimal; **nothing here says 60 is
   required.**

### ★★ The consequence for FK-7, which is the reason any of this was worth doing

**`configs/fk24-stage.ps1` injects four DLLs back to back** — `gft_ready_fix` → `tutorial_launch_fo`
→ `tutorial_launch_sp` → the probe. That is the same burst pattern, on the route where FK-7 lives.
Its steps are gated on log evidence rather than a fixed 3 s sleep, so the spacing is not identical
and this result does **not** transfer automatically — but it is now the **leading candidate
explanation for the ~1–5 minute tutorial deaths**, and it is directly testable by adding the same
gap. Combined with §12–§18, the standing conclusion holds and hardens: **instrumented-run deaths are
suspect by default, and a tutorial death is more likely ours than the game's.**

---

## 20. ⚠⚠ KNEE BISECT — and it RETRACTS §19's "eliminates"

**2026-08-05 00:21–01:14.** Gaps 10 / 20 / 30 s, 4 runs each, 300 s hold.

| gap | runs | exposure | injections | deaths |
|---:|---|---:|---:|---:|
| 3 s (stock) | 3 | 129 s | 12 | **3** |
| **10 s** | 4 | 1,210 s | 20 | **0** |
| **20 s** | 4 | 1,214 s | 20 | **0** |
| **30 s** | 4 | 669 s | 12 | **2** |
| 60 s | 5 | 3,015 s | 25 | **0** |

### ⚠ My scoring discarded two real deaths — corrected here

Both gap-30 deaths were auto-scored `DIED-VOID(gap-not-applied)`. **That verdict is wrong.** They show
`inj=1`, `observedGaps=[]`: the game died **after the first secondary injection but before the
second**, so there was no interval to measure. The treatment *was* applied — the flag was passed;
the run simply died too early for the instrument to observe it.

My check required `$gaps.Count -ge 1`, i.e. **≥2 injections**, and silently converted "too early to
measure" into "treatment absent". Had I taken the summary at face value, gap-30 would read clean and
**the residual hazard would have vanished from the record.** Correct rule: VOID only when gaps were
observed *and* differ from the request; a run dying before the second injection is a **real death at
an unmeasured gap**.

### The corrected numbers

| | stock (3 s) | spaced (≥10 s), pooled |
|---|---:|---:|
| exposure | 129 s | **6,108 s** |
| injections | 12 | **77** |
| deaths | **3** | **2** |
| rate | 1 per 43 s | **1 per 3,054 s** |

* per-second hazard: **71× lower**
* per-injection hazard: **9.6× lower** (0.250 → 0.026 deaths/injection)
* `P(≥3 of 5 events in the stock arm | exposure share 0.021) = 8.6×10⁻⁵`

⇒ **Spacing is a large, highly significant MITIGATION — not a cure.** §19 said "eliminates"; that is
**retracted**. At the pooled spaced hazard, §19's own 3,015 s arm expected **0.99** deaths and saw 0
— `P(0) = 0.37`, i.e. **entirely luck-consistent**. A single clean arm was never evidence of
elimination, and I should not have written it as one.

### Where the knee is

10 s and 20 s are **indistinguishable from 60 s** in this data (0 deaths in 20 injections each).
Gap-30's 2 deaths vs gap-10+20's 0 in 2,424 s gives `p = 0.047` on a **post-hoc–selected** comparison,
so it is **not** evidence that 30 is worse than 10 — with 5 events spread over 4 gaps, this is what
noise looks like.

⇒ **Nothing here shows 60 s is required. 10 s buys the same measured benefit for ~40 s of extra menu
wait instead of ~4.3 minutes.** Caveat, stated because the arms are small: each gap arm is only ~20
injections, powered to detect *full* lethality (`P(0|λ=4)=0.018`), **not** to prove a small residual
hazard is absent. It plainly is not absent — 2 deaths across the spaced arms prove that.

### Recommendation

**Set the default `GapSeconds` to 10–20** (I would take **20**: same measured result as 10, double the
margin, still only ~80 s). That captures a ~70× hazard reduction for a cost the workflow will not
notice. Then re-derive the residual with a long run at the chosen gap — the current bound is 1 death
per ~3,054 s, which over a 15-minute tutorial sitting is roughly a **1-in-3.4 chance of a
protector-induced death**. That is much better than 1-in-43-seconds, and it is **not zero**, so
tutorial sittings should still archive dumps and treat an unexplained death as possibly ours.

### Both gap-30 dumps are Family B

```
knee-g30-2  pc=0x202FAF8205D  parm0=0x0  -> FAMILY B
knee-g30-3  pc=0x24F44DC205D  parm0=0x0  -> FAMILY B
```

Running total: Family B now dominates the spaced/low-hazard regime, while Family A (`+1`) clustered in
the high-hazard burst arms. Suggestive of two thresholds on one mechanism; **not tested, and not
claimed.**

---

## 21. ★★★ TUTORIAL SITTINGS WITH THE NEW SPACING — every death is the PROTECTOR

**2026-08-05 01:36–02:11.** First test of the S109 spacing on the route where FK-7 actually lives.
`forceTutorialMatch=true`, `-NoHook`, then `fk24-stage.ps1 -Probe tutorial_launch_play.dll` with the
new 20 s minimum inter-injection gap. Probe verified by **`.text` sha `ae532866e15fd8ac`** = CLAUDE.md's
`play` candidate (the whole-file hash differs — that table lists `.text` hashes; checking the wrong one
would have run the `play-statictest` control by mistake).

| attempt | outcome | uptime | armed at | armed window |
|---|---|---:|---:|---:|
| 1 | **DIED** | 529 s | t+179 s | 350 s |
| 2 | **SURVIVED** (killed at hold) | **604 s** | t+209 s | 395 s |
| 3 | NOSTAGE — died during staging | 339 s | — | — |
| 4 | **DIED** | 267 s | t+191 s | 76 s |

**3 of 4 attempts reached the armed window** — better than CLAUDE.md's documented ~2 of 4, though
n=4 makes that anecdotal.

### ★★ The headline: all three dumps are Family A, and the game is not on the stack

```
tut1-DEATH     pc=0x7FFD3B400001  parm0=0x8 EXECUTE/DEP  chain=EMPTY
tut3-NOSTAGE   pc=0x7FFD3B400001  parm0=0x8 EXECUTE/DEP  chain=EMPTY
tut4-DEATH     pc=0x7FFD3B400001  parm0=0x8 EXECUTE/DEP  chain=EMPTY
```

**Every death in this sitting is `runtime.dll + 1` with ZERO SUPERVIVE frames.** `0x7FFD3B400001` is
now the fault address in **seven** independent deaths across the session. Not one of these is a game
bug: the game's own code is not on the faulting stack in any of them.

⇒ **The "~1–5 minute tutorial death" that has driven FK-7 for multiple sessions is, in every instance
we have ever captured, the protector killing the process.** That does not prove FK-7 has no separate
existence — it proves that **no captured tutorial death has yet been shown to be one.**

### Survival: suggestive, not significant

| | exposure | deaths | 1 per |
|---|---:|---:|---:|
| S108b baseline (stock ~5 s spacing): 50, ~170, 290, ~130, >301 s | 941 s | 4 | 235 s |
| **this sitting (20 s spacing)** | **1,739 s** | **3** | **580 s** |

**2.5× improvement**, but if the baseline hazard held we would have expected 7.4 deaths and saw 3:
`P(≤3 | λ=7.4) = 0.063`. **Not significant.** Two of three armed runs (529 s, >604 s) exceed the
entire S108b `play` range of 50–290 s, and the longest previously recorded run of any kind was
>301 s — but with n=3 and a loosely-recorded baseline this is **encouraging, not established.**

### ⚠ An open item this sitting surfaced, and it is NOT the spacing's doing

My summary column read `anim=False` on all three armed runs. **That boolean was my own bad regex** —
it required the literal words `run`/`idle`, but the marker prints asset names
(`PlayAnimation(A_Ronin_Cosmetic_HeroSelect_Breathe, loop) ok`). Corrected reading of the markers:

* `[PL] *** init complete: body=BUILT; camera + WASD active ***` — **present** on all armed runs
* `[ANIM] run anim A_Ronin_Movement_OutOfCombat_N = 0x… (AnimSequence)` — resolved
* `[ANIM] self-driven walk START` — reached
* **but no repeated `PlayAnimation(run/idle, loop) ok` cycling**, which S108b §3 reports as the
  signature of a healthy locomotion swap
* **no `FAULTED` and no `anim swapping DISABLED`** — so this is *not* the `KSTATICTEST` bug S108b fixed

**Unexplained, and explicitly not attributed.** The spacing change only inserts sleeps between
injections and has no plausible path to animation behaviour. Candidates: a real regression elsewhere,
a marker-truncation artifact (FK-25), or the cycling simply not being reached in these runs. **Needs
its own look; do not read it as a cost of the spacing.**

### Where this leaves FK-7

Combined with §12–§20: instrumented-run deaths are suspect by default, the injection burst is a
measured cause, spacing cuts the menu-route hazard ~71×, and **every tutorial death ever captured is
the protector with no game frames**. The honest position is not "FK-7 is closed" — it is that
**FK-7 has never had a confirmed instance**, and the phenomenon it was named for is now substantially
accounted for by our own instrumentation. Any future claim of an FK-7 death needs a dump with
SUPERVIVE frames on the faulting stack; none has ever been produced.

---

## 22. ★★ THE ANIMATION CYCLING — ROOT-CAUSED: the run anim is GC'd 13 s before it is needed

Follow-up to §21's open item. **Root cause found, and it is NOT the injection spacing.**

### The chain, all MEASURED from the three armed-run markers

**1. Rooting fails — the shim refuses to guess, correctly.** `KGCROOT` is default 1, but its root-bit
corroboration does not resolve on this build:

```
[GC] rootbit: nRooted=5 and=42000000 nUnrooted=64 or=41000004 cand=02000000
              expect=40000000 -> NOT corroborated -> REFUSING to poke flags
[GC] loaded-asset  0x…  NOT rooted (bit unresolved)      <- run anim
[GC] body-component 0x…  NOT rooted (bit unresolved)
[GC] anim-instance rooted x0 (rooted=0 failed=5)
```

`KGCROOTBIT` is `0x40000000` (`RootSet`, "corroborated live" per the source), but the observed
candidate is `0x02000000` and `expect` is not met, so the shim declines to poke flags. **That refusal
is right** — guessing a flag bit would be far worse — but the consequence is that **nothing is rooted.**

**2. The run anim is then collected, fast and reproducibly:**

```
attempt 1  [GCW] *** RUN ANIM 0x1F93525FA00 WAS GARBAGE-COLLECTED (t=7828ms after body build) ***
attempt 2  [GCW] *** RUN ANIM 0x219AF95AC00 WAS GARBAGE-COLLECTED (t=6860ms after body build) ***
attempt 4  [GCW] *** RUN ANIM 0x1A5B67D0600 WAS GARBAGE-COLLECTED (t=7781ms after body build) ***
```

**3 of 3 runs, 6.9–7.8 s after body build.**

**3. But the walk that needs it does not start for 20 s.** `KAUTOWALKATMS = 20000` — "ms after body
build when the self-driven walk starts (AFTER the three idle shots)". The idle↔run swap only fires
when `|velocity| > KRUNSPEED (40)`, and the only thing that moves the hero unattended is that walk
(`KPUPSPEED = 600`, comfortably over the threshold).

⇒ **The asset is dead ~13 seconds before anything asks to play it.**

**4. And attempt 4 caught the collision explicitly** — the one run where the swap was actually
attempted:

```
[GCW] run: DEAD UObject before PlayAnimation (comp=0x1A4CA3AB140 alive=1 anim=0x1A5B67D0600 alive=0)
      -> anim swapping DISABLED. The asset was garbage-collected: check the [GC] lines above.
```

`comp alive=1, anim alive=0` — the component survived, the **animation asset** did not. `PlayAnimOn`'s
S106 `GcAlive` guard then latched `g_plAnimDead` and stopped swapping, exactly as designed.

### Why this is not the spacing change

The spacing only inserts sleeps **between injections**, before the body is built. Every timing above is
measured **relative to body build**, so the whole chain is invariant to it. Attempts 1/2/4 each show
`self-driven walk START`, i.e. the walk logic ran on schedule.

### ⚠ Whether this is a REGRESSION is NOT established — and the reason is FK-25 again

`docs/s108b-ksmactor-bisect.md` §3 reports repeated `PlayAnimation(run/idle, loop) ok` cycling on the
`KSTATICTEST=0` arms. I could not compare against it: **the S108b step-4 marker copy is 406 bytes** —
`fk24-stage` copies the marker 2 s after injection, and `Marker()` opens `CREATE_ALWAYS`, so the copy
captured the file *before the probe had written anything*. That is FK-25 costing a comparison, again.
So: either the GC was slower in S108b, or the rooting resolved then, or cycling was always marginal.
**Unknown, and I am not guessing.**

### The fixes, cheapest first

1. **Move the walk before the collection.** `KAUTOWALKATMS 20000 → ~4000` puts the swap inside the
   asset's ~7 s lifetime. **One `-D`, and it would confirm the entire causal chain in a single run** —
   if cycling reappears, the story is proven end to end. ⚠ The 20 s value exists so the walk lands
   after the three idle screenshots, so this trades a diagnostic for a diagnostic; adjust the shot
   schedule with it.
2. **Re-resolve the root bit.** The corroboration expects `0x40000000` and sees a `0x02000000`
   candidate. Fixing that makes `KGCROOT` do its job and fixes the *cause* rather than out-running it —
   and it would also root the body component and anim instances, which is what S106 built it for.
3. **Re-load on death** instead of latching off: when `GcAlive(anim)` fails, `LoadMeshByPath` again
   rather than disabling swapping for the session. Robust, but treats the symptom.

**Recommendation: (1) to confirm, then (2) as the real fix.** Note this is a *cosmetic/locomotion*
defect — it does not affect survival, the crash families, or any S109 conclusion.

---

## 23. ★★★ ANIM CHAIN CONFIRMED — the swap now fires, and the ORDERING is the proof

**2026-08-05 02:14–02:35.** `play-earlywalk` (`-DKAUTOWALKATMS=4000`, walk at t+4 s instead of t+20 s),
3 attempts, 300 s hold. **Prediction registered before the run: `swapRun > 0`.**

⚠ **The A/B is real, and nearly was not.** `play-earlywalk` is **234,496 bytes with a 161,280-byte
`.text` — byte-identical sizes to `play`.** Only the `.text` hash separates them
(`1882cbddf870020b` vs `ae532866e15fd8ac`). Size alone would have read as a failed build, and running
the wrong one would have produced a confident null result. Registered in `build.ps1` as a proper
one-dimension variant; C++ EH gate passes on a raw byte scan.

### Result: 3 of 3, and the control was already in hand

| arm | attempts | `swapRun` | `swapIdle` | armed |
|---|---|---|---|---|
| `play` (walk t+20 s) — **control** | 3 | **0, 0, 0** | 0, 0, 0 | 3/4 |
| **`play-earlywalk` (walk t+4 s)** | 3 | **1, 1, 1** | 0, 1, 1 | **3/3** |

### The ordering, which is the actual evidence

```
attempt 3
  [ANIM] PlayAnimation(A_Ronin_Cosmetic_HeroSelect_Breathe, loop) ok
  [ANIM] run anim A_Ronin_Movement_OutOfCombat_N = 0x238F72E6200 (AnimSequence)
  [ANIM] self-driven walk START
  [ANIM] PlayAnimation(run, loop) ok                                     <- THE SWAP FIRES
  [ANIM] PlayAnimation(idle, loop) ok                                    <- and returns
  [GCW] *** RUN ANIM 0x238F72E6200 WAS GARBAGE-COLLECTED (t=10250ms) *** <- collected AFTER
```

**Same asset pointer `0x238F72E6200` in the resolve, the swap and the collection.** In the control the
GC (6.9-7.8 s) preceded the walk (20 s); here the walk (4 s) precedes the GC (10.25 s). Nothing about
the GC was fixed — **the swap simply now wins the race.** Attempt 2 is the same shape with the *idle*
anim collected at 9,625 ms after both swaps completed.

⇒ **§22's chain is confirmed end to end: rooting fails → assets are collected ~7-10 s after body build
→ with the walk at 20 s the asset was already dead → with the walk at 4 s the swap succeeds.**
One run→idle cycle is exactly what a single 5 s walk window (`KAUTOWALKMS=5000`) should produce; the
"repeated cycling" S108b describes would need repeated motion.

### ⚠ This is a DIAGNOSTIC. Do not adopt it.

* It does not fix anything — the assets are still unrooted and still collected. It only moves the use
  earlier than the collection. **The real fix remains re-resolving the root bit** (expect
  `0x40000000`, observed candidate `0x02000000`), which would also root the body component and the
  anim instances as S106 intended.
* The 20 s value exists so the walk lands **after** the three idle screenshots; 4 s overlaps them.

### Survival in this arm — noted, NOT concluded

All three died at **265 / 269 / ~300 s** (0 of 3 past 300 s), against the `play` arm's 267 / 529 /
>604 s (2 of 3 past 300 s). Both dumps recovered are **Family A, `pc=0x7FFD3B400001`** — the protector
again, now **nine** independent deaths at that address.

**Do not read this as "earlywalk is less stable."** n=3 per arm; the hold here was capped at 300 s so
the upper tail is truncated by construction and the arms are not comparable on exposure; and this is a
different binary. It is a flag for a future comparison, not a finding.

---

## 24. ★★ ROOT-BIT RESOLUTION FIXED — and it does NOT keep the asset alive

**2026-08-05 02:50–03:10.** The §22/§23 root cause said rooting fails, so assets are collected. I fixed
the rooting. **Half of that story survives contact with the game; the other half does not.**

### The bug, and it was exactly as diagnosed

The old corroboration was `cand = AND(native classes) & ~OR(64 sampled ordinary objects)`, accepted
only if `cand` contained `KGCROOTBIT`. Its comment asserted ordinary objects "must not have" RootSet.
**False** — anything that called `AddToRoot` (GameInstance, engine subsystems, managers) is an ordinary
non-class object legitimately in the root set, and the filter excluded only Class/Package/Function/
Enum/ScriptStruct and CDOs.

**The fix keeps the strong half** (the bit must be set on *every* native class) and replaces the
brittle half with a **frequency test**: RootSet is rare among random objects, a generic flag is not.
`-DKGCROOTSTRICT=1` restores the old test; `play-strictroot` is registered as a one-dimension control.

**It works, and the new telemetry confirms the diagnosis to the sample:**

```
[GC] rootbit[FREQ]: nRooted=5 and=42000000 nUnrooted=64 or=40000004 cand=02000000 expect=40000000
                    onNatives=1 bitFreq=1/64(1%) max=33% -> CORROBORATED (rooting enabled)
[GC] anim-instance rooted x2 (rooted=5 failed=0)
```

**`bitFreq = 1/64`.** Exactly one contaminated sample in sixty-four was vetoing the correct bit — the
predicted failure, measured. Rooting went **`rooted=0 failed=5` → `rooted=5 failed=0`**, and every poke
verifies by readback: `flags 00000004 -> 40000004 OK`.

### ⚠ But the asset is STILL collected — and sooner

The run AnimSequence is rooted with a verified readback, and dies anyway:

```
[GC]   ROOT loaded-asset 0x226FBC09E00 (AnimSequence) … flags 00000004 -> 40000004 OK
[ANIM] run anim A_Ronin_Movement_OutOfCombat_N = 0x226FBC09E00 (AnimSequence)
[ANIM] PlayAnimation(run, loop) ok
[ANIM] PlayAnimation(idle, loop) ok
[GCW] *** RUN ANIM 0x226FBC09E00 WAS GARBAGE-COLLECTED (t=5484ms after body build) ***
```

| | GC of the run anim, ms after body build |
|---|---|
| before (bit unresolved, **nothing** rooted) | 7828 / 6860 / 7781 |
| **after (rooted, readback OK)** | **5484 / 2140** |

**Rooting made no difference — if anything the collections came earlier.** So:

⇒ **RETRACTED, from §22: "rooting fails ⇒ the asset is collected" was only half right.** Rooting did
fail, and fixing it was a real bug fix — but **rooting is not what was keeping the asset alive, and
making it work does not stop the collection.** The premise that the poked `RootSet` bit protects the
object — inherited from S106 and never tested end-to-end until now — **does not hold in this build.**

### What that leaves

`GcAlive` fails on vtable-outside-image or `NamePrivate == 0`, so the object really is being torn down;
this is not a detector artifact. Candidates, none tested:
1. **The GC does not honour a directly-poked flag here** — it may consult a separate root-set structure,
   or `0x40000000` may not be `RootSet` in this build. The native-class `AND` of `0x42000000`
   (= `RootSet|Native` under the stock enum) is suggestive but **not proof**: native classes survive GC
   for other reasons, so they cannot discriminate.
2. **The asset is not GC'd at all but streamed/unloaded**, or explicitly marked garbage.
3. The initial flags are `0x00000004` — **bit 2 is not a value in the stock `EInternalObjectFlags`**,
   which is a hint that the flag word here is not laid out as assumed.

**Keep the fix**: the corroboration was genuinely broken, `KGCROOT` had been silently inert since S106,
and it now does what it says. **But do not describe it as a fix for the animation** — it is not.
`play-earlywalk` (racing the collection) remains the only thing measured to make the swap fire reliably.

### ⚠ `play`'s hash changed — CLAUDE.md's reference is now stale

```
play OLD (pre-fix)  ae532866e15fd8ac
play NEW (§24 fix)  7bc4df9236ead0ac
```
Same trap S108b created with `a67239a0`. `play` and `play-strictroot` share a **161,792-byte `.text`**
and differ only by hash. Survival was unremarkable (275 / 292 s, 2 of 3 armed).

---

## 25. FLAG-WORD LAYOUT CHECKED — it is CORRECT, which eliminates the cheapest remaining hypothesis

§24 left three candidates for why a rooted object is still torn down. The third — *"the flag word is
not laid out as assumed"* — was the cheapest, and it is now **eliminated**.

**Method.** `tools/re/uobjitem_layout.py` (new, read-only RPM, no injection). Sample the live
`FUObjectArray` at the **menu** — no tutorial staging needed — split objects into a reference set that
*must* be rooted (native `UClass`es, which UE allocates with `RF_MarkAsRootSet`) and everything else,
then report per-bit frequencies **at every dword offset in the item**, not just the assumed one. If the
field had moved, this finds it.

**MEASURED** (pid 47216, base `0x7FF681610000`, 189,760 objects; 115 native UClasses / 3,803 ordinary):

```
offset +0x08   AND(native)=40000000  OR(native)=42000000
    bit 30 (0x40000000)  native 100%  ordinary  19%   <== RootSet-like
    bit 25 (0x02000000)  native  99%  ordinary  14%   (Native)
    bit  1 (0x00000002)  native   0%  ordinary  81%
offset +0x0C   AND=0  OR=0        (uniform ~1-19% noise -> ClusterRootIndex, an index not flags)
offset +0x10   AND=0  OR=00007FFF (small integers -> SerialNumber)
offset +0x14   AND=0  OR=0
```

Raw items confirm it by eye — every native class reads `… | 00 00 00 42 …` at +0x08:

```
NATIVE  LandscapeProxy            80 12 2f 09 f3 01 00 00 | 00 00 00 42 00 00 00 00 …
Package//Script/TextureUtili      90 30 84 07 f3 01 00 00 | 00 00 00 40 00 00 00 00 …
```

⇒ **The assumed layout is right.** `FUObjectItem` is `{Object@0x00, Flags@0x08, ClusterRootIndex@0x0C,
SerialNumber@0x10}`, stride `0x18`, and **bit 30 is the RootSet-like bit**: universal on native
classes (`AND(native) = 0x40000000` exactly) and present on a minority of ordinary objects. `KGCROOTBIT
= 0x40000000` is the correct constant, and the shim was poking the correct bit in the correct field.

**It also validates §24's fix quantitatively.** Ordinary objects carry RootSet at **19%** here — so the
old `& ~OR(64 samples)` test had essentially **no chance** of surviving: at 19%, the probability all 64
samples lack the bit is `0.81^64 ≈ 1.2 × 10⁻⁶`. The guard was not unlucky, it was **arithmetically
doomed**, and `KGCROOT` could never have worked since S106. The frequency threshold (33%) sits
correctly above the observed 19%.

### What remains

Of §24's three candidates, only two survive, and both are about **semantics, not layout**:

1. **The GC does not honour a directly-poked bit.** UE's `AddToRoot` sets this flag *through*
   `GUObjectArray`, and modern UE also keeps cluster/reachability state that a raw poke does not touch.
   A flag we set may simply be recomputed or ignored.
2. **The asset is not GC'd at all** — streamed out, package-unloaded, or explicitly marked garbage.
   `GcAlive` (vtable-in-image + `NamePrivate != 0`) cannot distinguish those from collection.

**Next probe, and it is again read-only:** watch one loaded AnimSequence's item across its death —
sample `Flags`, `ClusterRootIndex` and `SerialNumber` every 250 ms from body build. A **SerialNumber
change means the slot was recycled** (real destruction + reuse); flags flipping `Unreachable` means
reachability GC; neither changing while the object's vtable/name go bad means something tore the object
down out of band. That distinguishes all three without a single write.

⚠ Also worth recording: **bit 1 is set on 81% of ordinary objects and 0% of native classes.** It is not
a value in the stock `EInternalObjectFlags`. Unexplained, unused by us, and a hint that this build's
flag semantics are not entirely stock — but it is **not** the field-layout error I went looking for.
