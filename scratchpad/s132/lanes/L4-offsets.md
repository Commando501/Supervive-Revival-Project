# S132 LANE 4 — ULokiRideableComponent / AActor offsets pinned by independent routes

**Method:** offline only. Cold PE dumps (`dumps/merged4.dump.exe`, ImageBase `0x7FF6AF000000`,
file offset == RVA) plus `tools/asdump/out/binds_members.csv` and one cooked-asset JSON.
Zero launches, zero injections, zero `.text` writes.
Every VA→RVA conversion below was recomputed with `python -c`, never by hand. (One hand slip was
caught this way: the detach's `TArray` remove target is `0x11F3860`, not `0x1F3860`.)
Tooling written for this lane: `scratchpad/s132/{uht.py,uhtdec.py,bools.py,fdis.py}`.

**Coverage control:** every code region cited was checked for the all-zero (never-demand-decrypted)
condition in `merged4`. **All 15 regions are present and non-zero.** Nothing here is
coverage-blocked, and no negative below rests on an unread page.

**Cross-image control:** the four load-bearing `.rdata` records and the four load-bearing
`SetBitFunc` bodies were re-read in **four independent images** — `merged4`, `tuthero`, `merged2`,
and `rideable` (`dumps/s131-rideable-live`). **All four agree byte-for-byte on every value.**
(`.rdata` is not demand-decrypted — FK-18 — so the `.rdata` agreement is expected; the `.text`
agreement is the informative half.)

---

## 0. HEADLINE

| claim under test | verdict | grade |
|---|---|---|
| `PlayersInsideCount` IntProperty **@0x11C** | **CONFIRMED** | [M], 2 disjoint instruments |
| `PlayersInside` ArrayProperty **@0x120**, size 16 | **CONFIRMED** | [M], 2 instruments, 4 use sites |
| `PlayersAttached` **@0x130** (Data 0x130 / Num 0x138 / Max 0x13C) | **CONFIRMED** | [M], 2 instruments, 3 use sites |
| `OnPlayersInsideCountChanged` MulticastInlineDelegate **@0xE0**, 16 B | **CONFIRMED** | [M], 2 instruments |
| `bCanExit` — no offset was stated in the task | **it is @0x118**, real `bool` (NativeBool), 1 byte | [M], 3 instruments |
| **`AActor::bHidden` → offset 0x68, ByteMask 0x80** | **CONFIRMED EXACTLY** | [M] |
| **`AActor::bAlwaysRelevant` → offset 0x68, ByteMask 0x08** | **CONFIRMED EXACTLY** | [M] |
| `PlayersAttached` inner is an ObjectProperty, pointer size 8 | **CONFIRMED** | [M], 4 independent routes |
| `PlayersAttached` is **NOT** replicated (no `CPF_Net`) | **CONFIRMED** | [M] |
| `ALokiDropPod::LokiRideable @0x6C8` | ⚠ **CANNOT BE CONFIRMED — and it is not a native or script member at all** | see §7 |

**Two corrections the arm must absorb before it is written:**

1. ⚠⚠ **`FBoolPropertyParams` contains NO `ByteOffset`, `ByteMask` or `FieldMask` fields.**
   Deliverable 3 presumes they are in the record. They are not (§4.2). The record carries
   `ElementSize`, `SizeOfOuter` and a **`SetBitFunc` lambda pointer**; the engine derives
   offset+mask at runtime by *calling* that lambda on a zeroed buffer and seeing what changed.
   An in-arm decoder written against the assumed field list would read `SetterFunc`/padding
   and return garbage. The correct in-arm decode is a 5–8 byte instruction decode (§4.3).
2. ⚠⚠ **`LokiRideable @0x6C8` is a Blueprint-generated component property on `BP_DropPod_C`**,
   not a UHT property and not an Angelscript member. No offline instrument can produce its offset.
   Resolve it by NAME on the live class, or use the game's own `ULokiRideableComponent::Get`. §7.

---

## 1. THE INSTRUMENTS

**(a) UHT reflection metadata in `.rdata` — the primary route.**
`ULokiRideableComponent`'s `FClassParams` is at **`.rdata 0x8A503A0`**:

```
+0x00 ClassNoRegisterFunc          0x5452740
+0x08 ClassConfigNameUTF8          0x76BC130 -> "Engine"
+0x10 CppClassInfo                 0x8A50390   (16 zero bytes -> bIsAbstract = false)
+0x18 DependencySingletonFuncArray 0x8A50258   (2 entries)
+0x20 FunctionLinkArray            0x8A50270   (18 entries, 16 B stride)
+0x28 PropertyArray (PropPointers) 0x8A501F0   (13 entries)   <-- decoded in §2
+0x30 ImplementedInterfaceArray    0
+0x38 packed counts                0x00068122
+0x3C ClassFlags                   0x00B000A4
```
The array extents are self-corroborating: `PropPointers` runs `0x8A501F0..0x8A50258` = 13 entries,
immediately followed by the 2-entry dependency array, then the 18-entry function array
(`0x8A50270..0x8A50390`), then `CppClassInfo`.

**(b) Disassembly displacements at real use sites** — six functions, quoted per offset in §3.

**(c) `tools/asdump/out/binds_members.csv`** — the Angelscript binding table, a UHT-derived
member/type table produced by a *different tool*. It carries types and declaration order but
**no offsets**, so it is a type oracle, not an offset oracle. Used as such.

---

## 2. THE FULL DECODED PROPERTY TABLE — `ULokiRideableComponent` [M]

`PropPointers` @ `.rdata 0x8A501F0`, 13 entries:

```
 #  record      name                          gen flags                ArrayDim  Offset   PropertyFlags
 0  0x8A4FEA0   OnCanExitChanged              InlineMulticastDelegate   1        0x0D0    0x0010000010080000
 1  0x8A4FEE0   OnPlayersInsideCountChanged   InlineMulticastDelegate   1        0x0E0    0x0010000010080000
 2  0x8A4FF20   OnPlayerEntered               InlineMulticastDelegate   1        0x0F0    0x0010000010080000
 3  0x8A4FF60   OnPlayerExited                InlineMulticastDelegate   1        0x100    0x0010000010080000
 4  0x8A4FFA0   InsideEffect                  Class                     1        0x110    0x0024080000010015
 5  0x8A4FFF0   bCanExit                      Bool|NativeBool           1        (bool)   0x0020080100000034  RepNotify=OnRep_bCanExit
 6  0x8A50030   PlayersInsideCount            Int                       1        0x11C    0x0020080100000034  RepNotify=OnRep_PlayersInsideCount
 7  0x8A50070   PlayersInside     (INNER)     Object                    1        0x000    0
 8  0x8A500B0   PlayersInside                 Array                     1        0x120    0x0020080000000034
 9  0x8A500F0   PlayersAttached   (INNER)     Object                    1        0x000    0
10  0x8A50130   PlayersAttached               Array                     1        0x130    0x0020080000000014
11  0x8A50170   PlayersThatExited (INNER)     Object                    1        0x000    0
12  0x8A501B0   PlayersThatExited             Set                       1        0x140    0x0020080000000014
```

Decoded `PropertyFlags`:
* `0x...0034` = `BlueprintVisible | BlueprintReadOnly | **Net**` (+ Protected / NativeAccessSpecifierProtected)
* `0x...0014` = `BlueprintVisible | BlueprintReadOnly` — **no `CPF_Net`**
* `0x0000000100000000` = `CPF_RepNotify` (on `bCanExit` and `PlayersInsideCount` only)

`EPropertyGenFlags` decode used throughout: `TypeMask = 0x3F`, `NativeBool = 0x40`,
`ObjectPtr = 0x80`; `Bool=0x0C, Class=0x11, Object=0x12, Array=0x16, Set=0x18,
InlineMulticastDelegate=0x1B, Int=0x03`. This mapping is validated inside the data itself —
every record's gen value matches the type `binds_members.csv` independently declares for the
same name (13/13, including the three inners).

`binds_members.csv` (instrument c) lists the same ten declared properties **in the same order**:
`FOnCanExitChanged`, `FOnPlayersInsideCountChanged`, `FOnPlayerMoved OnPlayerEntered`,
`FOnPlayerMoved OnPlayerExited`, `TSubclassOf<UGameplayEffect> InsideEffect`, `bool bCanExit`,
`int PlayersInsideCount`, `TArray<ALokiPlayerState> PlayersInside`,
`TArray<ALokiPlayerState> PlayersAttached`, `TSet<ALokiPlayerState> PlayersThatExited`.

**Derived complete layout — every byte from 0xD0 to 0x190 accounted for, no gaps:**

```
+0x0D0  FMulticastInlineDelegate   OnCanExitChanged              16
+0x0E0  FMulticastInlineDelegate   OnPlayersInsideCountChanged   16
+0x0F0  FMulticastInlineDelegate   OnPlayerEntered               16
+0x100  FMulticastInlineDelegate   OnPlayerExited                16
+0x110  TSubclassOf<UGameplayEffect> InsideEffect                 8
+0x118  bool   bCanExit                                           1   (+3 pad)
+0x11C  int32  PlayersInsideCount                                 4
+0x120  TArray<ALokiPlayerState*> PlayersInside                  16   Data 0x120 / Num 0x128 / Max 0x12C
+0x130  TArray<ALokiPlayerState*> PlayersAttached                16   Data 0x130 / Num 0x138 / Max 0x13C
+0x140  TSet<ALokiPlayerState*>   PlayersThatExited            ~0x50  Elems.Data 0x140 / Elems.Num 0x148 /
                                                                      NumFreeIndices 0x174 / inline hash 0x178 /
                                                                      Hash 0x180 / HashSize 0x188
+0x190 .. 0x1E0   non-reflected tail
sizeof(ULokiRideableComponent) = 0x1E0
```

`sizeof = 0x1E0` is **[M] from two instruments**: the `SizeOfOuter` field of the `bCanExit`
`FBoolPropertyParams`, **and** the `InSize` literal in the class's own `GetPrivateStaticClassBody`
call — `0x54527D5  c7442420e0010000  mov dword ptr [rsp+0x20], 0x1e0`.
Two further unreflected members are visible in code at `+0xB8` and `+0xC0` (not identified; not needed).

---

## 3. PER-OFFSET CONFIRMATION — WHICH INSTRUMENTS AGREED

### `PlayersInsideCount` @ **0x11C** — UHT + disasm
* **UHT [M]** record `0x8A50030`, gen `Int`, `Offset = 0x11C`.
* **Disasm [M]** — `ULokiRideableComponent::OnRep_PlayersInsideCount` impl `0x55E0FC0`
  (from the `.data` `{name, thunk, impl}` record; thunk `0x5457730`). Three instructions, and it
  pins **both** this offset and the delegate at once:
```
0x55E0FC0  8b911c010000     mov  edx, dword ptr [rcx + 0x11c]    ; PlayersInsideCount
0x55E0FC6  4881c1e0000000   add  rcx, 0xe0                        ; &OnPlayersInsideCountChanged
0x55E0FCD  e9ae15cefd       jmp  0x032C2580                       ; FMulticastScriptDelegate::Broadcast(int32)
```

### `OnPlayersInsideCountChanged` @ **0xE0**, 16 bytes — UHT + disasm
* **UHT [M]** record `0x8A4FEE0`, gen `InlineMulticastDelegate`, `Offset = 0xE0`.
  **16-byte size [M]** from the exact `0xD0 / 0xE0 / 0xF0 / 0x100` spacing of the four sibling
  delegates in the same class.
* **Disasm [M]** `0x55E0FC6 add rcx, 0xe0` above, plus the parallel `OnRep_bCanExit` impl
  `0x55E1000`: `0fb69118010000 movzx edx, byte [rcx+0x118]; 4881c1d0000000 add rcx, 0xd0;
  e9ada4e4fe jmp 0x0442B4C0` — which pins `OnCanExitChanged @0xD0` and therefore the 16-byte
  stride from the other end.

⇒ This directly re-confirms the S131 §13 correction recorded in CLAUDE.md: on
**`ULokiRideableComponent`**, `+0xE0` is `OnPlayersInsideCountChanged`, a 16-byte delegate — it is
**not** a cached round-game-mode pointer. (The cache at `+0xE0` is on
`ULokiGameModeDropPlaneComponent`, a different class.)

### `PlayersInside` @ **0x120**, 16 bytes (Data 0x120 / Num 0x128 / Max 0x12C) — UHT + disasm ×4
* **UHT [M]** record `0x8A500B0`, gen `Array`, `Offset = 0x120`. Size 16 follows from
  `PlayersAttached` starting at `0x130` [M].
* **Disasm [M]**, four attributed sites:
  * `AuthPlayerEnterWorld` impl `0x55CCE70` (`this` in `rcx`, mirrored into `rdi` at `0x55CCEB7`):
```
0x55CCEC2  488b8920010000   mov    rcx, qword ptr [rcx + 0x120]   ; PlayersInside.Data
0x55CCEC9  48638728010000   movsxd rax, dword ptr [rdi + 0x128]   ; PlayersInside.ArrayNum
0x55CCED0  488d14c1         lea    rdx, [rcx + rax*8]             ; end = Data + Num*8   (stride 8)
0x55CCED4  483bca           cmp    rcx, rdx
0x55CCED7  0f840a060000     je     0x55CD4E7                      ; empty -> silent bail
0x55CCEE0  4c3921           cmp    qword ptr [rcx], r12           ; linear search for the PlayerState
```
  * `ContainsPlayer` impl `0x55D0270`: `mov rax,[rcx+0x120]` · `movsxd rcx,[rcx+0x128]` ·
    `lea r8,[rax+rcx*8]` (S131 used this function live as a positive control).
  * `HasEverContainedPlayer` impl `0x55DCAA0`: `mov rax,[rcx+0x120]` · `movsxd r8,[rcx+0x128]`.
  * (`AuthAddPlayer`, the only would-be writer, is a stripped fold — §8a.)
* ⚠ **`Max @0x12C` is [I], not [M]** — no site in the whole `0x55CC000..0x55E2000` scan touches
  `+0x12C`, precisely because nothing in this client ever grows `PlayersInside`. It follows from
  the `TArray` ABI, which is itself [M] (§5).

### `PlayersAttached` @ **0x130** (Data 0x130 / Num 0x138 / Max 0x13C) — UHT + disasm ×3
* **UHT [M]** record `0x8A50130`, gen `Array`, `Offset = 0x130`.
* **Disasm [M] — the append itself**, inside `AuthPlayerEnterWorldAttachedToRidable` impl
  `0x55CD510`, where `0x55CD543  4c8bf1  mov r14, rcx` establishes `r14 == this` for the whole body:
```
0x55CD738  49639e38010000   movsxd rbx, dword ptr [r14 + 0x138]   ; OldNum = ArrayNum
0x55CD73F  8d4301           lea    eax, [rbx + 1]                  ; NewNum
0x55CD742  41898638010000   mov    dword ptr [r14 + 0x138], eax    ; ArrayNum = NewNum   <-- FIRST
0x55CD749  413b863c010000   cmp    eax, dword ptr [r14 + 0x13c]    ; vs ArrayMax
0x55CD750  760e             jbe    0x55CD760
0x55CD752  8bd3             mov    edx, ebx                        ; arg2 = OldNum
0x55CD754  498d8e30010000   lea    rcx, [r14 + 0x130]              ; arg1 = &PlayersAttached
0x55CD75B  e870b19cfb       call   0x00F988D0                      ; ResizeGrow
0x55CD760  498b8630010000   mov    rax, qword ptr [r14 + 0x130]    ; Data
0x55CD767  48893cd8         mov    qword ptr [rax + rbx*8], rdi    ; Data[OldNum] = PlayerState
```
  * `AuthPlayerDetachPlayerFromRidable` impl `0x55CCCB0` (`0x55CCCCE mov rbp, rcx`):
    `0x55CCCEC mov rcx,[rcx+0x130]` · `0x55CCCF3 movsxd rax,[rbp+0x138]` ·
    `0x55CCCFA lea rdx,[rcx+rax*8]` · `0x55CCD01 je 0x55CCE5B` — **gated on the array being
    non-empty**, exactly as CLAUDE.md records.
  * Same function, the removal: `0x55CCE2B  488d8d30010000  lea rcx, [rbp + 0x130];
    e8296ac2fb call 0x011F3860`.

### `bCanExit` @ **0x118**, real `bool`, 1 byte — UHT + disasm ×2
The task's layout list gave `bCanExit` with no offset. It is **0x118** [M]:
* **UHT [M]** record `0x8A4FFF0`: gen `Bool|NativeBool` (`0x4C`), `ElementSize = 1`,
  `SizeOfOuter = 0x1E0`, `RepNotifyFuncUTF8 = "OnRep_bCanExit"`, `SetBitFunc = 0x332B950`:
```
0x332B950:  c6 81 18 01 00 00 01 | c3
            mov byte ptr [rcx + 0x118], 1
            ret
```
* **Disasm [M]** `CanExit` impl `0x525C240` = `0fb68118010000 movzx eax, byte ptr [rcx+0x118]; c3 ret`
  — a **1-byte** read, independently confirming the whole-byte (`NativeBool`) form.
* **Disasm [M]** `OnRep_bCanExit` impl `0x55E1000` (quoted above).

### `PlayersThatExited` @ **0x140** — UHT + disasm (bonus, closes the layout)
`HasEverContainedPlayer` impl `0x55DCAA0`, on the TSet-lookup path:
`0x55DCB39 mov rcx, qword ptr [r10 + 0x140]` (Elements.Data), `[r10+0x148]` (Elements.ArrayNum)
compared against `[r10+0x174]` (NumFreeIndices — the `Num() = ArrayNum - NumFreeIndices` idiom
S123 already documented), `[r10+0x180]` Hash with `[r10+0x178]` inline storage,
`[r10+0x188]` HashSize.

---

## 4. ★ CRITICAL: `AActor::bHidden` / `bAlwaysRelevant`, AND THE REAL `FBoolPropertyParams` LAYOUT

`AActor`'s `FClassParams` is at **`.rdata 0x7F227E0`** (`ClassNoRegisterFunc 0x2BE1050`,
`ClassConfigNameUTF8 0x76BC130 -> "Engine"`); its `PropertyArray` is at **`.rdata 0x7F21540`** and
runs to `0x7F218D0` = **114 entries**, matching the `NumProperties` field decoded from `+0x38`
(§9) and matching CLAUDE.md's recorded 114.

