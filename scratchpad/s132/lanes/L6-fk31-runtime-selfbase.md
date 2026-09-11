# L6 — FK-31: hunting the code that computes `runtime.dll base + 1` and jumps there

**Fully offline.** Zero launches, zero injections, zero `.text` writes. All work against the
on-disk `runtime.dll`. Every address in this report was computed with `python`, never by hand.

---

## 0. Headline claims, with grades

| # | Claim | Grade |
|---|---|---|
| H1 | `runtime.dll` located and identity-confirmed: `G:\git\GAME BACKUPS FOR REVERSE ENGINEERING\SUPERVIVE\Loki\Binaries\Win64\runtime.dll`, 67,511,496 B, `ImageBase 0x200000000`, `SizeOfImage 0x4066000`, 11 sections matching FK-10's and S131's recorded layout. The `packer/3.3.1` Sentry DSN is at file offset `0x7C1BEC` — the exact offset FK-10 recorded. | **[M]** |
| H2 | **`ImageBase == 0x200000000 == 2^33`.** Every "is this constant `ImageBase`?" test in this binary is therefore aliased with ordinary MBA arithmetic on bit 33. This is a property of the target, not of my instrument, and it defeats the constant-search method the task proposed. | **[M]** |
| H3 | **No code in 48,129,536 bytes of executable sections computes `ImageBase+1` as an address.** All 13 candidate `movabs` sites (10 x `+0x200000001`, 3 x `-(0x200000001)`) are refuted individually by their consuming instruction — they are bit-masks and 2^33 MBA. | **[M]** |
| H4 | **The protector uses a computed-tail-jump architecture, and the jump target is `runtime_value + (ImageBase + target_RVA)`.** 4,769 of 18,580 functions end in `jmp <reg>`; target addresses are carried as `movabs reg, -(ImageBase + RVA)` folded into an MBA polynomial. | **[M]** |
| H5 | **⇒ A jump to `base + 1` is the native output shape of this dispatch when the resolved target RVA is 1 — or is 0 with the MBA `inc` applied.** This gives FK-31 a mechanism class rather than a mystery. | **[I]** |
| H6 | The obfuscated idiom that computes **`variable + ImageBase`** at runtime exists, at 3 sites. If the variable is the relocation delta, these compute the live module base. Top leads: RVA `0x01DB0940`, `0x020DBB99`, `0x02C779CE`. | **[I]** |
| H7 | FK-10's kill primitive re-verified byte-exact, and its owning object found: `RVA 0x80F7F0` is `NtTerminateProcess([this+0x10], 0xDEAD)`; it is **slot 4 of a 5-method vtable at `packer0 RVA 0x1831C0`**, installed by a **constructor at `RVA 0x7F86F0`** which is that table's only xref image-wide. | **[M]** |
| H8 | The search did **not** find the kill routine itself. Reported below with full coverage denominators and an explicit list of what the scanner is structurally blind to. | **[M]** |

---

## 1. Target located and identity-confirmed  [M]

Found via `configs/launch-redirect.ps1:46` (`$GameRoot`).

```
G:\git\GAME BACKUPS FOR REVERSE ENGINEERING\SUPERVIVE\Loki\Binaries\Win64\runtime.dll
filesize 0x40624C8 (67,511,496)   ImageBase 0x200000000   SizeOfImage 0x4066000
AddressOfEntryPoint 0x855440
EXCEPTION dir RVA 0x14D8758 size 0x366F0 = 222,960 B = 18,580 x 12   (matches the brief exactly)
```

Identity probe — file offset `0x7C1BEC`, UTF-16LE:

```
/api/5710262/minidump/?sentry_client=packer/3.3.1&sentry_key=149a7ac2a7914150b87ce714fd4d6444
```

Byte-identical to FK-10's recorded string at its recorded offset. **This is the right file.**

### Section map + coverage denominators

