# FK-27 — How a UObject is actually kept alive in THIS build

**Offline RE only.** No process was launched. All work against `dumps/merged2.dump.exe`
(ImageBase `0x7FF6AF000000`) and `dumps/tutorial-hero/SUPERVIVE-Win64-Shipping.dump.exe`
(ImageBase `0x7FF6505C0000`). Tools written for this pass live in `scratchpad/fk27/`
(`dumplib.py`, `riprefs.py`, `funcs.py`, `callers.py`, `immscan.py`, `lockscan.py`,
`strfind.py`, `ctx.py`).

Every claim is tagged **[M] measured** (read out of the image) or **[I] inferred**.

---

## 0. HEADLINE

> **`AddToRoot` in this build does TWO things, not one.** It (1) inserts the object's
> `InternalIndex` into a **global `TSet<int32>` at `.data +0x99D3CA0`**, under a global
> `RTL_CRITICAL_SECTION` at `.data +0x9E23BF0`; and only then (2) atomically ORs
> `0x40000000` into `FUObjectItem.Flags`.
>
> **The garbage collector's root gather reads the `TSet`. It does not read the flag.** [M]
> The GC's own name for that pass — read verbatim out of `.rdata` — is
> `GC.MarkRootObjectsAsReachable`.
>
> ⇒ The shim's `InterlockedOr(&item->Flags, 1<<30)` sets a bit that the collector never
> consults for root discovery. **The measured inertness is fully explained, and the missing
> half is a container insert that only the engine's own code performs.**
>
> ⇒ **The flag value is NOT the bug.** `RootSet == bit 30 == 0x40000000` is correct and is
> confirmed three independent ways below. The project's constant `KGCROOTBIT` was right;
> the *mechanism* was incomplete.

**And there is a second-order trap that makes the current shim actively harmful:**
`SetRootFlags` early-outs on `if (item->Flags & 0x4E100000) skip the container insert`.
An object the shim has already poked therefore looks "already a root" to the real
`AddToRoot`, which then **skips the `TSet` insert and returns having done nothing useful.**
The existing poke does not merely fail — **it poisons the correct call.** See §6.

---

## 1. Coverage and instrument caveats (state these with any negative)

| image | `.text` pages non-zero | % |
|---|---|---|
| `merged2.dump.exe` | 16,638 / 30,281 | **54.95 %** [M] |
| `tutorial-hero/…dump.exe` | 16,112 / 30,281 | **53.21 %** [M] |

⚠ `CLAUDE.md` records merged2 as 16,625 / 54.90 %. My count (`dumplib.py:coverage`) is
non-zero 4 KB pages over the raw section size and gives 16,638. The 13-page difference is
not chased here; **do not treat either number as exact to the page** — the point is ~55 %,
and every specific address below was checked individually.

- Every address named in this document was checked: **not on an all-zero page in either
  image, and byte-identical between the two images** (different ImageBases, so this is a
  real cross-check, not a copy). [M]
- Function extents come from `tools/strxref/index/pdata_union.csv` (382,704 rows, union of
  ~69–76 dumps). The `.pdata` **section** is 100 % zero in every capture (CLAUDE.md S115-a/b),
  so extents must never be read from the image itself. **Several of the functions here are
  split into multiple pdata CHUNKS** — a chunk row is not a function start; e.g. the entry of
  the disregard pass is `0x123E0B0`, not the `0x123E0E1` chunk row a naive lookup returns.
- `riprefs.py`'s back-off decoder can render `48 8B 05` as `mov eax,…` (it takes the first
  decode that resolves to the target). **Treat its mnemonics/registers as advisory; the
  target RVA is the reliable part.** All load-bearing instructions in this document were
  re-read by a linear disassembly from a pdata function start.
- Negative results below (e.g. "no reflected route") name the corpus they were taken over.

---

## 2. The three entry points, measured

All three were found by **reading a shipped artifact, not by pattern-hunting**: the game's
Angelscript bind table registers them, and the registration site hands the binder a raw
function pointer. Declaration strings at `.rdata +0x84D2B38`:

