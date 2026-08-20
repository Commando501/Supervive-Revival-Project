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

> ★ **ADDENDUM — S132, 2026-08-20. Read §6b.** A second fully-offline pass (zero launches, zero
> injections) re-verified this file's core structural claims against the on-disk `runtime.dll`,
> **found the kill primitive's owning object and its constructor**, and mapped the protector's
> **computed-tail dispatch architecture** — which hands FK-31's `runtime.dll base + 1` fault a
> mechanism class. It also **sharpens two grades in this file** (§5's poison-jump negative and §6's
> `NtTerminateProcess` identity). Nothing in §1–§4 is disturbed. Raw:
> `scratchpad/s132/lanes/L6-fk31-runtime-selfbase.md` + its `-VERIFY.md`.

---

## 0. TL;DR for the next session

| question | answer |
|---|---|
| Is it VMProtect or Themida? | **No.** Six independent refutations, HIGH confidence |
| What is it? | Internally named **"Packer" v3.3.1**; first-party Theorycraft; **vendor unidentified** (deliberately not renamed — see §7) |
| Is `runtime.dll` packed/encrypted? | **No.** 46.6 MB of **plaintext obfuscated x86-64**. Its *data* and *resources* are encrypted; its *instructions* never are |
| Can we disassemble the protector? | **YES, today, offline.** Use the loader function table at RVA `0x14D8758` (18,580 entries) — **not** the vestigial `.pdata` section |
| Is the *game exe* packed? | Not in the wrapper sense — **stock section layout, selectively encrypted in place**. `.text` 100 % ciphertext at rest |
| Wall #7 (the integrity check) | **Not located, but the search is now narrowed to a 251 KB address range** and the old xxHash lead is spent (§5). ★ **S132: stop xref-hunting it** — decode the computed tails instead (§6b.4, §6b.6, §8 step 0) |
| FK-32 (`0x0000DEAD` deaths) | **CLOSED on mechanism** — it is the protector deliberately calling `NtTerminateProcess(h, 0xDEAD)` (§6). ★ **S132 found the OWNING object + its constructor `0x7F86F0`** (§6b.6) — the closest lead yet to the *trigger*. ⚠ the `NtTerminateProcess` *identity* is [I], not [M] (§6b) |
| FK-31 (`runtime.dll base + 1` deaths) | **S132 gives it a MECHANISM CLASS** — `live_base + 1` is the native output of the protector's computed-tail dispatch on a null target RVA (§6b.4–§6b.5). **[I]** |

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

⚠⚠ **"No instruction anywhere forms `base+1` as an address" is TOO STRONG AS WRITTEN — sharpened
S132, 2026-08-20 (§6b).** An independent offline re-scan of all **48,129,536 executable bytes** of
`runtime.dll` reached the same conclusion for **64-bit literal immediates**, and then its own
adversarial verifier **refuted the general form**: at `packer31` RVA **`0x03C8EDF2`** an MBA block
computes **`[rsp+0x158] + ImageBase + 1`** (verified by concrete evaluation over 2,000 random
inputs, 2000/2000) and the result **is dereferenced** at `0x03C8EFF3 movzx r12d, byte ptr [r9]`.
The `+1` there is produced *by the polynomial*, not by an immediate, which is exactly the blind
spot a literal-constant scan has. ⇒ **The defensible negative is: "no 64-bit literal immediate
equal to ±(ImageBase+1) survives adjudication as an operative address constant."** The open
question — *what supplies `base+1`* — is unchanged, but §6b gives it a **mechanism class** for the
first time. ⚠ The role of the `0x03C8EDF2` site is **[S]**, not the kill: its surrounding
`test byte ptr [rsp+0x28],1` / `cmove` shape is the MSVC inline-buffer idiom, so a biased pointer
(`stored = ptr − IB − 1`) is the likelier reading.

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

