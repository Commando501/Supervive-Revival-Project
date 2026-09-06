# asdump (impl_b) — SUPERVIVE Angelscript decompiler

Decompiles the game's Angelscript gameplay layer out of the three plaintext caches
that ship in `Loki/Script/`. Stdlib-only Python 3. Reads the game install `'rb'`
only; never writes inside it.

```
python asdump.py                        # -> ../out/b/**.as.txt + _index.md
python asdump.py --validate             # self-check + census, writes nothing
python asdump.py --no-asm               # omit the disassembly appendix (easier reading)
python asdump.py --module LokiDropShip  # one module
python asdump.py --no-binds             # skip Binds.Cache (loses UFunction aliases)
```

## Files

| file | role |
|---|---|
| `asdump.py` | CLI, self-validation, declaration rendering, output |
| `ascache.py` | `PrecompiledScript.Cache` reader (declarations + bytecode + symbol trailer) |
| `asbinds.py` | `Binds.Cache` / `.Headers` reader (AS type ⇄ `/Script/Mod.Class` ⇄ C++ header) |
| `aslift.py` | bytecode decode → symbolic lift → structured pseudo-source |
| `opcode_table.py` | **generated** opcode table |
| `gen_opcodes.py` | regenerates `opcode_table.py` from the game binary |

## Measured results on the 2025-12-17 build

```
PrecompiledScript.Cache   1,184,817 / 1,184,817 bytes parsed, 0 unaccounted
Binds.Cache               5,764,301 / 5,764,301 bytes parsed, 0 unaccounted
Binds.Cache.Headers       2,050,287 / 2,050,287 bytes parsed, 0 unaccounted
78 modules · 110 classes · 600 properties · 1,463 functions
bytecode                  1,463 / 1,463 streams decode exactly (36,293 instructions,
                          105 distinct opcodes, RET count == function count)
symbol resolution         type pointers      4,283 / 4,283   100%
                          factory/behaviour    440 /   440   100%
                          call + global ptrs 5,970 / 5,970   100%
                          script-call ids      862 /   862   100%
                          member accesses    3,530 / 3,530   100%
lifting                   1,463 / 1,463 bodies structured, 0 unmodelled opcodes,
                          19 residual `goto` lines, 5 `<?>` stack markers
```

## What is EXACT vs what is RECONSTRUCTED

**Exact** — stored verbatim in the cache, not inferred: module names, `.as` source
paths, class names and bases, every property with its type and full UPROPERTY
metadata (including `Replicated` / `ReplicationCondition` / `RepNotify`), every
function name, return type, parameter types **and names**, default-argument source
text, UFUNCTION flags and metadata (including the `UnrealName` alias), enums, module
imports/events/delegates, and the bytecode itself.

**Reconstructed** — decompiled, best effort: function bodies.

**Absent from a SHIPPING cache and therefore unrecoverable**: local variable names
and line numbers. `InitFrom()` guards `DeclaredAt` and `LineNumbers` with
`#if !UE_BUILD_SHIPPING`, and `BuildIdentifier == 4` (SHIPPING), so all 1,463
functions carry `DeclaredAt == 0` and an empty `LineNumbers`. Locals render as `vN`
(the AngelScript stack-frame slot offset) and there is no source-line mapping.

## Facts established from the bytes in this session

Everything below was measured against the real files or the game binary, not
assumed from upstream AngelScript.

* **Opcode table** is read out of the game's own `asBCInfo[256]` at RVA `0x084A22C0`
  in `dumps/merged.dump.exe`, with `asBCTypeSize[]` at `0x084B45A0` (cross-checked
  against an identical second copy at `0x084EA4A0`). 213 decodable opcodes (0..212).
* **Operand layouts** are *derived* from the `asEBCType` names using AngelScript's
  positional accessor rule (SWORDARG0/1/2 at +2/+4/+6; INT/QWORD args on the next
  free dword boundary). That derivation independently reproduces **all 22 entries**
  of the binary's own size table — which is what pins the fork-added type 21
  (`asBCTYPE_W_rW_ARG`, used by `GETOBJ`/`GETOBJREF`/`GETREF`) that a prior pass had
  flagged as unverified.
* **`asBC_MAXBYTECODE` in the fork's header reads 212**, but slot 212
  (`ThrowException`) is a fully populated real entry — the fork appended an opcode
  without bumping the constant. The table is trusted over the constant.
* **eTokenType ordinals** verified against `Binds.Cache` declaration strings by
  matching `FunctionReference`s to their binds and aligning parameter positions:
  `65=bool 68=int 76=uint8 80=float32 81=float64 82=void`. This fork's
  `as_tokendef.h` has *both* `ttFloat`(79) and `ttFloat32`(80)/`ttFloat64`(81);
  only 80/81 occur.