| section | VA | raw bytes | zero bytes | zero pages | EXEC |
|---|---|---:|---:|---:|:--:|
| `.pdata` | `0x1000` | 22,248 | 25.8 % | 0/5 | no |
| **`.rwx`** | `0x7000` | 4,096 | **100 %** | **1/1** | **yes** |
| `packer0` | `0x8000` | 8,155,136 | 1.4 % | 0/1991 | no |
| `packer1` | `0x7CF000` | 1,505,414 | 6.6 % | 0/367 | yes |
| `packer2` | `0x93F000` | 49,168 | 42.3 % | 2/12 | no (RW) |
| `.rsrc` | `0x94C000` | 9,624,160 | 0.4 % | 0/2349 | no |
| `.reloc` | `0x127A000` | 4,268 | 5.4 % | 0/1 | no |
| `packer30` | `0x127C000` | 2,282,308 | 12.2 % | 0/557 | yes |
| `packer40` | `0x14AA000` | 480,048 | 22.8 % | 16/117 | no |
| `packer31` | `0x1520000` | 44,336,680 | 10.6 % | 0/10824 | yes |
| `packer42` | `0x3F69000` | 1,033,692 | 31.1 % | 0/252 | no |

**Executable total scanned = 48,129,536 bytes** (`.rwx` + `packer1` + `packer30` + `packer31`).
That is the denominator for every negative in section 3.

The loader function table at `0x14D8758` parses as a **well-formed `.pdata`**: 18,580 entries,
`Begin` monotonically non-decreasing, no all-zero entries, `Begin` distributed
packer1 1,774 / packer30 9,609 / packer31 7,197. I use it throughout for **exact function extents**,
which removes the instruction-alignment guesswork the obfuscation would otherwise force.

---

## 2. THE CENTRAL CONFOUND — state this before any constant-based claim  [M]

```
ImageBase = 0x200000000 = 2^33
```

The obfuscator is MBA-based and does heavy bit-33 arithmetic (`shl reg,0x21`, masks of
`0x200000001`, constants `0xFFFFFFFE00000000 = -2^33`). **Every one of those aliases exactly with
`+/- ImageBase`.** A search for "the constant `ImageBase+1`" therefore *cannot* be decisive in this
binary — it returns MBA noise at a rate that swamps any real hit.

This is why section 3's negatives are stated as "no candidate *survived its consuming instruction*"
rather than "the constant does not appear".

---

## 3. Refuted candidates — each with the evidence that killed it

### 3.1 A relocated qword equal to `ImageBase+1` — REFUTED [M]
Parsed `.reloc` completely (`0x10AC` of `0x10AC` bytes consumed): 2,020 `DIR64` + 10 `ABSOLUTE`,
located in `packer0` (2,004) and `packer2` (16). **Zero** DIR64 targets hold a value in
`[ImageBase, ImageBase+0x1000)`. No fixed-up pointer becomes `base+1`.

### 3.2 A literal `0x0000000200000001` qword in data — REFUTED [M]
17 occurrences file-wide; only one is 8-aligned and in a writable section (`packer2 RVA 0x941900`).
It is **not** a reloc target, and its neighbourhood decodes as a dword struct:

```
RVA 00941900 | 01 00 00 00  02 00 00 00 | 00 70 00 00  02 00 00 00
               ^dword 1      ^dword 2      ^-- qword @0x941908 IS a reloc -> ImageBase+0x7000 (.rwx)
```

i.e. a coincidental `{1, 2}` dword pair. Further: the code that reads/writes `0x941900`/`0x941904`
(`packer1 0x84B030..0x84B1DC`) is **MSVC CRT `__isa_available` CPU-feature detection** —
`cpuid`, `GenuineIntel` (`0x756E6547`/`0x49656E69`/`0x6C65746E`), `xgetbv`, AVX bit tests.
Not protector state. Recorded so a successor does not re-chase it.

### 3.3 A poisoned loader-table entry (`RVA = 1`) — REFUTED [M]
All 18,580 `RUNTIME_FUNCTION` entries checked: **0** have any field equal to 0 or 1.

### 3.4 An MZ / PE self-locate — REFUTED [M], with control
Over all 48,129,536 executable bytes:

- `imm32 0x00005A4D` ('MZ'): **0**
- `imm32 0x00004550` ('PE\0\0'): **0**
- targeted `cmp/and word ptr [reg], 0x5A4D` (`66 81 /x ... 4d 5a`): **0**
- targeted `cmp dword ptr [reg], 0x4550` (`81 /x ... 50 45 00 00`): **0**

