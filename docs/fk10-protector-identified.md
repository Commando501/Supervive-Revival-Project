# FK-10 — SETTLED: the protector is not VMProtect/Themida, and `runtime.dll` is not packed

**S113, 2026-08-09. Offline, read-only. Zero game launches consumed.**

FK-10 (`docs/ignorance-map-s101.md:655`) recorded the belief *"`runtime.dll` is packed"* /
*"the packer is VMProtect/Themida"*, severity HIGH, on the grounds that the vendor name was a
*shape* inference from the IAT stub pattern and had never been established.

**Verdict: the belief is REFUTED on six independent grounds, and its two factual sub-claims
("packed", "~48 MB") are both wrong.** The protector is a **bespoke, first-party protection
stack that internally calls itself "Packer", version 3.3.1**. Its own code is **plaintext and
disassemblable offline today**.

Everything below is offline file analysis of shipped artifacts. Method: every negative is
paired with a positive control, per `supervive-instrument-artifact-pattern`.

---

## 0. TL;DR for the next session

| question | answer |
|---|---|
| Is it VMProtect or Themida? | **No.** Six independent refutations, HIGH confidence |
| What is it? | Internally named **"Packer" v3.3.1**; first-party Theorycraft; **vendor unidentified** (deliberately not renamed — see §7) |
| Is `runtime.dll` packed/encrypted? | **No.** 46.6 MB of **plaintext obfuscated x86-64**. Its *data* and *resources* are encrypted; its *instructions* never are |
| Can we disassemble the protector? | **YES, today, offline.** Use the loader function table at RVA `0x14D8758` (18,580 entries) — **not** the vestigial `.pdata` section |
| Is the *game exe* packed? | Not in the wrapper sense — **stock section layout, selectively encrypted in place**. `.text` 100 % ciphertext at rest |
| Wall #7 (the integrity check) | **Not located, but the search is now narrowed to a 251 KB address range** and the old xxHash lead is spent (§5) |
| FK-32 (`0x0000DEAD` deaths) | **CLOSED on mechanism** — it is the protector deliberately calling `NtTerminateProcess(h, 0xDEAD)` (§6) |

---

## 1. The six refutations of the vendor name

**R1 — ★ Our own tool's 100 % success rate is incompatible with a VM packer. (MEASURED)**
`tools/usmapdump/deobfimports.go` resolves the import stubs by emulation. Its `emulateStub()`
is a straight-line integer machine supporting exactly 21 opcodes —
`PUSH POP MOV LEA ADD SUB XOR AND OR ROL ROR SHL SHR SAR NOT NEG BSWAP INC DEC NOP JMP` —
with **no conditional branches (no `Jcc` case exists), no `CALL`, no flags, no memory writes**,
a 192-byte stub window, a 128-instruction cap, and:
```go
default:
    return 0, false // unsupported instruction -- give up (verified => never wrong)
```
It resolved **1107/1107 slots, 0 undecodable, 0 off-target**.

VMProtect's import protection is **virtualized by construction** — a handler-dispatch
interpreter with conditional control flow. Themida/WinLicense mutate and virtualize with
polymorphic junk. Such a stub aborts this emulator at its first `Jcc` or `call`. A 100 % hit
rate therefore *proves* every one of the 1,107 stubs is branch-free arithmetic:
`real = C2 ^ ROL64(C1 + M, 0x33)`.
*Built-in positive control:* every recovered target is verified against an exports sidecar by
exact address match, so a mis-emulation can only ever yield "unresolved", never a wrong name.
0 undecodable means 0 stubs defeated it.

**R2 — the game exe has no packer sections and its entry point was never redirected. (MEASURED)**
Stock MSVC/UE5 layout: `.text .rdata .data .pdata .msvcjmc CPADinfo .rodata _RDATA .rsrc
.reloc`. `AddressOfEntryPoint = 0x751EFD0`, which lies **inside `.text`**. VMProtect and
Themida both append their own sections and move the OEP into them. Neither happened.

**R3 — zero vendor strings, in a module we can now prove is readable. (MEASURED, controlled)**
`VMProtect` / `Themida` / `vmp0` / `Enigma` / `Denuvo` = 0 occurrences in `runtime.dll`,
ASCII **and** UTF-16. This is admissible *only because* §3 establishes the protector's code is
plaintext; the control is that the same scanner recovers `packer/3.3.1`,
`o566896.ingest.sentry.io`, `DUMPER_SKIP_UPLOAD`, the verbatim XXH3 `kSecret`, and a
byte-exact `hde64_table` from the same file.

