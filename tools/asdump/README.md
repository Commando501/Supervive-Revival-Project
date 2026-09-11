# asdump — SUPERVIVE Angelscript decompiler

SUPERVIVE runs on a forked UE5.4 that embeds **UE-Angelscript** (Hazelight's plugin), and
a large slice of its gameplay logic is Angelscript rather than C++ or Blueprint. The
shipping build ships that whole layer as three plaintext caches. `asdump.py` reads them
and reconstructs **78 `.as` source files**: exact declarations plus decompiled function
bodies, each with a fully symbol-resolved disassembly appendix.

This includes the modules the revival project actually needs — the drop-in sequence
(`GameMode/DropPhase/*`), an FFA bot-deathmatch mode (`FFA/*`), and a complete
28-module MOBA mode nobody knew existed (`Barracuda/*`, with lane/jungle creeps, towers,
minion waypoints and an item-tree shop).

## Run it

```bash
cd "G:/git/Supervive Revival Project/tools/asdump"
python asdump.py                      # everything -> out/modules/ + out/_index.md
python asdump.py --validate           # self-check + census only, writes nothing
python asdump.py --module DropShip    # only modules matching a substring
python asdump.py --no-asm             # skip the disassembly appendix (smaller files)
python asdump.py --no-usmap           # don't name enum members
python asdump.py --script-dir DIR --out DIR
```

Stdlib-only, single file, Python 3. Takes ~0.8 s for the full corpus. Output is
byte-identical across runs.

Reads (all `'rb'`, never written):

```
<install>/Loki/Script/PrecompiledScript.Cache     declarations + bytecode
<install>/Loki/Script/Binds.Cache                 engine<->script bind table
<install>/Loki/Script/Binds.Cache.Headers         /Script/Mod.Class -> C++ header
```

Optionally picks up a `mappings.usmap` from the project tree (see *Enum names* below).
Everything works without it.

## What you get

`out/_index.md` — per-module table (source path, classes, function count, bytecode size)
plus the totals below. `out/modules/<Dir>/<Name>.as.txt` — one file per module, laid out
like real Angelscript source: globals, then each class with its properties and methods
nested inside it.

```
UCLASS(SuperIsCodeClass, Placeable)
class ALokiDropShip : ALokiDropPlane
// unreal base : /Script/Loki.LokiDropPlane
// C++ header  : ../../../Loki/Source/Loki/DropPhase/LokiDropPlane.h
{
    UPROPERTY(BlueprintReadable, BlueprintWritable, EditableOnDefaults)
    protected TSubclassOf<ALokiDropPod@> TeamDropPodClass;

    UFUNCTION(BlueprintCallable, CanOverrideEvent)
    protected bool SpawnDropPodForTeam(const int TeamIndex, const FVector& SpawnLocation,
                                       const FVector& LandingLocation)
    { ... }
    /* ---- SpawnDropPodForTeam: 150 dwords / 95 instructions (cache offset 0x94169) ----
        0000  PSF           v2
        ...
    */
}
```

**Declarations are exact — read straight out of the cache, not inferred.** Class names
and bases, every property with its type and full `UPROPERTY` metadata (including
`Replicated` / `ReplicationCondition` / `RepNotify`), every function name, return type,
parameter types **and names**, default-argument source text, and `UFUNCTION` flags with
the `UnrealName` alias. That alone is a complete header dump of the gameplay layer and
needs no bytecode at all.

**Bodies are decompiled** — named calls, named members, string/`FName` literals,
`if`/`else`/`while`, `break`/`continue`, `switch`, typed local declarations, real
`return` values.

## Validation numbers (real output of `--validate`, this build)

```
PrecompiledScript.Cache   1,184,817 / 1,184,817 bytes parsed   UNACCOUNTED 0  (100.0000%)
Binds.Cache               5,764,301 / 5,764,301 bytes parsed   UNACCOUNTED 0
Binds.Cache.Headers       2,050,287 / 2,050,287 bytes parsed   UNACCOUNTED 0

modules 78 (asserted) · classes 110 · properties 600 · functions 1,463

bytecode   decoded exactly            1,463 / 1,463   100.00%
           structured to pseudo-code  1,463 / 1,463   100.00%
           36,293 instructions, 105 distinct opcodes, RET count == function count
           unmodelled opcodes: NONE

symbols    type pointers              4,283 / 4,283   100%
           factory/behaviour ids        440 /   440   100%
           call + global ptr operands 5,970 / 5,970   100%
           script-call id operands      862 /   862   100%
           member accesses            3,530 / 3,530   100%   -> real property NAMES

convention independent dword-depth audit vs the game's own asBCInfo.stackInc table:
           balanced at RET            1,458 / 1,463    99.66%

output     16,643 pseudo-source lines · 38,813 disassembly lines
           4,023 local declarations, 2,877 typed (71.5%), 1,146 `auto`
           99 enum members named from mappings.usmap
           residual: 19 goto lines in 5 functions · 5 `<?>` markers · 0 dropped calls
```

Three of these are genuinely *independent* checks rather than self-consistency:

1. **Byte accounting.** There is no magic, chunk table or offset table anywhere, so
   landing exactly on EOF with zero gaps and zero overlap is only possible if every
   field's order and width is right.
2. **The dword-depth audit** is driven by the game binary's own `stackInc` table and
   shares no code with the lifter's symbolic stack. Agreement corroborates the calling
   convention; disagreement would mean the argument model is wrong.
3. **Call-preservation.** Every call target recovered from the raw bytecode was checked
   for presence in the corresponding pseudo-source: **0 of 3,286 missing**. A decompiler
   that silently drops a call is the dangerous failure mode, so this is measured rather
   than assumed.

**Fail-loud.** The parser raises with a byte offset on the first desynchronised byte and
never resynchronises. Verified by corrupting a *copy* of the cache: flipping a bool
canary, an array count or a string length each aborts with an offset and a context
hexdump. The game files are opened `'rb'` and are untouched (mtimes still 2025-12-17).

## Limitations

Honest list. The first two are permanent.

- **No local variable names, ever.** The shipping cache has `DeclaredAt == 0` and empty
  `LineNumbers` / `VariableInfo` for all 1,463 functions — the plugin guards them with
  `#if !UE_BUILD_SHIPPING`. Locals render as `vN`, where N is the stack slot. **No line
  numbers** either, so there is no source mapping.
- **No expression folding.** Output is close to three-address form
  (`v12 = a; v14 = b; v12 = v12 - v14;`) because the bytecode is. Readable but verbose.
  Copy propagation would fix it; it was skipped rather than risk reordering side effects.
- **19 `goto` lines across 5 functions**, all inside computed (`JMPP`) switch tables.
  Correct, with real labels and bodies, just not fully nested.
- **5 `<?>` markers** where a value crosses a control-flow join. The lifter only carries
  the symbolic stack across unambiguous fallthroughs; closing these needs SSA/phi.
- **2 of 31 multi-return functions** emit fewer distinct `return` expressions than the
  bytecode has paths. Read their disassembly.
- **Empty `if` bodies are usually real.** Degenerate compiled code (`JLowZ 0`, `JMP 0`)
  occurs in the actual game — e.g. the second loop of `ALokiDropShip::GetTeamDropLeader`
  calls `IsSpectator()` and `IsSpawnTeamLeader()` and discards both results. Verify
  against the appendix before assuming it is an artifact.
- **Statement order is bytecode order**, not source order.

### Fixes applied after the initial merge (2026-07-26, core-gameplay pass)

All three were found by reading the output against its own disassembly appendix, and all
three leave every validation number unchanged (100% parse / decode / symbol resolution,
same 1,449/1,463 depth balance, same 5 `<?>` markers) with **0 of 7,491 named callees
dropped** from the pseudo-source afterwards.

1. **`REFCPY` printed every handle assignment backwards.** `asBC_REFCPY` is `*dst = src`
   with the **destination on TOP of the stack** (`d = *l_sp; l_sp += AS_PTR_SIZE;
   s = *l_sp;`), emitted as `PshVPtr <src> ; PshVPtr this ; ADDSi .<member> ; REFCPY ;
   PopPtr`. The lifter read the first pop as the right-hand side, so
   `ALokiAimingLaser::UpdateOwner` — whose entire body assigns `OwnerHero` — rendered as
   `HeroOwner = this.OwnerHero;`, and other sites produced the impossible `nullptr = x;`
   and `this = x;`. **116 assignments corpus-wide** were inverted, including every
   `Owner*` / `*Instance` / `*MID` cache-back. Now `this.OwnerHero = HeroOwner;`.
2. **64/32-bit float immediates printed as raw integers.** `SetV8`/`PshC8` carry a bare
   64-bit immediate that is an int64 *or* a double, and the corpus is overwhelmingly
   doubles: `this.CameraPickupRadius = 13830554455654793216` is `-1.0`. The two are
   separable by exponent (a bit pattern only decodes to a normal double once the raw u64
   exceeds ~1.2e17, far above any int64 literal here) — measured over all 77 distinct
   64-bit immediates: 76 clean game numbers, 1 zero, 0 misclassified. Same for `SetV4`/
   `PshC4` above 1e6, where all 28 large immediates in the corpus are clean float32s
   (`1106247680` → `30.0`). ~270 constants across the corpus became readable.
3. **`LoadThisR` / `LoadRObjR` / `LoadVObjR` / `LDV` / `LDG` did not model the value
   register.** All five write the *address* of their operand into the VM's value
   register, which is exactly what `asBC_PshRPtr` then pushes; the lifter recorded it
   only in a private `refreg` and left a stale `pending` / `valreg` behind, so any member
   passed **by reference** printed as whatever the previous statement left lying around —
   `Math::Lerp(this.RangeMax, this.RangeMin, t)` in `ALokiAimingLaserSpreadLines_HookGuy`
   rendered as `Math::Lerp(v5, v5, v4)`, and one site printed a leftover FName literal as
   a float argument. Fixed by having the load flush `pending` (never discard it — that
   would drop `this.DoLaserTrace();` from `ALokiAimingLaser::Tick`) and set the value
   register. 24 call sites corrected, plus **2 functions that were returning nothing now
   return their real value** (`return this.RespawnType;`, `return
   this.InteractionCooldownStartTime;`).

### Fixes applied in the final synthesis pass (2026-07-26)

Two further defects, found during the long-tail subsystem pass and written up in
`PATCH-lifter-fixes.md`, are now **merged into `asdump.py`** and the whole `out/` corpus was
regenerated from the merged tool.

4. **`COPY` printed its assignment backwards** — same defect as `REFCPY` (fix 1 above), same
   cause: `asBC_COPY`'s destination is the pointer pushed **last**. 235 statements across 42
   of the 78 modules were inverted; the tell-tale `nullptr = <expr>;` appeared 32 times in
   `out/modules/` and is now **0**. Ground truth is `FLokiUsableData`'s default constructor
   (`PshNull ; PshVPtr this ; ADDSi .Actor ; REFCPY`) and
   `ULokiInteractionPlayerComponent::ProcessInteractionSelection`.
5. **Script-declared value types were not treated as returning on the stack.** 34 of the 110
   script types are AngelScript `asOBJ_VALUE` (every `F…` struct and every script delegate) —
   discriminated from the cache's own `BehaviorRefs` as *construct set, factory unset*. A
   value-type return takes the hidden return pointer, so every declared parameter shifted one
   slot. `ExecuteUAV` rendered `v68.Config = SourceLocation; v68.TeamIndex = arg_m8;` and now
   renders `v68.Config = Config; v68.TeamIndex = TeamIndex; v68.SourceLocation = SourceLocation;`.
   **The independent dword-depth audit rose 99.04% → 99.66%** on this fix alone, which is the
   corroboration that matters: that audit shares no code with the lifter.

**Still open (not a lifter bug):** the control-flow structurer can place a *shared join block*
inside an `else` arm when two conditional jumps target the same label, which silently inverts
the apparent meaning of a guard. Confirmed in `ALokiGem::OnComponentBeginOverlap`. The risk
shape (a label reached by ≥2 conditional jumps that is not the final instruction) occurs in
**46 of 1,463 functions**; that list is the audit set and is enumerated in
`PATCH-lifter-fixes.md`. Until it is fixed, treat the disassembly appendix as ground truth for
any guard whose polarity is load-bearing.

### The thing most likely to be wrong

Not the parser — that has 100% byte accounting, 100% decode and 100% symbol resolution,
each independently re-derived. It is the **stack-machine argument accounting** inside
`_do_call`. A wrong-but-plausible argument list would not announce itself. The `<?>`
markers and the 14 unbalanced functions in the depth audit are the visible tail of it.
**If a specific function matters, read its disassembly appendix** — every operand there
is named, and it is ground truth.

## Enum names (optional usmap)

Neither cache carries the members of a C++ `UENUM`, so on their own enum comparisons can
only decompile to `int(v25) == 1`. Unreal's `.usmap` does carry them, and this project
already generates one, so `asdump.py` auto-detects `mappings.usmap` in the project tree
and uses it:

```
if (v31 != ELokiAssetLookupExecPins::LookupFailed) { ... }
v34 = ESpawnActorCollisionHandlingMethod::Undefined;
v1 = v4 == ELokiCrewPodDetachState::DetachInputStarted;
```

⚠ usmap v0 stores members **positionally** with no explicit values, so index→value is
only right for enums that do not override values (`A = 3`). The disassembly appendix
always keeps the raw integer, so every name is checkable. `--no-usmap` turns it off. The
4 *script-declared* enums carry explicit values in the cache itself and are exact.

## Provenance

The opcode table is **not** copied from upstream AngelScript — the fork differs. It is
extracted byte-exact from the game binary's own `asBCInfo[256]` (RVA `0x084A22C0`) and
`asBCTypeSize[22]` (RVA `0x084B45A0`) in `dumps/merged.dump.exe`, and re-verified against
that binary as part of this merge (0 mismatches across all 213 real opcodes on name, type
and stackInc). Operand layouts are derived from the `asEBCType` names and independently
reproduce all 22 entries of the binary's own size table.

Full format documentation, including what remains unknown, is in **`FORMAT.md`**.

## Layout

```
asdump.py     the tool — single file, stdlib only, standalone
FORMAT.md     definitive format spec for all three caches (+ the usmap enum table)
README.md     this file
out/_index.md per-module index
out/modules/  78 reconstructed .as.txt files
impl_a/       first independent implementation (superseded; see below)
impl_b/       second independent implementation (this tool's base)
```

`asdump.py` is a merge of two independently built implementations. `impl_b` is the base:
its bodies are materially more correct — it renders 29 of 31 multi-return functions
right where `impl_a` renders 1, and emits 19 `goto`s where `impl_a` emits 236. Grafted
from `impl_a`: typed local declarations, template subtypes on constructed types, the full
callee signature in the disassembly, and the independent dword-depth audit. Fixed in the
merge, wrong in **both** sources: enum parameters were sized as 2 dwords instead of 1
(which mis-attributed parameter names in 10 functions, 7 of them in `LokiDropPod.as`),
and enum-typed arguments printed as `true`/`false`. `impl_a` additionally used
`FunctionTraits` bit 0 for `const`, which is `asTRAIT_CONSTRUCTOR`. The two are kept for
cross-checking; neither is needed to run the tool.