### 4.1 THE CLAIM IS CONFIRMED EXACTLY [M]

**`bHidden` — `FBoolPropertyParams` at `.rdata 0x7F1F880` (`PropPointers[7]`), raw 0x40 bytes:**
```
0x7F1F880:  a0 2a f2 b6 f6 7f 00 00   00 00 00 00 00 00 00 00
0x7F1F890:  35 00 00 00 02 00 40 00   0c 00 00 00 45 00 00 00
0x7F1F8A0:  00 00 00 00 00 00 00 00   00 00 00 00 00 00 00 00
0x7F1F8B0:  01 00 01 00 90 03 00 00   80 89 36 b2 f6 7f 00 00
```
decode: `NameUTF8 = 0x7FF6B6F22AA0` → `.rdata 0x7F22AA0` = **`"bHidden"`** ·
`RepNotifyFuncUTF8 = 0` · `PropertyFlags = 0x0040000200000035` =
`Edit|BlueprintVisible|BlueprintReadOnly|Net|Interp|NativeAccessSpecifierPrivate` ·
`Flags = 0x0C` = `Bool` **without** `NativeBool` ⇒ a **bitfield** ·
`ObjectFlags = 0x45` · `Setter = Getter = 0` · `ArrayDim = 1` · `ElementSize = 1` ·
`SizeOfOuter = 0x390` · `SetBitFunc = 0x7FF6B2368980` → `.text 0x3368980`.