```
+0x84D2B38  "UObject"
+0x84D2B40  "AddToRoot"
+0x84D2B50  "void AddToRoot()"
+0x84D2B68  "RemoveFromRoot"
+0x84D2B78  "void RemoveFromRoot()"
+0x84D2D60  "IsRooted"
+0x84D2D70  "bool GetIsRooted() const"
```

Registration site `.text +0x4892F90 … +0x48945CD` (one pdata function, seen in 69 dumps),
which does `lea rax,[decl-string]` … `lea r8,[implementation]` … `call <binder>`:

| bind | decl string | **implementation** | binder call |
|---|---|---|---|
| `AddToRoot` | `+0x84D2B50` | **`.text +0x489F9B0`** (`lea r8` at `+0x4893017`) | `+0x4893081` |
| `RemoveFromRoot` | `+0x84D2B78` | **`.text +0x48B4BD0`** (`lea r8` at `+0x48930AB`) | `+0x48930DB…` |
| `IsRooted` | `+0x84D2D70` | **`.text +0x48B2200`** (`lea r8` at `+0x4893153`) | `+0x48931A9` |

**Fold multiplicity: 1 each.** [M] The exact body bytes of each of the three occur **exactly
once** in `.text` (searched the whole section for the byte string), and each address is
`lea`-referenced from **exactly one** site in the image — the bind registration. These are
not ICF-folded shared thunks and cannot be confused with another function.

### 2.1 `AddToRoot` — `.text +0x489F9B0`, 0x31 bytes

Bytes read from `+0x489F9B0`:

```
+0x489F9B0  8b4110              mov   eax, [rcx+0x10]        ; UObject::InternalIndex  (this build: @+0x10)
+0x489F9B3  3b058b8f5905        cmp   eax, [rip+…]           ; -> +0x9E38944  ObjObjects.NumElements
+0x489F9B9  7d26                jge   +0x489F9E1             ; out of range -> null item
+0x489F9BB  8bc8                mov   ecx, eax
+0x489F9BD  0fb7c0              movzx eax, ax                ; within = idx & 0xFFFF
+0x489F9C0  48c1e910            shr   rcx, 0x10              ; chunk  = idx >> 16   (PerChunk = 65536)
+0x489F9C4  488d1440            lea   rdx, [rax+rax*2]       ; within*3
+0x489F9C8  488b05618f5905      mov   rax, [rip+…]           ; -> +0x9E38930  ObjObjects.Objects
+0x489F9CF  488b0cc8            mov   rcx, [rax+rcx*8]       ; chunk base
+0x489F9D3  488d0cd1            lea   rcx, [rcx+rdx*8]       ; + within*0x18  => FUObjectItem*
+0x489F9D7  ba00000040          mov   edx, 0x40000000        ; <=== EInternalObjectFlags::RootSet
+0x489F9DC  e9afb29ffc          jmp   +0x129AC90             ; TAIL CALL: SetRootFlags(item, flags)
+0x489F9E1  33c9                xor   ecx, ecx
+0x489F9E3  ba00000040          mov   edx, 0x40000000
+0x489F9E8  e9a3b29ffc          jmp   +0x129AC90             ; same helper with a NULL item
```

Signature [M]: `void __fastcall AddToRoot(UObject* obj /*rcx*/)`. Returns nothing usable.

⚠ **The out-of-range path passes `nullptr` and `SetRootFlags` dereferences it** (`mov eax,[rbx+8]`
after taking the lock). **A caller must validate `0 <= InternalIndex < NumElements` itself**;
a negative index passes the signed `jge` and indexes out of bounds.

### 2.2 `RemoveFromRoot` — `.text +0x48B4BD0`, 0x68 bytes

Same `IndexToObject` prologue into `r8`, then:

```
+0x48B4BFC  8b159eea1105        mov   edx, [rip+…]           ; -> +0x99D36A0  GReachableFlagValue
+0x48B4C02  f7d2                not   edx
+0x48B4C04  81e200000040        and   edx, 0x40000000        ; never clear the live reachability bit
+0x48B4C0A  7408                je    +0x48B4C14
+0x48B4C0C  498bc8              mov   rcx, r8
+0x48B4C0F  e93cef98fc          jmp   +0x1243B50             ; ClearRootFlags(item, flags)
+0x48B4C14  …                   ; plain CAS-clear fallback (a no-op when edx == 0)
```

Signature [M]: `void __fastcall RemoveFromRoot(UObject* obj /*rcx*/)`.

### 2.3 `IsRooted` — `.text +0x48B2200`, 0x31 bytes

Same prologue, then the tail read from `+0x48B2227`:

```
+0x48B2227  8b44d108            mov  eax, [rcx+rdx*8+8]      ; FUObjectItem.Flags
+0x48B222B  c1e81e              shr  eax, 0x1e               ; >> 30
+0x48B222E  2401                and  al, 1
+0x48B2230  c3                  ret
```

Signature [M]: `bool __fastcall IsRooted(const UObject* obj /*rcx*/)`.

⚠ **`IsRooted()` reads only the flag.** It will return `true` for an object the shim has
poked but that is NOT in the root container. **It is therefore a useless verifier for this
problem** — an instrument that reports success for the exact failure being investigated.
Use the container count in §5 instead.

---

## 3. `SetRootFlags` — `.text +0x129AC90` — where the real work happens

Reconstructed from a linear read of `+0x129AC90 … +0x129AF68` (three pdata chunks:
`0x129AC90/0x129ACDA/0x129ADA0`; all non-zero in both images).

```c
// bool __fastcall SetRootFlags(FUObjectItem* item /*rcx*/, int32 FlagsToSet /*edx*/)
RtlEnterCriticalSection(&GRootsCritical);              // .data +0x9E23BF0, IAT +0x764A420

if (!(item->Flags & 0x4E100000)                        // not already a root by ANY root flag
 && !(GUObjectArray.MaxObjectsNotConsideredByGC > 0    // .data +0x9E38928
      && GUObjectArray.OpenForDisregardForGC))         // .data +0x9E3892C
{
        GRoots.Add(item->Object->InternalIndex);       // TSet<int32> @ .data +0x99D3CA0
        //  inlined TSparseArray insert  (call +0x1242430)
        //  inlined hash rebuild         (call +0x10D5E90)
}

bool changed = /* CAS loop */ atomic_or(&item->Flags, FlagsToSet);   // +0x129AF24 lock cmpxchg
RtlLeaveCriticalSection(&GRootsCritical);              // IAT +0x764A428
if (changed && *(uint8*)(base+0x9E25428)) call +0x1258C00(item->Object);   // optional GC-debug hook
return changed;
```

- IAT identities are **[M]**, resolved from `dumps/merged2.dump.iat.exe`'s reconstructed
  import table: `+0x764A420 = ntdll!RtlEnterCriticalSection`,
  `+0x764A428 = ntdll!RtlLeaveCriticalSection` (neighbours `+0x764A418
  RtlSetCriticalSectionSpinCount`, `+0x764A430 RtlDeleteCriticalSection` — a coherent block,
  which is the control).
- **107 direct rel32 transfers target `+0x129AC90`** [M]. Counting the immediate in the
  4 instructions preceding each: **`0x40000000` × 99, `0x8000000` (bit 27) × 2,
  `0x100000` (bit 20) × 2** (the remaining 4 pass the flags in a register). Every literal
  seen is a member of the `0x4E100000` mask. So `0x129AC90` is the shared
  `FUObjectItem::SetRootFlags`, and 99 of its call sites are `UObject::AddToRoot()` inlined.

### 3.1 `0x4E100000` decodes exactly as UE 5.4's `EInternalObjectFlags_RootFlags`