**R4 — the toolchain is clang/LLD on Linux. (MEASURED)**
RSDS GUID tail `4C4C44205044422E` = ASCII `"LLD PDB."`; PDB paths `/work/runtime.pdb` and
`/work/preloader.pdb`; **no Rich header** (control: the parser returns full Rich tables for 2
of the other 5 binaries); an `IMAGE_DEBUG_TYPE_REPRO` record, so the odd `TimeDateStamp`
values are reproducible-build content hashes, not dates. Commercial Windows packers are
MSVC-built and do not leave `/work/*.pdb`.

**R5 — ★ the protector reports crashes into Theorycraft's OWN private Sentry project. (MEASURED,
independently replicated)**

| source | DSN |
|---|---|
| game, from `Loki.log` | `o566896.ingest.sentry.io:443/api/5710262/minidump/?sentry_client=`**`sentry.native.unreal/0.7.6`**`&sentry_key=149a7ac2a7914150b87ce714fd4d6444` |
| protector, `runtime.dll` @ file offset **`0x007C1BEC`** (UTF-16) | `/api/5710262/minidump/?sentry_client=`**`packer/3.3.1`**`&sentry_key=149a7ac2a7914150b87ce714fd4d6444` |

**Same org `o566896`, same project `5710262`, same public key** — differing only in
`sentry_client`. A commercial packer ships a generic runtime; it does not embed the customer's
private DSN. (Host string separately at `0x00007BF2`.)

**R6 — one identity across all five binaries. (MEASURED)**
Every binary carries the **identical** EV certificate: `CN=Theorycraft Games Inc.` (Delaware,
serial 4080935), DigiCert Trusted G4 RSA4096 SHA384 CS CA1, thumbprint
`512A91F0BC1471AC83C69280966895CF71EA66A5`. RFC-3161 timestamps cluster within **6 seconds**
(runtime 2025-12-12 21:52:34 UTC, 4 s after the exe, 2 s before preloader) — one build
pipeline, one signer.

---

## 2. The bill of materials — the real one

`Loki/Binaries/Win64/thirdpartylicenses.txt`, 31,834 B / 558 lines, **0 prior hits repo-wide**.
Read in full. **No version numbers are stated anywhere**, only copyright years.

All **10** ignorance-map claims CONFIRMED verbatim, **0 refuted**:

| component | line | capability it grants |
|---|--:|---|
| System Informer | 1 | process / handle / driver enumeration |
| constexpr-xxh3 | 28 | compile-time hashing |
| xxHash | 60 | fast hashing — **but see §5: it is Zstd's frame checksum, not the integrity hash** |
| Hacker Disassembler Engine 64 | 92 | instruction-length decoding — **what you need to detect a foreign inline hook** |
| MinHook | 125 | inline hooking — *our own technique* |
| Zstandard | 156 | decompression |
| bscanf | 219 | CRT-free scanf |
| mbedtls | 246 | independent TLS — **bypasses `cacert.pem`** |
| tiny-json | 499 | CRT-free JSON |
| tpm-tss | 526 | TPM-backed hardware identity |

**Two components the map missed:**
- *A printf/sprintf Implementation for Embedded Systems* (Marco Paland, L192) — CRT-free printf.
- ★ **Intel ISA-L Crypto (L467)** — a **third** hashing engine, whose headline feature is
  **hardware multi-buffer SHA/MD5**: an API for hashing *many independent buffers concurrently*
  in SIMD lanes. This turned out to be the key to §5.

**Structural proof this is the protector's BOM, not the game's (MEASURED):** `runtime.dll`,
`preloader.dll`, `thirdpartylicenses.txt` and `Diagnoser` appear in **none** of the three UE
shipping manifests, while `SUPERVIVE.exe` and `steam_api64.dll` do. They are a
post-packaging wrap set.
*(Aside: the `LICENSE` / `README.md` / `dwmapi.dll` sitting beside preloader are the user's own
UE4SS install, not game files.)*

**No kernel/driver component is attributed** — moderate confidence only, since System
Informer's GPL kernel driver would require separate attribution if present.

---

## 3. `runtime.dll` — the structural record (created here; none existed)

**File 67,511,496 B. `SizeOfImage = 0x4066000` = 67,526,656.** 11 sections; numbering is
sparse (`0,1,2,30,40,31,42`). Headers 1,024 + Σraw 67,500,032 + 10,440 Authenticode =
67,511,496 exactly — no gaps, no overlay.

