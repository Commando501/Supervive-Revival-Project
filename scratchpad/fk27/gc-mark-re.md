# FK-27 — the GC root-set / reachability exclusion predicate, at instruction level

Offline RE only. No process launched. All addresses are **RVAs** in the project's canonical cold
images; `file-offset == RVA` in both, so every quote below is a byte-for-byte read of the image.

* primary: `dumps/merged2.dump.exe` (ImageBase `0x7FF6AF000000`)
* control: `dumps/tutorial-hero/SUPERVIVE-Win64-Shipping.dump.exe` (ImageBase `0x7FF6505C0000`)

Tools written for this pass (all in `scratchpad/fk27/`): `fkdis.py` (PE reader + zero-page detector),
`dz.py` (capstone disassembler that resolves every rip-relative target **by machine**), `fn.py`
(exact function bounds from `tools/strxref/index/pdata_union.csv`), `grefs.py` / `grefs4.py`
(global-xref that verifies each candidate `disp32` by disassembling the containing function, so no
hand alignment guessing).

---

## 0. Answer in one paragraph

**The exclusion is INDEX-BASED, exactly as hypothesised — and the root *seed* is a separate
registry, exactly as the competing hypothesis (b) said. Both are true, and they are different
mechanisms.**

1. **Exclusion of the disregard-for-GC pool is a loop lower bound. [M]** Every one of the three
   whole-object-array sweeps in the GC starts iterating at `GUObjectArray.ObjFirstGCIndex`
   (`.data 0x9E38920`, value **39295** in both cold images *and* in the coordinator's live read),
   not at 0. Objects with `InternalIndex < 39295` are never visited, so their
   `FUObjectItem::Flags` word is never touched by GC and never acquires a reachability value.
   `EInternalObjectFlags::RootSet` (bit 30) plays **no part** in that exclusion.
2. **The root set that seeds the traversal is a `TSet<int32>` of InternalIndices at `.data 0x99D3CA0`. [M]**
   It is maintained by the *flag-setting function* `0x129AC90`, not derived from the flag word.
   `Num()` = **31** (merged2) / **29** (tuthero) — matching the coordinator's live "~32 high-index
   objects carrying bit 30". A raw `InterlockedOr` of bit 30 writes the mirror and never touches the
   registry, which is precisely why poking bit 30 does nothing.
3. **`EInternalObjectFlags::RootSet` IS tested by GC — but only inside a `test eax, 0x4E100000`
   whose branch *skips* the object**, and only in a pass that is itself gated off when
   `KeepFlags == 0`. It is never a "keep this" test on the sweep path.

---

## 1. Coverage statement (mandatory)

Every function quoted in this document is **fully decrypted in BOTH images and byte-identical
between them**. Measured with `fkdis.zero_pages` (page all-zero ⇒ not demand-decrypted):

| fn RVA | bytes | zero pages merged2 | zero pages tuthero | bytes identical |
|---|---|---|---|---|
| `0x0123D860` gather-unreachable body | 0x160 | 0 | 0 | yes |
| `0x0123E3B0` mark body A | 0xDC | 0 | 0 | yes |
| `0x0123E540` mark body B | 0xF6 | 0 | 0 | yes |
| `0x01243B50` clear-flag / registry remove | 0x13A | 0 | 0 | yes |
| `0x01250A40` GatherUnreachableObjects | 0x315 | 0 | 0 | yes |
| `0x01258F70` reachability-flag rotate | 0xAC | 0 | 0 | yes |
| `0x01259020` mark core (loop bounds) | 0x351 | 0 | 0 | yes |
| `0x0129AC90` set-flag / registry insert | 0x2D9 | 0 | 0 | yes |
| `0x0129B1A0` work-range splitter | 0x142 | 0 | 0 | yes |
| `0x0129B2F0` MarkObjectsAsUnreachable (timing) | 0x1C4 | 0 | 0 | yes |
| `0x01323CE0` internal-flag name printer | 0x235 | 0 | 0 | yes |
| `0x0135E3C0` CloseDisregardForGC | 0x41C | 0 | 0 | yes |
| `0x012398C2`, `0x01239B76` end-of-pass flag swap | 0xBE/0xBD | 0 | 0 | yes |

**Nothing in this report is coverage-blocked.** Detector calibration (positive control): the same
routine reports 13,642 all-zero pages of 30,280 in merged2 `.text` (54.95 % present), which agrees
with `tools/strxref/strxref.py census` (54.95 % readable) — so it does detect zero pages when they
exist.

`.data` values are read from single coherent snapshots: merged2 is a `.text`-only merge whose
`.data` is byte-identical to its seed (per `docs/fk18-fk19-multistate-merge-settled.md`), and
tuthero is a single dump. Both are quoted separately and never mixed.

---

## 2. How the code was located (method + positive control)

`tools/strxref/strxref.py` against merged2. `LogGarbage` itself has **0** code refs, so it was
useless — the productive anchors were the format strings, all of which resolve through the
UE 5.2+ `FStaticBasicLogRecord` pointer table:

| string RVA | text | site | function |
|---|---|---|---|
| `0x0773CCB0` | `CloseDisregardForGC: %d/%d objects in disregard for GC pool` | `0x135E7A0` | `0x135E3C0` |
| `0x0773CBB0` | `%i objects are not in the root set, but can never be destroyed because they are in the DisregardForGC set.` | `0x135E64C` | `0x135E3C0` |
| `0x0771D0F0` | `%f ms for MarkObjectsAsUnreachable Phase (%d Objects To Serialize)` | `0x129B488` | `0x129B2F0` |
| `0x0771D810` | `%f ms for Gather Unreachable Objects (…)` | `0x1250C62` | `0x1250A40` |
| `0x07736C18` | `(MaybeUnreachable<%d>) ` | `0x1323D52` | `0x1323CE0` |
| `0x07736C48` | `(Unreachable<%d>) ` | `0x1323D9E` | `0x1323CE0` |
| `0x0771D048` | `GC.MarkRootObjectsAsReachable` (trace scope) | `0x1259103` | `0x1259020` |
| `0x0771D088` | `GC.SlowMarkObjectAsReachable` (trace scope) | `0x12591BA` | `0x1259020` |
| `0x0771D8C8` | `GC.GatherUnreachable` (trace scope) | `0x1250B22` | `0x1250A40` |

Positive control that the search method works: the same technique located
`LogUObjectArray`'s `FLogCategoryBase` at `.data 0x9B38508` from
`lea rcx,[rip+0x8ad9d5a]` at `0x135E7A7`, and `byte[0x9B38508]` is compared against verbosity
constants (`cmp …,5`) exactly as the documented layout (`Verbosity@0`) predicts.

---

## 3. `GUObjectArray` — decoded [M]

**`GUObjectArray` (`FUObjectArray`) = RVA `0x9E38920`.** Independently derived here *before* the
coordinator's live read arrived, from `DisregardForGCEnabled()` inside `CloseDisregardForGC`
(`cmp dword ptr [0x9E38928], 0` at `0x135E63C`, i.e. `MaxObjectsNotConsideredByGC > 0`) plus the
`[rsi+0]/[rsi+4]/[rsi+8]/[rsi+0xC]` accesses in its tail. Agrees exactly with the live read.

| offset | RVA | field | merged2 | tuthero | live (coordinator) |
|---|---|---|---|---|---|
| +0x00 | `0x9E38920` | `int32 ObjFirstGCIndex` | **39295** | **39295** | **39295** |
| +0x04 | `0x9E38924` | `int32 ObjLastNonGCIndex` | 39294 | 39294 | 39294 |
| +0x08 | `0x9E38928` | `int32 MaxObjectsNotConsideredByGC` | 45000 | 45000 | 45000 |
| +0x0C | `0x9E3892C` | `bool OpenForDisregardForGC` | 0 | 0 | 0 |
| +0x10 | `0x9E38930` | `FUObjectItem** ObjObjects.Objects` | heap | heap | heap |
| +0x18 | `0x9E38938` | `FUObjectItem* PreAllocatedObjects` | NULL | NULL | NULL |
| +0x20 | `0x9E38940` | `int32 MaxElements` | 2162688 | 2162688 | 2162688 |
| +0x24 | `0x9E38944` | `int32 NumElements` | 455462 | 190844 | 207719 |
| +0x28 | `0x9E38948` | `int32 MaxChunks` | 33 | 33 | 33 |
| +0x2C | `0x9E3894C` | `int32 NumChunks` | 7 | 3 | 4 |
| +0x30 | `0x9E38950` | `FCriticalSection ObjObjectsCritical` | — | — | — |
| +0x60 | `0x9E38980` | free-index count (`ObjAvailableList`-ish) | 145668 | — | — |

Evidence for the layout, all in one function (`CloseDisregardForGC`, `0x135E3C0`):

```
0x0135E781  448b4604    mov r8d, dword ptr [rsi + 4]     ; ObjLastNonGCIndex
0x0135E785  41ffc0      inc r8d
0x0135E788  443b06      cmp r8d, dword ptr [rsi]         ; ObjFirstGCIndex
0x0135E78B  418bd0      mov edx, r8d
0x0135E78E  0f4c16      cmovl edx, dword ptr [rsi]
0x0135E791  8916        mov dword ptr [rsi], edx         ; ObjFirstGCIndex = max(ObjFirstGCIndex, ObjLastNonGCIndex+1)
0x0135E793  803d6e9dad0805  cmp byte ptr [rip + 0x8ad9d6e], 5      ; LogUObjectArray.Verbosity  (-> .data 0x9B38508)
0x0135E79C  448b4e08    mov r9d, dword ptr [rsi + 8]     ; MaxObjectsNotConsideredByGC
0x0135E7A0  488d15e1e43d06  lea rdx, [rip + 0x63de4e1]   ; -> 0x0773CC88, the log record whose Format is
                                                         ;    'CloseDisregardForGC: %d/%d objects in disregard for GC pool'
0x0135E7AE  e89dced0ff  call 0x0106B650
0x0135E7B3  c6460c00    mov byte ptr [rsi + 0xc], 0      ; OpenForDisregardForGC = false
0x0135E7BF  c605faa1660800  mov byte ptr [rip + 0x866a1fa], 0      ; -> .data 0x99D49C0  (GIsInitialLoad = false)
```

The chunked-array addressing (`chunk = idx >> 16`, `slot = idx & 0xFFFF`, stride `0x18`) is
reproduced verbatim in five separate places; canonical instance at `0x0123E596`:

```
0x0123E596  8bc1        mov eax, ecx                       ; ecx = ObjectIndex
0x0123E598  0fb7c0      movzx eax, ax
0x0123E59B  48c1e910    shr rcx, 0x10
0x0123E59F  488d1440    lea rdx, [rax + rax*2]             ; *3
0x0123E5A3  488b0586a3bf08  mov rax, qword ptr [rip + 0x8bfa386]   ; -> 0x9E38930  ObjObjects.Objects
0x0123E5AA  488b0cc8    mov rcx, qword ptr [rax + rcx*8]   ; chunk
0x0123E5AE  488b2cd1    mov rbp, qword ptr [rcx + rdx*8]   ; Item->Object      (+0x00)
0x0123E5B2  4c8d04d1    lea r8, [rcx + rdx*8]              ; FUObjectItem*
```

`(rax*3)*8 = rax*0x18` ⇒ stride `0x18` confirmed [M].

---

## 4. Reachability is a rotating *value* triple — the mechanism, found

Three `int32` globals, adjacent, in `.data`:

| RVA | role (from the debug printer) | merged2 | tuthero |
|---|---|---|---|
| `0x99D36A0` | **Reachable** (current) | 2 | 1 |
| `0x99D36A4` | **Unreachable** | 4 | 2 |
| `0x99D36A8` | **MaybeUnreachable** | 1 | 4 |
| `0x99D36AC` | unrelated int32, reads 1 in both — **unresolved** | 1 | 1 |

Roles are [M], not inferred: the internal-flag name printer `0x1323CE0` prints
`'(Unreachable<%d>) '` when `Flags & [0x99D36A4]` and `'(MaybeUnreachable<%d>) '` when
`Flags & [0x99D36A8]`, and it emits `'(Error: No reachability flag) '` when the item has none of
the three:

```
0x01323D04  8b0596f96a08  mov eax, dword ptr [rip + 0x86af996]   ; -> 0x99D36A0  Reachable
0x01323D0A  0b0598f96a08  or  eax, dword ptr [rip + 0x86af998]   ; -> 0x99D36A8  MaybeUnreachable
0x01323D10  0b058ef96a08  or  eax, dword ptr [rip + 0x86af98e]   ; -> 0x99D36A4  Unreachable
0x01323D16  85421c        test dword ptr [rdx + 0x1c], eax
0x01323D19  752a          jne 0x01323D45
0x01323D1B  448d461e      lea r8d, [rsi + 0x1e]                  ; 30
0x01323D1F  488d15622e4106 lea rdx, [rip + 0x6412e62]            ; -> 0x7736B88 '(Error: No reachability flag) '
```

**The rotation, in two O(1) steps per pass — no per-object write at all:**

*Start of pass* (`0x1258F70`, called from `MarkObjectsAsUnreachable`):
```
0x01258F84  8b051ea77708  mov eax, dword ptr [rip + 0x877a71e]   ; -> 0x99D36A8  MaybeUnreachable
0x01258F8C  448b050da77708 mov r8d, dword ptr [rip + 0x877a70d]  ; -> 0x99D36A0  Reachable
0x01258F96  890504a77708  mov dword ptr [rip + 0x877a704], eax   ; Reachable       = old MaybeUnreachable
0x01258FAE  448905f3a67708 mov dword ptr [rip + 0x877a6f3], r8d  ; MaybeUnreachable = old Reachable
```
*End of pass* (`0x12398C2` and the identical `0x1239B76`):
```
0x01239B76  8b0d289b7908  mov ecx, dword ptr [rip + 0x8799b28]   ; -> 0x99D36A4  Unreachable
0x01239B7C  8b05269b7908  mov eax, dword ptr [rip + 0x8799b26]   ; -> 0x99D36A8  MaybeUnreachable
0x01239B82  89051c9b7908  mov dword ptr [rip + 0x8799b1c], eax   ; Unreachable      = old MaybeUnreachable
0x01239B88  890d1a9b7908  mov dword ptr [rip + 0x8799b1a], ecx   ; MaybeUnreachable = old Unreachable
```

Net per pass: `(R,U,M) -> (M, R, U)` — a 3-cycle over the bit values `{1,2,4}`. **Internal
consistency check [M]:** tuthero is `(1,2,4)`; applying the cycle twice gives `(2,4,1)`, which is
exactly merged2. The two snapshots are two GC passes apart.

This is *the* reason "reachability is a value, not a bit" (S110): the sweep never clears anything
population-wide — it renames the constants, so every object that was `Reachable` becomes
`MaybeUnreachable` for free, and everything still `MaybeUnreachable` at the end of the pass becomes
`Unreachable` for free.

### The internal-flag vocabulary for THIS build [M]

Recovered wholesale from the printer at `0x1323CE0` (bit shift → label string it emits):

| bit | value | label emitted | note |
|---|---|---|---|
| 0/1/2 | 1/2/4 | `(Unreachable<%d>) ` / `(MaybeUnreachable<%d>) ` / *(reachable = silent)* | rotating triple |
| 20 | 0x00100000 | `(loaderimport) ` | |
| 21 | 0x00200000 | `(Garbage) ` | |
| 23 | 0x00800000 | *(not printed)* | tested in the cluster path at `0x0123D770` — `ReachableInCluster` [I] |
| 24 | 0x01000000 | `(ClusterRoot) ` | |
| 25 | 0x02000000 | `(native) ` | |
| 26 | 0x04000000 | `(async) ` | |
| 27 | 0x08000000 | `(asyncloading) ` | |
| 30 | 0x40000000 | `(root) ` | RootSet |

Also printed: `(standalone) ` from `EObjectFlags` bit 1, `(Clustered) ` when `ClusterRootIndex > 0`,
`(NeverGCed) ` from a bool, and — decisively — **`(Error: Reachable but NeverGCed) `**
(`0x7736BD0`, emitted at `0x1323D33` when a "NeverGCed" item carries the Reachable value). The
engine's own debug code treats "a disregard-for-GC object that is marked reachable" as an
**error state**, which is the same statement as the loop bound, said in the game's own words.

Stock `EInternalObjectFlags::Unreachable` (bit 28) is **absent from this vocabulary entirely** —
consistent with it never having been observed set.

---

## 5. The GC pass, as built

```
0x01259DA1  call 0x0129B2F0                      (sole caller)
  0x0129B2F0  FRealtimeGC::MarkObjectsAsUnreachable  [I name]
    ...        special-case: add GGCObjectReferencer if it is in the disregard pool  (§6.2)
    0x0129B449 call 0x01258F70
      0x01258F70  rotate Reachable/MaybeUnreachable  (§4)
                  + GObjectCountDuringLastMarkPhase = NumElements - Available - ObjFirstGCIndex
      0x01259017 jmp  0x01259020
        0x01259020  phase 1: copy root-index TSet -> TArray<int32>, split, ParallelFor
                              'GC.MarkRootObjectsAsReachable'  body 0x0123E3B0     (§7)
                    phase 2: IF KeepFlags != 0 -> split [ObjFirstGCIndex, NumElements), ParallelFor
                              'GC.SlowMarkObjectAsReachable'   body 0x0123E540     (§6.1)
  ...
  0x01250A40  GatherUnreachableObjects  [I name]
                    split [GExitPurge ? 0 : ObjFirstGCIndex, NumElements), ParallelFor
                    'GC.GatherUnreachable'  body 0x0123D860                        (§6.3)
  0x012398C2 / 0x01239B76  end-of-pass swap(Unreachable, MaybeUnreachable)
```

`0x129B1A0` is the **work-range splitter**, not a per-object body: it takes `r8d = End`,
`r9d = Start`, computes `ebp = End - Start` (`0x0129B1C5 sub ebp, r9d`), divides by the worker
count and emits 0x20-byte `{cur, cur, count, last}` range descriptors, advancing `edi += ebp`. Every
whole-array sweep goes through it, so the `Start` argument *is* the iteration lower bound.

---

## 6. The exclusion predicates — verbatim

### 6.1 The loop lower bound (this is the answer to the headline question) [M]

`0x01259020`, the mark core. Second `ParallelFor` domain:

```
0x01259156  399df0070000    cmp dword ptr [rbp + 0x7f0], ebx    ; ebx == 0 ; [rbp+0x7f0] == arg3 (KeepFlags)
0x0125915C  0f849b000000    je  0x012591FD                      ; KeepFlags == 0 -> SKIP THE WHOLE ARRAY SCAN
0x01259162  448b0db7f7bd08  mov r9d, dword ptr [rip + 0x8bdf7b7] ; -> 0x9E38920  ObjFirstGCIndex   <-- START
0x01259169  488d4d88        lea rcx, [rbp - 0x78]
0x0125916D  448b05d0f7bd08  mov r8d, dword ptr [rip + 0x8bdf7d0] ; -> 0x9E38944  NumElements       <-- END
0x01259174  8bd6            mov edx, esi
0x01259176  895c2420        mov dword ptr [rsp + 0x20], ebx
0x0125917A  e821200400      call 0x0129B1A0                      ; split [ObjFirstGCIndex, NumElements)
```

`[rbp+0x7f0] == arg3` is machine arithmetic, not a guess: entry does `mov [rsp+0x18], r8d`
(arg3 home slot); then `push rbp/rsi/rdi`, `lea rbp,[rsp-0x7c0]`, `sub rsp,0x8c0`; so
`rbp = E-0x7D8` and `rbp+0x7F0 = E+0x18`, the same slot (`0x7F0-0x7D8 = 0x18`). `ebx` is zeroed at
`0x0125904D` and is callee-saved across the intervening calls.

`0x01250A40`, GatherUnreachableObjects — same bound, and here the engine spells out the exception:

```
0x01250AC8  803d4986ad0800  cmp byte ptr [rip + 0x8ad8649], 0    ; -> .data 0x9D29118   (GExitPurge)
0x01250AD1  448b0d487ebe08  mov r9d, dword ptr [rip + 0x8be7e48] ; -> 0x9E38920  ObjFirstGCIndex
0x01250ADB  448b05627ebe08  mov r8d, dword ptr [rip + 0x8be7e62] ; -> 0x9E38944  NumElements
0x01250AE2  440f45cb        cmovne r9d, ebx                      ; if (GExitPurge) START = 0
0x01250AEA  e8b1a60400      call 0x0129B1A0
```

i.e. `const int32 First = GExitPurge ? 0 : GUObjectArray.GetFirstGCIndex();`. **The only code path
in the entire GC that ever visits an object below `ObjFirstGCIndex` is the shutdown full purge.**

Third independent instance — the public object iterator ctor `0x011CC000`:

```
0x011CC013  488d0506c9c608  lea rax, [rip + 0x8c6c906]           ; -> 0x9E38920  &GUObjectArray
0x011CC024  41b9ffffffff    mov r9d, 0xffffffff                  ; Index = -1
0x011CC034  4584c0          test r8b, r8b                        ; bOnlyGCedObjects
0x011CC037  7410            je  0x011CC049
0x011CC039  8b05e5c8c608    mov eax, dword ptr [rip + 0x8c6c8e5] ; -> 0x9E38924  ObjLastNonGCIndex
0x011CC042  448b0ddbc8c608  mov r9d, dword ptr [rip + 0x8c6c8db] ; -> 0x9E38924
0x011CC049  41ffc1          inc r9d                              ; Index = ObjLastNonGCIndex + 1
0x011CC050  443b0dedc8c608  cmp r9d, dword ptr [rip + 0x8c6c8ed] ; -> 0x9E38944  NumElements
```

### 6.2 The corroborating special case [M]

`MarkObjectsAsUnreachable` has to hand-inject one object precisely because the pool is skipped:

```
0x0129B3EC  488b2dbd23b808  mov rbp, qword ptr [rip + 0x8b823bd] ; -> .data 0x9E1D7B0, a single UObject*
                                                                 ;    (FGCObject::GGCObjectReferencer [I])
0x0129B3F3  8b052bd5b908    mov eax, dword ptr [rip + 0x8b9d52b] ; -> 0x9E38924  ObjLastNonGCIndex
0x0129B3F9  394510          cmp dword ptr [rbp + 0x10], eax      ; Object->InternalIndex
0x0129B3FC  7f22            jg  0x0129B420                       ; NOT in the pool -> nothing to do
   ; in the pool -> append it to the initial ObjectsToSerialize array
```

`InternalIndex <= ObjLastNonGCIndex` is `FUObjectArray::IsDisregardForGC()`. The engine only bothers
with this because a disregard-pool object is otherwise **unreachable to the reachability
analysis itself**. That is an independent, in-binary statement of the exclusion.

### 6.3 The flag tests that DO exist (and why they are not the discriminator) [M]

**Mark body B** (`0x0123E540`, the `'GC.SlowMarkObjectAsReachable'` sweep over
`[ObjFirstGCIndex, NumElements)`), per object:

```
0x0123E5B6  4885ed          test rbp, rbp
0x0123E5B9  7460            je  skip                              ; (1) empty slot
0x0123E5BB  418b4008        mov eax, dword ptr [r8 + 8]           ; FUObjectItem::Flags
0x0123E5BF  a90000104e      test eax, 0x4e100000
0x0123E5C4  7555            jne skip                              ; (2) <-- RootSet|Native|Async|AsyncLoading|LoaderImport => SKIP
0x0123E5C6  4584f6          test r14b, r14b                       ; [.data 0x9E25DA1] GarbageEliminationEnabled [I]
0x0123E5C9  740b            je  0x0123E5D6
0x0123E5CB  418b4008        mov eax, dword ptr [r8 + 8]
0x0123E5CF  c1e815          shr eax, 0x15                         ; bit 21 = Garbage
0x0123E5D2  a801            test al, 1
0x0123E5D4  7545            jne skip                              ; (3) garbage
0x0123E5D6  8b4d0c          mov ecx, dword ptr [rbp + 0xc]        ; UObject::ObjectFlags (EObjectFlags @ +0x0C)
0x0123E5D9  498b4708        mov rax, qword ptr [r15 + 8]          ; -> KeepFlags
0x0123E5DD  8508            test dword ptr [rax], ecx
0x0123E5DF  743a            je  skip                              ; (4) no EObjectFlags keep flag
   ; keep:
0x0123E5E1  8b05c1507908    mov eax, dword ptr [rip + 0x87950c1]  ; -> 0x99D36A8  MaybeUnreachable
0x0123E5E7  f7d0            not eax
0x0123E5E9  f041214008      lock and dword ptr [r8 + 8], eax
0x0123E5EE  8b05ac507908    mov eax, dword ptr [rip + 0x87950ac]  ; -> 0x99D36A0  Reachable
0x0123E5F4  f041094008      lock or  dword ptr [r8 + 8], eax
   ; then append the UObject* to ObjectsToSerialize
```

Two things to note, and both matter for the coordinator's question:

* **`0x4E100000` is the *keep mask*, and matching it makes body B `skip`, not keep.** Decoded
  against the §4 vocabulary: `RootSet(30) | AsyncLoading(27) | Async(26) | Native(25) |
  LoaderImport(20)` = `0x40000000+0x08000000+0x04000000+0x02000000+0x00100000` = `0x4E100000` ✓.
  The constant occurs **17** times in `.text`; controls `0x4E100001` and `0x4E110000` occur **0**
  times each, so it is a real shared constant, not a coincidence.
* **Body B never runs in a shipping game if `KeepFlags == 0`** (the `je` at `0x0125915C`). UE's
  `GARBAGE_COLLECTION_KEEPFLAGS` is `GIsEditor ? RF_Standalone : RF_NoFlags` [I], so in this build
  the whole-array pass is very likely dead at runtime and the only seed is §7. **The runtime value
  of `KeepFlags` is [I]/unresolved statically** — it is arg3 threaded from `0x01259DA1`.

**Gather body** (`0x0123D860`) — the "is it unreachable?" test, confirming the value model:

```
0x0123D8FE  8b44d108        mov eax, dword ptr [rcx + rdx*8 + 8]  ; FUObjectItem::Flags
0x0123D902  85059c5d7908    test dword ptr [rip + 0x8795d9c], eax ; -> 0x99D36A4  Unreachable
0x0123D90C  7422            je  skip
   ; append FUObjectItem* to the unreachable list
```

---

## 7. What the gather actually enumerates — the root registry [M]

**Mark body A** (`0x0123E3B0`, the `'GC.MarkRootObjectsAsReachable'` pass). It has **no predicate
at all**: it walks an `int32` array of InternalIndices and marks each one reachable.

```
0x0123E400  498b5608        mov rdx, qword ptr [r14 + 8]          ; -> the TArray<int32>
0x0123E40D  488b02          mov rax, qword ptr [rdx]              ; Data
0x0123E410  8b1488          mov edx, dword ptr [rax + rcx*4]      ; ObjectIndex = Data[i]
0x0123E413  0fb7c2          movzx eax, dx
0x0123E418  48c1e910        shr rcx, 0x10
0x0123E420  488b0509a5bf08  mov rax, qword ptr [rip + 0x8bfa509]  ; -> 0x9E38930  ObjObjects.Objects
0x0123E42B  8b0577527908    mov eax, dword ptr [rip + 0x8795277]  ; -> 0x99D36A8  MaybeUnreachable
0x0123E431  f7d0            not eax
0x0123E437  f02144d108      lock and dword ptr [rcx + rdx*8 + 8], eax
0x0123E43C  8b055e527908    mov eax, dword ptr [rip + 0x879525e]  ; -> 0x99D36A0  Reachable
0x0123E442  f00944d108      lock or  dword ptr [rcx + rdx*8 + 8], eax
   ; then append Item->Object to ObjectsToSerialize
```

The array is produced at the top of `0x01259020`:

```
0x0125907E  488d542478      lea rdx, [rsp + 0x78]                 ; out TArray<int32>
0x01259083  488d0d16ac7708  lea rcx, [rip + 0x877ac16]            ; -> .data 0x99D3CA0   <-- THE ROOT REGISTRY
0x0125908A  e831b4f7ff      call 0x011D44C0                       ; TSet<int32>::Array(out)
0x0125909C  448b4580        mov r8d, dword ptr [rbp - 0x80]       ; out.Num
0x012590A7  4533c9          xor r9d, r9d                          ; START = 0  (a list, not the object array)
0x012590B0  e8eb200400      call 0x0129B1A0
```

### `0x99D3CA0` is a `TSet<int32>` of InternalIndices [M]

Decoded from the sparse-array arithmetic in `0x0129AC90` / `0x01243B50` / `0x011D44C0`
(`Num() = Elements.ArrayNum - NumFreeIndices`; element stride 12 via `lea rcx,[rax+rax*2]`,
`[rdx+rcx*4]`):

| offset | RVA | field | merged2 | tuthero |
|---|---|---|---|---|
| +0x00 | `0x99D3CA0` | `Elements.Data` | heap | heap |
| +0x08 | `0x99D3CA8` | `Elements.ArrayNum` | 49349 | 70358 |
| +0x0C | `0x99D3CAC` | `Elements.ArrayMax` | 67925 | 93525 |
| +0x30 | `0x99D3CD0` | `FirstFreeIndex` | 34393 | 50089 |
| +0x34 | `0x99D3CD4` | `NumFreeIndices` | 49318 | 70329 |
| +0x40 | `0x99D3CE0` | `Hash.Data` | heap | heap |
| +0x48 | `0x99D3CE8` | `HashSize` | 32768 | — |
| | | **`Num()`** | **31** | **29** |

**31 / 29 against the coordinator's live "~32 high-index objects carrying bit 30".** Three
independent snapshots, same order of magnitude, and the mechanism below explains why they must be
equal.

### Membership is granted by the flag-*setting* function, not by the flag [M]

`0x0129AC90(FUObjectItem* rcx, EInternalObjectFlags edx)` — atomically OR flags **and** maintain
the registry:

```
0x0129AC90  4053            push rbx                              ; entry
0x0129AC9F  488d0d4a8fb808  lea rcx, [rip + 0x8b88f4a]            ; -> .data 0x9E23BF0 (a CRITICAL_SECTION)
0x0129ACA8  ff1572f73a06    call qword ptr [rip + 0x63af772]      ; EnterCriticalSection
0x0129ACAE  8b4308          mov eax, dword ptr [rbx + 8]          ; Item->Flags
0x0129ACB1  a90000104e      test eax, 0x4e100000
0x0129ACB6  0f854e020000    jne 0x0129AF0A                        ; already tracked -> no insert
0x0129ACBC  833d65dcb90800  cmp dword ptr [rip + 0x8b9dc65], 0    ; -> 0x9E38928 MaxObjectsNotConsideredByGC
0x0129ACC3  0f9fc0          setg al
0x0129ACC6  840560dcb908    test byte ptr [rip + 0x8b9dc60], al   ; -> 0x9E3892C OpenForDisregardForGC
0x0129ACCC  0f8538020000    jne 0x0129AF0A                        ; still in initial load -> no insert
0x0129ACD2  488b03          mov rax, qword ptr [rbx]              ; Item->Object
0x0129ACF0  8b7010          mov esi, dword ptr [rax + 0x10]       ; Object->InternalIndex
0x0129ACDF  488d0dba8f7308  lea rcx, [rip + 0x8738fba]            ; -> 0x99D3CA0
0x0129ACF3  e83877faff      call 0x01242430                       ; TSet<int32>::FindOrAdd(InternalIndex)
   ...  (hash-bucket insert inline through 0x0129AEF6)
0x0129AF0A  8b4308          mov eax, dword ptr [rbx + 8]          ; <-- common tail: the FLAG WRITE
0x0129AF20  8bc8            mov ecx, eax
0x0129AF22  0bcf            or  ecx, edi                          ; edi = FlagsToSet
0x0129AF24  f00fb14b08      lock cmpxchg dword ptr [rbx + 8], ecx
0x0129AF42  ff15e0f43a06    call qword ptr [rip + 0x63af4e0]      ; LeaveCriticalSection
```

Its exact inverse, `0x01243B50(FUObjectItem*, FlagsToClear)`:

```
0x01243B71  8b4b08          mov ecx, dword ptr [rbx + 8]
0x01243B74  f7c10000104e    test ecx, 0x4e100000
0x01243B7A  0f84c4000000    je  tail                              ; wasn't tracked
0x01243B80  8bc7            mov eax, edi
0x01243B82  f7d0            not eax
0x01243B84  23c1            and eax, ecx                          ; flags AFTER the clear
0x01243B86  a90000104e      test eax, 0x4e100000
0x01243B8B  0f85b3000000    jne tail                              ; still keeps something -> stay in the set
0x01243B91  8b0511017908    mov eax, dword ptr [rip + 0x8790111]  ; -> 0x99D3CA8
0x01243B97  3b0537017908    cmp eax, dword ptr [rip + 0x8790137]  ; -> 0x99D3CD4  (set empty?)
   ; else remove Object->InternalIndex from the TSet at 0x99D3CA0
```

**Invariant [M]:** `0x99D3CA0` contains `Object->InternalIndex` for exactly those objects whose
`FUObjectItem::Flags & 0x4E100000 != 0` **and** whose first keep-flag was set *after*
`OpenForDisregardForGC` went false.

Three consequences, all of which match the live measurements:

1. **A raw `InterlockedOr(&Item->Flags, 0x40000000)` never touches `0x99D3CA0`.** The object is not
   in the seed list, body A never sees it, and body B (if it even runs) *skips* it because
   `test eax,0x4E100000` now matches. So bit 30 poked externally is inert in both directions —
   two independent reasons. This is the answer to "bit 30 appears to be a MIRROR of a registration
   the root gather reads somewhere else": the registration is the `TSet<int32>` at `0x99D3CA0`.
2. **Objects that carry bit 30 "naturally" are the disregard-for-GC pool** — flagged during initial
   load, when the `0x0129ACCC` gate was still closed, so they were *never inserted*. They are also
   below `ObjFirstGCIndex`, so no sweep ever writes their Flags word. Hence 0 % of them carry a
   reachability value: **their flag word is simply never touched by GC.** That is the direct
   explanation of the tension in the task brief.
   `CloseDisregardForGC` is the proof: its loop calls this very function
   (`0x0135E4C9 mov edx,0x40000000; call 0x0129AC90` — `AddToRoot()`) while
   `OpenForDisregardForGC` is still 1, and only sets it to 0 afterwards at `0x0135E7B3`.
3. **The ~31 high-index rooted objects are the post-load `AddToRoot()` callers**, in the registry,
   marked unconditionally by body A on every pass.

---

### 7a. Complete writer census for `0x99D3CA0` [M]

Four functions reference the registry; `grefs4.py` verified every candidate `disp32` by disassembling
the containing function, so these are real instructions, not alignment guesses.

| function | what it does to the set | insert/remove condition | does it run in this build? |
|---|---|---|---|
| `0x0129AC90` set internal flags | **insert** `Object->InternalIndex` (via `0x01242430`, rehash `0x010D5E90`) | `!(Item->Flags & 0x4E100000)` **and** `!(MaxObjectsNotConsideredByGC > 0 && OpenForDisregardForGC)` | yes — every keep-flag set after initial load |
| `0x01243B50` clear internal flags | **remove** | had a keep flag **and** `(Flags & ~ToClear) & 0x4E100000 == 0` | yes — every `RemoveFromRoot` |
| `0x0123E0E1` body of the `'GC.OnDisregardForGCSetDisabled'` ParallelFor (thunk `0x012435B0`, driver `0x012596A0`) | marks **every** object Reachable, then **inserts** every object carrying a keep flag | `Flags & 0x4E100000` (opposite polarity to `0x0129AC90`) | **no.** Its domain is `[0, N)` — `0x012596D2 xor r9d, r9d` sets START = 0, so it *would* cover the pool. But it fires only when disregard-for-GC is *disabled*, and this build has `MaxObjectsNotConsideredByGC = 45000` / `ObjFirstGCIndex = 39295`, i.e. enabled. Independently bounded by the live census: 0 of ~4,915 pool objects carry a reachability value, which this pass would have given them. |
| `0x01259020` mark core | read-only (`0x011D44C0` copies it) | — | every GC pass |

**Fold multiplicity = 1 for both mutators [M].** The first 24 bytes of `0x0129AC90`, `0x01243B50`
and `0x0123E3B0` each occur **exactly once** in `.text`. Control: the first 7 bytes of
`0x05254180` — the execFoo thunk `CLAUDE.md` records as 91-way ICF-folded — occur **907** times.
So the detector distinguishes folded from unfolded, and these are unfolded.

---

## 8. Verdict on the four hypotheses

| hypothesis | verdict |
|---|---|
| (a) **index-based, disregard-for-GC / permanent pool** | **CONFIRMED [M]** — three independent sweeps bound at `[ObjFirstGCIndex, NumElements)`; `GExitPurge` is the only escape; `GGCObjectReferencer` needs a hand-written exception precisely because of it. |
| (b) **root set gathered into a separate array; flag is bookkeeping** | **CONFIRMED [M]** — `TSet<int32>` at `0x99D3CA0`, `Num()` = 31/29, maintained by `0x129AC90`/`0x1243B50`. Both (a) and (b) are true; they answer different halves of the question. |
| (c) **UE 5.4 clustering does the exclusion** | **NO.** Clustering exists (`ClusterRootIndex` at `FUObjectItem+0x0C`, cluster stride `0x50`, dissolve loop at `0x0123D6CC` testing bit 23), but it is a *separate* traversal optimisation, not the root/exclusion predicate. |
| (d) **the flag IS tested, with a different bit or compound mask** | **PARTLY — and it is a red herring.** The compound mask `0x4E100000` (`RootSet\|Native\|Async\|AsyncLoading\|LoaderImport`) is tested at `0x0123E5BF`, `0x0129ACB1` and `0x01243B74`. On the sweep path the matching branch **skips**; the mask's only *positive* use is registry bookkeeping. **This does not contradict the live measurement — it explains it.** |

---

## 9. Address index

| RVA | what it is | confidence |
|---|---|---|
| `.data 0x9E38920` | `GUObjectArray` (`FUObjectArray`) | [M] |
| `.data 0x9E38920/24/28/2C` | `ObjFirstGCIndex` / `ObjLastNonGCIndex` / `MaxObjectsNotConsideredByGC` / `OpenForDisregardForGC` | [M] |
| `.data 0x9E38930/40/44/48/4C` | `ObjObjects.Objects/MaxElements/NumElements/MaxChunks/NumChunks` | [M] |
| `.data 0x99D36A0/A4/A8` | Reachable / Unreachable / MaybeUnreachable flag **values** | [M] |
| `.data 0x99D36AC` | adjacent int32, reads 1 in both images | **unresolved** |
| `.data 0x99D3CA0` | **root registry**, `TSet<int32>` of InternalIndices | [M] |
| `.data 0x9E23BF0` | CRITICAL_SECTION guarding the registry | [M] |
| `.data 0x99D49C0` | `GIsInitialLoad` | [I] |
| `.data 0x9D29118` | `GExitPurge` | [I] |
| `.data 0x9E1D7B0` | single `UObject*` special-cased into the initial serialize set (`GGCObjectReferencer`) | [I] |
| `.data 0x9E25DA1` | bool, gates the bit-21 (Garbage) test (`gc.GarbageEliminationEnabled`) | [I] |
| `.data 0x9B38508` | `LogUObjectArray` `FLogCategoryBase` | [M] |
| `0x0129AC90` | set internal flags + insert into root registry | [M] |
| `0x01243B50` | clear internal flags + remove from root registry | [M] |
| `0x01242430` | `TSet<int32>::FindOrAdd` | [I] |
| `0x011D44C0` | `TSet<int32>::Array()` → `TArray<int32>` | [I] |
| `0x0129B1A0` | parallel work-range splitter (`Start`=r9d, `End`=r8d) | [M] |
| `0x01258F70` | start-of-pass reachability rotate + object-count | [M] |
| `0x01259020` | mark core; owns **both** loop bounds | [M] |
| `0x0123E3B0` | mark body A — root index list, unconditional | [M] |
| `0x0123E540` | mark body B — KeepFlags scan over `[ObjFirstGCIndex, NumElements)` | [M] |
| `0x01250A40` / `0x0123D860` | GatherUnreachableObjects + its body | [M] |
| `0x0123D6CC` | cluster dissolve / mark clustered objects unreachable | [I] |
| `0x0129B2F0` | `MarkObjectsAsUnreachable` timing wrapper (sole caller `0x01259DA1`) | [I] name |
| `0x0135E3C0` | `FUObjectArray::CloseDisregardForGC` | [I] name, [M] behaviour |
| `0x011CC000` | object-iterator ctor (`Index = ObjLastNonGCIndex + 1`) | [M] |
| `0x01323CE0` | internal-flag → debug string printer (the flag vocabulary oracle) | [M] |

---

## 10. `KeepFlags` — CLOSED offline. It is **0**, and the registry is the entire seed [M]

`KeepFlags` is not a threaded stack argument at the top: `CollectGarbage` parks it in a **static
global**, so it is directly RPM-readable and directly readable out of the cold images.

```
; 0x01243CE0  CollectGarbage(EObjectFlags KeepFlags /*ecx*/, bool bPerformFullPurge /*dl*/)
0x01243CF1  0fb6da          movzx ebx, dl
0x01243CF4  8bf9            mov edi, ecx                            ; edi = KeepFlags
...
0x01243D6C  893dd615be08    mov dword ptr [rip + 0x8be15d6], edi    ; -> .data 0x09E25348   KeepFlags
0x01243D72  881dd415be08    mov byte  ptr [rip + 0x8be15d4], bl     ; -> .data 0x09E2534C   bPerformFullPurge
0x01243D8B  488d0d2e15be08  lea rcx, [rip + 0x8be152e]              ; -> .data 0x09E252C0   the STATIC GC state object
0x01243D92  e8c9620100      call 0x0125A060                         ; CollectGarbageInternal(state, …)
```

`0x9E25348 - 0x9E252C0 = 0x88`, and `0x01259CFE mov ecx, dword ptr [rbx + 0x88]` in the incremental
driver reads the same field off the same state object — so the global *is* `state->KeepFlags`.

**Three independent measurements, all agreeing:**

1. **Every direct call site of both public entry points passes 0.**
   `CollectGarbage` (`0x1243CE0`): **8/8** sites `xor ecx, ecx`.
   `TryCollectGarbage` (`0x129C300`): **2/2** sites `xor ecx, ecx`.
   *Tool control* — `argtrace.py` is not simply printing `xor ecx, ecx` by default: pointed at
   `0x0129AC90` it reports **12 distinct** arg1 forms (`mov rcx, rdi` ×27, `mov rcx, r12` ×11,
   `xor ecx, ecx` ×11, `lea rcx, [rcx+rdx*8]` ×5, …).
2. **No indirect caller can exist.** `findptr` finds **zero** stored qwords equal to either entry
   point anywhere in the image, so no vtable/delegate/task can invoke them with a different value.
3. **The resting value reads 0 in both cold images** (two different process lifetimes):
   `[.data 0x9E25348] = 0` in merged2 **and** in tuthero.

`0` is `RF_NoFlags`, i.e. `GARBAGE_COLLECTION_KEEPFLAGS` with `GIsEditor == false` — the ternary was
constant-folded at compile time, which is why no site ever loads `RF_Standalone` (2).

⇒ **The gate at `0x01259156` always fires and mark body B never executes.** And the conclusion does
not even depend on the gate: body B's own inner test is
`0x0123E5DD test dword ptr [rax], ecx` with `[rax] == KeepFlags == 0`, which can never be true, so
the pass is semantically empty either way. **Mark body B is dead in this build.**

⇒ **The reachability seed is exactly two things: the `TSet<int32>` at `0x99D3CA0`, and the single
`GGCObjectReferencer` special case at `0x0129B3F9`.** Inserting into the registry is therefore
**sufficient**, not merely necessary.

*(Aside: the mark phase is additionally skipped on resumption —
`0x01259D8A cmp byte ptr [.data 0x9E2534D], 0` / `0x01259D9F jne 0x01259DA6` — that byte is
`state+0x8D`, the "incremental reachability already in progress" flag [I].)*

**If you want a live confirmation anyway (one RPM read, no breakpoint):**
`*(int32*)(base + 0x9E25348)` — expect `0`. Neighbours on the same static GC state object
`base + 0x9E252C0`: `+0x88` KeepFlags, `+0x8C` bPerformFullPurge, `+0x8D` in-progress.

---

## 11. THE DELIVERABLE — how an injected DLL gets a high-index UObject marked

**One call. Add the object's index to the registry by calling the engine's own flag-setter.**

```c
// base = module base of SUPERVIVE-Win64-Shipping.exe
// Microsoft x64 calling convention: rcx = FUObjectItem*, edx = flags. Returns bool in al
// (true == the flag word actually changed).  Fold multiplicity 1 [M].
typedef bool (*FSetInternalFlags)(void* /*FUObjectItem**/ item, uint32_t flags);
typedef bool (*FClrInternalFlags)(void* /*FUObjectItem**/ item, uint32_t flags);

FSetInternalFlags AddKeep    = (FSetInternalFlags)(base + 0x0129AC90);   // insert + set
FClrInternalFlags RemoveKeep = (FClrInternalFlags)(base + 0x01243B50);   // remove + clear

// FUObjectItem* for an object, from GUObjectArray at base + 0x9E38920:
//   int32          idx     = *(int32*)((char*)obj + 0x10);          // UObjectBase::InternalIndex
//   FUObjectItem** chunks  = *(FUObjectItem***)(base + 0x9E38930);  // ObjObjects.Objects
//   FUObjectItem*  item    = (char*)chunks[idx >> 16] + (idx & 0xFFFF) * 0x18;

AddKeep(item, 0x40000000);      // EInternalObjectFlags::RootSet
...
RemoveKeep(item, 0x40000000);   // paired teardown
```

Why this is sufficient, not just necessary: mark body A (`0x0123E3B0`) walks the copied registry
with **no predicate whatsoever** — it clears `MaybeUnreachable`, sets `Reachable`, and pushes the
`UObject*` into `ObjectsToSerialize`, so the object's *references* are traversed too. And per §10,
that list plus one hard-coded object is the whole seed.

**Preconditions and hazards (all [M] from the disassembly):**

* `item` must not already carry any of `0x4E100000` — otherwise `0x0129ACB1` skips the insert
  (harmless: it would already be registered, unless it was flagged during initial load). A
  runtime-loaded, high-index object never is.
* `OpenForDisregardForGC` (`base + 0x9E3892C`) must be `0` — it is, in every image and live.
* Objects **below** `ObjFirstGCIndex` (39295) do not need this and cannot benefit: they are never
  swept, so they can never be collected either.
* The function takes the critical section at `base + 0x9E23BF0` and may **allocate** (TSet growth /
  rehash through `0x010D5E90`). Do not call it from a GC callback or from inside a reachability
  pass, and do not call it on a thread that already holds that lock.
* Returns `true` only if the flag word changed; a `false` return with the object already registered
  is still a success.
* **No `.text` write, no module-image modification** — this is a heap + `.data` mutation through the
  engine's own entry point, i.e. the safest class on this project's measured hazard ladder.

**A raw `InterlockedOr(&item->Flags, 0x40000000)` does NOT work** and never did: it writes the
mirror without the registry insert, so body A never sees the object; and it simultaneously makes
`0x0129AC90` refuse the insert on any later, correct call. If a shim has already poked the bit, call
`RemoveKeep(item, 0x40000000)` first, then `AddKeep(item, 0x40000000)`.

---

## 12. Reconciliation note — `ArrayNum` is not `Num()` (recorded so it is not re-hit)

A live census independently read `0x99D3CA0` and got `ArrayNum = 49,307`, against the 31/29 reported
here, and provisionally concluded the registry contained ~39k disregard-pool objects. **Both numbers
were correct reads of different fields**; the discrepancy has been withdrawn by the coordinator, and
the mechanism is worth keeping:

* `0x99D3CA0` is a `TSet<int32>` over a `TSparseArray`. `+0x08 ArrayNum` counts **slots**
  (live + freed); the live count is `ArrayNum - NumFreeIndices` at `+0x34`. Live: `49307 - 49275 =`
  **32**. merged2: `49349 - 49318 =` **31**. tuthero: `70358 - 70329 =` **29**.
* The engine agrees: `0x011D44C0`, the function the mark core calls to materialise the root list,
  opens with `0x011D44EB mov edx,[rcx+8]` / `0x011D44EE sub edx,[rcx+0x34]`, then iterates with a
  **const-set-bit iterator** over the AllocationFlags bit array (`0x011D452C mov r10,[rax+0x10]`,
  `0x011D4533 cmove r10, rax`, `0x011D4576 eax = ecx & -ecx`, `bsr`), so only allocated slots are
  copied.
* Two traps that made the wrong read look validated:
  * **The inline `FF FF FF FF ×4` at `+0x10..0x1F` is dead storage, not "all bits allocated".**
    `NumBits = 49307 > 128`, so the `TInlineAllocator<4>` has spilled; `0x011D4533 cmove r10, rax`
    proves the code uses the secondary pointer whenever it is non-null and ignores the inline words.
  * **A freed slot is indistinguishable from a live one by field-range checks.** A free slot holds
    `FElementOrFreeListLink { int32 PrevFreeIndex; int32 NextFreeIndex; }` over the first 8 bytes of
    the 12-byte element, leaving the third dword stale. So "`HashNextId` is −1 or a valid index" is
    *tautologically* satisfied by the free-list encoding, "`HashIndex < HashSize`" is satisfied by
    the stale value, and "`Value` is a live object index" is satisfied ~80 % of the time because
    slot indices land in `[0, 49307)` and object indices `0..39294` are the always-live pool.
  * Quantitative tell: of the 49,307 slots, 39,263 had a `Value` below `ObjFirstGCIndex`.
    `39295 − 39263 = 32` — exactly the live element count. A genuine 49k-member root set has no
    reason to produce that identity; a free-list permutation over the slot space does.
* **Rule:** on any `TSet`/`TSparseArray` in this image, read `+0x08` and `+0x34` together, and gate
  enumeration on the AllocationFlags bit array at `+0x20` (secondary) / `+0x10` (inline, only when
  `NumBits <= 128`). Never enumerate `ArrayNum` slots raw.

---

## 13. Unresolved

* `.data 0x99D36AC` — adjacent to the reachability triple, compared against small ints at
  `0x012356F5`, `0x01235869`, `0x012398F6`, `0x01239BAA`, `0x01258FD7`. Not identified. Does not
  affect any conclusion above.
* Bit 23's name (`ReachableInCluster` [I]) — the printer emits no label for it; only the cluster
  path at `0x0123D770` tests it.
* `fn 0x01259D72` has **no** direct caller and **no** stored function pointer anywhere in `.text`
  or the data sections. Its caller is presumably in one of the 13,642 undecrypted `.text` pages —
  **coverage-blocked**. It does not matter: §10 settles `KeepFlags` at the value's origin and at its
  resting place, both of which are decrypted.
* `.data 0x99D36AC` — adjacent to the reachability triple, compared against small ints at
  `0x012356F5`, `0x01235869`, `0x012398F6`, `0x01239BAA`, `0x01258FD7`. Not identified.
* Bit 23's name (`ReachableInCluster` [I]) — the printer does not emit a label for it; only the
  cluster path at `0x0123D770` tests it.
* Whether anything besides `0x0129AC90` / `0x01243B50` can mutate `0x99D3CA0`. Verified refs are
  limited to `0x0123E0E1..0x0123E3A4`, `0x01243B50..0x01243C8A`, `0x01259020..0x01259371`,
  `0x0129ACDA..0x0129AF0A` — but that census only covers functions with a `.pdata` entry that the
  disp32 scan reached, so it is a lower bound, not an exhaustive proof.
