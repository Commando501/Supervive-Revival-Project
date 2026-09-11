# LANE 2 — ABI grade of `0x00F988D0` (the one raw direct call the S132 arm must hand-build)

Offline only. Image `dumps/merged4.dump.exe`, ImageBase `0x7FF6AF000000`, file offset == RVA.
Zero launches, zero injections. Every address recomputed with `python -c` / capstone; none by hand.

---

## 0. VERDICT (lead)

| # | claim | grade |
|---|---|---|
| V1 | `0x00F988D0` is `TArray<T, TSizedHeapAllocator<32>>::ResizeGrow(int32 OldNum)`, **specialised for an 8-byte element with 8-byte alignment**, `void __fastcall(TArray* rcx, int32 OldNum edx)` | **[M]** |
| V2 | It is **GENERIC / ICF-shared**, not the `PlayersAttached` instantiation — **≥ 4,256 verified direct call sites** across ≥ 3,292 distinct functions | **[M]** |
| V3 | The whole chain is **REAL, no fold anywhere**, and terminates in `FMemory::Realloc` → `GMalloc->Realloc` (virtual slot `+0x38`). The reallocator is **not stripped**. | **[M]** |
| V4 | The `jl` at `0x00F988EA` guards `ArrayNum >= OldNum` (signed 32-bit). Failing it calls a **`[[noreturn]]` UE_LOG(Fatal) + `jmp $` infinite loop** — process death/hang, unrecoverable, no crash dump. | **[M]** |
| V5 | With `Data=0 Num=0 Max=0` and `OldNum=0` the guard **passes**, `ArrayMax` becomes **4**, and **32 bytes** are requested. Identical result whether `Num` is 0 or 1 at call time. | **[M]** |
| V6 | No TLS, no segment-prefixed access, no lock taken by `ResizeGrow` itself, **zero UObject / UFunction / ProcessEvent involvement** ⇒ **cannot re-enter our hook**. | **[M]** |
| V7 | The call at `0x055CD75B` (inside `AuthPlayerEnterWorldAttachedToRidable`) really does target `0x00F988D0` — rel32 decoded by machine. | **[M]** |
| V8 | **A hand-built direct call is SAFE and CORRECT for `component+0x130` in its measured `Data=0 Num=0 Max=0` state.** Risk class = ordinary heap allocation, zero `.text` writes. | **[M]** for the mechanism; **[I]** that the live array still reads 0/0/0 at arm time (that is S131's measurement, not mine) |

---

## 1. Reproduced entry (the bytes I am reasoning from)

`python scratchpad/fk27/fkdis.py d 0xF988D0 200 --dump merged4`

```
0x00F988D0  48895c2408           mov qword ptr [rsp + 8], rbx        ; save RBX in caller shadow space
0x00F988D5  4889742410           mov qword ptr [rsp + 0x10], rsi     ; save RSI
0x00F988DA  57                   push rdi
0x00F988DB  4883ec30             sub rsp, 0x30
0x00F988DF  48635908             movsxd rbx, dword ptr [rcx + 8]     ; rbx = ArrayNum        <-- [rcx+8]
0x00F988E3  8bf2                 mov esi, edx                        ; esi = OldNum
0x00F988E5  488bf9               mov rdi, rcx                        ; rdi = arr
0x00F988E8  3bda                 cmp ebx, edx                        ; ArrayNum vs OldNum
0x00F988EA  7c71                 jl 0xF9895D                         ; ArrayNum <  OldNum -> FATAL
0x00F988EC  83790c00             cmp dword ptr [rcx + 0xc], 0        ; ArrayMax == 0 ?      <-- [rcx+0xC]
0x00F988F0  b804000000           mov eax, 4                          ; Grow = 4
0x00F988F5  7411                 je 0xF98908
0x00F988F7  488d045b             lea rax, [rbx + rbx*2]              ; 3*N
0x00F988FB  48c1e803             shr rax, 3                          ; 3*N/8
0x00F988FF  4883c010             add rax, 0x10                       ; +16
0x00F98903  4803c3               add rax, rbx                        ; +N     -> Grow = N + 3N/8 + 16
0x00F98906  eb07                 jmp 0xF9890F
0x00F98908  483bd8               cmp rbx, rax                        ; N vs 4 (64-bit; cmova is UNSIGNED)
0x00F9890B  480f47c3             cmova rax, rbx                      ; Grow = max(4, N)
0x00F9890F  488d0cc500000000     lea rcx, [rax*8]                    ; rcx = Grow * 8        <-- BytesPerElement = 8
0x00F98917  ba08000000           mov edx, 8                          ; edx = 8               <-- Alignment       = 8
0x00F9891C  e89fef0600           call 0x10078C0                      ; FMemory::QuantizeSize(bytes, 8)
0x00F98921  48c1e803             shr rax, 3                          ; / 8                   <-- BytesPerElement = 8
0x00F98925  b9ffffff7f           mov ecx, 0x7fffffff
0x00F9892A  3bd8                 cmp ebx, eax
0x00F9892C  c744242008000000     mov dword ptr [rsp + 0x20], 8       ; 5th arg  = Alignment 8
0x00F98934  41b908000000         mov r9d, 8                          ; 4th arg  = BytesPerElement 8
0x00F9893A  8bd6                 mov edx, esi                        ; 2nd arg  = OldNum
0x00F9893C  0f4fc1               cmovg eax, ecx                      ; if (ArrayNum > Retval) Retval = MAX_int32
0x00F9893F  488bcf               mov rcx, rdi                        ; 1st arg  = arr (== &AllocatorInstance)
0x00F98942  448bc0               mov r8d, eax                        ; 3rd arg  = NewMax
0x00F98945  89470c               mov dword ptr [rdi + 0xc], eax      ; ArrayMax = NewMax     <-- ONLY write to arr
0x00F98948  e863700100           call 0xFAF9B0                       ; ResizeAllocation(...)
0x00F9894D  488b5c2440           mov rbx, qword ptr [rsp + 0x40]     ; restore RBX
0x00F98952  488b742448           mov rsi, qword ptr [rsp + 0x48]     ; restore RSI
0x00F98957  4883c430             add rsp, 0x30
0x00F9895B  5f                   pop rdi
0x00F9895C  c3                   ret
0x00F9895D  8bcb                 mov ecx, ebx                        ; arg = ArrayNum
0x00F9895F  e81c230100           call 0xFAAC80                       ; OnInvalidArrayNum(...)   [[noreturn]]
0x00F98964  cc                   int3
```

**Extent.** `tools/strxref/index/pdata_union.csv` has exactly **one** row `0xF988D0..0xF98965`
(149 = `0x95` bytes, `seen_in_dumps 76`). The next row starts at `0xF98970`, so this function is
**NOT chained** and 149 B is its real size. The 11 bytes `0xF98965..0xF98970`
(`40 53 53 57 55 55 4c 8d 4c 24 60`) are **inter-function padding, not code** — they disassemble into
plausible-looking `push`es and are a decoy. Do not read past `0xF98964`.

**Coverage / cross-image control.** `fkdis cov` reports `page 0x00F98000 present` for every address above.
Stronger: the 149 bytes are **byte-identical in all 23 single-state dumps on disk** *and* in `merged`,
`merged2`, `merged4` — so this is not a merge artifact.
**Negative control proving the instrument can see an undecrypted page:** the same script reads
`0x055CD738` as **all zeros in `dumps/merged.dump.exe`** while it is real code in `merged2`, `merged4` and
`tutorial-hero`. `QuantizeSize`, `ResizeAllocation` and `FMemory::Realloc` are likewise decrypted **23/23**.
⇒ **The whole chain is always resident; the arm cannot land on a dark page.** [M]

---

## 2. Q1 — calling convention and signature: **CONFIRMED, plus one sharpening**

`void __fastcall ResizeGrow(void* arr /*rcx*/, int32_t OldNum /*edx*/)` — **your reading is correct in every part.**

| your claim | evidence | grade |
|---|---|---|
| `rcx` = array, `edx` = OldNum | `movsxd rbx,[rcx+8]`, `mov esi,edx`, `mov rdi,rcx`; a path-sensitive walk (§3) shows nothing else is consumed | **[M]** |
| layout `{void* Data@0, int32 Num@8, int32 Max@0xC}` | `[rcx+8]` read as Num; `[rcx+0xC]` read and written as Max; `rcx` handed to `ResizeAllocation`, which does `mov rcx,[rcx]` (Data@0) and `mov [rbx],rax` (Data@0) | **[M]** |
| 8-byte element, 8-byte alignment | the three literal 8s at `0xF98917` (Alignment arg to QuantizeSize), `0xF9892C` (5th stack arg = Alignment), `0xF98934` (`r9d` = BytesPerElement), **plus** `lea rcx,[rax*8]` and `shr rax,3` (multiply/divide by BytesPerElement). **Independently corroborated at the call site**: `mov [rax + rbx*8], rdi` — stride 8. | **[M]** |
| it is `ResizeGrow` | the arithmetic is `DefaultCalculateSlackGrow` verbatim — `Grow = 4` if `ArrayMax==0` else `N + 3N/8 + 16`; `QuantizeSize(Grow*BPE, Align)/BPE`; `if (N > Retval) Retval = MAX_int32`; then `ArrayMax = Retval; ResizeAllocation(OldNum, ArrayMax, BPE, Align)` | **[M]** |

**Sharpening — the allocator is named, not assumed.** It is not merely "the UE default": the sibling error path
inside `ResizeAllocation` (§5b) logs
`"Trying to resize TSizedHeapAllocator<%d> to an invalid size of %lld with element size %I64u"`
with its first argument loaded as `mov ecx, 0x20`.
⇒ **`TSizedHeapAllocator<32>` (= `FDefaultAllocator`, 32-bit `SizeType`)** [M].
That independently confirms `SizeType == int32`, i.e. `OldNum` really is a 32-bit signed value in `edx`.

---

## 3. Q2 — what it touches, clobbers, and returns

Exhaustive capstone `regs_access` over all 149 bytes, **plus a path-sensitive read-before-written walk**
(every branch followed; `call` treated as clobbering the volatiles):

```
ResizeGrow        incoming regs READ-BEFORE-WRITTEN: ['rbx', 'rcx', 'rdi', 'rdx', 'rsi']
ResizeAllocation  incoming regs READ-BEFORE-WRITTEN: ['r8', 'r9', 'rbx', 'rcx']       <-- note: NO rdx
QuantizeSize      incoming regs READ-BEFORE-WRITTEN: ['rcx', 'rdx']
FMemory::Realloc  incoming regs READ-BEFORE-WRITTEN: ['r8', 'rbx', 'rcx', 'rdi', 'rdx', 'rsi']
```

`rbx` / `rsi` / `rdi` appear **only because the prologue reads them in order to spill them**
(`mov [rsp+8], rbx` etc.), and they are restored from `[rsp+0x40]` / `[rsp+0x48]` / `pop rdi` before `ret`.
The frame arithmetic checks out: entry `rsp = R`; after `push rdi` + `sub rsp,0x30`, `rsp = R-0x38`, so
`[rsp+0x40] = R+8` is exactly the slot RBX was spilled to. Therefore:

- **True inputs: `rcx` and `edx`. Nothing else.** [M]
- **Nonvolatile registers RBX / RSI / RDI are correctly preserved.** [M]
- **Clobbers: RAX, RCX, RDX, R8, R9, RFLAGS** (plus R10/R11 and XMM0–5 through the callees) — exactly the Win64
  volatile set, nothing outside the ABI. [M]
- **It writes the caller's 32-byte shadow space** at `[rsp+8]` and `[rsp+0x10]`. Legal x64 ABI, but it means a
  hand-rolled asm call **must** reserve the 32-byte home area. A normal C++ function-pointer call does this. [M]
- **On `arr` it reads `[arr+8]` and `[arr+0xC]` and writes `[arr+0xC]` only.** `[arr+0]` (Data) is written by
  `ResizeAllocation`, not by this function. [M]
- **Segment-prefixed (TLS / `gs:`) memory operands: NONE** — in `ResizeGrow`, `QuantizeSize`, `ResizeAllocation`
  or `FMemory::Realloc`. [M]
- **No XMM register is touched by `ResizeGrow` itself** (none appears in `regs_access`). [M]

**Return value.** The source contract is `void`. Mechanically RAX *is* defined on return, but it is path-dependent
garbage: the epilogue never touches RAX after `call 0xFAF9B0`, so RAX = whatever `ResizeAllocation` left —
the new `Data` pointer on the allocating path, or the quantized element count on the degenerate
`Data==null && NewMax==0` early-out. **Do not read it. Declare the typedef `void`.** [M]

---

## 4. Q3 — the precondition that matters, and the cost of getting it wrong

### The guard
`0x00F988E8 cmp ebx, edx` / `0x00F988EA jl 0x00F9895D` — a **signed 32-bit** compare.

> **PASS iff `ArrayNum >= OldNum`.** Equality passes (`jl`, not `jle`). [M]

### The failure target is FATAL and NORETURN — graded

`0x00F9895D: mov ecx, ebx` (arg = ArrayNum) → `call 0x00FAAC80` → `int3`.

```
0x00FAAC80  4883ec28             sub rsp, 0x28
0x00FAAC84  4c8bc1               mov r8, rcx                     ; r8 = NewNum
0x00FAAC87  488d15ba0b6e06       lea rdx, [rip + 0x66e0bba]      ; -> RVA 0x768B848  (log-site descriptor)
0x00FAAC8E  488d0ddbe3d708       lea rcx, [rip + 0x8d7e3db]      ; -> RVA 0x9D29070  (FLogCategory)
0x00FAAC95  e856090c00           call 0x106B5F0                  ; the logger
0x00FAAC9A  660f1f440000         nop word ptr [rax + rax]
0x00FAACA0  ebfe                 jmp 0x00FAACA0                  ; <-- infinite loop == [[noreturn]]
```

Resolving the two `lea` targets (recomputed from the **next-instruction** address, by capstone, not by hand):

- `[0x768B848 + 0x00] -> 0x768B870` = UTF-16 **`"Trying to resize TArray to an invalid size of %llu"`**
- `[0x768B848 + 0x08] -> 0x768B8E0` = ANSI `C:\TheoryCraft\build-staging\Engine\Source\Runtime\Core\Private\Containers\ContainersHelpers.cpp`
- `[0x768B848 + 0x10]` = line **8**
- `0x9D29070` = `{Verbosity=5 (Log), DebugBreakOnLog=0, DefaultVerbosity=5, CompileTimeVerbosity=7 (VeryVerbose), FName=0x8E9}` — the `FLogCategoryBase` layout this repo already measured (FK-11).

⇒ **`0x00FAAC80` is `UE::Core::Private::OnInvalidArrayNum(unsigned long long)`: a Fatal `UE_LOG` followed by
`for(;;);`.** [M] The compiler emitted `int3` after the call, i.e. it knew the callee is `[[noreturn]]`. [M]

**Consequence of tripping it: a Fatal log followed by a permanently spinning game thread.** Not an exception,
not a crashpad dump you can read, not catchable by SEH. **This is the single hard precondition of the arm.**

### What relationship avoids it — and how much freedom you actually have

`OldNum` is consumed in exactly two places, and one of them is dead:

1. the guard above, and
2. as `PreviousNumElements` (`edx`) to `ResizeAllocation` — where the path-sensitive walk shows **`rdx` is never
   read before being overwritten** (`0xFAF9D7 movsxd rdx, r8d` on the live path, `0xFAF9F1` on the error path),
   and the `Data==null && NumElements==0` path returns without touching it at all. The heap allocator does not
   need it: `FMemory::Realloc` preserves contents itself.

⇒ **[M] `OldNum` has NO effect on the resulting array state whatsoever. Its only observable role is the guard.**

| `ArrayNum` at call | `OldNum` passed | guard | note |
|---|---|---|---|
| 1 | 0 | `1 >= 0` **pass** | the game's own idiom — increment `Num` first, pass the pre-increment value |
| 0 | 0 | `0 >= 0` **pass** | equality passes; my recommended ordering (publish `Num` last) |
| N | N | pass | legal |
| 0 | 1 | `0 >= 1` **FATAL** | the one thing you must never do |

**Direct answer to "must `ArrayNum` already be incremented to `OldNum+1` before the call?" — NO.**
It is *sufficient* (that is what the game does) but not *necessary*. The necessary and sufficient condition is
`ArrayNum >= OldNum`, and `0 >= 0` satisfies it. `ebx >= edx` passing is confirmed for both orderings.

---

## 5. Q4 — both callees traced and graded

### 5a. `0x010078C0` — `FMemory::QuantizeSize(SIZE_T Count /*rcx*/, uint32 Alignment /*edx*/)` — **REAL**

```
0x010078C0  448bc2               mov r8d, edx                        ; r8d = Alignment
0x010078C3  488bd1               mov rdx, rcx                        ; rdx = Count
0x010078C6  488b0db318d408       mov rcx, qword ptr [rip + 0x8d418b3]; rcx = GMalloc   (RVA 0x9D49180)
0x010078CD  4885c9               test rcx, rcx
0x010078D0  7504                 jne 0x010078D6
0x010078D2  488bc2               mov rax, rdx                        ; GMalloc==null -> return Count unchanged
0x010078D5  c3                   ret
0x010078D6  488b01               mov rax, qword ptr [rcx]            ; vtable
0x010078D9  48ff6050             jmp qword ptr [rax + 0x50]          ; GMalloc->QuantizeSize(Count, Alignment)
```

- 29 bytes, **not** any of the five known folds
  (`0xF7EC20` / `0xF7EB50` / `0xF7EB60` / `0xB9E1F0` / `0xFC6CF0`). **REAL.** [M]
- **No `.pdata` row — and that is correct, not a coverage gap:** it is a leaf with no stack frame, so it needs no
  unwind data. (Stated explicitly because "no pdata row" reads like "missing" and is not.) [M]
- Tail-jumps to virtual slot **`+0x50` (index 10)** on `GMalloc` with arg shape
  `(this, SIZE_T Count, uint32 Alignment)` — matching `FMalloc::QuantizeSize`. [M]
- `GMalloc` global RVA **`0x9D49180`**, machine-recomputed from the instruction *end* and cross-checked against
  the two independent loads inside `FMemory::Realloc`; **all three resolve to `0x9D49180`.** [M]
  ⚠ I first fed the instruction *start* into the arithmetic and got `0x9D49179`. Recomputing with capstone's
  `address + size` gave `0x9D49180`. Recorded because it is exactly the hand-arithmetic trap this repo logs.
- `*(void**)0x9D49180` in `merged4` = `0x1FC1C1486A0` — a live heap pointer, so **`GMalloc` was non-null in the
  snapshot** and the null branch is not the live behaviour. [M for that snapshot]
- Concrete allocator: `.rdata` carries the wide string
  `"FMallocBinned2 Attempt to free an unrecognized small block %..."` at RVA `0x76A0AD0`, with 5 sibling
  FMallocBinned2 messages. ⇒ **FMallocBinned2 is compiled in** [M]. Whether `GMalloc` *is* that instance is
  **[I]** — the object is on the heap and is not in a module dump.

### 5b. `0x00FAF9B0` — `TSizedHeapAllocator<32>::ForElementType::ResizeAllocation(int32 PrevNum /*edx — DEAD*/, int32 NewNum /*r8d*/, SIZE_T BPE /*r9*/, uint32 Align /*[rsp+0x28]*/)` — **REAL**

```
0x00FAF9B0  4053                 push rbx
0x00FAF9B2  4883ec20             sub rsp, 0x20
0x00FAF9B6  488bd9               mov rbx, rcx                        ; rbx = &Data
0x00FAF9B9  488b09               mov rcx, qword ptr [rcx]            ; rcx = Data
0x00FAF9BC  4885c9               test rcx, rcx
0x00FAF9BF  7505                 jne 0x00FAF9C6
0x00FAF9C1  4585c0               test r8d, r8d
0x00FAF9C4  7425                 je 0x00FAF9EB                       ; Data==null && NewNum==0 -> no-op
0x00FAF9C6  4585c0               test r8d, r8d
0x00FAF9C9  7826                 js 0x00FAF9F1                       ; NewNum < 0 -> FATAL
0x00FAF9CB  498d41ff             lea rax, [r9 - 1]
0x00FAF9CF  483dfeffff7f         cmp rax, 0x7ffffffe
0x00FAF9D5  771a                 ja 0x00FAF9F1                       ; BPE outside [1, 0x7FFFFFFF] -> FATAL
0x00FAF9D7  4963d0               movsxd rdx, r8d                     ; <-- kills the incoming PrevNum
0x00FAF9DA  448b442450           mov r8d, dword ptr [rsp + 0x50]     ; Alignment (5th arg)
0x00FAF9DF  490fafd1             imul rdx, r9                        ; NewNum * BPE = byte count
0x00FAF9E3  e808850500           call 0x01007EF0                     ; FMemory::Realloc(Data, bytes, Align)
0x00FAF9E8  488903               mov qword ptr [rbx], rax            ; Data = result
0x00FAF9EB  4883c420             add rsp, 0x20
0x00FAF9EF  5b                   pop rbx
0x00FAF9F0  c3                   ret
0x00FAF9F1  4963d0               movsxd rdx, r8d
0x00FAF9F4  b920000000           mov ecx, 0x20                       ; <-- TSizedHeapAllocator<32>
0x00FAF9F9  4d8bc1               mov r8, r9
0x00FAF9FC  e83fb3ffff           call 0x00FAAD40                     ; [[noreturn]]
0x00FAFA01  cc                   int3
```

- 82 bytes, single `.pdata` row `0xFAF9B0..0xFAFA02`. **REAL, not a fold.** [M]
- Error callee `0x00FAAD40` resolves the same way as §4: format string
  **`"Trying to resize TSizedHeapAllocator<%d> to an invalid size of %lld with element size %I64u"`**,
  file `...\Containers\ContainerAllocationPolicies.cpp`, line **14**, then `jmp $`. **`[[noreturn]]`.** [M]
  With our inputs (`NewNum = 4 > 0`, `BPE = 8`) **neither of its two fatal conditions can fire.** [M]

### 5c. `0x01007EF0` — `FMemory::Realloc(void* Original /*rcx*/, SIZE_T Count /*rdx*/, uint32 Alignment /*r8d*/)` — **REAL, and this is the allocator**

```
0x01007EF0  48895c2408           mov qword ptr [rsp + 8], rbx
0x01007EF5  4889742410           mov qword ptr [rsp + 0x10], rsi
0x01007EFA  57                   push rdi
0x01007EFB  4883ec20             sub rsp, 0x20
0x01007EFF  488bf1               mov rsi, rcx                        ; Original
0x01007F02  418bd8               mov ebx, r8d                        ; Alignment
0x01007F05  488b0d7412d408       mov rcx, qword ptr [rip + 0x8d41274]; GMalloc  (RVA 0x9D49180)
0x01007F0C  488bfa               mov rdi, rdx                        ; Count
0x01007F0F  4885c9               test rcx, rcx
0x01007F12  750c                 jne 0x01007F20
0x01007F14  e8a714ffff           call 0x00FF93C0                     ; lazily create GMalloc
0x01007F19  488b0d6012d408       mov rcx, qword ptr [rip + 0x8d41260]; reload GMalloc (same 0x9D49180)
0x01007F20  488b01               mov rax, qword ptr [rcx]            ; vtable
0x01007F23  448bcb               mov r9d, ebx                        ; Alignment
0x01007F26  4c8bc7               mov r8, rdi                         ; Count
0x01007F29  488bd6               mov rdx, rsi                        ; Original
0x01007F2C  488b5c2430           mov rbx, qword ptr [rsp + 0x30]     ; restore
0x01007F31  488b742438           mov rsi, qword ptr [rsp + 0x38]
0x01007F36  4883c420             add rsp, 0x20
0x01007F3A  5f                   pop rdi
0x01007F3B  48ff6038             jmp qword ptr [rax + 0x38]          ; GMalloc->Realloc(Original, Count, Alignment)
```

- **REAL, not a fold**, `.pdata` row `0x1007EF0..0x1007F3F`. Tail-jumps to virtual slot **`+0x38` (index 7)**
  with arg shape `(this, void*, SIZE_T, uint32)` = `FMalloc::Realloc`. [M]

> **The reallocator is NOT stripped — the recipe is alive.** The complete chain is
> `ResizeGrow → {QuantizeSize, ResizeAllocation} → FMemory::Realloc → GMalloc->Realloc`, and every hop is a real
> multi-instruction body ending in a virtual dispatch on a non-null `GMalloc`. **[M]** This was the thing the lane
> brief said must be found now if it were dead; it is not dead.

---

## 6. Q5 — growth math for `Max==0, Num==1, OldNum==0`: **your reading is CORRECT**

| pc | effect |
|---|---|
| `0xF988DF` | `rbx = ArrayNum = 1` |
| `0xF988E8/EA` | `cmp ebx(1), edx(0)` → not less → **guard passes** |
| `0xF988EC/F0/F5` | `[rcx+0xC] == 0` → `eax = 4`, **`je` taken** to `0xF98908` |
| `0xF98908` | `cmp rbx(1), rax(4)` → CF=1 (below) |
| `0xF9890B` | `cmova rax, rbx` — **NOT taken** (1 is not *above* 4) ⇒ **`Grow = 4`** ✔ exactly your reading |
| `0xF9890F` | `rcx = 4 * 8 = 32` |
| `0xF98917` | `edx = 8` |
| `0xF9891C` | `QuantizeSize(32, 8)` → `Q`, with `Q >= 32` (it rounds **up** to a bin size) |
| `0xF98921` | `rax = Q/8 >= 4` |
| `0xF9892A / 3C` | `cmp ebx(1), eax(>=4)`; `cmovg` **NOT taken** ⇒ no `MAX_int32` clamp |
| `0xF98945` | **`ArrayMax = 4`** (for `Q == 32`) |
| `0xF98948` | `ResizeAllocation(arr, OldNum=0, NewMax=4, BPE=8, Align=8)` → `imul` → **32 bytes** → `FMemory::Realloc(nullptr, 32, 8)` |

**Result: `ArrayMax = 4`, 32 bytes requested, `Data` = a fresh 32-byte GMalloc block, `ArrayNum` unchanged.** ✔

Two robustness notes:

- If `QuantizeSize` returns a larger bin, `ArrayMax` is simply larger. `Q >= 32` ⇒ `Q/8 >= 4` ⇒
  **`ArrayMax >= 4` unconditionally**, and `ResizeAllocation` then allocates `ArrayMax * 8 >= 32`, so the
  invariant `ArrayMax >= ArrayNum` always holds. [M] The exact value of `Q` is **[I]** (it depends on the live
  allocator's bin table) and nothing downstream cares.
- **`Num == 0` produces the identical outcome:** at `0xF98908`, `cmp rbx(0), rax(4)` → `cmova` not taken →
  `Grow = 4` again. I simulated both; `ArrayMax = 4`, 32 bytes, in both cases. [M]

The `Data==null` path through `ResizeAllocation` was walked explicitly: `mov rcx,[rcx]` → `rcx = null`;
`test rcx,rcx` → `jne` NOT taken; `test r8d,r8d` (`NewMax = 4`) → nonzero so `je` NOT taken; fall through to
`0xFAF9C6`; not negative; `r9-1 = 7 <= 0x7FFFFFFE`; ⇒ `FMemory::Realloc(nullptr, 32, 8)` = a fresh allocation.
`rcx` is not modified between `0xFAF9B9` and the call, so the `Original` argument really is `null`. [M]

---

## 7. Q6 — generic or specific? **GENERIC, overwhelmingly. Uncapped scan, written from scratch.**

`fkdis callxref` caps at 200 rows, so I did **not** use it. I scanned the whole `.text`
(VA `0x1000`, VS `0x7649000`, taken from the PE section table) for every `E8`/`E9` whose rel32 lands on
`0xF988D0`, then **verified each hit is a true instruction boundary** by locating its containing
`pdata_union.csv` row and linear-disassembling that row from its start with capstone:

```
naive E8/E9 rel32 hits targeting 0xf988d0 : 4363     (4362 x E8 call, 1 x E9 jmp)
verified instruction boundary             : 4256
NOT a boundary (false positive)           :    1     (0x00E4A03F)
no pdata row -> unverifiable              :  106
distinct containing pdata rows            : 3292
```

> **True direct-caller count lies in `[4256, 4362]`. Report `>= 4,256` as a FLOOR, across `>= 3,292` distinct
> functions.** [M]

Spot-checking one of the 106 unverifiable hits shows it is a genuine, structurally identical site:

```
0x011EA290  413b878c050000   cmp eax, dword ptr [r15 + 0x58c]     ; NewNum vs ArrayMax
0x011EA297  760e             jbe 0x011EA2A7
0x011EA299  8bd3             mov edx, ebx                          ; OldNum
0x011EA29B  498d8f80050000   lea rcx, [r15 + 0x580]                ; &TArray
0x011EA2A2  e829e6daff       call 0x00F988D0
0x011EA2A7  498b8780050000   mov rax, qword ptr [r15 + 0x580]      ; re-read Data
0x011EA2AE  4c8934d8         mov qword ptr [rax + rbx*8], r14      ; Data[OldNum] = ptr  (stride 8)
```

⇒ It is the **ICF-shared instantiation for every `TArray<8-byte T, FDefaultAllocator>`** in the image
(`TArray<UObject*>`, `TArray<void*>`, `TArray<int64>`, …). It is **not** specific to `PlayersAttached`. [M]
Practical consequence: this is one of the most heavily exercised non-trivial functions in the binary — the
arm is calling code the game runs thousands of times per frame, not a cold path.

**Indirect reachability: NONE.** An **uncapped** scan of the entire 178 MB image for the qword
`0x7FF6AFF988D0` returns **0 hits** — nothing stores its address. It is reached only by direct rel32 call. [M]
(Consistent with, and mechanically explaining, `CLAUDE.md`'s note that it is not a `UFunction` and the S55 thunk
primitive does not apply to it.)

### The call at `0x055CD75B` — rel32 decoded by machine

```
bytes @0x55cd75b: e8 70 b1 9c fb    opcode = 0xE8    rel32 = 0xFB9CB170 (-73,895,568)
0x55CD75B + 5 + (-73895568) = 0x00F988D0     ✔ CONFIRMED
```

Context — this is the game's own `PlayersAttached.Add(PlayerState)` and is the exact template for the arm:

```
0x055CD738  49639e38010000   movsxd rbx, dword ptr [r14 + 0x138]   ; OldNum = Num
0x055CD73F  8d4301           lea eax, [rbx + 1]
0x055CD742  41898638010000   mov dword ptr [r14 + 0x138], eax      ; Num = OldNum + 1   <-- FIRST
0x055CD749  413b863c010000   cmp eax, dword ptr [r14 + 0x13c]      ; vs Max
0x055CD750  760e             jbe 0x055CD760                        ; fits -> skip growth (UNSIGNED)
0x055CD752  8bd3             mov edx, ebx                          ; OldNum
0x055CD754  498d8e30010000   lea rcx, [r14 + 0x130]                ; &PlayersAttached
0x055CD75B  e870b19cfb       call 0x00F988D0
0x055CD760  498b8630010000   mov rax, qword ptr [r14 + 0x130]      ; RE-READ Data after the call
0x055CD767  48893cd8         mov qword ptr [rax + rbx*8], rdi      ; Data[OldNum] = PlayerState
```

Binding the registers from the function prologue (`fkdis d 0x55CD510`):

```
0x055CD510  4885d2           test rdx, rdx
0x055CD513  0f847a020000     je 0x055CD793          ; silent null-PlayerState return (matches CLAUDE.md)
0x055CD53E  488bfa           mov rdi, rdx           ; rdi = PlayerState
0x055CD543  4c8bf1           mov r14, rcx           ; r14 = this (ULokiRideableComponent)
0x055CD572  e8d9159bfb       call 0x00F7EB50        ; the stripped round-game-mode getter (fold)
0x055CD57A  0f8432020000     je 0x055CD7B2          ; -> the "failed to get the round game mode" bail
```

⇒ **`PlayersAttached` is `this + 0x130`, with `Num @ +0x138`, `Max @ +0x13C`, element size 8** — agreeing with the
offsets already in `CLAUDE.md`, derived here from a completely independent direction. [M]

Incidental free confirmation: `AuthPlayerEnterWorldAttachedToRidable` occupies **five chained** `pdata` rows —
`0x55CD510..0x55CD5A5..0x55CD77B..0x55CD794..0x55CD7B2..0x55CD7FA` = **746 bytes**, exactly the figure
`CLAUDE.md` records, and a live demonstration of the "the first row is not the function size" warning.

---

## 8. Q7 — reentrancy / thread safety

| hazard | finding | grade |
|---|---|---|
| takes a lock | `ResizeGrow` itself: **no**. `GMalloc->Realloc` (FMallocBinned2) takes its own internal locks — the same ones every UE allocation on the game thread already takes. | [M] for ResizeGrow; [I] for allocator internals (virtual call on a live object) |
| TLS / `gs:` access | **zero segment-prefixed memory operands** across all four functions (capstone `op.mem.segment != 0` count = 0) | **[M]** |
| can re-enter our `ProcessInternal` hook / `Func` swap | **No.** The complete call graph is `ResizeGrow -> {0x10078C0, 0xFAF9B0, 0xFAAC80}`; `0xFAF9B0 -> {0x1007EF0, 0xFAAD40}`; `0x1007EF0 -> {0xFF93C0, GMalloc vtable}`. **No UObject, no UFunction, no ProcessEvent, no script VM, no reflection, no GC entry point anywhere.** | **[M]** |
| GC interleave between grow and publish | Not reachable from inside the call, and the arm runs on the game thread inside a UFunction dispatch — which is also where GC runs. | [M] mechanism / [I] scheduling |
| cross-thread race on the array | The only real hazard: another thread mutating `component+0x130` concurrently. The arm is on the **game thread**, and the array reads `Data=0 Num=0 Max=0` (nothing has ever touched it). | [I] — rests on S131's live read |
| `GMalloc == null` | Handled by both callees (`QuantizeSize` returns `Count`; `Realloc` calls the lazy creator `0xFF93C0`). `merged4` shows GMalloc non-null. Not a hazard on a running game. | [M] |
| stack alignment / shadow space | `ResizeGrow` spills into the caller's 32-byte home area, and its callees may use aligned SSE. **A normal C++ function-pointer call satisfies both automatically; hand-written asm must not skip either.** | [M] |
| freeing a foreign pointer later | **Eliminated by construction** — the buffer comes from `GMalloc`, so the game's later `Empty()`/`RemoveAt()`/`Reset()`/destructor frees a pointer GMalloc owns. This is precisely the hazard the "point `Data` at our own buffer" alternative carries. | **[M]** |

**Verdict: no reentrancy hazard.**

---

## 9. Q8 — FINAL VERDICT and the exact call

**A hand-built direct call to `base + 0x00F988D0` from an injected DLL is SAFE and CORRECT for
`component+0x130` in its measured `Data=0 Num=0 Max=0` state.** [M for the mechanism]

Risk class: **DATA + one ordinary heap allocation. Zero module-image (`.text`) writes**, which puts it in this
project's 0/22 hazard bucket alongside every other data poke.

### Exact code

```cpp
// ---------------------------------------------------------------------------
//  base + 0x00F988D0
//  TArray<T, TSizedHeapAllocator<32>>::ResizeGrow(int32 OldNum), sizeof(T)==8, alignof(T)==8.
//
//  GENERIC ICF-shared instantiation: >= 4,256 verified direct call sites across
//  >= 3,292 functions.  NOT a UFunction -- an uncapped whole-image scan finds ZERO
//  stored pointers to it, so the S55 thunk primitive does not apply; this must be a
//  plain typed function-pointer call.
//
//  PRECONDITIONS (each one is FATAL-NORETURN: UE_LOG(Fatal) then `jmp $`, no dump):
//     arr->Num >= OldNum     0x00F988EA jl  -> OnInvalidArrayNum              (0x00FAAC80)
//     NewMax   >= 0          0x00FAF9C9 js  -> OnInvalidSizedHeapAllocatorNum (0x00FAAD40)
//
//  Clobbers only the Win64 volatiles (RAX RCX RDX R8 R9 R10 R11 XMM0-5, RFLAGS);
//  preserves RBX/RSI/RDI; uses the caller's 32-byte shadow space; takes no lock of its
//  own; touches no UObject / UFunction / ProcessEvent, so it cannot re-enter our hook.
//  Returns void (RAX is defined but is path-dependent garbage -- do not read it).
// ---------------------------------------------------------------------------
typedef void (__fastcall *FnArrayResizeGrow8)(void* /*TArray*  rcx*/, int32_t /*OldNum  edx*/);

// TArray<ALokiPlayerState*> memory layout -- confirmed from BOTH the callee's operands
// ([rcx+8] Num, [rcx+0xC] Max, [rcx+0] Data) and the game's own call site (stride 8).
struct FArray8 { void* Data; int32_t Num; int32_t Max; };
static_assert(sizeof(FArray8) == 16, "TArray header must be 16 bytes");

// ULokiRideableComponent::PlayersAttached  @ this+0x130 / Num +0x138 / Max +0x13C
FArray8* arr = (FArray8*)((uint8_t*)RideableComponent + 0x130);

const FnArrayResizeGrow8 ResizeGrow8 =
    (FnArrayResizeGrow8)(g_moduleBase + 0x00F988D0);

// ---- refuse rather than trip a noreturn ----
if (arr->Num < 0 || arr->Max < 0)                 { /* refuse: corrupt header */ return; }
if ((arr->Data == nullptr) != (arr->Max == 0))    { /* refuse: Data/Max disagree */ return; }

// ---- mirror the game's own tail at 0x055CD738..0x055CD767, with the publish deferred ----
const int32_t OldNum = arr->Num;                     // measured live: 0
if ((int64_t)OldNum + 1 > (int64_t)arr->Max) {       // 1 > 0  -> must grow
    ResizeGrow8(arr, OldNum);                        // guard: Num(0) >= OldNum(0) -> PASSES
}
// post-state, from walking the arithmetic: Data != null, Max == 4, Num still OldNum.
if (arr->Data == nullptr) { /* refuse: allocation failed */ return; }

((void**)arr->Data)[OldNum] = PlayerState;           // re-read Data: Realloc MAY have moved it
arr->Num = OldNum + 1;                               // publish LAST
```

### Two deliberate deviations from the game's own sequence, and why

1. **The game sets `Num = OldNum + 1` *before* calling; I publish `Num` last.**
   Both satisfy the guard (`1 >= 0` and `0 >= 0`), and I verified by walking the arithmetic that the two produce
   an **identical** result (in the `Max==0` branch `Grow = max(4, ArrayNum)` = 4 for `ArrayNum` of either 0 or 1;
   the `cmovg` MAX_int32 clamp fires in neither). Publishing last means that if anything aborts mid-sequence the
   array is left **consistent and empty** rather than `Num=1` over a null or uninitialised slot — which matters
   because `PlayersAttached` is a reflected `UPROPERTY` that GC and replication traverse, and the freshly
   `Realloc`'d 32 bytes are **uninitialised**.
   If you would rather match the measured-good path byte for byte, moving `arr->Num = OldNum + 1;` above the
   call is equally correct and equally safe.
2. **`arr->Data` is re-read after the call** — the game does this too (`0x055CD760`), because `Realloc` may move
   the block. Caching it across the call is the one easy way to get this wrong.

### What this lane does NOT establish

- That `component+0x130` still reads `Data=0 Num=0 Max=0` **at arm time** — that is S131's live read, **[I]** here.
- The concrete `GMalloc` subclass and therefore the exact `QuantizeSize` return — **[I]**, and nothing downstream
  depends on it (any `Q >= 32` is correct).
- 106 of the 4,362 naive call sites could not be boundary-verified (no `pdata_union` row), so **4,256 is a floor,
  not an exact count.** One hit (`0x00E4A03F`) was refuted as a mid-instruction false positive.
- Whether appending to `PlayersAttached` actually produces the dismount — that is Lane 1 / the arm's question.
  This lane says only that the *append* is mechanically safe and correct.
- The ordering hazard `CLAUDE.md` records — *do not poke `PlayersInside` (`+0x120`) first; it makes
  `HasEverContainedPlayer` true, which turns the wall into a silent no-op and destroys the error-line receipt* —
  concerns a **different array at a different offset** and is untouched by anything here. It still governs the arm.