**The lambda body, read at `0x3368980`:**
```
0x3368980:  80 49 68 80 c3
            or byte ptr [rcx + 0x68], 0x80
            ret
```
⇒ **`bHidden`: ByteOffset = 0x68, ByteMask = 0x80, FieldMask = 0x80.**

**`bAlwaysRelevant` — `FBoolPropertyParams` at `.rdata 0x7F1F730` (`PropPointers[3]`), raw 0x40 bytes:**
```
0x7F1F730:  28 2a f2 b6 f6 7f 00 00   00 00 00 00 00 00 00 00
0x7F1F740:  05 00 01 00 00 00 10 00   0c 00 00 00 45 00 00 00
0x7F1F750:  00 00 00 00 00 00 00 00   00 00 00 00 00 00 00 00
0x7F1F760:  01 00 01 00 90 03 00 00   00 71 2f b2 f6 7f 00 00
```
decode: `NameUTF8 = 0x7FF6B6F22A28` → `.rdata 0x7F22A28` = **`"bAlwaysRelevant"`** ·
`PropertyFlags = 0x0010000000010005` =
`Edit|BlueprintVisible|DisableEditOnInstance|NativeAccessSpecifierPublic` (note: **no `CPF_Net`** —
`bAlwaysRelevant` is not itself replicated) · `Flags = 0x0C` = `Bool`, bitfield ·
`ArrayDim = 1` · `ElementSize = 1` · `SizeOfOuter = 0x390` ·
`SetBitFunc = 0x7FF6B22F7100` → `.text 0x32F7100`.