⚠ **GRADE SHARPENED S132 (see §6b): the BYTES are [M]; the `NtTerminateProcess` IDENTITY is not
derivable from this file.** The syscall *number* is `ROL32(0x618E77BF XOR *(dword*)0x94A800, 7) +
0x6710C747`, and the on-disk `packer2` cookie is `0x10BFA9CE`, which evaluates to **`0xFFFFFFFF`** —
not a valid service number. `packer2` is `RW`, so the cookie is patched at runtime. **All the file
supports is `Nt???(HANDLE from [this+0x10], 0xDEAD)`** — a shape `NtTerminateThread` also has.
The `NtTerminateProcess` reading is an annotation inside a MEASURED block, not a measurement; it is
almost certainly right (a thread kill would not end the process) but it should be graded **[I]** and
settled by the live read already listed at §8 step 3. ★ Useful side effect: that `0xFFFFFFFF` is
**positive evidence** the number really is computed at runtime — which is why no syscall-number scan
ever found these stubs.

---

## 6b. ★★ S132 (2026-08-20) — the kill primitive's OWNER, and the protector's dispatch architecture

**Fully offline. Zero launches, zero injections, zero `.text` writes.** Two independent agents: a
recon lane and an adversarial verifier that re-derived every number with its own PE parser and its
own scanners rather than re-running the lane's. Raw:
`scratchpad/s132/lanes/L6-fk31-runtime-selfbase.md` and `…-VERIFY.md`
(scripts in `scratchpad/s132/l6/` and `scratchpad/s132/verify/l6/`).
Verifier scoreboard: **20 load-bearing claims CONFIRMED · 7 REFUTED · 3 UNSUPPORTED · 1
degenerate control.** Both the refutations and the confirmations are recorded below.

### 6b.1 The target, located and identity-confirmed [M]

```
G:\git\GAME BACKUPS FOR REVERSE ENGINEERING\SUPERVIVE\Loki\Binaries\Win64\runtime.dll
67,511,496 B   md5 5e73e00ab52bc8f30574d8c023a84171
ImageBase 0x200000000   SizeOfImage 0x4066000   AddressOfEntryPoint 0x855440
EXCEPTION dir RVA 0x14D8758 size 0x366F0 = 222,960 B = 18,580 x 12
```

Found via `configs/launch-redirect.ps1:46` (`$GameRoot`), i.e. **the file the launcher actually
uses**. Identity probe: the `packer/3.3.1` Sentry DSN is **byte-identical at file offset
`0x7C1BEC`** — the exact offset §1/R5 recorded. ⇒ **this file is the one §3 measured**, so every
structural claim in §3 now has a second, independent confirmation: the 11-section map, the
vestigial `.pdata` vs the 18,580-entry loader table (`Begin` strictly increasing, 0 all-zero,
split `packer1` 1,774 / `packer30` 9,609 / `packer31` 7,197), the all-zero 4,096-byte `.rwx`, and
the entry point `0x855440 → jmp 0x139238F` into a 54,233-byte flattened function.

**Executable total scanned = 48,129,536 bytes** (`.rwx` + `packer1` + `packer30` + `packer31`).
★ **That is the denominator for every negative in this section — quote it whenever one is cited.**

### 6b.2 ⚠⚠ THE INSTRUMENT LIMIT THAT GOVERNS ALL CONSTANT WORK IN THIS BINARY [M]

```
ImageBase == 0x200000000 == 2^33
```

The obfuscator is MBA-based and does heavy **bit-33** arithmetic — `shl reg,0x21`, masks of
`0x200000001`, constants `0xFFFFFFFE00000000 = -2^33`. **Every one of those aliases exactly with
`± ImageBase`.** ⇒ *"is this constant the ImageBase?"* is **not a decidable test in this binary**;
each hit must be adjudicated by its **consuming instruction**, never by its value.
★ **This is a property of the TARGET, not of the tool** — no better scanner fixes it.