* **`FunctionTraits` bit 2 == `asTRAIT_CONST`**, verified 401/401 against the
  independent `FunctionReference.is_const` field. Bit 0 occurs only on constructors
  (130/130), bit 1 only on behaviours (68/68), bits 3/4 only on methods
  (private/protected). Bits 5/13/18 are set far too broadly to be stock
  FINAL/OVERRIDE/SHARED, so they are printed raw (`// traits=0x...`) rather than
  guessed at.
* **`PropertyReferences` composite key** `((TypeId << 1) | (Offset << 33) | 1)`
  confirmed: 3,530 / 3,530 member accesses resolve to a property name, including
  `LoadRObjR`/`LoadVObjR` (whose offset is `SWORDARG1`, not `SWORDARG0`).
* **`MethodTable` is NOT a list of function ids** (a prior spec said it was, and it
  resolves at only 56/1040 that way). It is the virtual dispatch table: an index
  into the class's own `Methods` array per virtual slot, or `-1`. 100 of 110 classes
  have the degenerate `[0..N-1]`; the exceptions (e.g.
  `UBarracudaTowerTargetingComponent` = `[-1,-1,-1,0,-1,-1,-1,1]`) are what make the
  meaning unambiguous.
* **Parameter slot assignment**: `this` (methods) at variable offset 0, parameters
  marching negative with `off[i] = off[i-1] - width(param[i-1])`. Verified on
  `ALokiAirship_AS::Spawn` — 5 params land on 0,-2,-4,-6,-7 for widths 2,2,2,1,2,
  exactly the offsets its bytecode references. This is what lets the disassembly and
  the pseudo-source print **real parameter names** instead of slot numbers.
* **Calling convention**, read off the bytes rather than assumed:
  arguments are pushed last-parameter-first, then the by-value return pointer (if
  any), then the object pointer — so at the call the stack reads
  `top -> [this] [retptr] [param0] [param1] ...`.
  Evidence: `PSF v18 ; PSF v8 ; CALLSYS TArray::Iterator` ⇒ `v18 = v8.Iterator()`,
  and `PshV4 TeamIndex ; PshGPtr __WorldContext ; PSF v8 ; CALLSYS
  GetPlayerStatesOnTeam` ⇒ `v8 = GetPlayerStatesOnTeam(__WorldContext, TeamIndex)`.
* **Enums do not return on the stack.** `asCScriptFunction::DoesReturnOnStack()`
  requires `asOBJ_VALUE`; an enum has type info but is `asOBJ_ENUM`. Treating enum
  returns as by-value struct returns silently eats one argument and shifts the whole
  call — fixing it cut stack-underflow markers from 23 to 5.
* **`__STATIC_NAME(n)`** indexes the cache's own `StaticNames` pool, so FName
  literals recover: `System::SetTimer(this, n"UpdateLocalState", ...)`.
* String literals are `GlobalReferences` entries with `bIsString`; gameplay tags and
  `__StaticType_*` class pointers resolve through the same table.

## Known limitations (read before trusting a body)

1. **Locals are `vN`, not names.** Unavoidable — see above.
2. **No line numbers**, so no mapping back to the original `.as`.
3. **19 residual `goto` lines** across the corpus, all inside computed `switch`
   jump tables. Cases are emitted as `case N: goto Lxxxx;` with real labels; the
   case bodies follow. Correct, just not fully nested.
4. **5 `<?>` markers** where a value is pushed on one control-flow path and consumed
   after a join. The lifter carries the symbolic stack only across an unambiguous
   fallthrough (single predecessor, immediately preceding block); a real fix needs
   SSA/phi. `<?>` is deliberately visible rather than silently wrong.
5. **Expression temporaries are not folded.** The output is close to three-address
   form (`v12 = a; v14 = b; v12 = v12 - v14;`) because AngelScript's own bytecode is.
   No copy propagation pass is applied — it would read better but would risk
   misordering side effects.
6. **`traits=0x...` comments** appear wherever bits outside the five verified ones
   are set. That is honesty, not noise.
7. **Empty `if` bodies are real.** e.g. `ALokiDropShip::GetTeamDropLeader`'s second
   loop genuinely compiles to `JLowZ 0` (a jump to the next instruction) and `JMP 0`
   — degenerate code in the shipped build, not a decompiler artefact. Check the
   disassembly appendix when a body looks too empty.
8. The **`--no-binds`** path loses the Binds-backed struct/class classification used
   by `returns_on_stack`, which then falls back to a naming heuristic
   (`E<Upper>...` ⇒ enum). Prefer running with binds.

## Regenerating the opcode table

`opcode_table.py` is checked in so the tool runs without the dump. To rebuild it
after a game update:

```
python gen_opcodes.py     # needs dumps/merged.dump.exe at the recorded ImageBase
```

It asserts that the two `asBCTypeSize` copies agree and that the name-derived
operand layouts reproduce that table exactly, so a silent format change fails loudly.