**The lambda body, read at `0x32F7100`:**
```
0x32F7100:  80 49 68 08 c3
            or byte ptr [rcx + 0x68], 8
            ret
```
⇒ **`bAlwaysRelevant`: ByteOffset = 0x68, ByteMask = 0x08, FieldMask = 0x08.**

> **Both are at 0x68, with masks 0x80 and 0x08 respectively. The claim under test is correct
> exactly as written.**

**Two positive controls against previously published project measurements, in the same pass and
from the same instrument:**
* `bCanEverReplicate` (`PropPointers[27]`, record `.rdata 0x7F1FDF0`) → SetBitFunc `0x2078900`:
  `c6 41 6c 01 c3` = `mov byte ptr [rcx+0x6c], 1; ret` → **0x6C**, `NativeBool` set.
  Matches CLAUDE.md's `[M] AActor+0x6C = bCanEverReplicate` (S130).
* `bEnablePooling` (`PropPointers[100]`, record `.rdata 0x7F21160`) → SetBitFunc `0x3368BF0`:
  `c6 81 d3 02 00 00 01 c3` = `mov byte ptr [rcx+0x2d3], 1; ret` → **0x2D3**.
  Matches CLAUDE.md's `[M] +0x2D3 = bEnablePooling` (S130).

**The full byte-0x68 and byte-0x69 bit families** (for anyone reaching for a second flag):
* `0x68`: `bNetTemporary 0x01` · *(0x02 = an unreflected bitfield, no UHT record)* ·
  `bOnlyRelevantToOwner 0x04` · `bAlwaysRelevant 0x08` · `bReplicateMovement 0x10` ·
  `bCallPreReplication 0x20` · `bCallPreReplicationForReplay 0x40` · `bHidden 0x80`
* `0x69`: `bTearOff 0x01` · `bForceNetAddressable 0x02` · `bExchangedRoles 0x04` ·
  `bNetLoadOnClient 0x08` · `bNetUseOwnerRelevancy 0x10` · `bRelevantForNetworkReplays 0x20` ·
  `bRelevantForLevelBounds 0x40` · `bReplayRewindable 0x80`

⚠⚠ **`bHidden` and `bAlwaysRelevant` share byte `0x68` with six other flags, four of which are
replication controls.** An in-arm control that sets or clears them **must `or`/`and` the mask**.
A whole-byte `mov` there would clobber `bReplicateMovement`, `bNetTemporary`,
`bOnlyRelevantToOwner` and both pre-replication hooks in a single store — and the resulting
misbehaviour would look like anything but an instrument fault.

### 4.2 THE RECORD LAYOUT, AND THE CORRECTION TO DELIVERABLE 3

`FBoolPropertyParams` **does not contain `ByteOffset`, `ByteMask` or `FieldMask`.** UHT emits
`ElementSize`, `SizeOfOuter` and a `SetBitFunc` lambda; `FBoolProperty`'s constructor allocates a
zeroed buffer of `SizeOfOuter` bytes, calls `SetBitFunc` on it, and scans for the byte and bit that
changed. **Decoding `SetBitFunc` reproduces the engine's own algorithm**, so the offline answer and
the live `FBoolProperty` cannot disagree by construction — that is what makes §4.1 a measurement
rather than an inference about runtime behaviour.