`0x4E100000` = bits **{20, 25, 26, 27, 30}** = `LoaderImport | Native | Async | AsyncLoading |
RootSet`. [M] on the value; [I] on the UE names, but the fit is exact and every bit is
independently corroborated by a `mov edx, imm` at a caller of `SetRootFlags`.

**Three independent measurements agree that RootSet == bit 30:**
1. `AddToRoot` passes `mov edx, 0x40000000` (`+0x489F9D7`).
2. `IsRooted` returns `Flags >> 30 & 1` (`+0x48B222B`).
3. The root-flags mask `0x4E100000` contains bit 30 and is tested at 4 memory sites.

The project's `KGCROOTBIT 0x40000000` was **correct**. Do not change it.

---

## 4. The collector reads the container, not the flag — `.text +0x1259020`

`0x1259020` (pdata `0x1259020…0x1259371`) is the reachability root gather. **The game names
its own passes**, and the names are in `.rdata`:

- `+0x771D048` = `L"GC.MarkRootObjectsAsReachable"`
- `+0x771D088` = `L"GC.SlowMarkObjectAsReachable"`

```
+0x1259059  lea  rcx, [rip+…]   ; -> +0x9E23BF0   GRootsCritical
+0x1259078  call [rip+…]        ; -> RtlEnterCriticalSection
+0x125907E  lea  rdx, [rsp+0x78]                     ; TArray<int32> out
+0x1259083  lea  rcx, [rip+…]   ; -> +0x99D3CA0      GRoots (TSet<int32>)
+0x125908A  call +0x11D44C0                          ; copy the set's keys into the array
+0x125908F  lea  rcx, [rip+…]   ; -> +0x9E23BF0
+0x1259096  call [rip+…]        ; -> RtlLeaveCriticalSection
+0x125909C  mov  r8d, [rbp-0x80]                     ; = copied array Num
   …
+0x1259103  lea  rcx, [rip+…]   ; -> +0x771D048  L"GC.MarkRootObjectsAsReachable"
+0x125911F  call +0xF9FE70                           ; ParallelFor(name, Num, lambda +0x12435C0, …)
```

Per-index body (`lambda +0x12435C0` → `+0x123E3B0`, three chunks):

```
+0x123E410  mov  edx, [rax+rcx*4]     ; idx = RootIndices[i]
+0x123E413..+0x123E433                ; item = ObjObjects.Objects[idx>>16] + (idx&0xFFFF)*0x18
+0x123E42B  mov  eax, [rip+…]         ; -> +0x99D36A8   reachability-bit MASK
+0x123E431  not  eax
+0x123E437  lock and [rcx+rdx*8+8], eax      ; clear stale reachability bits
+0x123E43C  mov  eax, [rip+…]         ; -> +0x99D36A0   CURRENT reachability bit value
+0x123E442  lock or  [rcx+rdx*8+8], eax      ; MARK REACHABLE
+0x123E433  mov  rbp, [rcx+rdx*8]            ; item->Object
+0x123E465  …                                 ; append to the initial-reference array
```

**There is no read of bit 30 anywhere on this path.** [M] — the loop consumes indices, not
flags. The second `ParallelFor` (`GC.SlowMarkObjectAsReachable`, body `+0x123E540`) is gated
on the caller's third argument being non-zero, i.e. on `KeepFlags != RF_NoFlags` [I], and
scans the object index range rather than the root set.

**Anchoring:** `+0x1259020` has exactly one inbound transfer (`+0x1259017 jmp`, from
`+0x1258F70`), and `+0x1258F70` has exactly one (`+0x129B449 call`, inside `+0x129B2F0`,
a function full of `cvtsi2sd`/`mulsd` GC timing arithmetic). Single-path, and named by the
engine's own `TEXT()` literals.

### 4.1 The one pass that DOES build the set from the flags is a one-shot, and it has not run

There is a third GC lambda, entry `.text +0x123E0B0` (chunks `0x123E0B0/0x123E0E1/0x123E3A4`),
whose body at `+0x123E110` does: mark every object reachable, then
`if (item->Flags & 0x4E100000) GRoots.Add(index)`. **That would rescue a flag-only poke — so
it had to be identified before the headline could stand.**

