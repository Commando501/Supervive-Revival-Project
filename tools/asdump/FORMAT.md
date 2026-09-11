# SUPERVIVE Angelscript cache — definitive format spec

Reverse-engineered 2026-07-26 from the shipping build dated **2025-12-17**, by two
independent implementations that were then cross-checked against each other and against
the game binary. Everything below is **verified against the actual bytes**, not inferred
from upstream source. Where something is still unknown it says so explicitly.

The three files live in `<install>/Loki/Script/`:

| file | size | content |
|---|---:|---|
| `PrecompiledScript.Cache` | 1,184,817 | declarations + compiled bytecode |
| `Binds.Cache` | 5,764,301 | engine↔script binding table |
| `Binds.Cache.Headers` | 2,050,287 | `/Script/Mod.Class` → C++ header path |

**Both `Binds.Cache` files and `PrecompiledScript.Cache` parse to 100.0000% byte
coverage with zero gaps and zero overlap.** That is the primary evidence the layout
below is right: there is no magic, no chunk table, no offset table and no alignment
anywhere, so the only way to reach EOF exactly is to replay the correct `operator<<`
order for every field.

---

## 0. Provenance and engine version

The files are raw `FMemoryWriter` dumps of UE-Angelscript's
`FAngelscriptPrecompiledData` and `FAngelscriptBindDatabase`. SUPERVIVE's fork of
Hazelight's plugin sits in a known window:

- It is **after** the commit that added `FStringInArchive` (see §1.2).
- It is **before** upstream `661ba173` ("bitpacking bools"), because every C++ `bool`
  is still serialised as a **4-byte legacy UBOOL**.

That bracket was not narrowed further. It does not matter for this build, but if a
future SUPERVIVE build fails to parse, re-bracket the revision before assuming the
format changed.

### The opcode table is NOT upstream AngelScript's

The fork's VM differs from stock in ways that break a naive decoder. The table used by
`asdump.py` was extracted **byte-exact from the game binary's own tables** rather than
copied from `as_bytecode.h`:

```
asBCInfo[256]     RVA 0x084A22C0    entry = { u32 bc; u32 type; i32 stackInc; u32 pad; u64 name; }  (24 B)
asBCTypeSize[22]  RVA 0x084B45A0    (an identical second copy sits at 0x084EA4A0)
ImageBase         0x7FF6AF000000    in dumps/merged.dump.exe (dumpimage sets file-offset == RVA)
```

`asBCTypeSize` = `[0,1,1,1,2,2,3,3,2,3,2,1,2,3,2,2,4,3,2,3,3,2]` (in **dwords**).

Fork differences worth knowing:

- There are **22** `asEBCType` entries; upstream has 21. The extra one is ordinal 21,
  `asBCTYPE_W_rW_ARG`.
- Opcode **212 `ThrowException`** has a real name, type and size, but the dummy slots
  213–250 carry `bc == 212`, which would imply `asBC_MAXBYTECODE == 212`. Treat
  **0..212 inclusive as valid**; the fork appears not to have bumped `MAXBYTECODE` when
  `ThrowException` was appended.
- 251–255 are the pseudo-instructions (`VarDecl`, `Block`, `ObjInfo`, `LINE`, `LABEL`)
  and never appear in final bytecode. Upstream 2.38's `TryBlock` at 250 is a dummy here.
- `CALLSYS` / `Thiscall1` are **3 dwords** in this build.

**Operand layout** is positional and derives from the `asEBCType` *name*:

```
opcode      = byte 0 of dword 0
W0/wW0/rW0  = int16  at byte +2       (asBC_SWORDARG0)
W1/rW1      = int16  at byte +4       (asBC_SWORDARG1)
rW2         = int16  at byte +6       (asBC_SWORDARG2)
DW          = int32  on the next free dword boundary (min +4)
QW          = int64  on the next free dword boundary (min +4)
instruction length = asBCTypeSize[type] dwords
```

Deriving lengths from the names this way reproduces all 22 entries of the binary's own
`asBCTypeSize` exactly — that is what pins the layout of the fork-added type 21.