**Positive control:** the comparably-rare `imm32 0x0000FFFF` occurs **123** times in the same scan
over the same bytes — so a 4-byte immediate search over this corpus does find things.
⇒ The protector does **not** self-locate by walking back to its DOS header.

### 3.5 The 13 `movabs` sites naming `ImageBase +/- 1` — ALL REFUTED [M]

**10 x `movabs reg, 0x200000001`.** Nine are immediately followed by `and reg, <a just-shifted
value>` — a two-bit extraction **mask** (bits 0 and 33), always preceded by a `shr`:

```
0164407c  48bf0100000002000000   movabs rdi, 0x200000001
01644086  4821cf                 and    rdi, rcx          ; rcx = shr'd value -> MASK, not an address
```

The tenth (`0x03F13A40`) is `add r9, rdx` inside an MBA chain.

**3 x `movabs reg, 0xFFFFFFFDFFFFFFFF` (= `-(ImageBase+1)`).** All three are `-(2^33)-1` MBA
constants, each with a `shl reg,0x21` (`<<33`) in the immediately preceding instructions:

```
035a4708  4c01c8                 add    rax, r9            ; rax = r9*(2^33+1)  <- shl 0x21 just above
035a470b  49bcfffffffffdffffff   movabs r12, 0xfffffffdffffffff
035a4715  49ffc4                 inc    r12                ; = -2^33
035a4718  4d0fafe2               imul   r12, r10
```

### 3.6 The 406 `+1 -> jmp reg` pairs — REFUTED as the kill [M]
Alignment-agnostic scan over all 48 MB for a `+1` on a 64-bit register (`inc`, `add r,1`,
`sub r,-1`, `add r,imm32=1`, `lea r,[r+1]`) followed within 40 bytes by `jmp`/`call` **on that same
register**: 4,749 `+1` sites, 22,877 register-indirect transfers, **406 paired hits — all in
`packer31`**, all `inc reg -> jmp reg` at distance 22–40, none in `packer1`/`packer30`/`.rwx`.

Disassembled at true `.pdata` boundaries, every one is the *last arithmetic op of an MBA polynomial*
in a control-flow-flattened function tail — the `not`/`inc` two's-complement identity, not a
base-plus-one:

```
0153701b  4a8d044f   lea rax, [rdi + r9*2]
0153701f  4829c8     sub rax, rcx
01537022  48ffc0     inc rax          <-- part of the MBA algebra
...       epilogue (does not touch rax)
0153703f  ffe0       jmp rax
```

Corroborating count: of the 4,769 functions ending in a computed `jmp reg`, only **244 (5.1 %)**
carry a same-register `+1` in their last 80 bytes. A universal "+1 marker" would be ~100 %.

---

## 4. THE POSITIVE FINDING — the protector's computed-tail dispatch, and its address encoding

This is the real deliverable of the lane.

### 4.1 4,769 of 18,580 functions end in a computed `jmp <reg>`  [M]

Classifying the final instruction of every function using exact `.pdata` `End` addresses:

| function ends in | count |
|---|---:|
| `jmp rax..rdi` | 4,251 |
| `jmp r8..r15` | 518 |
| `ret` | 406 |
| `int3` | 97 |
| (non-terminal / mid-stream byte) | 13,308 |

By section: **`packer1` 1,111**, **`packer31` 3,658**, `packer30` 0.

### 4.2 Jump targets are carried as `movabs reg, -(ImageBase + target_RVA)`  [M]

Worked example, fully decoded by hand from function `0x0166E230..0x0166E50C` (732 B, the smallest
`packer31` computed-tail function):

```
0166e3a2  4889f8                 mov    rax, rdi
0166e3a5  48f7d0                 not    rax                     ; rax = ~rdi
0166e3a8  49b8855599fefdffffff   movabs r8, 0xfffffffdfe995585   ; C
0166e3b2  490fafc0               imul   rax, r8                 ; ~rdi * C
0166e3b6  49ffc0                 inc    r8                      ; C+1
0166e3b9  4c0fafc7               imul   r8, rdi                 ; (C+1)*rdi
0166e3bd  4901c0                 add    r8, rax
...
0166e509  41ffe0                 jmp    r8
```