⚠⚠ **But do NOT restate that as "the constant-search method is defeated."** The lane wrote exactly
that and its verifier **REFUTED it with a count**: over the same 48,129,536 bytes the bit-33
population is `movabs r64, 0x200000001` **×10**, `movabs r64, −(0x200000001)` **×3**,
`movabs r64` within ±4 of `−2^33` **×10**, `shl r64,0x21` **×9**. **A few dozen sites — every one
individually adjudicable, which is what the lane then did.** Nothing swamps anything. And the
search *was* decisive: it produced the `0x03C8EDF2` hit (§5, poison-jump annotation) that the
adjudication then mis-scored. ⇒ **The correct rule is "each bit-33 hit needs individual
adjudication", not "the method does not work."** *(Recorded because "the method is defeated" is
precisely the shape of a foreclosed technique — `docs/method-rules.md` §1.)*

### 6b.3 What was refuted as the `base+1` source, each with its own evidence [M]

| candidate | verdict | evidence |
|---|---|---|
| a relocated qword equal to `ImageBase+1` | **REFUTED** | full `.reloc` parse, 4,268/4,268 bytes consumed → 2,020 `DIR64` + 10 `ABSOLUTE`; **0** DIR64 values anywhere in `[IB, IB+0x1000)` |
| a literal `0x0000000200000001` qword in data | **REFUTED** | 17 file-wide; the one 8-aligned writable instance (`packer2 0x941900`) is a `{1,2}` dword pair inside **MSVC CRT `__isa_available`** CPU detection (`cpuid` ×3, `xgetbv`, all three `GenuineIntel` dwords at `packer1 0x84B030..0x84B1DC`) |
| a poisoned loader-table entry (`RVA == 1`) | **REFUTED** | all 18,580 `RUNTIME_FUNCTION`s: **0** with any field `== 0` or `== 1` |
| an MZ/PE self-locate walking back to the DOS header | **REFUTED**, controlled | `imm32 4d5a0000` **0** · `50450000` **0** · targeted `cmp word [reg],0x5A4D` **0** · **positive control** `imm32 0000ffff` **123**. Strengthened by the verifier: all **60** raw `4d 5a` byte pairs in exec sections sit inside `movabs` immediates |
| the 13 `movabs ±(ImageBase+1)` sites | **refuted as literal constants** | 9 of the 10 positives are consumed by `and reg,<just-shifted value>` — a **two-bit mask** (bits 0 and 33), always preceded by a `shr`; the 10th is an `add` inside an MBA chain. ⚠ **See §5's annotation: one of the three negatives, `0x03C8EDF2`, is a real `x + IB + 1` computation whose result is dereferenced — the `+1` is produced by the polynomial, not the immediate.** |
| a generic "`+1` then `jmp reg`" marker | **REFUTED** | 4,749 `+1` sites × 22,877 register-indirect transfers → **406 paired hits, all in `packer31`**, all the `not`/`inc` two's-complement identity at the end of an MBA polynomial. Corroborator: only **244 of 4,769 (5.1 %)** computed-tail functions carry a same-register `+1` — a universal marker would be ~100 % |

⚠ **Two verifier corrections inside that table, both worth keeping.** (a) The lane wrote that all
three `−(IB+1)` sites have *"a `shl reg,0x21` in the immediately preceding instructions"* — **false
for `0x019DC131`**, whose preceding eight instructions contain no `shl` at all and whose constant is
adjusted by `add r9,2`. The generalisation was made from the two sites that were opened to the one
that was not. (b) The lane claimed the `+1→jmp` distance histogram **saturates** at its 40-byte
window, implying uncounted longer pairs — **it peaks at +29 and decays**, and re-running at `W=60`
moves 406 → 435. ⇒ that stated blind spot was **over**-stated, not under-stated.

### 6b.4 ★★★ THE POSITIVE FINDING — a computed-tail dispatch, with the address encoding decoded [M]

Classifying the **final** instruction of all 18,580 functions at exact `.pdata` extents:

| function ends in | count |
|---|---:|
| computed `jmp <reg>` | **4,769** |
| `ret` | 406 |
| `int3` | 97 |
| non-terminal / mid-stream byte | 13,308 |

By section: `packer1` **1,111** · `packer31` **3,658** · `packer30` **0**.
⚠ The lane's *register* split ("`jmp rax..rdi` 4,251 / `jmp r8..r15` 518") is **REFUTED** — 1,108 of
the 4,251 carry a `0x49` REX.B prefix; the true split is ≈3,143 / 1,626. The totals and the section
split reproduce exactly.

**Targets are carried as `movabs reg, −(ImageBase + target_RVA)` folded into an MBA polynomial.**
Worked example, function `0x0166E230..0x0166E50C`:

```asm
0166e3a2  mov    rax, rdi
0166e3a5  not    rax                            ; ~rdi
0166e3a8  movabs r8, 0xfffffffdfe995585         ; C
0166e3b2  imul   rax, r8
0166e3b6  inc    r8                             ; C+1
0166e3b9  imul   r8, rdi
0166e3bd  add    r8, rax                        ; (~x)*C + (C+1)*x  ==  x - C
...
0166e509  jmp    r8
```

`−C = ImageBase + 0x166AA7B`. **Prediction registered from the algebra, then tested: `0x166AA7B`
should be a real function start.** It is — an *exact* `.pdata` start carrying `packer31`'s
universal prologue. The identity `(~x)*C + (C+1)*x == x − C` was verified over 2,000 random `x` and
50 random `C`; the verifier independently confirmed `r8` has **no intervening write** between the
`add` and the `jmp`.

**At scale**, over every `movabs r64, imm64` in exec sections whose *negation* lands in
`[ImageBase, ImageBase+SizeOfImage)`: **940 constants, all in `packer31`** — **335 (35.6 %) are
exact `.pdata` function starts**, 353 land inside some function, 614 sit inside a computed-tail
function.

⚠⚠ **The lane's stated negative control was DEGENERATE and the finding survives anyway** — worth
recording as a method note. *"940 random qwords, same test → 0/940"* tests only the range filter
(a random qword passes it with p ≈ 3.7e-12), so it returns 0 whether or not the hypothesis is
true. **Replacement controls, all against the same 940-item hit set:** uniform random RVA in the
image → **0/940**; uniform random RVA within `packer31` → **0/940**; the same 940 targets shifted
`+0x4 / +0x10 / +0x1000` → **0 / 1 / 2**; shifted `+0x1` → 13. Against a 0.0275 % base rate,
**35.6 % is far above chance.** ⇒ finding **[M]**, its stated control worthless.

⚠ **Grade the population claim narrowly.** *"**The** jump target is carried as
`movabs −(IB+RVA)`"* is **[M] for one function** and **[I] at population scale**: only **168 of the
614** in-tail constants are materialised into the *same register the tail jumps through* (446 into a
different one; chance baseline ≈38 — a 4.4× enrichment, consistent with MBA register shuffling).
What is **[M] at scale** is the weaker and still-valuable claim: **these constants are addresses of
real functions.** ⚠ Also refuted: the lane's section split of the 605 non-exact targets omitted
`packer31`, which is the 4th largest bucket (`packer2` 213 · `packer1` 117 · `packer30` 112 ·
**`packer31` 85** · `packer40` 33 · `packer0` 34 · `.rsrc` 1 · unmapped 10).

**And the runtime `+ ImageBase` step is compiled in too** [M on the identity, [I] on its role]: the
`movabs reg, 0xFFFFFFFE00000000` (`−2^33`) sites are the same MBA identity computing
`variable + 2^33` = `variable + ImageBase`. Leads: `0x01DB0940`, `0x020DBB99`, `0x02C779CE`.
⚠ *"at 3 sites"* is a **literal-immediate floor**, not a count — at least 5, with 10 `movabs`
sitting within ±4 of `−2^33`.