**Measured record layout — `FBoolPropertyParams`, sizeof = 0x40:**

| off | width | field | evidence it is this field |
|---|---|---|---|
| `+0x00` | 8 | `const char* NameUTF8` | resolves to the ASCII property name on every record decoded (13 + 114) |
| `+0x08` | 8 | `const char* RepNotifyFuncUTF8` | `bCanExit` → `"OnRep_bCanExit"`, `PlayersInsideCount` → `"OnRep_PlayersInsideCount"`; both names exist as real reflected UFunctions of the class; 0 when not RepNotify |
| `+0x10` | 8 | `EPropertyFlags PropertyFlags` (u64) | the `CPF_RepNotify` bit is set on exactly the two records that carry a `+0x08` name |
| `+0x18` | 4 | `EPropertyGenFlags Flags` (u32) | `TypeMask 0x3F` matches `binds_members.csv` types 13/13; `NativeBool 0x40` matches the `mov`-vs-`or` SetBitFunc form 8/8 |
| `+0x1C` | 4 | `EObjectFlags ObjectFlags` (u32) | `0x45` on every record image-wide |
| `+0x20` | 8 | `SetterFuncPtr SetterFunc` | 0 on all records seen |
| `+0x28` | 8 | `GetterFuncPtr GetterFunc` | 0 on all records seen |
| `+0x30` | 2 | `uint16 ArrayDim` | 1 on all |
| `+0x32` | 2 | **`uint16 ElementSize`** | 1 for every bool (both bitfield and `NativeBool`) |
| `+0x34` | **4** | **`uint32 SizeOfOuter`** | see the two-sided control below — **4 bytes, NOT `SIZE_T`** |
| `+0x38` | 8 | **`void (*SetBitFunc)(void*)`** | the lambda decoded in §4.1 |

**`SizeOfOuter` is a `uint32` at `+0x34`, not a `SIZE_T` at `+0x38`** — [M], with a two-sided
control against an entirely different function in each direction:

```
bCanExit record 0x8A4FFF0, bytes at +0x30:  01 00 | 01 00 | e0 01 00 00 | 50 b9 32 b2 f6 7f 00 00
                                            ArrDim  ElemSz  SizeOfOuter    SetBitFunc VA
   SizeOfOuter = 0x1E0  ==  ULokiRideableComponent::GetPrivateStaticClassBody InSize
                            0x54527D5  c7442420e0010000  mov dword ptr [rsp+0x20], 0x1e0    ✓
   AActor bools SizeOfOuter = 0x390  ==  AActor::GetPrivateStaticClassBody InSize
                            0x338BDA4  c744242090030000  mov dword ptr [rsp+0x20], 0x390    ✓
```
If `SizeOfOuter` were 8 bytes at `+0x38`, `SetBitFunc` would land at `+0x40` and every decode above
would fail. Record size `0x40` is independently confirmed by `PropPointers` spacing
(`0x8A4FFF0` → next record `0x8A50030`; `0x7F1F880` → `0x7F1F8C0`).

For reference, the same head is shared by the other families, with per-family tails:
`FObjectPropertyParams` `+0x38 = ClassFunc` (0x40 total) · `FArrayPropertyParams`
`+0x38 = ArrayFlags` (0x40 with padding) · `FClassPropertyParams` `+0x38 = MetaClassFunc,
+0x40 = ClassFunc` (0x50) · `FGenericPropertyParams` (Int) 0x38 head, 0x40 spacing.
Sizes here are **pointer-spacing derived**, so they include linker alignment padding.

### 4.3 THE FOUR `SetBitFunc` ENCODINGS THE IN-ARM DECODER MUST HANDLE [M]

All four occur in this image. A decoder handling only one will silently mis-read:

| bytes | instruction | meaning |
|---|---|---|
| `80 49 <d8> <mask> c3` | `or byte ptr [rcx+d8], mask; ret` | **bitfield** — ByteOffset = d8, ByteMask = FieldMask = mask (`bHidden`, `bAlwaysRelevant`) |
| `80 89 <d32> <mask> c3` | `or byte ptr [rcx+d32], mask; ret` | bitfield, 32-bit disp (`AActor::bAggregateTicks` @0x1D9) |
| `c6 41 <d8> 01 c3` | `mov byte ptr [rcx+d8], 1; ret` | **NativeBool** (real `bool`) — ByteMask = FieldMask = 0xFF (`bCanEverReplicate` @0x6C) |
| `c6 81 <d32> 01 c3` | `mov byte ptr [rcx+d32], 1; ret` | NativeBool, 32-bit disp (`bEnablePooling` @0x2D3, `bCanExit` @0x118) |

Cross-check the `mov` forms against the `NativeBool` bit (`Flags & 0x40`) in the same record — they
agreed on 8/8 bools inspected, in both directions.
⚠ For the `d32` forms the instruction is **7 bytes plus `c3`**. My own first decoder sliced a fixed
5 bytes and still returned the correct offset only because the disp32's high bytes happen to be
zero. **Decode the instruction; do not slice a fixed width.**

### 4.4 RUNTIME `FBoolProperty` MEMBER LAYOUT — **NOT ESTABLISHED, [S]**

If the shim would rather read the *live* `FBoolProperty` FField object: FK-14 established
`sizeof(FProperty) == 0x70` with the derived class's first member at `+0x70`, which would put
`FieldSize@0x70, ByteOffset@0x71, ByteMask@0x72, FieldMask@0x73`. **I could not confirm this.**
A `.text` scan for the characteristic paired-`0xFF` store — `66 c7 4? 72 ff ff`
(`mov word ptr [reg+0x72], 0xffff`, how `FieldMask = ByteMask = 0xff` compiles for a NativeBool) —
returned **0 hits**, while the same pattern at other displacements does occur in the same scan
(disp 0x6C ×4, 0x78 ×2, 0x7C ×1), so the search itself is live.
**That is a failed search, not a negative result** — `SetBoolSize` may be on an undecrypted page or
may have compiled to two byte stores. **Grade [S]; do not build a control on it.**
The `SetBitFunc` route in §4.3 needs no such assumption and is what the engine itself uses.

---

## 5. `PlayersAttached`'s INNER TYPE — ObjectProperty, pointer size 8 [M], four routes