Seven opcodes carry AngelScript's `0xFFFF` "variable stackInc" sentinel:
`CALL, RET, CALLSYS, CALLBND, ALLOC, CALLINTF, CallPtr`.

---

## 1. Primitives

Everything is **little-endian and byte-packed at whatever offset the cursor reached**.
There is no padding and no alignment anywhere in any of the three files.

### 1.1 Scalars

| type | encoding |
|---|---|
| `int8/int32/uint32/int64/uint64` | plain LE, unaligned |
| `bool` | **4-byte legacy UBOOL**, value always 0 or 1 |

The bool encoding is the single best desync canary in the format — a run over the whole
file checks roughly 250,000 of them, and any value > 1 means the walk has slipped.

### 1.2 Strings — two encodings, NOT interchangeable

This is the one thing that makes naive scanners conclude "NUL handling is inconsistent".
It is not inconsistent; there are simply **two different string types**, and both
implementations independently arrived at the same rule.

**`FString`** (stock UE) — length **INCLUDES** the trailing NUL.

```
int32 len ; len bytes (last byte is NUL)
len == 0            -> empty string, nothing follows
len <  0            -> UTF-16LE, |len| code units (still NUL-terminated)
```

Used for **exactly one field** in `PrecompiledScript.Cache` — the `Modules` TMap key —
and for **every** string in `Binds.Cache` / `Binds.Cache.Headers`.