| # | name | VirtAddr | VirtSize | RawSize | R/W/X | H | 4K pages H≥7.90 |
|--:|---|---|---|---|---|--:|--:|
|0|`.pdata`|`0x1000`|`0x56E8`|`0x5800`|R--|5.926|0/6|
|1|`.rwx`|`0x7000`|`0x1000`|`0x1000`|**RWX**|**0.000**|0/1|
|2|`packer0`|`0x8000`|`0x7C7000`|`0x7C7000`|R--|**7.987**|1888/1991 (94.8 %)|
|3|`packer1`|`0x7CF000`|`0x16F886`|`0x16FA00`|R-X|7.203|68/368 (18.5 %)|
|4|`packer2`|`0x93F000`|`0xC010`|`0xC200`|RW-|5.424|0/13|
|5|`.rsrc`|`0x94C000`|`0x92DA60`|`0x92DC00`|R--|**8.0000**|2348/2350 (99.9 %)|
|6|`.reloc`|`0x127A000`|`0x10AC`|`0x1200`|R--|5.274|**0/2**|
|7|`packer30`|`0x127C000`|`0x22D344`|`0x22D400`|R-X|6.459|**0/558**|
|8|`packer40`|`0x14AA000`|`0x75330`|`0x75400`|RW-|6.570|28/118|
|9|`packer31`|`0x1520000`|`0x2A48628`|`0x2A48800`|R-X|6.089|**0/10825**|
|10|`packer42`|`0x3F69000`|`0xFC5DC`|`0xFC600`|RW-|5.357|0/253|

### ★ It is NOT packed — four independent controlled tests
1. **Linear disassembly sweep.** `packer31` at three widely separated offsets → **0.00 %
   invalid bytes** (0–2 per 200,000); mnemonic histogram `mov 13.6k / not 6.7k / and 6.6k /
   imul 5.3k`. *Controls* `packer0` and `.rsrc` (known ciphertext) → **5.25 % / 5.52 %**
   invalid with a *flat* histogram. Two different populations, not a threshold judgement.
2. **Dedup.** `packer31` = 10,824/10,824 unique 4 KiB blocks; longest identical-byte run = 8.
   Not filler, not padding.
3. **Prologue census.** The prologue `41 57 41 56 41 55 41 54 56 57 55 53 48` occurs **7,190**
   times against **7,197** `packer31` functions in the loader table.
4. **Character of the obfuscation.** `not`/`and`/`imul` ≈ 43 % of instructions = **MBA
   (mixed boolean-arithmetic) obfuscation**; `packer30` is `call`-heavy with every `jcc`
   flavour ≈1,000× = opaque predicates. **Native obfuscation, not a bytecode VM** — which
   independently corroborates R1.

⇒ **The protector encrypts the protectee, not itself.** Game exe `.text`: 100 % ciphertext.
Protector code: 0 %. Shared fingerprint: both leave `.reloc` at 0 %, both EV-signed 6 s apart.

### The "~48 MB at entropy 5.3–6.6" claim — resolved as an exact subtotal
`packer30 + packer40 + packer31 + packer42` = **48,133,632 B**, entropies **5.36–6.57**.
The prior figure measured *only the four protector-appended sections* and omitted the 19.3 MB
where all the encryption lives (`packer0` 7.99, `packer1` 7.20, `.rsrc` 8.0000). The old claim
was right about the code and wrong about the file — another instrument-scope artifact.

### ★ Two exception tables — and the build pipeline they reveal
The `.pdata` *section* (`0x1000`, 1,854 functions, `packer1` only) is **vestigial; the loader
never reads it**. `DataDirectory[3]` points instead to **RVA `0x14D8758` in `packer40`,
222,960 B, 18,580 functions** covering 45.1 MiB (`packer1` 1,774 / `packer30` 9,609 /
`packer31` 7,197). Sizes: median 186 B, p90 7,844 B, max 259,180 B.

Diffing the two tables cracked the build pipeline: exactly **80** original functions are absent
from the loader table, and **80/80 begin with a 5-byte `E9 jmp` into `packer30`** — no
exceptions. The bytes after those jumps measure entropy **7.9835** (vs 6.6666 for in-place
bodies; random control 7.9991), i.e. the vacated bodies are random filler.
**386,883 B of original code → 46,533,713 B of protector code: a 120.3× expansion, 80 functions
→ 16,806.** `packer1`'s 18.5 % "encrypted" pages are these 80 holes, not encryption.

### `.rsrc` — 6 leaves, no plaintext embedded PE
| type | name | size | H | identification |
|---|---|--:|--:|---|
|RT_DIALOG|101|832|3.31|"Crash Report Handler"|
|RT_DIALOG|111|360|3.06|"Hardware Tester"|
|RT_RCDATA|**10001**|393,178|7.999|**Zstd frame** → decompresses to **579,410 B**; leading literals are DER X.509 ⇒ **[I]** the mbedTLS root-CA store — *the mechanism that bypasses `cacert.pem`*|
|RT_RCDATA|**10100**|5,542,856|**8.0000**|encrypted|
|RT_RCDATA|**10150**|3,685,668|7.9999|encrypted|
|RT_MANIFEST|1|867|5.00|XML|