No usmap was consulted (FK-14: usmap container inners are ~70 % wrong, deterministically).

1. **UHT gen flag [M]** — the inner record `0x8A500F0` has `Flags = 0x12` = `EPropertyGenFlags::Object`,
   with `ObjectPtr (0x80)` **clear** and no Weak/Lazy/Soft/Interface variant. An `FObjectProperty`
   is `sizeof(UObject*)` = 8 by definition on x64.
2. **UHT class getter [M]** — the inner record's trailing `ClassFunc` at `+0x38` is
   `0x5276490`, which is `e9dbaa1b00 jmp 0x5430F70`; that function is a
   `GetPrivateStaticClassBody` call with
   `0x5430FB6 lea rdx, [rip+0x35F334D]` → `.rdata 0x8A2430A` = UTF-16 **`"LokiPlayerState"`**,
   `0x5430FC5 lea rcx, [rip+0x33E42F4]` → `.rdata 0x88152C0` = UTF-16 **`"/Script/Loki"`**,
   `0x5431005 mov dword ptr [rsp+0x20], 0xeb8` = `sizeof(ALokiPlayerState)`.
   ⇒ element type = **`ALokiPlayerState*`**. The *same* `ClassFunc` pointer is shared by the inners
   of `PlayersInside`, `PlayersAttached` and `PlayersThatExited` — one more internal consistency check.
3. **`binds_members.csv` [M]** — `TArray<ALokiPlayerState> PlayersAttached`, from a disjoint tool.
4. **Disassembly stride [M]** — all six scan/append sites index with `*8`:
   `lea rdx, [rcx + rax*8]`, `lea r8, [rax + rcx*8]`, `mov qword ptr [rax + rbx*8], rdi`,
   `cmp qword ptr [rcx], r12`.

**And the `ResizeGrow` target is type-correct.** `0x00F988D0` is a
`TArray<T*, FDefaultAllocator>` specialisation with element size **8 baked in as a compile-time
constant** — there is no element-size parameter to get wrong:
```
0x0F988DF  48635908           movsxd rbx, dword ptr [rcx + 8]     ; ArrayNum   -> TArray+0x08
0x0F988EC  83790c00           cmp    dword ptr [rcx + 0xc], 0     ; ArrayMax   -> TArray+0x0C
0x0F9890F  488d0cc500000000   lea    rcx, [rax*8]                 ; NumBytes = NewMax * 8
0x0F98917  ba08000000         mov    edx, 8                       ; alignment
0x0F9892C  c744242008000000   mov    dword ptr [rsp+0x20], 8      ; NumBytesPerElement
0x0F98934  41b908000000       mov    r9d, 8                       ; NumBytesPerElement
```
Signature: **`void __fastcall ResizeGrow(FScriptArray* rcx, int32 OldNum edx)`**.
This also reads out the `TArray` ABI directly — `Data +0x0`, `ArrayNum +0x8`, `ArrayMax +0xC` —
which is what promotes the `0x130 / 0x138 / 0x13C` mapping from "assumed by convention" to
"read off two independent functions".

⚠ **`ResizeGrow 0x00F988D0` has ≥ 200 callers.** `fkdis.py callxref` **CAPS AT 200 ROWS**, so 200 is
a **floor, not a count**. It is heavily ICF-shared across every 8-byte-element `TArray` in the
image — which is exactly *why* it is the right function to reuse, and simultaneously why the
address identifies nothing about any particular caller.

⚠⚠ **ORDER IS LOAD-BEARING, AND THE NAIVE ORDER IS WRONG.** The game's own append writes
`ArrayNum = NewNum` **before** calling `ResizeGrow(&arr, OldNum)`, and `ResizeGrow` reads the
already-updated `ArrayNum` out of the array (`movsxd rbx,[rcx+8]`) while taking `OldNum` in `edx`
(`0x0F988E8 cmp ebx, edx`). An arm that grows first and sets `Num` afterwards hands the function a
state it was not compiled for.

---

## 6. IS `PlayersAttached` REPLICATED? — **NO** [M]

`PlayersAttached`'s `PropertyFlags = 0x0020080000000014` =
`BlueprintVisible | BlueprintReadOnly | Protected | NativeAccessSpecifierProtected`.
**`CPF_Net` (0x20) is clear.**

The discriminating control sits in the same class, decoded by the same instrument in the same pass:
`PlayersInside` reads `0x0020080000000034` — **identical except for the `0x20` bit**. `bCanExit`
and `PlayersInsideCount` additionally carry `CPF_RepNotify` (`0x0000000100000000`) and name their
`OnRep_` functions in the record's `RepNotifyFuncUTF8` field, both of which exist as real reflected
UFunctions of the class (§8a). So the instrument demonstrably *can* see replication on this class;
it simply is not present on `PlayersAttached`.

`CPF_Net` is the flag UHT sets from the `Replicated`/`ReplicatedUsing` specifier, and the flag
`UClass::SetUpRuntimeReplicationData` filters on when assigning `RepIndex`. A property without it
has no `RepIndex` and cannot appear in any lifetime list.

⇒ **Writing `PlayersAttached` by hand skips nothing.** No RepNotify to miss, no
`MARK_PROPERTY_DIRTY` obligation, no client-side consumer that reads it through the net serializer.
Independently: S131 measured `Loki::LokiIsServer()` (impl `0x0F7EB60` = `xor al,al; ret`) as
hardcoded FALSE on this client, so nothing replicates outward regardless.

The three **replicated** properties on this component are `bCanExit`, `PlayersInsideCount` and
`PlayersInside`. ⚠ If the arm ever pokes `PlayersInsideCount` directly it will **not** fire
`OnRep_PlayersInsideCount` and therefore will **not** broadcast `OnPlayersInsideCountChanged @0xE0`
— that delegate's only emitter is the OnRep (impl `0x55E0FC0`, §3), which the net serializer calls
on a receiving client. Call the OnRep thunk (`0x5457730`) explicitly if the broadcast is wanted.

---

## 7. ⚠ `ALokiDropPod :: LokiRideable @ 0x6C8` — CANNOT BE CONFIRMED, AND THE PREMISE IS WRONG

Three instruments were run; **all three say there is no such native or script member.**