It is registered by `ParallelFor` at `+0x125975A` under the name at `+0x771CE50` =
**`L"GC.OnDisregardForGCSetDisabled"`**. Its enclosing function `+0x12596A0` has **exactly one
caller**, `+0x1360E55`, inside `+0x1360E30` — a function that afterwards writes
`GUObjectArray.ObjFirstGCIndex = 0` and `MaxObjectsNotConsideredByGC = 0`
(`+0x1360E5C`, `+0x1360E5F`), i.e. `FUObjectArray::DisableDisregardForGC` [I on the name].

**It is a one-shot teardown of the disregard-for-GC pool, not a periodic pass, and the
coordinator's own live readout proves it has not run in the measured process**
(`ObjFirstGCIndex = 39295`, `MaxObjectsNotConsideredByGC = 45000` — both non-zero, and this
function zeroes both). ⇒ nothing periodically reconstructs `GRoots` from the flags.

### 4.2 What I did *not* prove

I did **not** exhaustively prove that no code anywhere reads bit 30. What I measured:
- `0x4E100000` appears as an imm32 at **17 decoded sites, 4 with a memory operand**; one is
  `test [rbx+8], 0x4e100000` (`+0x135A5C6`), the rest are at `[reg+0x1c]`, a different struct.
- `test dword ptr [reg+8], 0x40000000` occurs at **zero** decoded sites. 26 mem-operand
  `test/and/cmp/or/xor` sites carry that immediate; **three of them ARE at `[reg+8]`**
  (`+0x2AEF460`, `+0x2AF5568`, `+0x2AF5788` — all `lock xor`), and I checked each rather
  than asserting the tidy version: they are a **reference-count release loop on an unrelated
  struct** (guard `test eax, 0x3fffffff`, vtable at `[obj+0]`, `call [vtable]` with `edx=1`),
  not `FUObjectItem`. No `FUObjectItem.Flags` bit-30 *test* was found.
- 381 `bt/bts/btr …, 0x1e` sites exist image-wide and were **not** individually classified —
  most will be unrelated bitfields (`0x40000000` is also float `2.0f` and a common flag).
  **This is the one place a reader could still surprise me**, and it is bounded: it cannot
  affect the root *gather*, which I read end to end.

---

## 5. The data structures, for a shim

| what | address | notes |
|---|---|---|
| `FUObjectArray GUObjectArray` | `.data +0x9E38920` | matches the coordinator's live readout exactly |
| `…ObjObjects.Objects` | `.data +0x9E38930` | the project's existing `kObjObjectsRva` |
| `…ObjObjects.NumElements` | `.data +0x9E38944` | bound used by all three entry points |
| `…MaxObjectsNotConsideredByGC` | `.data +0x9E38928` | read by `SetRootFlags` |
| `…OpenForDisregardForGC` | `.data +0x9E3892C` | byte; read by `SetRootFlags` |
| **`GRoots` — `TSet<int32>`** | **`.data +0x99D3CA0`** | the actual root set |
| `GRoots.Elements.Data` (ptr) | `+0x99D3CA0` | `TSetElement<int32>` stride **12** (`{Value, HashNextId, HashIndex}`) |
| `GRoots.Elements.Data.Num` | `+0x99D3CA8` | int32 |
| `GRoots.Elements.Data.Max` | `+0x99D3CAC` | int32 |
| `GRoots.…AllocationFlags` inline | `+0x99D3CB0` | TBitArray inline words |
| `…AllocationFlags` heap ptr | `+0x99D3CC0` | |
| `GRoots.…FirstFreeIndex` | `+0x99D3CD0` | int32 |
| `GRoots.…NumFreeIndices` | `+0x99D3CD4` | int32 |
| `GRoots.Hash` inline | `+0x99D3CD8` | |
| `GRoots.Hash` heap ptr | `+0x99D3CE0` | |
| `GRoots.HashSize` | `+0x99D3CE8` | int32 |
| **`GRootsCritical`** | **`.data +0x9E23BF0`** | `RTL_CRITICAL_SECTION` |
| current reachability bit VALUE | `.data +0x99D36A0` | int32, rotates each GC pass |
| reachability bit MASK | `.data +0x99D36A8` | int32 |