### 6b.5 ⇒ What this hands FK-31 [I]

`packer31`'s constants encode **preferred** VAs (`ImageBase + RVA`) and carry **no relocation
entries** (all 2,020 `DIR64` relocs live in `packer0`/`packer2`), yet S131 measured the module live
at `0x7FFD3B400000`. So a runtime term supplies the delta:

```
jump_target = delta + (ImageBase + target_RVA) = live_base + target_RVA
```

⇒ **`live_base + 1` is the native output shape of this dispatch when `target_RVA` resolves to 1** —
or resolves to 0 with the tail's `inc` applied. That reframes FK-31: **the kill need not be a
bespoke crash primitive at all**; it is consistent with the protector's ordinary flattened dispatch
being handed a null/poisoned target, landing on its own read-only DOS header and faulting EXECUTE.
Matches every S131 measurement — `ExceptionInformation[0]==8`, the READONLY/MEM_IMAGE page, and the
per-boot constancy (the base is per-boot stable; the *offset 1* is constant because a null RVA is).

⚠ **[I], and the alternative is equally consistent:** the delta's storage is **not identified**, and
the protector's own manual mapper may instead apply a **custom fixup table** to these constants from
the encrypted `packer0`. Both routes predict the same output shape, so the FK-31 *consequence* is
robust to which is true — **the repair is not.**

### 6b.6 ★★★★ THE KILL PRIMITIVE'S OWNER — the concrete new lead [M]

§6's stub reproduced byte-for-byte, `0x80F804 + 0x13AFFC = 0x94A800` recomputed by machine, and the
`packer0 0x1831C0` table re-read as 5 pointers + NULL:

```
[0] 0x1831C0 -> RVA 0x871030   (reads [rcx+0x34])
[1] 0x1831C8 -> RVA 0x8D9480
[2] 0x1831D0 -> RVA 0x8B8B60   (large; saves xmm10.., 0x7C8 frame)
[3] 0x1831D8 -> RVA 0x8131D0   (writes [rcx+0x30]; same syscall-number decrypt idiom)
[4] 0x1831E0 -> RVA 0x80F7F0   <-- Nt???(handle@[this+0x10], 0xDEAD)   == §6's killer
```

**Exactly one** qword in the whole file equals `ImageBase + 0x80F7F0`, and it is slot 4 — which
independently validates the RVA↔file-offset mapping against §6's prior work. ⚠ Slot 3's identity
(§6 calls the 4th entry `NtCreateThreadEx`) rests on the **same runtime-decrypted syscall number**
and therefore carries the **same [I] caveat** as §6's annotation above.

★★ **NEW — the table's SOLE xref image-wide is a constructor at RVA `0x7F86F0`:**

```asm
007f86f0  push   rsi
007f86f1  sub    rsp, 0x20
007f86f5  mov    rsi, rcx                  ; ctor arg
007f86f8  mov    ecx, 0x38                 ; sizeof(object) = 56
007f86fd  call   0x896e00                  ; allocator
007f8702  lea    rcx, [rip - 0x675549]     ; -> 0x1831C0   <<< THE VTABLE
007f8709  mov    qword ptr [rax], rcx      ; obj->vtbl = table
007f870c  xorps  xmm0, xmm0
007f870f  movups xmmword ptr [rax+8], xmm0
007f8713  mov    qword ptr [rax+0x18], 0
007f871b  mov    qword ptr [rax+0x20], rsi
007f871f  mov    qword ptr [rax+0x28], 0
007f8727  mov    dword ptr [rax+0x30], 0
007f872e  mov    word  ptr [rax+0x34], 0
007f8739  ret
```

A **0x38-byte object wrapping a process handle at `+0x10`** (zeroed here, filled later) whose
vtable's last method terminates that process with `0xDEAD`.
⇒ ★★ **This is the object Wall #7 should be hunting the users of, and it is the closest anything has
come to FK-32's TRIGGER.**