**`FStringInArchive`** (the plugin's own type, `StringInArchive.h`) — length **EXCLUDES**
the NUL, and `len + 1` bytes follow.

```
int32 len ; len bytes ; one NUL byte
len == 0            -> NOTHING follows, not even the NUL      <-- the asymmetry
```

Used for **every other string** in `PrecompiledScript.Cache`.

Worked example at the very start of the file:

```
0x18  14 00 00 00  "Airship.LokiAirship\0"   FString,          len 20 INCLUDES the NUL
0x30  13 00 00 00  "Airship.LokiAirship" 00  FStringInArchive, len 19 EXCLUDES it
```

### 1.3 Arrays

`TArray<T>` = `int32 count`, then `count` elements back to back. A negative count is
malformed. There is no element-size prefix, so a wrong element reader desyncs the whole
remaining file rather than one record.

---

## 2. `PrecompiledScript.Cache`

### 2.1 Top level

```
0x00  FGuid   DataGuid           16 B, four u32
0x10  int32   BuildIdentifier    1=DEBUG 2=DEVELOPMENT 3=TEST 4=SHIPPING   (this build: 4)
0x14  TMap<FString, FAngelscriptPrecompiledModule>  Modules
      ... 7 trailer tables, in this exact order ...
```

**The GUID is NOT a format identifier.** It is regenerated per save. In this build it is
`95a76d41-99c2-a148-89f7-1e3269f88eeb` (as four LE u32:
`416DA795-48A1C299-321EF789-EB8EF869`). Do not gate parsing on it.

A `TMap` serialises exactly like a `TArray` of key/value pairs — `int32 count`, then
`count` × (key, value). There is no hash or bucket data.

Measured region ledger for this build:

```
0x00000000..0x00000014        20 B   0.00%  header
0x00000014..0x000C5B09   809,717 B  68.34%  Modules (78)
0x000C5B09..0x000CE4F9    35,312 B   2.98%  TypeReferences (546)
0x000CE4F9..0x000CFE95     6,556 B   0.55%  TypeIdReferenceToPointer (546)
0x000CFE95..0x00110398   263,427 B  22.23%  FunctionReferences (1946)
0x00110398..0x00115ED4    23,356 B   1.97%  FunctionIdReferenceToPointer (1946)
0x00115ED4..0x00119115    12,865 B   1.09%  GlobalReferences (187)
0x00119115..0x0011A516     5,121 B   0.43%  StaticNames (208)
0x0011A516..0x00121431    28,443 B   2.40%  PropertyReferences (867)
                       ---------
                       1,184,817 B  = file size, UNACCOUNTED 0
```

> The original task brief described the region after the last module as "unidentified,
> ~34% of the file". It is not unidentified: it is those **seven trailer tables**, and
> they are what turn raw bytecode operands into names. `FunctionReferences` alone is 22%
> of the file.

### 2.2 `FAngelscriptPrecompiledDataType` — 36 bytes, flat

Read in this order. Six UBOOLs (24 B) + int64 + int32.

```
bool   bIsReference
bool   bIsObjectConst
bool   bIsObjectHandle
bool   bIsConstHandle
bool   bIsAuto
bool   bIfHandleThenConst
int64  TypeInfo        save-time asCObjectType*  -> look up in TypeReferences
int32  TokenType       eTokenType
```

⚠ The plugin's **master** branch has a 10-byte version of this struct. Using it desyncs
about 120 bytes into the first function. This build's is 36 bytes.

**`TokenType` ordinals that actually occur** (measured over every DataType in the file —
these are the only eight values present):

| value | meaning | count |
|---:|---|---:|
| 5 | `ttIdentifier` — an object/struct/enum; the name is in `TypeInfo` | 3,116 |
| 59 | `?` (AngelScript variable type) | 13 |
| 65 | `bool` | 577 |
| 68 | `int` | 321 |
| 76 | `uint8` | 1 |
| **80** | **`float` (float32)** | 94 |
| **81** | **`double` (float64)** | 460 |
| 82 | `void` | 1,973 |

Values 79 and 94 do **not** occur; if you saw a table claiming 79=float/94=double, it is
not what this build emits.

### 2.3 Module record

Key is an `FString`; the value is:

```
FStringInArchive          ModuleName          (always == the TMap key -- assert it)
TArray<Function>          Functions           module-level / static functions
TArray<Class>             Classes
TArray<Enum>              Enums
TArray<GlobalVar>         GlobalVariables
TArray<(FStringInArchive, FuncSig)>  FunctionImports
int64                     CodeHash
TArray<FStringInArchive>  ImportedModules
FStringInArchive          StaticsClassName
TArray<FStringInArchive>  DeclaredEvents
TArray<FStringInArchive>  DeclaredDelegates
FStringInArchive          ScriptRelativeFilename    e.g. "GameMode/DropPhase/LokiDropShip.as"
TArray<FStringInArchive>  PostInitFunctions
```

78 modules; record sizes 1,405 → 61,534 bytes.

### 2.4 Function record

```
FStringInArchive          FunctionName
FStringInArchive          Namespace
DataType                  ReturnType
TArray<DataType>          ParameterTypes
TArray<FStringInArchive>  ParameterNames          parallel with ParameterTypes
TArray<int32>             ParameterFlags          asETypeModifiers, parallel
TArray<FStringInArchive>  ParameterDefaultArgs    SOURCE TEXT, e.g. "FVector::ZeroVector"
int32                     FunctionTraits          see below
TArray<int32>             ByteCode                <-- count is in DWORDS, not bytes
TArray<int32>             ByteCodeReferences      ALWAYS EMPTY in this build
int32                     VariableSpace
TArray<int64>             ObjVariableTypes        parallel with ObjVariablePos
TArray<int32>             ObjVariablePos          -> types every object local exactly
int32                     ObjVariablesOnHeap
TArray<int32>             VariableInfoProgramPos  } parallel; EMPTY in shipping
TArray<int32>             VariableInfoOffset      }
TArray<int32>             VariableInfoOption      }
int32                     StackNeeded
uint32                    Id                      globally unique across the file
int32                     DeclaredAt              ALWAYS 0 in shipping
TArray<int32>             LineNumbers             ALWAYS EMPTY in shipping
bool                      bIsUFunction
  if bIsUFunction:
    FStringInArchive          UnrealFunctionName  the UFunction alias, may differ
    TArray<FStringInArchive>  MetaSpec            } parallel
    TArray<FStringInArchive>  MetaValues          }
    bool[18]                  Flags               order in §2.8
```

`DeclaredAt == 0` and `LineNumbers == []` for **all 1,463 functions**. The plugin guards
both with `#if !UE_BUILD_SHIPPING`, so **local variable names and line numbers are not
recoverable at any effort** — they were never written.

#### `FunctionTraits` bits — measured, not guessed

Correlated against `FunctionReferences[].bIsConst`, which is an independent boolean
stored elsewhere in the same file (813 functions matched by name+namespace+arity):

| bit | meaning | evidence |
|---:|---|---|
| 0 | **constructor** | set on exactly 130 functions, all constructors, **none const** |
| 1 | destructor / behaviour | set on exactly 68, all behaviours |
| 2 | **`const` method** | 56 set&const, 0 set&NOT-const, 1 unset&const → 812/813 |
| 3 | private | methods only (64) |
| 4 | protected | methods only (120) |
| 5, 13, 18 | **UNKNOWN** | set far too broadly to be stock FINAL/OVERRIDE/SHARED — bit 5 is on 1,451 of 1,463 functions. Report raw; do not guess. |

> ⚠ Using **bit 0** for `const` (an easy mistake — it is `asTRAIT_CONSTRUCTOR`, and
> `asTRAIT_CONST` is bit 2) prints `const` on all 130 constructors and on none of the 73
> genuinely-const methods. One of the two source implementations did exactly this.

### 2.5 Class record

```
FStringInArchive   ClassName
FStringInArchive   Namespace
int32              Flags
TArray<Property>   Properties
TArray<Function>   Methods
TArray<int32>      MethodTable          see the note below
int64              DerivedFrom
int64              ShadowType
TArray<Function>   Constructors
TArray<int64>      FactoryRefs
TArray<int64>      BehaviorRefs         0 or exactly 7 entries
TArray<Function>   BehaviorFunctions    } parallel
TArray<int32>      BehaviorFunctionTypes}
bool               bInPreprocessor
  if bInPreprocessor:
    FStringInArchive  SuperClass
    FStringInArchive  CodeSuperClass
    bool[7]           SuperIsCodeClass, Abstract, Transient, HideDropdown,
                      DefaultToInstanced, EditInlineNew, DeprecatedClass
    FStringInArchive  ConfigName
    FStringInArchive  StaticClassGlobal    e.g. "__StaticType_ALokiDropShip"
    bool              Placeable
    TArray<FStringInArchive> MetaSpec      } parallel
    TArray<FStringInArchive> MetaValues    }
    FStringInArchive  ComposeOnto
```

The 7 `BehaviorRefs` slots are, in order:
`factory, listFactory, copyfactory, construct, copyconstruct, destruct, copy`.

> **`MethodTable` is NOT a list of function ids.** Interpreted that way it resolves
> 56/1040. It is the **virtual dispatch table**: each entry indexes the class's own
> `Methods` array, or is `-1`.

### 2.6 Property, Enum, GlobalVar

```
Property:
  FStringInArchive  Name
  DataType          Type
  bool              bIsPrivate
  bool              bIsProtected
  bool              bIsUnrealProperty
    if bIsUnrealProperty:
      TArray<FStringInArchive> MetaSpec, MetaValues       (parallel)
      bool[13]  BlueprintReadable, BlueprintWritable, EditConst, EditableOnDefaults,
                EditableOnInstance, InstancedReference, PersistentInstance,
                AdvancedDisplay, Transient, Replicated, SkipReplication,
                SkipSerialization, SaveGame
      if Replicated:                                       <-- CONDITIONAL, easy to miss
        int32  ReplicationCondition
        bool   bRepNotify
      bool[3]   Config, Interp, AssetRegistrySearchable

Enum:      FStringInArchive Name, Namespace
           TArray<FStringInArchive> EnumNames
           TArray<int32> EnumValues            (parallel; EXPLICIT values)

GlobalVar: FStringInArchive Name, Namespace
           DataType Type
           bool bIsDefaultInit
             if not: bool bIsPureConstant
               if pure:  uint64 PureConstantValue
               else:     bool bHasInitFunction ; Function InitFunc
```

Only **4** enums are script-declared (`EBarracudaMinionGoldRewardMethod`,
`EBarracudaShopValueType`, `EBarracudaRespawnBehaviorType`, `ETemporaryFloorState`).
Every other enum the script touches is a C++ `UENUM` and its members are **not in any of
the three cache files** — see §4.

### 2.7 The seven trailer tables

These resolve bytecode operands to names. Two kinds of int64 appear in bytecode and they
must not be confused:

- **pointer-valued** — the save-time address of an `asCObjectType` /
  `asCScriptFunction` / global. Looks up **directly**.
- **id-valued** — a small AngelScript id. Must go through the `…IdReferenceToPointer`
  map **first**.

```
TypeReferences               TMap<int64 ptr, {sia Name, sia Module, sia Namespace,
                                              TArray<DataType> SubTypes}>
TypeIdReferenceToPointer     TMap<int32 typeId, int64 ptr>
FunctionReferences           TMap<int64 ptr, {sia Name, sia Module, sia Namespace,
                                              bool bIsConst, bool bIsImportedDecl,
                                              bool bIsMethod, int64 ObjectType,
                                              TArray<DataType> ParameterTypes,
                                              DataType ReturnType}>
FunctionIdReferenceToPointer TMap<int32 funcId, int64 ptr>
GlobalReferences             TMap<int64 ptr, {sia Name, sia Module, sia Namespace,
                                              bool bIsString}>
StaticNames                  TArray<FStringInArchive>      the FName literal pool
PropertyReferences           TMap<int64 key, {sia Name, int32 OldTypeId}>
```

**Member access uses a third scheme.** `ADDSi` / `LoadThisR` / `Load*ObjR` carry a DWORD
(owning type id) and a SWORD (byte offset); the `PropertyReferences` key is the composite

```
key = (TypeId << 1) | (Offset << 33) | 1
```

That resolves 3,530/3,530 member accesses to real property names in this build — so
`obj+0x478` never has to be printed.

> The int64 **pointer** values are live save-time addresses (e.g. `0x26e6e875800`) and
> are meaningless as addresses offline. They are only ever used as **table keys**. Never
> try to dereference them.

### 2.8 `UFUNCTION` flag order (18 bools)

```
BlueprintCallable, BlueprintOverride, BlueprintEvent, BlueprintPure, NetFunction,
NetMulticast, NetClient, NetServer, NetValidate, Unreliable, BlueprintAuthorityOnly,
Exec, CanOverrideEvent, DevFunction, Static, Const, ThreadSafe, NoOp
```

---

## 3. The calling convention (needed to read the bytecode at all)

Nothing in the file states this; it was derived and then checked two ways.

**Parameter slots.** `this` (methods only) is at variable offset **0**; parameters march
**negative**, each starting where the previous ended:

```
off[0] = -2 if method else 0            (AS_PTR_SIZE == 2 dwords on x64)
off[i] = off[i-1] - width(param[i-1])
```

**Widths on the value stack**, in dwords:

| kind | width |
|---|---:|
| reference (`&`, `&in`, `&out`, `&inout`) | 2 |
| object handle / object | 2 |
| `int64`, `uint64`, `double`/`float64` | 2 |
| `bool`, `int`, `uint`, `float`, small ints | 1 |
| **enum** | **1** |

> ⚠ **An enum is 1 dword, not 2.** It *has* `TypeInfo`, so the obvious "has type info ⇒
> pointer ⇒ 2" rule is wrong for it. Getting it wrong shifts the offset of every
> parameter that follows an enum. Measured impact in this corpus: **19 functions**
> affected, **10** of which reference a shifted slot — including 7 in
> `GameMode/DropPhase/LokiDropPod.as`, where `SetCrewPodDetachState`'s
> `InputPercent` / `DetachDirection` / `VectorDirection` all get mis-attributed.
> Both source implementations of this tool hit this bug; only one caught it.

Worked example — `ALokiDropShip::Spawn(Location, Rotation, Name, bDeferredSpawn, Level)`
with widths 2,2,2,1,2 lands on offsets **0, −2, −4, −6, −7**, exactly the slots its
bytecode references.

> ⚠ **The hidden by-value return pointer occupies a slot in the callee's own frame.**
> The rule above is only complete for a function that does NOT return a value type.
> When `DoesReturnOnStack()` is true, the frame is `[this] [hidden ret ptr] [param0] …`,
> so every declared parameter starts **two dwords further down**: `off[0] = −4` for a
> method, `−2` for a global. Measured over this corpus: **34** script functions return a
> value type on the stack and **20** of those take parameters, so 20 functions had every
> parameter name attached to the wrong slot — the hidden pointer wore `param0`'s name and
> the real `param0` printed as an anonymous `arg_mN`. Visible cases:
> `ULokiRespawnComponent::GetValidPlayerStart` (`PS` landed on the `FTransform` temp) and
> `LokiScriptUtility::LinearColorToVector`, which read `arg_m2.B` instead of `Color.B`.
> `asdump.py` names that slot `__ret`, so `__ret = FVector(v56)` is a by-value `return`.

**`REFCPY` operand order** (`*dst = src`, refcounted). The **destination is the TOP of
the stack**, the source sits below it, and only the destination is consumed:

```
asDWORD **d = (asDWORD**)*(asPWORD*)l_sp;   // top  -> destination
l_sp += AS_PTR_SIZE;
asDWORD  *s = (asDWORD*) *(asPWORD*)l_sp;   // next -> source
*d = s;
```

The compiler emits `PshVPtr <src> ; PshVPtr this ; ADDSi .<member> ; REFCPY ; PopPtr`
(the trailing `PopPtr` discards the source `REFCPY` left behind). Reading the first pop
as the right-hand side inverts **every handle assignment in the file** — 116 sites here
— and shows up as impossible statements like `nullptr = this.HitHeightIndicator;`.

**Numeric immediates.** `SetV8`/`PshC8` carry a bare 64-bit value that is an `int64`
*or* an IEEE-754 `double`, with nothing in the encoding to distinguish them. Exponent
separates them: a bit pattern only decodes to a normal double (|d| >= 1e-300) once the
raw u64 exceeds ~1.2e17, well above every int64 literal in this corpus. Measured over
all 77 distinct 64-bit immediates: 76 are clean game numbers (`1.0`, `0.8`, `500.0`,
`1e-8`, `DBL_MAX`), 1 is zero (identical text either way), 0 are misclassified. `SetV4`/
`PshC4` is the same story for `float32` but only above |v| > 1e6 (all 28 such immediates
in the corpus are clean floats; `1106247680` is `30.0f`).

**Call stack shape**, from the top down:

```
[this] [hidden by-value return ptr] [param0] [param1] ...
```

Arguments are pushed in **reverse** order (last parameter first).

- The hidden return pointer exists only when the callee returns a **value type** neither
  by reference nor as a handle (`asCScriptFunction::DoesReturnOnStack`). **Enums do not
  return on the stack** — they are `asOBJ_ENUM`, not `asOBJ_VALUE`. Treating an enum
  return as a by-value return silently eats one argument and shifts the entire call.
- A `?&` (variable-type) parameter costs **one extra dword** beyond its declared width —
  the reference plus a `TYPEID` dword.
- `ALLOC` consumes the destination pointer (2 dwords) plus the constructor's arguments;
  its `QW` is the **type**, its `DW` the **constructor function id**.

**Independent check.** Accumulating the game's own `asBCInfo.stackInc` per instruction,
and deriving the delta from the callee signature only for the seven `0xFFFF` sentinel
opcodes, the depth returns to zero at `RET` in **1,449 / 1,463** functions (99.04%). The
14 residuals are all value-type struct constructors (`FLaserTraceResult`,
`FAimingLaserSettings`, `FLokiUsableData`), where a list-factory / copy-construct
behaviour is not yet modelled. This audit shares no code with the lifter, so agreement
between the two is real corroboration of the convention.

---

## 4. `Binds.Cache` and `Binds.Cache.Headers`

`FAngelscriptBindDatabase::Serialize` — two `TArray`s back to back, no header, no magic,
no version. **All strings here are plain `FString`** (len includes the NUL), *not*
`FStringInArchive`.

```
Binds.Cache:
  TArray<Struct>  Structs      4,784
  TArray<Class>   Classes      5,582     (15,327 methods, 33,961 properties)

  Struct = FString TypeName, FString UnrealPath, TArray<Property>
  Class  = FString TypeName, FString UnrealPath, TArray<Method>, TArray<Property>

  Property = FString Declaration, FString UnrealName,
             bool bCanWrite, bCanRead, bCanEdit, bGeneratedGetter, bGeneratedSetter,
             FString GeneratedName, bool bGeneratedHandle, bGeneratedUnresolvedObject

  Method   = FString Declaration, FString UnrealName,
             bool bStaticInUnreal, bStaticInScript, bGlobalScope,
                  bNotAngelscriptProperty, bTrivial,
             int8 WorldContextArgument, int8 DeterminesOutputTypeArgument,
             FString ClassName, FString ScriptName

Binds.Cache.Headers:
  TArray<(FString /Script/Mod.Class, FString C++ header path)>     14,184 entries
```

This is what supplies `ALokiDropShip : ALokiDropPlane` →
`/Script/Loki.LokiDropPlane` → `../../../Loki/Source/Loki/DropPhase/LokiDropPlane.h`,
and the `UnrealName` aliases (script `GetActorLocation` ↔ UFunction
`K2_GetActorLocation`).

It also carries the **struct vs class** distinction, which the decoder needs: a bound
`UStruct` is a value type (returns on the stack), a bound `UCLASS` is a reference type
(handle only).

### Optional: `mappings.usmap` for enum member names

Not part of the game's script data, but the project generates one
(`tools/usmapdump`) and it is the only place C++ `UENUM` members exist. Version 0,
uncompressed:

```
u16 magic = 0x30C4 | u8 version | u8 compression | u32 csize | u32 dsize
u32 nameCount   ; nameCount * (u8 len, len bytes)
u32 enumCount   ; enumCount * (u32 nameIdx, u8 numValues, numValues * u32 nameIdx)
u32 structCount ; ...                                (not needed for enums)
```

Ours holds 52,324 names and **2,226 enums**. This turns `if (v31 != 1)` into
`if (v31 != ELokiAssetLookupExecPins::LookupFailed)`.

⚠ usmap v0 stores members **positionally**, with no explicit values, so index→value is
only right for enums that do not override values (`A = 3`). The disassembly appendix
always keeps the raw integer, so any name is checkable.

---

## 5. What is still UNKNOWN

Honest list. Nothing below blocks decompilation; all of it is cosmetic or marginal.

1. **`FunctionTraits` bits 5, 13, 18.** Bit 5 is set on 1,451 of 1,463 functions, bit 18
   on 387, bit 13 on 38 (all constructors). Too broad to be stock FINAL/OVERRIDE/SHARED.
   Printed raw as `traits=0x…`.
2. **Class `Flags` (int32)** and **`BehaviorFunctionTypes` (int32 each)** are read and
   round-trip correctly but their bit/enum meanings were not decoded.
3. **`CodeHash` (int64 per module)** — presumably a source hash for staleness checks;
   algorithm not identified.
4. **`ShadowType` / `DerivedFrom` (int64)** — pointer-valued, resolve through
   `TypeReferences`, but the precise semantic difference between them was not pinned.
5. **`PropertyReferences[].OldTypeId`** — read, never needed; meaning unconfirmed.
6. **`ByteCodeReferences`** is declared in the struct but never written by `InitFrom()`.
   It is empty in all 1,463 functions. A non-empty one means the field order is wrong,
   not that the data is exotic — the parser asserts this.
7. **Value-type constructor stack accounting** — the 14 functions in §3 that do not
   balance. Almost certainly the list-factory / copy-construct behaviours.
8. **Exact fork revision.** Bracketed, not pinned (§0).
9. **`JMPP` computed jumps** decode fine and their switch tables are recovered, but the
   general lowering was not fully characterised; 5 sites in this corpus remain as
   labelled `goto`s.

## 6. What is NOT in these files at all

Do not go looking; it was never serialised.

- **Local variable names.** `VariableInfo*` arrays are empty in shipping.
- **Line numbers / source mapping.** `DeclaredAt == 0`, `LineNumbers == []`.
- **Comments, original formatting, expression nesting.** Bytecode order is all there is.
- **C++ `UENUM` members.** Only the 4 script-declared enums carry names. Everything else
  needs the usmap (§4).
- **The `.as` source itself.** Only the relative path per module.