10100/10150 share the constant `ED D9 31 02 26 65 E2` at **+4** with a length at +0;
χ² = 249.9 / 261.5 against ~255 expected ⇒ **encrypted, not compressed**; **0 duplicate
8/16/32-byte blocks** across 9.2 MB ⇒ a stream/CTR/CBC mode, not ECB.
⚠ **Bounded negative:** a whole-file MZ→PE scan finds exactly 1 hit (its own header); controls
on `preloader.dll` / `steam_api64.dll` return 1 each, so the scanner works. There is **no
*plaintext* embedded PE — but a driver inside 9.2 MB of ciphertext is NOT excluded.**

### Entry surface
No exports. **No TLS directory at all** — the usual packer TLS-callback trick is unused.
`.rwx` is **4,096 bytes of `0x00`**, verified byte-exact: a scratch page, not code at rest.
`AddressOfEntryPoint = 0x855440` is one of the 80 relocated functions — a lone
`e9 4a cf b3 00` → **`packer30:0x139238F`**, a 54,233-byte routine that saves all 8 GPRs *and
all 10 non-volatile XMMs*, takes a 1,912-byte frame, aligns `rsp` to 64, then jumps past inline
junk. `packer31` opens with a 5-byte-stride `jmp rel32` thunk table.

*Positive controls for every absence above:* the same parser reads 1,059 exports
(`steam_api64`), 689 exports + 1 TLS callback (game exe), 239 (`tbb`), 2 (`preloader`), and
Rich headers in 2 of 5 binaries. `runtime.dll`'s zeros are real.