Algebra: `~x = -x-1`, so `(~rdi)*C + (C+1)*rdi = rdi - C`.
`-C = 0x0000000200000000 + 0x0166AA7B` = **`ImageBase + 0x166AA7B`**.

**Prediction made from that, then tested:** `0x166AA7B` should be a real function.

```
is 0166aa7b an EXACT .pdata function start?  True    section = packer31
0166aa7b  4157  push r15
0166aa7d  4156  push r14
0166aa7f  4155  push r13   ... (the identical prologue every packer31 function has)
```

**Confirmed.**

### 4.3 Validated at scale, with a negative control  [M]

Enumerated every `movabs r64, imm64` in executable sections whose **negation** falls inside
`[ImageBase, ImageBase+SizeOfImage)`: **940 constants, all in `packer31`.**

| test | result |
|---|---|
| target == an **exact** `.pdata` function start | **335 / 940 (35.6 %)** |
| target inside some function's range | 353 / 940 |
| **negative control** — 940 random qwords from the same section, same test | **0 / 940** |
| of the 940, sit inside a function that ends in a computed `jmp reg` | 614 (65 %) |
| of the 3,658 `packer31` computed-tail functions, carry >=1 such constant | 558 (15.3 %) |

The remaining 605 decode into `packer30`/`packer2`/`packer1`/`packer0`/`packer40` — data pointers
and non-function targets — plus an unquantified share of 2^33 MBA noise (section 2). **I do not
claim all 940 are addresses; I claim >=335 are, and that is enough to establish the encoding.**

### 4.4 And the runtime `+ ImageBase` step is compiled in too  [M on the identity, I on its role]

The three `movabs reg, 0xFFFFFFFE00000000` (= `-2^33`) sites are all the *same* MBA identity, and it
computes **`variable + 2^33` = `variable + ImageBase`**:

```
01db0932  4c89d8                 mov    rax, r11
01db0935  48f7d0                 not    rax
01db0940  49b900000000feffffff   movabs r9, 0xfffffffe00000000     ; C = -2^33
01db094a  490fafc1               imul   rax, r9                    ; ~r11 * C
01db094e  4983c901               or     r9, 1                      ; C+1  (C is even, so or == add)
01db0952  4d0fafcb               imul   r9, r11                    ; (C+1)*r11
01db0956  4901c1                 add    r9, rax                    ; = r11 - C = r11 + 2^33
01db0959  4c894c2420             mov    qword ptr [rsp + 0x20], r9
```

Sites: **`0x01DB0940`**, **`0x020DBB99`**, **`0x02C779CE`**.

### 4.5 What this means for FK-31  [I]

`packer31`'s constants encode **preferred** VAs (`ImageBase + RVA`) and carry **no relocation
entries** (all 2,020 DIR64 relocs are in `packer0`/`packer2`). Yet S131 measured the module live at
`0x7FFD3B400000`. So a runtime term must supply the delta:

```
jump_target = delta + (ImageBase + target_RVA)     where delta = live_base - ImageBase
            = live_base + target_RVA
```

⇒ **`live_base + 1` is exactly what this dispatch emits when `target_RVA` resolves to 1** — or when
it resolves to 0 and the tail's MBA algebra contributes the `inc` seen in 244 of these functions.

This reframes FK-31: the kill need not be a bespoke "crash primitive" at all. It is consistent with
**the protector's ordinary flattened dispatch being handed a null/poisoned target**, which lands on
the module's own read-only DOS header and faults EXECUTE — matching S131's
`ExceptionInformation[0]==8`, the READONLY/MEM_IMAGE page, and the per-boot constancy (the base is
per-boot stable; the *offset* 1 is constant because a null RVA is constant).

**Grade discipline.** 4.1–4.3 are **[M]**. The `delta` decomposition here is **[I]** — I have not
identified the storage of `delta`, and an alternative is that the protector's own manual mapper
applies a **custom fixup table** to these constants from `packer0` (encrypted; see section 6). Both
routes predict the same output shape, so the FK-31 consequence is robust to which is true; the
*repair* is not.

---

## 5. FK-10 corroboration and one new structure  [M]

### 5.1 The `0xDEAD` kill primitive, byte-exact

