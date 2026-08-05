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

## 15. ★★★ DOSE-RESPONSE: the `ProcessInternal` hook is the mechanism, and multiplicity multiplies it

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