### C5 resolved — it is manually mapped **and** enumerable
The exe imports exactly one DLL (`preloader.dll`); preloader holds the UTF-16 string
`runtime.dll` and imports `NtCreateSection`, `NtMapViewOfSection`, `NtProtectVirtualMemory`,
`LdrGetProcedureAddress`, `ZwCreateThreadEx` — and **no `LoadLibrary`/`LdrLoadDll`**. So
`runtime.dll` is manually mapped (absent from crashpad's PEB loader list) but still
**file-backed via `SEC_IMAGE`**, hence nameable by anything enumerating `MEM_IMAGE` +
`GetMappedFileName` — which is why UE's own ModuleList names it. The map's *"not even
enumerable as a module"* is the wrong half of a true statement.

---

## 4. The game exe — selectively encrypted in place, not wrapped

Per-4 KB-page entropy, threshold H ≥ 7.90. *Positive control:* the same scanner reads `.data`
at H = 3.38 and finds directly readable content in plaintext windows — e.g.
`6e64696e674172726179` = `"ndingArray"`, `456e67696e6540414b404059413f4157` = a mangled C++
symbol. It is not saturating.

| section | pages | encrypted | enc % |
|---|---:|---:|---:|
| `.text` | 30,281 | 30,281 | **100.0 %** |
| `.pdata` | 1,534 | 1,534 | 100.0 % |
| `_RDATA` | 94 | 94 | 100.0 % |
| `.rsrc` | 15 | 13 | 86.7 % |
| `.rdata` | 9,085 | 2,549 | 28.1 % |
| `.data` | 826 | 58 | 7.0 % |
| `.reloc` | 700 | **0** | **0.0 %** |

`.text` is uniformly ciphertext end to end — 12/12 contiguous 64 KB probes read H =
7.9967–7.9978, zero-fill 0.34–0.43 %. No plaintext island anywhere in it.

**The design is loader-aware, and the IAT proves it is deliberate:**

| data directory | RVA | H | state |
|---|---|--:|---|
| IMPORT | 0x09C4C180 | 1.569 | PLAINTEXT — loader **reads** it |
| BASERELOC | 0x0A725000 | 5.441 | PLAINTEXT — loader **reads** it |
| TLS | 0x093B1C80 | 6.846 | PLAINTEXT — loader **reads** it |
| LOAD_CONFIG | 0x09364D20 | 7.232 | PLAINTEXT — loader **reads** it |
| **IAT** | 0x0764A000 | 7.956 | **ENCRYPTED** — loader only **writes** it |

Every directory the loader reads is plaintext; the one it merely overwrites is encrypted. That
is a build-time tool with a precise model of the OS loader — not a wrapper.

**Two consequences:**
1. It explains the long-documented **demand-decrypt** behaviour: `.text` is 100 % ciphertext at
   rest, so pages become readable only once the process faults on them.
   ⚠⚠ **"necessarily … only as they execute" is RETRACTED (S121, 2026-08-14).** That was an
   inference from the encryption model, not a measurement, and it is one of three mutually
   inconsistent restatements the repo carried. MEASURED live: dark pages are **`PAGE_NOACCESS`**
   (14,609 of 30,281), which faults on **read, write AND execute** — so "only as they execute" is
   not entailed by anything here. The read-vs-execute filter is **OPEN**; see
   `docs/fk18-fk19-multistate-merge-settled.md` §12 for the mechanism and the pre-registered probe.
2. **22.8 MB of `.rdata` is plaintext ON DISK**, in 47 runs of ≥64 KB (first at RVA
   0x0764C000–0x0768D000). Static string work against the on-disk exe is viable over that
   region — and a scan seeing this plaintext/ciphertext *mixture* is very likely the true
   origin of the old FK-4 false-known ("the packer decrypts strings to the heap").

### ⭑⭑ Cross-track finding: the game exe's exception directory is ZEROED
**MEASURED, with four controls:**

| binary | `EXCEPTION` RVA | size | `.pdata` section |
|---|---|--:|---|
| **SUPERVIVE-Win64-Shipping.exe** | **0x0** | **0** | present, raw = 6,283,264 (1,534/1,534 pages encrypted) |
| runtime.dll | 0x14d8758 | 222,960 | present |
| tbb.dll | 0x34000 | 10,716 | present |
| steam_api64.dll | 0x46000 | 9,084 | present |
| preloader.dll | 0x6000 | 156 | present |

The game ships a 6.28 MB `.pdata` section holding ~523,605 functions' worth of unwind data —
**encrypted, unsorted, and unreachable, because the directory pointing at it is zeroed.**

**[I] `RtlLookupFunctionEntry` therefore returns nothing for the main image**, so the OS cannot
unwind through game code unless the protector registers a table at runtime. That is a
materially better explanation for CLAUDE.md's standing rule *"never propose another
C++-exception-using payload"* than the recorded mechanism ("the packer's VEH kills the
process"): **a missing function table kills all three canaries identically.**
⚠ **The rule STANDS; only its stated mechanism is in doubt.** One cheap probe settles it: call
`RtlLookupFunctionEntry` on a known game `.text` address from an injected shim and log whether
it resolves.

---

## 5. Wall #7 — the xxHash lead is SPENT; the replacement has an address range

The ignorance map's recommended next step for Wall #7 was literally *"Hunt xxHash/Zstd
constants in `.rdata` (FK-10 names the algorithms)."* It was run. **The inference is falsified.**

*Controls first:* 49/49 planted constants recovered; a synthetic 30,281-record page table was
detected by the same scanner; the section-name matcher finds `.pdata`/`.rsrc`/`.reloc` in real
headers. And `runtime.dll` is plaintext on disk (§3), so **its negatives mean something** —
unlike the game exe's.

**Found:** the full XXH3 `kSecret` (192 B) at RVA **`0x9c00`** (packer0) plus 3 partial copies;
all 10 xxHash primes; XXH3 `PRIME_MX1/MX2` 63/48 hits; Zstd frame + skippable magics in
`packer1`. Routines identified exactly: `XXH64_round 0x8eb250`, `mergeRound 0x8d98b0`,
`finalize 0x8ed920` (rol27×P1+P4 / rol23×P2+P3 / rol11×P1 — textbook), `digest 0x889b20`,
stripe loop `0x8fb340`, one-shot `0x8200f0`.

**But the one-shot has exactly ONE caller:** `0x8f9dd0`, which tests
`(dword & 0xFFFFFFF0) == 0x184D2A50` and uses a `[rbx+0x7598]` context — **Zstd's decompressor.**
⇒ **xxHash in this binary is Zstd's frame checksum. It is not the integrity hash.**
*(Scope: direct `E8`/`E9` call edges only; `packer30/31` are obfuscated, so an indirect caller
is not excluded.)*

### The likely engine, with an exact range to disassemble
SHA-256 IV ×7, SHA-256 K ×4, SHA-1 IV ×3 and the MD5 T-table cluster in `packer2`
**`0x942740–0x9467e0`**, including **two back-to-back SHA-256 IVs** — the signature of **lane
packing**. Tracing those tables lands on `AVX2 vmovdqu ymm12` loads and MMX `movq mm7` at
`packer1` **`0x933982–0x93b7b0`**, plus a **16-entry `cmovne` job-selection ladder**, all inside
a **`.pdata`-free executable tail at RVA `0x8ffcd4–0x93e886`, 251 KB, entropy 6.547**.

**[I] That is Intel ISA-L Crypto multi-buffer assembly** — which ships as hand-written `.asm`
and therefore carries no unwind records, exactly explaining the `.pdata` hole. ISA-L was the
BOM component the ignorance map missed (§2).

**A 16-lane multi-buffer page hasher fits every measurement**, including two the project could
not previously reconcile:
- `.text`-only lethality; heap/bytecode writes free (0/9) — only `.text` has a baseline.
- the dose-response (0 writes 0 % · 3 transient 33 % · 1 standing 88 %, commit `67b19c1`, whose
  own conclusion is *"cost ~ .text write volume × standing time"*).
- ★ **the NEGATIVE Rayleigh periodicity result** (N=91, bootstrap p=0.414, working positive
  control). A periodic timer that hashes a *subset* of pages per pass yields
  `period × Geometric(p)` detection times — **aperiodic, long-tailed**, which is exactly the
  measured 87–524 s spread that no `T+<n>` rule has ever fitted.
  ⇒ **The correct claim is not "the check is not periodic". It is "the check does not verify
  all of `.text` on every pass."** That is materially different and it reopens a closed line.

### Honest negatives, each controlled
- **No `.text` section-name walker found.** The literal `.text` appears **0** times anywhere in
  `runtime.dll` (matcher verified against real headers). The module's *only* `e_lfanew` read
  (`0x8e9a2f`) belongs to `0x8e9980`, an `NtProtectVirtualMemory` wrapper that **refuses to
  reprotect its own image** (`0xC000004E`) — self-defence, not the checker.
- **No stored hash table on disk at any stride** (control: a synthetic 30,281-entry table *was*
  detected). This is *expected rather than disconfirming*: the exe's `.text` is ciphertext at
  rest (§4), so any plaintext baseline must be **built after decryption, at runtime** — which
  also neatly explains why a *self-restoring* patch still dies (the baseline was taken clean and
  the sampler runs asynchronously).
- **MinHook/HDE64:** `hde64_table` is **byte-exact** at `packer0 0x7c6a10`, sole consumer at
  `packer30 0x132a8ee`. Hooks not yet enumerated.

### The poison jump — partial
`base+1` is referenced **399×**, always as `movzx byte` → `and 2` → `add` into a syscall gadget:
a gadget selector fused with an MZ-tamper check. `base+0` is `lea`'d 38× (`__ImageBase`).
**No instruction anywhere forms `base+1` as an address**, so what supplies it as a thread start
routine is still unidentified. `HMODULE|1` (the `LOAD_LIBRARY_AS_DATAFILE` tag) remains the best
hypothesis and is **untested**.

Supporting context (S109, MEASURED across 3 dumps / 3 launches / 2 dumpers / 4 ASLR bases):
the fault is a **thread entry**, not an inline jump — `ExceptionInformation = [0x8, addr]`
(DEP/execute), `rax rcx rsi r12 r13 r14 r15` all zero, `rbx == r10`, `rdi == rsp`,
`[rsp] = KERNEL32+0x17374`, 40 bytes of zero, `[rsp+0x30] = ntdll+0x4CC91`, **0 game frames** —
the canonical `BaseThreadInitThunk` → `RtlUserThreadStart` frame. And the process holds a
pristine `Type=IMAGE`, `PAGE_READONLY` mapping of size `0xA9E1000`, which I confirmed from the
PE header is **exactly** the game exe's `SizeOfImage` — a reference copy of the game image.

---

## 6. ★ FK-32 CLOSED on mechanism — `0x0000DEAD` is the protector killing the process

**MEASURED — `runtime.dll` RVA `0x80f7f0`:**
```asm
mov  r10, [rcx+0x10]
test ...; jz  ret0
<obfuscated syscall number>
mov  edx, 0xDEAD
syscall                  ; = NtTerminateProcess(handle, 0xDEAD)
```
Reachable only via a NULL-bounded **5-entry pointer table** at `packer0 0x1831c0`, whose **4th**
entry is `NtCreateThreadEx(&h, THREAD_ALL_ACCESS, NULL, -1, …)` and whose **5th** is this killer.

**`preloader.dll` is eliminated as the silent killer** (control: `0x0000DEAD` occurs **0** times
in preloader, **twice** in runtime.dll). Preloader's own `NtTerminateProcess` passes NTSTATUS
codes (`0xE1110000`, `0xC00004C2`, `0xC0000017`, `0xC000003A`) and **always MessageBoxes first**.

⇒ The artifact-less `0x0000DEAD` death class is **the protector deliberately terminating the
process**, not a hang and not our code. This resolves the FK-32 mechanism; what *triggers* it
remains open, and the 5-entry table plus `NtCreateThreadEx` neighbour is the thread to pull.

---

## 7. What to call it now — and what NOT to do

**The label to propagate: *"a bespoke protector that self-identifies as `packer/3.3.1`;
vendor unidentified."***

The internal product name is literally **"Packer"**. Neighbours of the DSN string at
`0x007C1BEC` include **`Packer/1.0`** (`0x7C2F90`, a User-Agent), **`Packer`** (`0x7C4740`),
and — pleasingly — **`You aren't supposed to be here`** (`0x7C5BB0`), plus `dbgcore.dll`, a
Windows-SDK-debuggers download URL, and an `srcsrv` path.

**Confidence, stated honestly:**
- "not VMProtect / not Themida / not a commercial packer" — **HIGH** (six independent grounds).
- "self-identifies as `packer/3.3.1`" — **HIGH** (measured string, replicated).
- "built from the components in the BOM" — **MEDIUM-HIGH**.
- "Theorycraft in-house *versus* contracted/bespoke-for-them" — **MEDIUM only.** A small vendor
  could ship a per-customer build carrying the customer's DSN and signature.

⚠ **Do not substitute a second vendor name.** Replacing one unfounded label with another is the
exact failure FK-10 exists to correct. "Vendor unidentified" is the accurate state.

---

## 8. Cheapest next steps, ranked

1. **Offline, no game needed — disassemble `0x8ffcd4–0x93e886`** (251 KB) and find its callers.
   That should yield the page-feed loop and the comparator, i.e. Wall #7's mechanism.
2. **Offline — disassemble `packer30` first** (2.2 MB; holds the entry function and the four
   largest functions; `call`-structured rather than MBA-saturated). Feed the disassembler the
   loader table at **RVA `0x14D8758`**, *not* the stale `.pdata` section. All sampled
   `UNWIND_INFO` is Version 1 and valid, so IDA/Ghidra will get correct frames.
3. **Read-only RPM, 26 dwords** at `runtime_base+0x94a6d8…0x94a824` (`packer2`). All 155 syscall
   stubs compute `sysno = ROL32(K1^key,7)+K2` and **all decode to `0xFFFFFFFF` on disk** — they
   are runtime-patched. Reading them live names every syscall the protector makes and confirms
   `0x80f7f0`.
4. **One shim probe:** call `RtlLookupFunctionEntry` on a known game `.text` address and log
   whether it resolves — settles §4's exception-directory mechanism.
5. **Two free instruments nobody is using:** `%TEMP%\SUPERVIVE_SUPERCODE.DAT` (exists, 0 bytes)
   and `SUPERVIVE_COMPATIBILITY_LOG.DAT`. The Diagnoser reads both back.
6. Re-run every scanner against a **live** `usmapdump dumpimage` of `runtime.dll` — `packer0`'s
   4.4 MB high-entropy run and the 9.2 MB `.rsrc` are genuinely unmeasured.

---

## 9. Ancillary results from this pass

- **`SUPERVIVE.exe` is stock Unreal `BootstrapPackagedGame-Win64-Shipping.exe`** with
  Theorycraft's switch block compiled in. **9/9 suspected switches confirmed + 3 new**
  (`-FactoryResetAllEACGames`, `-UninstallEAC`, `-ReinstallEAC`); **5/5 env vars confirmed + 8
  new**, incl. `SUPERVIVE_SET_PACKER_TAGS`, `SUPERVIVE_COMPUTER_NAME`,
  `EOS_USE_ANTICHEATCLIENTNULL`, `DUMPER_KV_*`, and
  `SUPERVIVE_EAC_PRODUCT_IDENTIFIER = 12eabb84b13b400fbbd96ec576bc555a`.
- **EAC is genuinely ABSENT** (control-backed: the same greps find `steam_api64.dll` and all 8
  Win64 manifest entries). `-NoEAC` / `-NullEAC` are dead levers.
  Most promising untested lever: **`PACKER_CRASH_FLAGS=skip_uef`** (string at `0x16AD0`, sitting
  between `-NoSentry` and `PACKER_CRASH_FLAGS`) — plausibly disables the packer's unhandled
  exception filter. **Adjacency-inferred, not disassembled.**
- **`preloader.dll`: "ntdll-only imports" is REFUTED** — 52 imports across ntdll (43), USER32
  (8), GDI32 (1: `Pie`, a module-anchor decoy; `runtime.dll` uses `CloseEnhMetaFile` the same
  way). Fully unpacked (`.text` 6,198 B at H = 5.46) and **disassemblable today**. Its ordinal-1
  export *name* is a 256-bit hex token
  (`/* 758006cd4e6979455628cd475a97f5b98258f9beb7243814801800b64ee5420c */`, `.rdata` 0x2CC6),
  present only in preloader and **not** the SHA-256 of any of the five binaries — **[I]** a
  preloader↔runtime pairing token. Internal name `preloader.unsigned.dll`; ord 2 =
  `preloader_link_func`.
- **`SUPERVIVE-Diagnoser.exe` is a REPORTER, not a DETECTOR** (control-backed: 116 imports
  across 6 DLLs resolved, yet **zero** toolhelp / `EnumProcesses` / `NtQuerySystemInformation` /
  psapi / WMI). It reads back artifacts the protector wrote — so its vocabulary *is* the
  protector's, quoted by its own tool. **7 detection categories** in a contiguous UTF-16
  `.rdata` table (`0x40648→0x40990`): *Incompatible tools are running concurrently with the
  game* · *Missing Hyper-V Installation Component* · *Hyper-V Generic Incompatibility* ·
  *virtual environment* · *debuggers* · *A hardware error was encountered* · *hypervisor*, plus
  `*UNSET*` / `*UNKNOWN*` and the titles *Compatibility Error* / *Critical Engine Error*.
  Hyper-V gets three distinct codes, and "virtual environment" ≠ "hypervisor".
  **There is no embedded cheat/debugger blocklist** (control: the same scanner found
  `CrowdStrike` and all 537 UTF-16 strings). The **only** product named anywhere is
  **CrowdStrike** (`SOFTWARE\CrowdStrike`, ANSI, 0x40630, with an RT_STRING recommending
  ML/Sensor-Visibility exclusions for the three protected binaries).
  It also carries `DLL Load Failure Log (unsigned file):` + `Logged DLL Path` (0x41900/0x41960)
  — **the protector logs unsigned DLL paths.**
- **An embedded X.509 DN for `Nvidia Corporation` / `Santa Clara` / `California`** at
  `runtime.dll 0x181EB0` — **[I]** a pinned publisher allow-list.
- **Every behavioural string in these binaries is UTF-16LE.** An ASCII-only scan finds
  essentially nothing (preloader: 1 of 6 cited strings; `runtime.dll`: its 249,822 "ASCII
  strings" are dominated by 7,197 copies of the token `AWAVAUATVWUSH`, which is a **function
  prologue, not text**). `packer1`/`packer30`/`packer31` contain **zero** real plaintext strings.

---

## 10. Corrections this pass makes to the project record

| claim | where | correction |
|---|---|---|
| "imports are VMProtect/Themida-PROTECTED" | `CLAUDE.md:513` + 23 other sites | **REFUTED** — bespoke `packer/3.3.1`, vendor unidentified |
| "`runtime.dll` is packed" | FK-10, `coverage-audit-s101.md:286` | **REFUTED** — 46.6 MB plaintext obfuscated code; only data/resources are encrypted |
| "~48 MB at entropy 5.3–6.6" | FK-10 | Exact subtotal of the 4 appended sections; the file is 67,511,496 B and 19.3 MB of it IS encrypted |
| "22,248-byte plaintext `.pdata`" | FK-10 | That is the **vestigial** table's VirtualSize; the loader uses a 222,960 B / 18,580-entry table at RVA `0x14D8758` |
| "`preloader.dll`, ntdll-only imports" | FK-10 / C7 | **REFUTED** — 52 imports across ntdll + USER32 + GDI32 |
| "not even enumerable as a module" | C5 | Wrong half — manually mapped **but** `SEC_IMAGE` file-backed, hence nameable |
| "`.rsrc` is 9.62 MB" | C14 | That figure is `.rsrc`+`.reloc`; `.rsrc` alone is `0x92DA60`. Contents now enumerated; no plaintext embedded PE |
| "Hunt xxHash — FK-10 names the algorithms" | Wall #7 | **Lead SPENT** — xxHash here is Zstd's frame checksum. Successor: ISA-L multi-buffer SHA at `0x8ffcd4–0x93e886` |
| "no string names the integrity check — CLEAN NEGATIVE, not coverage-blocked" | `fk3-fk4-settled.md:513`, `strxref-open-questions.md:321` | **Scope error — 20th instrument-artifact instance.** `strxref.py:63` hardcodes `merged.dump.exe` (the *game exe*); `runtime.dll` appears 0 times in either doc. The negative structurally excluded the protector |
| "the packer's VEH kills exception-using payloads" | `CLAUDE.md` | ⚠⚠ **BOTH halves of the mechanism are now REFUTED (S121, 2026-08-14).** (a) **There is no protector VEH.** `LdrpVectorHandlerList` decoded with the live cookie holds **exactly one** entry — the exe's own `cmp [rax],0xC0000374` heap-corruption handler. The protector hooks `KiUserExceptionDispatcher` via a **ProcessInstrumentationCallback** instead, leaving ntdll byte-identical to disk. (b) **`RtlLookupFunctionEntry` DOES resolve for the main image.** The static `EXCEPTION` dir is RVA=0/size=0, but the protector registers a **dynamic function table of 524,439 `RUNTIME_FUNCTION`s** covering `.text 0x8a00–0x7649f39` (sorted, 0 out of order), with **29,688 language handlers across 48 distinct handlers, all inside the exe** (top: `__C_specific_handler` ×26,219). ⇒ the rule *"no C++-exception payloads"* **STANDS empirically but now has NO known mechanism.** Do not cite the missing-function-table explanation. |
| FK-32 `0x0000DEAD` unattributed | `fk31-fk32-successors.md` | **Mechanism CLOSED** — `NtTerminateProcess(h, 0xDEAD)` at `runtime.dll 0x80f7f0` |