```
0080f7f0  4c8b5110          mov    r10, qword ptr [rcx + 0x10]
0080f7f4  4d85d2            test   r10, r10
0080f7f7  741b              je     0x80f814
0080f7f9  b8bf778e61        mov    eax, 0x618e77bf
0080f7fe  3305fcaf1300      xor    eax, dword ptr [rip + 0x13affc]   ; -> packer2 0x94A800
0080f804  c1c007            rol    eax, 7
0080f807  0547c71067        add    eax, 0x6710c747                   ; = syscall number, decrypted
0080f80c  baaddead00        mov    edx, 0xdead                       ; <-- exit code
0080f811  0f05              syscall
0080f813  c3                ret
0080f814  31c0              xor    eax, eax
0080f816  c3                ret
```

`NtTerminateProcess(this->handle@+0x10, 0xDEAD)`. The syscall **number** is not a literal — it is
`ROL(0x618E77BF XOR *(dword*)0x94A800, 7) + 0x6710C747`, decrypted from a `packer2` cookie at
runtime. *That is why no syscall-number scan ever found these stubs.*

### 5.2 It is vtable slot 4 of a 5-method class

`packer0 RVA 0x1831C0`, NULL-bounded exactly as FK-10 recorded:

```
[0] 0x1831C0 -> RVA 0x871030   (reads [rcx+0x34])
[1] 0x1831C8 -> RVA 0x8D9480
[2] 0x1831D0 -> RVA 0x8B8B60   (large; saves xmm10.., 0x7C8 frame)
[3] 0x1831D8 -> RVA 0x8131D0   (writes [rcx+0x30]; same syscall-number decrypt idiom)
[4] 0x1831E0 -> RVA 0x80F7F0   <-- NtTerminateProcess(handle, 0xDEAD)
[5] 0x1831E8 -> NULL
```

Exactly **one** qword pointer to `ImageBase+0x80F7F0` exists in the whole file, and it is this slot.
That independently validates my RVA<->file-offset mapping against FK-10's prior work.

### 5.3 NEW: the table's sole xref is a constructor  [M]

A rip-relative `disp32` sweep over all 48 MB found exactly one clean reference (the other candidate
had no valid instruction prefix):

```
007f86f0  56                     push   rsi
007f86f1  4883ec20               sub    rsp, 0x20
007f86f5  4889ce                 mov    rsi, rcx              ; ctor arg
007f86f8  b938000000             mov    ecx, 0x38             ; sizeof(object) = 56
007f86fd  e8fee60900             call   0x896e00              ; allocator
007f8702  488d0db7aa98ff         lea    rcx, [rip - 0x675549] ; -> 0x1831C0   <<< THE VTABLE
007f8709  488908                 mov    qword ptr [rax], rcx  ; obj->vtbl = table
007f870c  0f57c0                 xorps  xmm0, xmm0
007f870f  0f114008               movups xmmword ptr [rax+8], xmm0
007f8713  48c7401800000000       mov    qword ptr [rax+0x18], 0
007f871b  48897020               mov    qword ptr [rax+0x20], rsi
007f871f  48c7402800000000       mov    qword ptr [rax+0x28], 0
007f8727  c7403000000000         mov    dword ptr [rax+0x30], 0
007f872e  66c740340000           mov    word  ptr [rax+0x34], 0
007f8739  c3                     ret
```

A 0x38-byte object wrapping a **process handle at `+0x10`** (zeroed here, filled later), whose
vtable's last method terminates that process with `0xDEAD`. **This is the object FK-10's Wall #7
should be hunting the users of.** It has **0 rel32 callers and 0 stored pointers** — it is reached
only through the flattened dispatch of section 4, which is precisely why direct xref hunting has
failed for FK-10 across many sessions.

### 5.4 Entry point

`AddressOfEntryPoint 0x855440` = `jmp 0x139238F` -> a single **54,233-byte** flattened function
(`0x139238F..0x139F768`) in `packer30`. It saves xmm6–xmm15, `and rsp, -0x40`, then enters the
dispatcher. It contains deliberate overlapping-instruction obfuscation (`test`-then-`jae`, where
`test` always clears CF, jumping into the middle of a preceding instruction), so **linear
disassembly of `packer30`'s entry function is not trustworthy** — noted as an instrument limit.

---

## 6. What this scan is structurally blind to — read before trusting any negative here