1. **UHT [M]** — `ALokiDropPodBase` (`/Script/Loki.LokiDropPodBase`, the C++ base) has a
   `PropPointers` array with **exactly one entry**: `PilotPlayerState`, gen `Object`,
   `Offset = 0x3C0`, record `.rdata 0x8934170`, array `.rdata 0x89341B0`.
   ★ That is an exact match for CLAUDE.md's independently recorded
   `[M] PilotPlayerState 0x3C0 (LokiDropPodBase, UHT)` — a positive control on my decoder against
   a prior session's measurement, on a class I did not otherwise touch. There is no `LokiRideable`
   property on it.
2. **Angelscript oracle [M]** — `tools/asdump/out/GameMode/DropPhase/LokiDropPod.as.txt`
   lines 153–250 carry the full verbatim declaration of `class ALokiDropPod : ALokiDropPodBase`
   (~45 members, incl. every offset S131 measured: `bPilotHasPodControl`, `bIsTeamLeaderPod`,
   `PodTeamIndex`, `CurrPodDestination`, `AttachedCrewPods`, `LeaderPod`, `bHasStartedGameplay`,
   `PodStateEvent`, `PodMeshComponent`). It declares **no** `ULokiRideableComponent` member.
   Every access in the whole module is `ULokiRideableComponent::Get(this, NAME_None)` — a component
   *lookup* — at lines 1530, 2258, 3940, 5104 (and line 159 in `LokiDropShip.as.txt`).
   A grep over all of `tools/asdump/out/modules/` finds **zero** `ULokiRideableComponent` member
   declarations in any script class.
3. **String search [M]** — `"LokiRideable\0"` and `"LokiRideable_GEN_VARIABLE"` have **0** byte
   occurrences in `merged4`. Positive control: `"RideableComponent\0"` **is** present at
   `.rdata 0x8933730`, and `binds_members.csv` attributes it to
   `ALokiDropPlane::RideableComponent` — so the search would have found a real property name.

**Where the name actually comes from [M]:** the cooked asset. `tools/extractor/out/BP_DropPod.json`
export #50 is
```json
{"Type":"LokiRideableComponent","Name":"LokiRideable_GEN_VARIABLE","Outer":"BP_DropPod_C",
 "Class":"UScriptClass'LokiRideableComponent'",
 "Flags":"RF_Public | RF_Transactional | RF_ArchetypeObject | RF_WasLoaded | RF_LoadCompleted"}
```
⇒ `LokiRideable` is a **Blueprint-generated default-subobject `ObjectProperty` on
`BP_DropPod_C`**. Its offset is assigned when the `BlueprintGeneratedClass` is linked at load time,
downstream of `sizeof(ALokiDropPod)` (itself an Angelscript class whose size is computed at load)
plus any preceding BP-declared properties. **No offline instrument in this repo can produce it.**

⇒ **Do NOT hard-code `0x6C8` in the arm.** Either resolve `LokiRideable` **by name** off the live
class's property chain (what the S131 probe evidently did — its `LokiRideable = 0x0` reading on the
deferred pod is a *live* observation, and remains valid as such), or — better and layout-free —
use the game's own route, `ULokiRideableComponent::Get(actor, NAME_None)`, which is what all four
Angelscript call sites do. `0x6C8` is an observation from one live process, not a property of the
build, and it should be re-derived per BP subclass: `BP_DropPod_C`, `BP_DropPod_Tutorial_C` and
`BP_DropPod_Child_C` are three distinct `BlueprintGeneratedClass`es.

---

## 8. BONUS FINDINGS THE ARM SHOULD KNOW

### (a) Four of the component's own entry points are STRIPPED FOLDS

Graded from the `.data` `{name_ptr, exec_thunk, impl}` record table against the five known folds:

| function | thunk | impl | grade |
|---|---|---|---|
| **`AuthAddPlayer`** | `0x2C2CE30` | **`0x00F7EC20`** | **EMPTY (`ret 0`)** |
| **`AuthRemovePlayer`** | `0x2C2CE30` | **`0x00F7EC20`** | **EMPTY** |
| **`AuthSetCanJump`** | `0x5296F30` | **`0x00F7EC20`** | **EMPTY** |
| **`AuthPlayerEnterWorldNew`** | `0x5456460` | **`0x00F7EC20`** | **EMPTY** |
| `AuthPlayerDetachPlayerFromRidable` | `0x5456100` | `0x55CCCB0` | REAL |
| `AuthPlayerEnterWorld` | `0x54561D0` | `0x55CCE70` | REAL |
| `AuthPlayerEnterWorldAttachedToRidable` | `0x5456380` | `0x55CD510` | REAL |
| `AuthPlayerPreSpawnOnAddToPlane` | `0x5456540` | `0x55CD800` | REAL |
| `CanExit` | `0x5260EC0` | `0x525C240` | REAL |
| `ContainsPlayer` | `0x5456700` | `0x55D0270` | REAL |
| `GetLandingTeleportLocation` | `0x5456C80` | `0x55D89F0` | REAL |
| `GetRidePosition` | `0x5457070` | `0x55DAB50` | REAL |
| `MulticastOnPlayerEntered` / `...EnteredWorld` / `...Exited` | `0x53BD130` / `0x3BCD5B0` / `0x54573B0` | `0x5453780` / `0x54537C0` / `0x5453800` | REAL |
| `OnRep_bCanExit` | `0x54577B0` | `0x55E1000` | REAL |
| `OnRep_PlayersInsideCount` | `0x5457730` | `0x55E0FC0` | REAL |

The four REAL `Auth*` impls and the `0x5456100`/`0x55CCCB0` detach pair match CLAUDE.md's
recorded values exactly — a fourth positive control on this table.

⇒ **There is no working API to add to `PlayersInside`** — `AuthAddPlayer` is a no-op. That is a
stronger statement than "don't poke it": the hand poke is the *only* route, and §8b says not to
take it.
⚠ `0x2C2CE30` is shared by `AuthAddPlayer` and `AuthRemovePlayer` — an ICF-folded one-argument exec
thunk, **non-identifying**; only the impl grades the function.
⚠ `HasEverContainedPlayer` returned **two** `.data` records (`0x53369E0`→`0x55DCA90` and
`0x5457280`→`0x55DCAA0`) because the lookup is by name string and another class ships a function of
the same name. The one reached from the wall is `0x55DCAA0` (§8b); the other is unattributed and
should not be quoted as this class's.