⚠⚠ **AND IT EXPLAINS WHY DIRECT XREF HUNTING HAS FAILED FOR FK-10 ACROSS MANY SESSIONS:** the
constructor has **0 rel32 callers and 0 stored pointers**. It is reached **only through the
flattened dispatch of §6b.4.** The verifier extended the `disp32` sweep to three variants the lane
did not run (disp32 followed by imm8 / imm16 / imm32) and still found **exactly one** reference, so
the "sole xref" claim is *stronger* than reported. ⇒ **xref hunting is the wrong instrument on this
binary; decoding the computed tails is the right one.**

### 6b.7 ⚠ What this scan is structurally blind to — read before trusting any negative above

1. **`.rwx` (RVA `0x7000`, 4,096 B, `IMAGE_SCN 0xE0000060` = CODE|EXEC|READ|WRITE) is 100 % zero on
   disk**, and a `DIR64` reloc at `packer2 0x941908` points at it. **Any code the protector
   *generates* there at runtime is invisible offline, by construction** — and a generated kill stub
   is fully consistent with every negative in §6b.3. **This is the single largest blind spot.**
2. `packer0` (8.15 MB) and `.rsrc` (9.6 MB) are the protector's **encrypted data**. A dispatch
   table, custom fixup table or target-RVA array living there is unreadable — which is exactly where
   §6b.5's alternative sits.
3. **MBA expression of the `+1`.** The scanner sees `inc r64`, `add r64,1`, `sub r64,-1`,
   `add r64,imm32=1`, `lea r64,[r64+1]`. It **cannot** see a `1` carried in a register, a `1`
   produced by the polynomial, or `neg`/`not` pairs that net +1 across intervening instructions.
   With ~43 % of instructions being MBA this is a **real recall gap** — and it is the gap the
   `0x03C8EDF2` counter-example fell into.
4. **The rip-relative `disp32` sweep is a candidate GENERATOR, not an xref engine.** Measured
   false-positive rate: **712 candidates for 27 real `ff 15` uses** of IAT slot `0x8148` (~96 % FP).
   Over a zero-filled region it produces one hit per byte and is useless.
5. **`call`/`ret`-based transfers were not searched.** A kill implemented as a poisoned return
   address, or an indirect `call [reg+disp]` through a heap object, leaves no signature here.
6. **`packer30`'s 54 KB entry function was not decoded**, and linear disassembly of it is **not
   trustworthy** — it carries deliberate overlapping-instruction obfuscation (`test`-then-`jae`,
   where `test` always clears CF, jumping into the middle of a preceding instruction).

⇒ ★ **The honest headline is: the kill ROUTINE was not found, over a stated 48,129,536-byte
denominator, with the blind spots above enumerated.** What *was* found is the object it hangs off
and the dispatch mechanism that reaches it.

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

★★ **RE-RANKED S132 — the new #0, and a warning that changes how #1 must be attempted.**