1. **`.rwx` (RVA `0x7000`, 4,096 B, `IMAGE_SCN 0xE0000060` = CODE|EXEC|READ|WRITE) is 100 % zero on
   disk**, and a relocated pointer to it sits at `packer2 0x941908`. Any code the protector
   *generates* there at runtime is **invisible offline, by construction**. A generated kill stub is
   fully consistent with every negative in section 3. This is the single largest blind spot.
2. **`packer0` (8.15 MB) and `.rsrc` (9.6 MB) are the protector's encrypted data.** Any dispatch
   table, custom fixup table, or target-RVA array living there is unreadable. Section 4.5's
   alternative (custom relocation of the `packer31` constants) sits exactly here.
3. **MBA expression of the `+1`.** My scan detects `inc r64`, `add r64,1`, `sub r64,-1`,
   `add r64,imm32=1`, `lea r64,[r64+1]`. It **cannot** see a 1 carried in a register
   (`add rax,rbx` with `rbx==1`), a 1 produced by the MBA polynomial itself, or `neg`/`not` pairs
   that net +1 across intervening instructions. With ~43 % of instructions being MBA, this is a real
   recall gap; I do not claim exhaustiveness.
4. **Window bound.** The paired scan used a 40-byte window between the `+1` and the transfer. The
   hit-set's distance histogram is saturated at its upper edge (max observed = 40), so longer-range
   pairs exist and were not counted.
5. **The rip-relative `disp32` sweep is a candidate generator, not an xref engine.** Measured
   false-positive rate: **712 candidates for 27 real `ff 15` uses** of IAT slot `0x8148` (~96 % FP).
   Only candidates whose preceding bytes form a valid instruction prefix were kept. Over a
   zero-filled region it produces one hit per byte and is useless (as seen on `.rwx`).
6. **`call`/`ret`-based transfers.** A kill implemented as a poisoned return address, or an indirect
   `call [reg+disp]` through a heap object, leaves no static signature I searched for.
7. I did **not** decode the 54 KB entry function or the flattened CFG. Section 4 identifies the
   *encoding*; it does not identify *which block* jumps to a null target.

---

## 7. Ranked next steps (all offline, all cheap)

1. **Decode all 3,658 `packer31` computed tails symbolically.** The MBA is a fixed polynomial family
   (`sum of imul(const_i, term_i)`, then a final add), it is machine-decodable with capstone
   `regs_access`, and section 4.2 shows the target constant falls straight out. That yields the
   protector's **control-flow graph**, which turns "find the block that decides to kill" into a graph
   query instead of a needle hunt. Natural successor lane, and free.
2. **Enumerate the users of the `0x1831C0` vtable** the same way — the constructor at `0x7F86F0` has
   no direct callers, so its call site is inside the flattened dispatch, and step 1 is the way there.
3. **Grade the 605 unclassified negated constants** (section 4.3) against the 2^33-MBA signature
   (`shl 0x21` / `or reg,1` / mask-`and` nearby). That partitions "address constant" from "MBA noise"
   and sharpens the 335 floor.
4. **Check `packer0` for a custom fixup table** (section 4.5's alternative): look in the plaintext
   1.4 % of `packer0` for a run of dwords whose values are `packer31` RVAs of `movabs` immediates.
5. **Cheap offline check I did not run (out of lane scope):** if the FK-31 fault is this dispatch,
   the faulting `jmp` is the **last instruction of a `packer31` function**, so the return-address
   chain should be intact and a minidump's stack should contain a `packer31`-range frame at a
   `.pdata` function boundary. That is testable against the minidumps **already on disk** in
   `scratchpad/s131/evidence/`, with no launch.

---

## 8. Files

- `scratchpad/s132/l6/rt.py` — reusable loader: RVA<->file mapping, `.pdata` function extents
  (18,580 exact ranges), capstone helper. **Use this instead of re-deriving addresses.**
- `scratchpad/s132/l6/scan_plus1.py` — the alignment-agnostic `+1 -> indirect transfer` scanner.
- `scratchpad/s132/l6/negconst.json` — the 940 negated target constants
  (`section, site RVA, raw imm64, decoded target RVA`).
- `scratchpad/s132/l6/pairs.json`, `secs.json`, `ripind.json`.