### (b) ⚠⚠ THE ORDERING TRAP IS NOW MEASURED, NOT INFERRED

CLAUDE.md warns that poking `PlayersInside` first turns the wall itself into a silent no-op and
destroys the `"failed to get the round game mode"` receipt. The mechanism is now visible in two
places:

* `HasEverContainedPlayer` impl `0x55DCAA0` **linear-scans `PlayersInside` (`+0x120`/`+0x128`)
  FIRST** and returns `1` on a hit (`0x55DCAC0 cmp qword ptr [rax], r9` → `je 0x55DCB57` →
  `b0 01 mov al,1; ret`), only falling through to the `PlayersThatExited` TSet lookup on a miss.
* The wall's own prologue calls it and bails on true:
```
0x55CD54E  e84df50000   call 0x055DCAA0        ; HasEverContainedPlayer
0x55CD553  84c0         test al, al
0x55CD555  0f8520020000 jne  0x055CD77B        ; -> plain restore-and-ret epilogue
```
  `0x55CD77B` is the epilogue (`lea r11,[rsp+0x160] ... pop rbp; ret`) — **a silent bail, before
  any logging point and before `0x55CD572 call 0x00F7EB50`.**

### (c) The detach's two folds are confirmed at the exact addresses CLAUDE.md records

`0x55CCD5B e8c01e9bfb call 0x00F7EC20` and `0x55CCE4E e8cd1d9bfb call 0x00F7EC20`, and there are
**no** `0x00F7EB50` calls anywhere in `0x55CCCB0..0x55CCE60`. This re-confirms CLAUDE.md §14.1's
correction ("NOT fold-free — TWO `0xF7EC20` calls") and its narrower companion claim
("zero `0xF7EB50`"), from an independent pass.

---

## 9. DISAGREEMENTS AND CAVEATS (deliverable 6)

**Between UHT metadata and disassembly: ZERO disagreements.** Every offset both instruments can
speak to agreed: `0xD0`, `0xE0`, `0x118`, `0x11C`, `0x120`/`0x128`, `0x130`/`0x138`/`0x13C`,
`0x140`. There is likewise no disagreement with `binds_members.csv` on any type or on declaration
order (10/10), nor with the four CLAUDE.md values this lane happened to re-derive
(`AActor+0x6C`, `AActor+0x2D3`, `LokiDropPodBase+0x3C0`, the detach/wall impl addresses).

Everything below is a limit of *my* instruments, stated so a successor does not read it as a fact
about the game:

* ⚠ **`PlayersInside.ArrayMax @0x12C` is [I], not [M].** No use site exists — nothing in this
  client grows that array, because `AuthAddPlayer` is a fold. It follows from the `TArray` ABI,
  which *is* [M] (§5).
* ⚠ **The runtime `FBoolProperty` member layout is [S]** — §4.4. A failed search, not a negative.
* ⚠ **The `FClassParams` count packing is [I], fitted from 2 samples.** `+0x38` holds the four
  counts bit-packed (`+0x3C` is `ClassFlags`). Best fit over both samples:
  `deps = bits[0:4]`, `funcs = bits[4:15]`, `props = bits[15:]` — `0x00068122` → 2 / 18 / 13 and
  `0x00390992` → 2 / 153 / 114. The **`props` field is independently corroborated** by the
  `PropPointers` array extents (13 and 114, measured from array bounds), which is what the rest of
  this report rests on; the `deps` and `funcs` widths have free parameters and must not be quoted
  as measured.
* ⚠ **`callxref` and `findptr` cap at 200 rows.** "≥200 callers" for `ResizeGrow` is a floor.
* ⚠ The `PlayersThatExited` TSet internals (`+0x140..~+0x190`) were read opportunistically out of
  `HasEverContainedPlayer` and were not checked against a UE `TSet` ABI reference. They are
  self-consistent and match the `Num() = ArrayNum - NumFreeIndices` idiom S123 recorded, but treat
  the sub-field names as [I].
* ⚠ Instrument note for a successor: my first `SetBitFunc` decoder sliced a fixed 5 bytes, which
  truncates the `disp32` encodings; it returned correct offsets only because the high disp bytes
  are zero. **Decode the instruction, do not slice a fixed width.** (Same family as the
  `pod_verdict.py` regex defect S131 recorded: an analysis script is an instrument too.)

---

## 10. WHAT THE ARM SHOULD WRITE — a restatement of the above, not new evidence

```
comp = <live ULokiRideableComponent*>          # e.g. ULokiRideableComponent::Get(pod, NAME_None)

# PlayersAttached : TArray<ALokiPlayerState*>
D = comp + 0x130     # Data     (void**)
N = comp + 0x138     # ArrayNum (int32)
M = comp + 0x13C     # ArrayMax (int32)

# game-identical single append, mirroring 0x55CD738..0x55CD767 exactly:
oldNum = *N                       # measured live by S131 as 0 (Data=0 Num=0 Max=0)
*N = oldNum + 1                   # write Num FIRST
if (*N > *M):
    ResizeGrow(rcx = comp + 0x130, edx = oldNum)      # 0x00F988D0, element size 8 baked in
(*D)[oldNum] = playerState        # qword store at Data + oldNum*8
```
* **Do NOT touch `+0x120` (`PlayersInside`) first** — §8b: it makes `HasEverContainedPlayer` return
  true, which makes the wall bail silently and destroys its own receipt.
* `+0x130` is **not replicated** (§6), so no dirty-marking or RepNotify is being skipped.
* `ResizeGrow` is **not a `UFunction`** — the S55 native-call primitive does not apply. It is a
  plain `__fastcall(FScriptArray*, int32)` direct call, and it performs zero module-image writes.
* If an in-arm control is wanted on the pod actor, `AActor::bHidden` (`+0x68`, bit `0x80`) and
  `AActor::bAlwaysRelevant` (`+0x68`, bit `0x08`) are confirmed — but they live in a **shared
  bitfield byte** with six other flags: `or`/`and` the mask, never store a whole byte (§4.1).
* A cheaper, already-proven control on this same component: `ContainsPlayer` (`0x5456700` →
  `0x55D0270`), which S131 flew live with `fault=no`.