0. **Offline, free — symbolically decode the 3,658 `packer31` computed tails (§6b.4).** The MBA is a
   fixed polynomial family (`Σ imul(const_i, term_i)` then a final add), machine-decodable with
   capstone `regs_access`, and §6b.4 shows the target constant falls straight out. That yields the
   protector's **control-flow graph**, which turns *"find the block that decides to kill"* into a
   **graph query instead of a needle hunt** — and it is the only route to the users of the
   `0x1831C0` vtable and its constructor `0x7F86F0` (§6b.6), both of which have **zero** direct
   callers. Two cheap sub-tasks fall out: grade the 605 unclassified negated constants against the
   2^33-MBA signature (`shl 0x21` / `or reg,1` / nearby mask-`and`) to sharpen the 335 floor, and
   look for a **custom fixup table** in the plaintext 1.4 % of `packer0` (§6b.5's alternative) —
   a run of dwords whose values are `packer31` RVAs of `movabs` immediates.
   ★ **One offline check nobody has run, against minidumps ALREADY ON DISK** (`scratchpad/s131/
   evidence/`, `dumps/crashpad-*`): if the FK-31 fault really is this dispatch, the faulting `jmp`
   is the **last instruction of a `packer31` function**, so the return-address chain should be intact
   and the stack should carry a `packer31`-range frame at a `.pdata` function boundary. **Zero
   launches.**

1. **Offline, no game needed — disassemble `0x8ffcd4–0x93e886`** (251 KB) and find its callers.
   That should yield the page-feed loop and the comparator, i.e. Wall #7's mechanism.
   ⚠⚠ **"find its callers" is the part that will fail as stated (S132, §6b.6).** Direct xref hunting
   does not work on this binary — the kill primitive's own constructor has **0 rel32 callers and 0
   stored pointers**, and the `disp32` sweep runs ~96 % false positives. **Do step 0 first**; callers
   here are reached through the flattened dispatch, not through call edges.
2. **Offline — disassemble `packer30` first** (2.2 MB; holds the entry function and the four
   largest functions; `call`-structured rather than MBA-saturated). Feed the disassembler the
   loader table at **RVA `0x14D8758`**, *not* the stale `.pdata` section. All sampled
   `UNWIND_INFO` is Version 1 and valid, so IDA/Ghidra will get correct frames.
3. **Read-only RPM, 26 dwords** at `runtime_base+0x94a6d8…0x94a824` (`packer2`). All 155 syscall
   stubs compute `sysno = ROL32(K1^key,7)+K2` and **all decode to `0xFFFFFFFF` on disk** — they
   are runtime-patched. Reading them live names every syscall the protector makes and confirms
   `0x80f7f0`.
   ★ **PROMOTED by S132 — this is now the ONLY way to settle §6's `NtTerminateProcess` identity**,
   which §6b downgrades to [I] precisely because that `0xFFFFFFFF` is unknowable from the file.
   The relevant cookie for the killer is the dword at `packer2` RVA **`0x94A800`**.
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
| "`0x80f7f0` **is** `NtTerminateProcess(h, 0xDEAD)`", stated inside a MEASURED block | **this file, §6** | ⚠ **GRADE SHARPENED S132 (§6b)** — the *bytes* are [M]; the *identity* is **[I]**. The syscall number is `ROL32(0x618E77BF ^ *(dword*)0x94A800, 7) + 0x6710C747` and the on-disk cookie yields `0xFFFFFFFF`. The file supports only `Nt???(HANDLE, 0xDEAD)`. Settle it with §8 step 3 |
| "**No instruction anywhere** forms `base+1` as an address" | **this file, §5** | ⚠⚠ **TOO STRONG — sharpened S132 (§5 annotation, §6b.2–§6b.3).** True for 64-bit literal immediates over 48,129,536 exec bytes; **false in general** — `packer31 0x03C8EDF2` computes `[rsp+0x158] + ImageBase + 1` via MBA and **dereferences it**. Defensible form: *"no 64-bit literal immediate equal to ±(ImageBase+1) survives adjudication as an operative address constant."* |
| "the protector's kill code should be findable by xrefs" | implicit throughout Wall #7 | ⚠⚠ **REFUTED S132 (§6b.6)** — the killer's own constructor has **0 rel32 callers and 0 stored pointers**, and the `disp32` sweep is ~96 % FP. It is reached only through the flattened computed-tail dispatch. **Xref hunting is the wrong instrument on this binary** |
| `runtime.dll`'s on-disk location was never recorded | this file | ★ **S132**: `G:\git\GAME BACKUPS FOR REVERSE ENGINEERING\SUPERVIVE\Loki\Binaries\Win64\runtime.dll`, 67,511,496 B, md5 `5e73e00ab52bc8f30574d8c023a84171`, resolved from `configs/launch-redirect.ps1:46`. DSN identity-confirmed byte-identical at file offset `0x7C1BEC` (§6b.1) |