★ **FREE VERIFICATION RECEIPT — use this instead of `IsRooted`:**

```
liveRootCount = *(int32*)(base + 0x99D3CA8) - *(int32*)(base + 0x99D3CD4)
```

Both `SetRootFlags` (`+0x129AD0D`/`+0x129AD1B`/`+0x129AD2A`) and `ClearRootFlags`
(`+0x1243B91`/`+0x1243B97`) compute exactly this difference — two independent derivations of
the same expression, which is the control. It must increase by **one per newly rooted
object** and is readable by pure RPM. **This is the discriminator the project has been
missing: it distinguishes "flag set" from "actually rooted".** Reading it before the shim
does anything also gives a baseline (it should be ≈ the engine's own root population).

Blind spot to state with it: the difference is the TSet's live element count, so it moves for
*any* engine rooting too — sample it immediately either side of the call.

---

## 6. ⚠⚠ THE EXISTING POKE POISONS THE FIX

`SetRootFlags` opens with `if (item->Flags & 0x4E100000) → skip the container insert`
(`+0x129ACB1 test eax, 0x4e100000` / `+0x129ACB6 jne +0x129AF0A`).

An object the shim has already `InterlockedOr`'d with `0x40000000` therefore satisfies that
test, so a subsequent **correct** `AddToRoot(obj)` call will **skip the `GRoots.Add` and only
re-OR a bit that is already set.** The object stays collectable, `IsRooted()` still says
`true`, and there is no error anywhere.

**Required sequence for any object the shim has ever poked:**
1. `RemoveFromRoot(obj)` — `.text +0x48B4BD0`. Safe: `ClearRootFlags` looks the index up in
   the hash, finds nothing (`+0x1243BD3 cmp edx,-1; je`), skips the removal, and clears bit 30.
2. `AddToRoot(obj)` — `.text +0x489F9B0`.
3. Confirm `liveRootCount` moved by +1.

**Better: delete the poke.** `GcRoot()` in `tools/sigbypass-mod/tutorial_launch.cpp` (~line
1611) should call `+0x489F9B0` instead of writing `item+8`. `GcResolveBit()` and
`KGCROOTBIT`/`KGCROOTMAXPCT`/`KGCROOTSTRICT` become dead weight — the bit was never the
problem — though keeping `GcResolveBit` as a cheap *sanity* gate costs nothing.

A related hazard, for completeness: rooting an object **while it is still async-loading**
(bit 27 set) would hit the same early-out. In the real engine that is correct (the async
loader already inserted the index); for a shim it is another reason to check the count.

---

## 7. Candidate grading

| # | mechanism | exists in this build? | callable from an injected DLL? | verdict |
|---|---|---|---|---|
| **1** | **`UObject::AddToRoot()` / `RemoveFromRoot()`** | **YES, as real out-of-line bodies** `.text +0x489F9B0` / `+0x48B4BD0`, fold multiplicity **1**, non-zero and byte-identical in both images | **YES — trivially.** `void __fastcall f(UObject*)`. One `rcx`, no frame, no reflection, **no `.text` write**, thread-safe by its own critical section | ★★★★★ **SHIP THIS** |
| **1b** | `FUObjectItem::SetRootFlags(item, 0x40000000)` `.text +0x129AC90` | YES, 107 inbound transfers | YES. `bool __fastcall f(FUObjectItem*, int32)`. Skips the index math the shim already does; returns whether the flag changed | ★★★★ equivalent; use if you already hold the item |
| **1c** | `IsRooted` `.text +0x48B2200` | YES | YES, but **reads the flag only** | ⚠ **not a valid verifier here** |
| **2** | `FUObjectArray::AddObjectToRoot` / a separate `SetRootSet` inline | **Does not exist as a distinct entity.** The rooting logic is `SetRootFlags` (§3); "the inline" is exactly the 0x31-byte prologue in §2.1, inlined at 107 sites | n/a | folded into #1 |
| **3** | `FGCObject` / `UGCObjectReferencer` | **Class IS compiled in** [M]: `Z_Construct_UClass_UGCObjectReferencer` at `.text +0x11E5CF0`, name literal `L"GCObjectReferencer"` at `.rdata +0x76EE692` (`L"UGCObjectReferencer"` at `+0x76EE690`), singleton slot `.data +0x9E1D798`, `sizeof = 0x40`. `UGCObjectReferencer::AddReferencedObjects` = **`.text +0x11D3420`**; it walks two `TArray<FGCObject*>` at `[[this+0x30]+0x28]/[+0x30]` and `[+0x38]/[+0x40]` and calls each element's **vtable slot 1** (`call [rax+8]`) | **In principle, badly.** Requires the DLL to supply a live `FGCObject` vtable that UE calls **from GC worker threads every pass**, plus either finding `AddObject` or mutating a UE `TArray` from foreign code. Unload-safety becomes the DLL's problem | ⛔ **strictly worse than #1** — more surface, a permanent callback into our module, no upside |
| **4** | clusters (`FUObjectItem.ClusterRootIndex@0x0C`, `ClusterRoot` bit 24, `ReachableInCluster` bit 23) | bits exist; **neither is in the `0x4E100000` root mask**, so a cluster is not a root — it is kept alive *by* its root | would require building an `FUObjectCluster`; not investigated further | ⛔ wrong tool |
| **5** | **a reflected (UFUNCTION) route** | **NO.** Exact-name scan over the UHT oracle `tools/re/out/uht_funcflags_tuthero.csv`, **18,325 reflected functions**, for `AddToRoot / RemoveFromRoot / IsRooted / AddReferencedObjects / AddObject / RemoveObject / GetIsRooted / IsRootSet / AddToCluster / CreateCluster` → **1 hit, and it is a false friend**: `ALokiCharacter::IsRooted` (`Final\|Native\|Public\|Const`) is the *movement* "rooted" status effect, a different subsystem | n/a | ⛔ no reflected route exists |
| **5b** | the **Angelscript** bind | YES — that is how #1 was found. But AS binds are **not** `UFunction`s, so the S55 `UFunction.Func @ +0xE0` native-call primitive cannot reach them | n/a — go direct to the address | informational |

---

## 8. Recommended primitive

```c
// resolve once
typedef void (__fastcall *FnRoot)(void* uobject);
FnRoot AddToRoot      = (FnRoot)(g_modBase + 0x489F9B0);
FnRoot RemoveFromRoot = (FnRoot)(g_modBase + 0x48B4BD0);

static int32_t LiveRootCount(void) {                       // pure read, no lock needed for a sample
    return *(int32_t*)(g_modBase + 0x99D3CA8) - *(int32_t*)(g_modBase + 0x99D3CD4);
}

static bool RootObject(void* obj) {
    int32_t idx = *(int32_t*)((char*)obj + 0x10);          // InternalIndex
    int32_t num = *(int32_t*)(g_modBase + 0x9E38944);      // ObjObjects.NumElements
    if (idx < 0 || idx >= num) return false;               // AddToRoot would pass NULL to SetRootFlags
    int32_t before = LiveRootCount();
    RemoveFromRoot(obj);                                   // clears any legacy poke; no-op otherwise
    AddToRoot(obj);
    int32_t after = LiveRootCount();
    return after > before;                                 // the ONLY honest receipt
}
```

- **No `.text` write** — the project's single largest self-inflicted hazard is untouched.
- **No new `ProcessInternal` hook**, no manual map beyond what the shim already does.
- `SetRootFlags` serialises on its own critical section, so this is callable off the game
  thread; it will simply block if a GC root gather is in flight. Do **not** call it from a
  thread already inside `GRootsCritical` (nothing in a shim would be).
- ⚠ `RootObject` returning `false` because `after == before` is **not necessarily failure** —
  the count is global and another thread may have removed a root in the same window. Sample
  tightly and, if it matters, repeat.

**Pre-registerable prediction, if someone wants a single-variable live test:** with the poke
removed and `AddToRoot` called on the run `AnimSequence`, `LiveRootCount()` must increase by
exactly 1 per rooted asset, and `tools/re/item_watch.py` must show the asset re-marked at
two consecutive GC passes — the same observable that showed `KANIMREF` working. The
matched negative control already exists: the current `InterlockedOr` build must leave
`LiveRootCount()` **unchanged**, which is the whole claim in one number.

---

## 8a. Independent corroboration (two analysts, opposite entry points)

`scratchpad/fk27/gc-mark-re.md` was written concurrently by the `gc-mark-re` agent, which
approached this from the **mark path** (GC → what seeds the traversal). I approached it from
the **write path** (the Angelscript bind strings → `AddToRoot` → what it does). We converged
on the same middle without sharing intermediates:

| fact | this doc | `gc-mark-re.md` |
|---|---|---|
| root registry is a `TSet<int32>` of InternalIndices at `.data 0x99D3CA0` | §3, §5 | §"THE ROOT REGISTRY" |
| maintained by `0x129AC90` (add) and `0x1243B50` (remove) | §3, §2.2 | same |
| guarded by the CRITICAL_SECTION at `.data 0x9E23BF0` | §3 | same |
| gathered by `0x1259020` → `L"GC.MarkRootObjectsAsReachable"` → body `0x123E3B0` | §4 | same |
| the mark body has **no** bit-30 predicate | §4 | same |
| `0x1242430` = TSet add, `0x11D44C0` = TSet→TArray | §3, §4 ([I]) | same ([I]) |

★ They also have a **live** reading the offline work cannot produce: the registry's
`Num()` = **31 / 29**, which matches the coordinator's independently observed "~32 genuine
`AddToRoot` callers at high index that get re-marked every pass." Three separate
measurements land on the same population — that is as closed as this gets.

**What is only here:** the three callable entry points (`0x489F9B0` / `0x48B4BD0` /
`0x48B2200`), their Angelscript-bind provenance, their fold-multiplicity-1 proof, and the
**§6 poisoning trap** — which matters because it means removing the poke is not optional
housekeeping, it is a precondition for the fix working at all.

---

## 9. Unresolved

1. **`UGCObjectReferencer::AddObject`** was not located (only `AddReferencedObjects`
   `+0x11D3420` and the member layout). Not pursued — candidate 3 is dominated by #1.
2. **`FGCObject::GGCObjectReferencer`** (the singleton instance pointer) not located. The
   *UClass* singleton slot `.data +0x9E1D798` is not it.
3. **The 381 `bt*,0x1e` sites were not individually classified** (§4.2). This cannot affect
   the root gather, which was read end to end, but it is the residual on "nothing else reads
   bit 30".
4. The exact UE function names are **[I]** throughout (`SetRootFlags`, `ClearRootFlags`,
   `DisableDisregardForGC`, `GRoots`, `GRootsCritical`). The *addresses and behaviour* are
   [M]; the names are a reading of UE 5.4 source conventions and should be treated as labels,
   not evidence.
5. `+0x1258C00`, called by `SetRootFlags` when `byte[.data +0x9E25428]` is set, is unread —
   an optional GC-verification/debug hook. Harmless as far as I can tell, but not verified.
6. `0x4E100000` at `[reg+0x1c]` (three sites, `+0x130DF8F`, `+0x131F05D`, `+0x1331E16`) sits
   on a struct I did not identify. Probably an `FUObjectItem` reached through a wrapper;
   not load-bearing here.
