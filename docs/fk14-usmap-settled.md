# FK-14 SETTLED — the usmap is deterministic; its container types are ~70 % wrong from a fixed offset bug

**Session S116, 2026-08-12/13. Four parallel agents. Entirely offline + read-only RPM; zero launches
spent, the user's running game (pid 50016) never disturbed, no repo artifact modified.**

> **Read this before touching anything usmap-, extractor-, schema.txt-, or asset-dump-shaped.**
> It supersedes `docs/ignorance-map-s101.md` §FK-14, corrects two clauses of
> `docs/fk1-angelscript-settled.md` §6, and re-scopes the rule at `CLAUDE.md` ("Don't trust the
> extracted usmap for replicated container types").

---

## 0. The one-paragraph version

FK-14 believed the usmap extractor was **non-deterministic**, because two schema dumps of the same
unchanged exe a week apart disagreed on **326 property types**. The 326 is real and reproducible.
The diagnosis was wrong. **The tool is deterministic** — three back-to-back extractions from one live
process are **byte-identical** [M]. The disagreements come from a **fixed offset bug**:
`extract.go:115` reads a container's inner property **inline at `FField+0x80`**, which is past the end
of the object, so it captures **whatever FField the heap allocator placed next**. Adjacency is frozen
within a process instance and differs across launches — which is exactly why 3/3 runs matched and two
sessions disagreed. Correct offset is **`*(FField+0x78)`, as a pointer** [M, 96.6 % vs 3.4 % vs 0.1 %].
The variance was never the interesting part: **~70 % of container inner types are wrong in every
usmap this project has ever produced**, deterministically, and a *second* writer defect drops **100 %
of enum properties** and renumbers **7,713** schema indices.

**Net: FK-14's headline is refuted, its mitigation was mis-scoped in both directions, and the damage
is both larger and far more sharply bounded than anyone thought.**

---

## 1. Determinism — REFUTED as a property of the tool [M]

Three `extract` runs against pid 50016, back-to-back (23:43:22 → 23:49:53), each to its own directory:

| artifact | run1 | run2 | run3 |
|---|---|---|---|
| `mappings.usmap` | `2d56482bd615b40d288095c4e894e1fe` | *identical* | *identical* |
| `schema.txt` | `72ac41b6460380586c8ada2b1a713ed3` | *identical* | *identical* |

**Byte-identical, all three.** 5,324 UClass / 6,060 UScriptStruct / 2,226 UEnum / 44,398 properties.

**Positive controls** (so the null is interpretable — this project has 31 recorded instances of an
uncontrolled null being recorded as a fact):
- the same `md5sum` separates all four historical usmaps, separates the fresh output from all of them,
  and separated run4 — the instrument discriminates;
- each run writes the usmap **twice** from one in-memory model and both copies matched, so a
  constant-output bug would have been invisible. It isn't.

**Run 4, 13 minutes later, DIFFERS** (`44b3ede4…`, +49 B). Schema-level diff run1↔run4: struct name
sets identical, enum sets identical, **0 type disagreements**, 41,441 properties identical. The entire
delta is **one extra record named `AnimBlueprintGeneratedConstantData`** (29 → 30).

**Independent source audit**, run regardless of the empirical result: the one genuine nondeterminism
source is `vtscan.go:221` (`for v, c := range counts`, randomised Go map iteration) feeding a
**non-stable** `sort.Slice` at `vtscan.go:226` that compares only `count`, so ties are arbitrary. It is
neutralised downstream — emitted order comes from `instMap[vt]` slices built in **address order** by
`collectAllInstancesByVtable` (`vtscan.go:178-183`), and the metaclass/vtable searches
(`pipeline.go:76-83`, `:101-121`) have unique answers. **Map order never reaches the output.** Audit
and measurement agree.

---

## 2. Why four usmaps have four sizes — SOLVED, and it is not coverage [M]

Every extraction ever taken carries **exactly 11,344 unique struct names and 2,226 enums**, with
**identical enum value tables** and identical name sets. Union of `(struct, prop)` pairs across five
extractions = 41,455; intersection = 41,427 — only **28** pairs missing from any one.

The whole size spread is **duplicate records of two names** — `AnimBlueprintGeneratedConstantData` and
`AnimBlueprintGeneratedMutableData`, one generated UScriptStruct **per loaded Anim Blueprint**, all
sharing a name:

| usmap | md5 | records | unique names | dup records | bytes |
|---|---|---:|---:|---:|---:|
| `mappings.usmap` (root) | `f9e32271` | 11,347 | 11,344 | 3 | 1,858,496 |
| worktree (`f5908e6` blob) | `d72c22e9` | 11,361 | 11,344 | 17 | 1,864,442 |
| **fresh, this session** | `2d56482b` | 11,384 | 11,344 | 40 | 1,870,775 |
| `tools/usmapdump/` | `9f1b8e55` | 11,387 | 11,344 | 43 | 1,870,780 |
| **`tools/extractor/` — CANONICAL** | **`3892b937`** | 11,428 | 11,344 | **84** | 1,876,427 |

Causally confirmed by run1→run4: **+1 record of that exact name, +49 bytes, 0 type changes.**

⇒ **Size tracks anim-BP residency, not coverage, not tool version, not randomness.**

> ⚠ **Latent hazard, previously unrecorded.** The usmap format is **name-keyed**, so CUE4Parse keeps
> exactly ONE of the canonical file's **84** `AnimBlueprintGenerated*Data` records — **the last
> written**. More records is a **risk, not a benefit.** The fix must de-duplicate deliberately (keep
> the richest), not incidentally.
>
> ⚠⚠ **DO NOT HARDEN THE PARTICULAR NUMBERS HERE INTO A CANARY.** An earlier draft said the kept
> record *"has 0 properties, while siblings carry up to 259."* **That does not reproduce** — in the
> live state measured later the last-written record holds **49** and the richest **263**. The 0/259
> pair was a true observation of one process instance and is **anim-BP-residency-dependent**, exactly
> like the record counts in the table above. The **hazard** is real and general; the **numbers** are
> per-instance.
> ⚠ Likewise **84 is the canonical file's DUPLICATE COUNT, not the number of lossy collapses** — in the
> measured run 11,385 → 11,344 collapses 41 records of which only **2** are lossy under either rule.

---

## 3. The root cause — a fixed offset bug, and the offset that settled it

### 3.1 What the tool does

`extract.go:115` `const offFFieldEmbeddedInner = 0x80`, applied by `tryEmbedded`
(`extract.go:158-186`) to Array / Set / Map / Optional / Enum: it treats `outerFField + 0x80` as an
**inline FField**. `sizeof(FArrayProperty)` is `0x80`, so that address is **one byte past the end of
the object** — it reads the next FField in the heap.

`extract.go:164`'s owner guard cannot catch this, for two independent reasons [M]:
- it is **inert at depth 0** — `walkProperties` (`extract.go:195`) always passes `ownerHint = 0`, so
  `ownerHint != 0` is never true for any top-level property;
- it is **self-confirming** — a neighbouring property of the same UStruct has the same Owner.

The only surviving filter is a 33-entry `knownPropTypes` name whitelist, which a bare *type* check
passes **83.1 %** of the time. **That is the false-positive engine that makes the output look
plausible.**

### 3.2 The offset — measured live, with a control [M]

Probe over **4,247 container FProperties** in pid 50016, three discriminators applied
**simultaneously** (target's `ClassPrivate` names a known property type; target's `Owner` == the
container itself; target's `Name` == the container's name):

| candidate | passes all three |
|---|---:|
| **`*(outer+0x78)` — as a POINTER** | **4,103 / 4,247 = 96.6 %** |
| `*(outer+0x70)` | 144 = **3.4 %** |
| **inline at `outer+0x80` — what the tool does today** | 5 = **0.1 %** |
| +0x60 / +0x68 / +0x88 / +0x90 / +0x98 / +0xA0 | **0.0 %** |

**Positive control:** Struct / Object / Class inner via pointer `@+0x70` = **13,360 / 13,360 =
100.0 %.** The probe validates `+0x70` perfectly where `+0x70` is right, so it is not biased toward
`+0x78`.

**Offline corroboration, no RPM:** in the fresh `schema.txt` the reported inner equals the type of the
**next property in the same struct** 1,194 / 3,389 = **35.2 %**, against a previous-property control
of **6.7 %** and a random-other-property chance control of **8.4 %**.

**Semantic corroboration** — reading `*(+0x78)` yields four independently-known-correct stock UE 5.4
answers:

| property | tool today (inline `+0x80`) | corrected `*(+0x78)` |
|---|---|---|
| `GameMode.InactivePlayerArray` | `FloatProperty` | `ObjectProperty UClass:PlayerState` ✔ |
| `AbilitySystemComponent.SpawnedAttributes` | `NameProperty` | `ObjectProperty UClass:AttributeSet` ✔ |
| `AIPerceptionSystem.Senses` | `FloatProperty` | `ObjectProperty UClass:AISense` ✔ |
| `LokiHeroCharacter.RelevantEquipmentAttributes` | `StrProperty` | `StructProperty UStruct:GameplayAttribute` ✔ |

### 3.2b ★★ CORRECTION — the five container families do NOT share one offset [M]

**The 96.6 % above is correct as an aggregate and was OVER-GENERALISED into a uniform rule.** A
per-family probe (two independent full passes over 44,398 top-level FProperties, agreeing **to the
digit**) decomposes it exactly. **Every winner is 100 % with a 0 % runner-up:**

| family | member | **offset** | score | runner-up |
|---|---|---|---|---|
| `FArrayProperty` | `Inner` | **`*(f+0x78)`** | 3,548/3,548 = 100 % | `+0x70`: **0/3,548** |
| `FSetProperty` | `ElementProp` | **`*(f+0x70)`** | 142/142 = 100 % | `+0x78`: **0/142** |
| `FOptionalProperty` | `ValueProperty` | **`*(f+0x70)`** | 2/2 | `+0x78`: 0/2 |
| `FMapProperty` | `KeyProp` | **`*(f+0x70)`** | 555/555 = 100 % (549 named `<outer>_Key`) | |
| `FMapProperty` | `ValueProp` | **`*(f+0x78)`** | 555/555 = 100 % | `+0x80`: **0/555 — REFUTED** |
| `FEnumProperty` | `UnderlyingProp` | **`*(f+0x70)`** | 1,840/1,840 = 100 % | `+0x78`: **0/1,840** |
| `FEnumProperty` | `Enum` | **`*(f+0x78)`** | 1,840/1,840 = 100 % | `+0x80`: **0/1,840** |

**The decomposition of §3.2's numbers, exactly:** the 4,103 hits at `+0x78` = Array 3,548 + Map
**Value** 555. The 699 at `+0x70` = Set 142 + Optional 2 + Map **Key** 555. The 144 that passed the
name-equality gate = Set 142 + Optional 2 — a map key is named `<X>_Key`, so it fails name-equality
**by construction**. ⇒ *"containers sit at `+0x78`"* holds for **1 of 5 families**.

Same-pass controls: `StructProperty *(f+0x70)`→`UStruct:` 9,119/9,119 · `ObjectProperty`→`UClass:`
3,655/3,655 · `ClassProperty` 586/586 · `ByteProperty`→`UEnum:` 735/887 = **82.86 %** (reproduces the
published 82.9 %) · **negative control** `Bool/Int/Float` → any UObject **0/16,332**.

> ⚠⚠ **THE SILENT FAILURE THIS AVERTED.** Applying `+0x78` uniformly fixes Array, makes `FMapProperty`
> read its **value as the key** and garbage as the value, and leaves all **142 Sets + 2 Optionals**
> broken — and `tryEmbedded` returns false on a non-pointer, so **nothing throws or logs.** Worse, a
> calibrator that scores "containers" as one **pooled** family gives `+0x78` a **96.6 %** score, which
> clears any 90 % gate and would have shipped the bug **CERTIFIED**.
> ⇒ ★★ **Calibrate PER FAMILY, PER MEMBER** (Map's Key and Value scored separately; Enum's
> `UnderlyingProp` and `Enum` scored separately). **This is the third over-generalisation in this
> investigation, and the second that a control nearly blessed.**

**Cheap permanent self-check [M]:** with correct offsets, `FEnumProperty` underlying types come out
**100 % numeric** — `ByteProperty` 1,636 / `IntProperty` 174 / `UInt32` 14 / `UInt16` 10 / `Int8` 5 /
`Int64` 1, all named `UnderlyingType` — versus **28.5 % even legal** for the current broken read.

### 3.3 The layout — NEITHER hypothesis; `sizeof(FProperty) == 0x70` [M]

**Both hypotheses this doc originally offered are REFUTED [M].** The truth is simpler:
**`sizeof(FProperty) == 0x70`, and `+0x70` is uniformly the DERIVED CLASS'S FIRST MEMBER.** The
"type-carrying vs container" split does not exist.

- **(i)** *(merged `UObject* TypeObject` slot at `+0x70` inside `FProperty`)* — **REFUTED**: one merged
  slot cannot simultaneously be `Set::ElementProp`, `Map::KeyProp`, `Enum::UnderlyingProp` **and**
  `FBoolProperty`'s 5-byte bitfield descriptor, which is measured at `+0x70` (`0xFF010001`×4541,
  `0x1010001`×889, `0x2020001`×511, `0x4040001`×368 — a clean bit progression).
- **(ii)** *(five coincident container edits)* — **REFUTED**: `*(f+0x70)` is never a link pointer.
  Links measured at `0x48` (20,069/22,460 FField, 83.8 % same-owner) / `0x50` / `0x58` / `0x60`;
  `+0x68` is non-zero 0.5 % and never an FField. `FIntProperty+0x70` is **94.4 % zero** (past the
  object).

⇒ **The layout is essentially STOCK.** Stock trailing members confirmed by slot-after-inner controls:
`Set+0x78` = `FScriptSetLayout` int32 pairs (8,12)/(16,20) · `Map+0x80` = `FScriptMapLayout`
(8,16)/(16,24) · `Struct+0x78` = 94.5 % zero.

★ **One family deviates: `FArrayProperty` has an 8-byte HOLE at `+0x70`** (93.3 % zero, 1
pointer-ranged value in 3,548) **with `Inner` at `+0x78`.** ⚠ **What that hole is remains
UNIDENTIFIED** — it is **not** `ArrayFlags` (the values are high-entropy, not small integers). Recorded
as unidentified rather than filled with a plausible name.

**Direct corroboration of the root cause:** `ArrayProperty+0x80` is 99.8 % pointer-ranged with only
**39 distinct values**, all inside the module image ⇒ **`+0x80` is literally the next FField's
vtable.** Same shape at `EnumProperty+0x80` (49 distinct values).

### 3.4 `FEnumProperty` — MEASURED, no longer inferred [M]

An earlier draft of this section correctly flagged that `EnumProperty` was in **neither** of the
original measurements (`3,548 Array + 142 Set + 555 Map + 2 Optional = 4,247` is the probe denominator
**exactly**, excluding all 1,840 enum rows) and warned against inferring by homology. It has now been
measured directly:

**`FEnumProperty::UnderlyingProp = *(f+0x70)` — 1,840/1,840 = 100 %** (`+0x78`: **0/1,840**).
**`FEnumProperty::Enum = *(f+0x78)` — 1,840/1,840 = 100 %** (`+0x80`: **0/1,840**).

Sanity distribution, which is itself strong evidence: underlying types come out **100 % numeric** —
`ByteProperty` 1,636 / `IntProperty` 174 / `UInt32` 14 / `UInt16` 10 / `Int8` 5 / `Int64` 1, all named
`UnderlyingType`. Compare the current broken read, only **28.5 %** of whose captured enum inners are
even *legal* for an enum (`StructProperty` 366, `BoolProperty` 323, `FloatProperty` 201, …).

★ **Both homology guesses in the earlier draft (`UnderlyingProp@+0x78`, `Enum@+0x80`) were WRONG —
scoring 0/1,840 each.** The warning not to infer them was correct, and measuring cost one probe.

---

## 4. Seven defects, not one

| # | site | effect | evidence |
|---|---|---|---|
| **1** | `extract.go:115` + `:158-186` — inline read at `+0x80` | container/enum inner types read from an adjacent FField | §3, [M] |
| **2** | `usmap.go:246-257` — drop on unresolved inner NAME | **1,840 EnumProperty records dropped, 100 % of them, 0 kept**, in every base usmap | [M] |
| **3** | `usmap.go:258-261` — `SchemaIdx = i` over the **filtered** list | **7,713 properties** emitted with a wrong schema index, max shift **10**; **1,222 / 11,387 structs** affected | [M] |
| **4** | `usmap.go:262` — `body.u8(1)` hardcodes `ArrayDim` | **66 / 75,907** UHT records (0.087 %) have `ArrayDim != 1` (`StyleColors[61]`, `BoneIndices[12]`, `Translation[3]`); each shifts everything after it | [M] |
| **5** | `emitSchema` sorts **in place** | the same backing arrays `emitUsmapBeside` later serialises (`pipeline.go:205` runs before `:213`) ⇒ printing the schema silently decides the usmap's enum section order | [M] |
| **6** | name-keyed duplicate struct records | 84 `AnimBlueprintGenerated*Data` records collapse to the **last written**, which has **0** properties (siblings up to 259) | [M] |
| **7** | `usmap.go:226`, `:263`, `:298-302`, `:307-311` — `nt.idx[...]` Go-map miss → `0` | any unresolvable name **silently aliases to name index 0** | [M] |

### 4.1 The deterministic damage dwarfs the nondeterministic damage

`usmap.go:325-343 writeInnerOrByte` has **no `StructProperty` branch** and falls back to bare
`ByteProperty` — **deliberately**, per its own code comment (*"CUE4Parse then sees
`ArrayProperty<Byte>` and parses element-wise, which is safer than crashing on a wrong inner-name
lookup"*). That is a **defensive workaround for defect #1**, and it erases type information wholesale:

- **1,516 / 3,699 (41.0 %)** of Array/Set/Optional inners in the canonical file are `ByteProperty`,
  against only **172 / 3,548 (4.8 %)** genuinely byte in `schema.txt` ⇒ **~36 % of all container inner
  types are fabricated.**
- Downgraded inners by true type: **StructProperty 1,163**, *nothing captured* 722, ArrayProperty 6
  (nested containers unsupported), EnumProperty 5.
- **Every `MapProperty` (555) and every `SetProperty` (142) in every usmap ever produced is
  `Map<Byte,Byte>` / `Set<Byte>`** — **697 properties with zero type information.** [M]

### 4.2 Accuracy against an independent oracle

Graded against `tools/asdump/out/binds_members.csv` (different toolchain, derived from `Binds.Cache`,
49,289 rows; 2,193 container declarations; 1,927 matched):

| usmap | discriminable | correct | accuracy | **confidently WRONG** |
|---|---:|---:|---:|---:|
| root `f9e32271` | 799 | 237 | 29.7 % | 542 (48.3 %) |
| worktree `d72c22e9` | 799 | 237 | 29.7 % | 552 (49.2 %) |
| `tools/usmapdump` `9f1b8e55` | 799 | 239 | 29.9 % | 538 (48.0 %) |
| **canonical `3892b937`** | 799 | 235 | **29.4 %** | 546 (48.7 %) |
| **fresh, this session** | 799 | 239 | **29.9 %** | 550 (49.1 %) |

*(A second agent, using a different "discriminable" definition — excluding cases where the `Byte`
catch-all can score a false hit — measured **38.3 % correct / 61.7 % wrong**. Different definitions,
same conclusion; not a contradiction.)*

> ★ **A FRESH EXTRACTION IS NOT BETTER.** fresh vs canonical: wrong in **both 554**, wrong only in
> fresh **6**, wrong only in canonical **10** — **symmetric**. Identical type coverage.
> **Re-extracting without the offset fix buys nothing. The win is the fix, not a re-run.**

---

## 5. The two load-bearing properties — BOTH DECIDED, both by two independent methods

Oracle: UHT `UECodeGen_Private::FPropertyParamsBase` statics in
`dumps/tutorial-hero/SUPERVIVE-Win64-Shipping.dump.exe` (`.rdata` 100 % readable — the standing rule).
Layout control: `ObjectFlags == 0x45` on 100 % of accepted rows. Positive controls:
`PlatformSettings → 0x19 Struct` ✔, `bEnableUserSettings → 0x0C Bool` ✔.

### 5.1 `EnhancedInputDeveloperSettings.DefaultMappingContexts` = **`TArray<FDefaultContextSetting>`** [M]

- `params@0x08647610`: `GenFlags = 0x19 Struct`, inner ctor `base+0x4BCBFD0`
- `params@0x08647650`: `GenFlags = 0x16 Array`
- sibling `DefaultWorldSubsystemMappingContexts` (`params@0x086476C8`) uses the **same** struct ctor —
  matching stock UE 5.4, where both are `TArray<FDefaultContextSetting>`
- in-artifact corroboration: `schema.txt:15154` `DefaultContextSetting` has exactly the 4 stock members
- independently reached by live RPM: `StructProperty UStruct:DefaultContextSetting`

⇒ **Both FK-14 candidates are wrong or right-by-luck, and NO usmap this project has ever produced can
express the right answer** — `writeInnerOrByte` has no Struct branch, so even the run that *read* it
correctly had it destroyed at write time.
★ **This is exactly the property S79/S80 measured as "EMPTY."** A `TArray<FDefaultContextSetting>`
decoded as `TArray<uint8>`/`TArray<int32>` cannot produce mapping contexts. **The S79/S80 "EMPTY"
reading was taken against a wrong inner type and must not be treated as a property of the game.**

### 5.2 `LokiScreenEffectComponent.ScreenEffectCollections` = **`TArray<UMaterialParameterCollection*>`** [M]

- `params@0x08A57150`: `GenFlags = 0x12 **Object**`, ClassFunc `base+0x3A36080`
- `params@0x08A57190`: `GenFlags = 0x16 Array`
- **fold multiplicity printed, per project rule:** `base+0x3A36080` is referenced by **17** property
  params — `MPC`, `Collection` ×6, `ParameterCollection` ×2, `SourceMaterialCollection`,
  `BaseCollection`, `LocalizedCollection`, `InCollection`, `TeamColorsParameters`, `Parameters`,
  `ScreenEffectCollections`. `MPC` is UE's standard Material Parameter Collection asset prefix, and
  `(WorldContextObject, Collection, ParameterName, ParameterValue)` is `UKismetMaterialLibrary`'s exact
  signature ⇒ class = `UMaterialParameterCollection` **[I, strong]**; the **type** (`Object`) is **[M]**
  and is what settles FK-14.
- independently reached by live RPM: `ObjectProperty UClass:MaterialParameterCollection`

⇒ ★★ **FK-14's `Array<Byte UEnum:ELokiGameFeatureToggle>` reading is FALSE** — a `labelPtr` hit on the
`+0x80` garbage. `ELokiGameFeatureToggle` has nothing to do with this property.
★★ **THE S88 GAME-FEATURE-TOGGLE WALL WAS BUILT ON AN ARTIFACT.** Three sessions (S88–S90) were spent
bit-splicing a replicated subobject on the strength of a type annotation that came from adjacent heap.
The only `ScreenEffect` symbols in the image are `ULokiScreenEffectComponent`, `LogScreenEffects`,
`ResetScreenEffects`, `&ULokiScreenEffectComponent::OnSpawnedCharacterChanged`.
⚠ The canonical usmap's `Array<ObjectProperty>` is **CORRECT and must not regress.**

---

## 6. FK-1's recorded root cause — audited, 2 of 4 clauses survive

`docs/fk1-angelscript-settled.md:280-282` says:
> *"Root cause located: `tools/usmapdump/usmap.go:325 writeInnerOrByte()` falls back to `ByteProperty`,
> and `writeUsmap()` silently drops unknown-typed properties while re-sequencing `SchemaIdx`."*

| clause | verdict |
|---|---|
| `usmap.go:325 writeInnerOrByte()` falls back to `ByteProperty` | **TRUE [M]** — `:325-343`, line 341 `default: b.u8(pByteProperty)`. Silent: no counter, no log. |
| `writeUsmap()` **silently drops** properties | **TRUE, wrong filter [M]** — the drop is `:246-257` (unresolved inner **NAME**), not `:239-243` (unknown **TYPE**). |
| …**"unknown-typed"** | **FALSE [M]** — every `typeName` the extractor produces is in `propTypeByte`'s switch. **That filter has fired ZERO times in both on-disk runs.** |
| …**"while re-sequencing `SchemaIdx`"** | **TRUE and severe [M]** — `:261 body.u16(uint16(i))` over the filtered list. |
| cited defect `LokiGameState.SpawnSelectEndTime` typed `Float` | **NOT A DEFECT [M]** — UHT ground truth `params@0x08982810 GenFlags = 0x0A Float`. **The usmap is correct; FK-1 mislabelled a correct value as a defect.** |
| cited defect `LokiGameState.XPRequiredToCompleteLevels` = `Array<ByteProperty>` | **CONFIRMED DEFECT [M]** — UHT `params@0x089824F0 GenFlags = 0x03 Int` + `params@0x08982528 GenFlags = 0x16 Array` ⇒ true type `Array<Int>`. |

**And the whole sentence names a symptom, not a cause.** `usmap.go` is **downstream**; the cause is
`extract.go`'s `+0x80` read (§3). Same failure shape as `docs/fk1-stub-claim-recheck.md`:
**the error was in the prose about the code, not in the code.**

---

## 7. Consumer map + canonical MD5 table (ignorance-map audit item 26 — **DONE**)

| path | bytes | md5 | provenance | loaded by |
|---|---:|---|---|---|
| `mappings.usmap` (root) | 1,858,496 | `f9e32271c25564e876103c3ca25e7be4` | run 2026-07-01 16:30 | `tools/asdump/asdump.py` ⚠ **STALE** |
| `tools/usmapdump/mappings.usmap` | 1,870,780 | `9f1b8e5509e92689d7f63678aee0af4f` | run 2026-07-08 20:09 | `asdump/analyze.py:9`, `compare.py:10` ⚠ **STALE** |
| **`tools/extractor/mappings.usmap`** | **1,876,427** | **`3892b9378e5ea9809149afb0239c91f6`** | **orphan run — NO schema survives** | **extractor (CANONICAL)**, `as_usmap.py`, `verify_usmap.py` |
| `tools/asdump/out/usmap/mappings+as.usmap` | 1,892,181 | `8114a302be70875248fb816ebf98f523` | canonical + 91 AS structs (S113) | ⚠ **NOBODY** |
| `tools/asdump/out/usmap/angelscript.usmap` | 17,567 | `200b25191518974019e6ce9dd28b02af` | S113 supplement | `verify_usmap.py` |
| worktree `tools/usmapdump/mappings.usmap` | 1,864,442 | `d72c22e9a459dab126902fbef3c9267f` | blob of `01f35ddc` (2026-06-26) | nobody |

- **Extractor resolution [M]:** `Program.cs:767-781`, 3 search dirs, `SelectMany → FirstOrDefault`.
  Slot 1 (`bin/Release/net9.0/`) verified to contain no `.usmap` → slot 2 → `3892b937`. FK-1 confirmed.
  ⚠ Latent: `GetFiles(d, "*.usmap")` means a second file dropped there wins by filesystem order, and
  **there is no CLI override.**
- **Staleness severity: LOW, measured.** `asdump.py` uses the usmap only for enum member names, and
  the **enum tables are byte-identical across all five usmaps** (2,226/2,226 in every pair). Positive
  control: the same comparison caught 154–188 property-type differences between those same pairs, so it
  would have detected an enum difference. Still a real hazard for any future non-enum use.
- ⚠ **`mappings+as.usmap` is loaded by nobody.** Its directory is not in the extractor's search path
  and there is no override. **`CLAUDE.md`'s "the usmap gap is CLOSED" describes an artifact that is
  built and verified but NOT WIRED IN.**

### ⚠ Live foot-gun — `pipeline.go:214`

```go
213: emitUsmapBeside("mappings.usmap", ...)                                            // relative
214: emitUsmapBeside(`G:\git\Supervive Revival Project\tools\extractor\mappings.usmap`, ...)  // ABSOLUTE
```

**Every `usmapdump extract`, from any CWD, silently overwrites the canonical usmap** — no versioning,
no `schema.txt` archived beside it. That is [M] how the canonical file became an **orphan whose schema
cannot be recovered without a re-run** (fingerprint-matched against all four recoverable schemas: best
score 1516/1599 = 94.8 %, vs 100 % on the diagonal). Given §4.2, the right fix is to **delete the
second write**, not to add versioning.
**Verified backup taken this session:**
`scratchpad/fk14-safety/mappings.usmap.CANONICAL-3892b937.bak`.

---

## 8. Blast radius — and what is SAFE

**Affected:** every container element type (3,516 Array + 555 Map + 142 Set + 2 Optional in the
canonical file), every enum property, and every property sitting after a drop in its struct.
Confirmed in **shipped output**, not inferred from mechanism alone:
- `tools/extractor/out/BP_StoreOffer_StarterPack.json` → `"AssetGrants": [0,5,0,3,10,0,0,0]` — a store
  offer's grants decoded as raw bytes (**directly load-bearing for this project's STORE work**)
- `BP_TemporaryFloor.json` → `"MoveIgnoreComponents": [0,0,0,0,0,0,0,0]`
- `BP_DebugGlobals.json` → `"DebugCommands": [128,13,7,8,0,0,0,80]`

⇒ **`tools/extractor/out` — 69,142 JSON files ✔, 58 directories ✔ — is invalidated for container and
enum values.** ⚠ **"1.3 GB" is wrong**: logical bytes are **1,105,036,403 (1.105 GB)**; 1.55 GB is
size-on-disk at G:'s 8 KiB clusters. JSON alone is 837 MB.

⚠⚠ **THE `Name[n]` FINGERPRINT HYPOTHESIS IS FALSIFIED — do not reuse it as a signal.** The *count*
was always [M] (7,473 keys / 1,875 files by my own re-census; the "8,569 / 2,116" figure counted
slightly differently), but the *mechanism* — *"`ArrayIndex` derives from `schemaSlot − SchemaIdx`, so
defects #3/#4 surface as bogus index suffixes"* — was flagged **[I]** and has now been **REFUTED by
the regeneration it was pre-registered to validate**:
- `catalog/comp/Comp_GameState_HotZone.json` is **unchanged**, PRE and POST, on exactly the keys cited
  as the worked example: `ClearHotZoneOverlayAfterPhase[3]`, `HotzoneOverlayColor[4]`,
  `CurrentMilbaseZone[5]`, `ClearMilbaseOverlayAfterPhase[6]`, `MilbaseOverlayColor[7]`.
- Corpus-wide the **lone-`Name[n]` count went UP, 5,168 → 14,441** (1,744 → 3,088 files) — the
  opposite of the predicted collapse to ~0.
⇒ Whatever produces those suffixes, it is **not** the `SchemaIdx` renumbering. **The mechanism is
UNKNOWN and is now an open question**, not a settled fingerprint. ★ Recording this because the
prediction was pre-registered in §9.1 and failed: an inference dressed as a diagnostic signal.

★ **What the regeneration DID show, measured:** repeated-`Name[n]` keys (**genuine C-style static
arrays**) went **2,305 → 798,311**. Worked case: `SK_WaveMaker_Default.json` now carries
`BoneIndices[1..8]` and `BoneWeights[1..8]` ×2,304 each. Because `usmap.go:262` hardcoded
`ArrayDim = 1`, **CUE4Parse previously read only element 0 of every static array — silently
discarding 7 of 8 bone influences per vertex, in every skeletal mesh the project has ever extracted.**
That is a larger and more concrete win than the fingerprint was ever going to be.

Corroborating pre-fix census: 74,159 all-integer arrays (13.6 M elements), only **93** enum-valued
properties outside containers, and **1** map-like object in the entire corpus (defects #2 / #4.1).

★★ ⚠ **`out/` IS MIXED-PROVENANCE — this is a regeneration trap [M].** Although §7 correctly says
nothing *loads* `mappings+as.usmap`, **26 of the 140 AS-referencing assets on disk were dumped with the
MERGED usmap**: re-dumping all 140 with the canonical base gives **114 identical, 26 DIFFERENT**, and
those 26 match a merged-usmap dump byte-for-byte. `BP_GameMode_Barracuda.json` is 66,126 B / 65 props
on disk vs 61,964 B / 27 props from the canonical base — the same 26 `CLAUDE.md` cites for
"263 newly decoded", i.e. the **drop-pod / respawn / FFA / Barracuda / aiming-laser** assets (the FK-1
deploy surface). ⇒ **The regeneration MUST use fixed-base + AS supplement.** A bare-base run silently
reverts those 26 and the diff would book the regression under the FK-14 fix. AS blast radius overall is
**141 / 69,142 = 0.20 %**.
⚠ **Never overwrite `tools/extractor/mappings.usmap` with the merged file** — `as_usmap.py:25` pins
that path as the *base*, so the next rebuild would double the 91 AS structs.

**NOT affected — measured 0.000 % variant across every extraction, and correct:**
struct/enum **inventory**, property **names**, **super-struct links**, **`StructProperty` type names**,
all **scalar** *types*, and the **2,226-entry enum VALUE table**. These must be held **byte-identical**
by any fix.

⚠⚠ **CORRECTION — scalar *VALUES* were NOT safe, and the damage is bigger than this section claimed.**
The regeneration measured **5,723 of 12,129 true scalar leaves changing value** in the affected files
(paths containing no container anywhere). They changed **from garbage to sane**, which is the tell:
`MaximumDuration 2.7e-44 → 1.2396458` (2.7e-44 is a **denormal float** — the classic signature of
reading at a wrong offset), `MinimumDuration 0.0 → 1.2396458`, `MaxAttenuationRadius 0.0 → 2000.0`,
`EventCookedData/DebugName "deDE_855772031" → "vo_cha_alchemist_ping_needcoin"`.
**Mechanism:** defect #3's `SchemaIdx` renumbering shifted every property *after* a drop, so scalars
downstream of a dropped `EnumProperty` were decoding **another property's bytes**. Scalar *types* were
never wrong; scalar *values* after a drop were. ⇒ the pre-fix corpus was corrupt well beyond its
container properties, and `endpoints.md:49`'s all-scalar `CoreGamePlayer` is safe only because it has
**no enum and no container to be shifted by** — not because scalars are inherently safe.

★ **The backend model work is therefore largely SAFE.** `docs/endpoints.md:49`'s
*"usmap ground truth `CoreGamePlayer` (4 props)"* — `ID`(str), `MatchID`(str), `Version`(int64),
`CanDisassociate`(bool) — is **all scalars, no containers, no enums**, so none of the 326 can touch it.
The ignorance map's row (g) worry (*"FK-14 shows the usmap disagrees with itself on 326 types"*) **does
not apply to it**, and the claim survives on these grounds. `MatchInfo`'s nested structs
(`GameConfig`, `ConnectionDetails`, `PlayerInfo`) are `StructProperty` **type names** — also in the
safe set. ⚠ Its `State`/`StateEnum` (`ECoreGameMatchState`) is an **enum** and is in the affected set.

**`mappings+as.usmap` must be rebuilt — but the "worse than a rebuild" warning is RETRACTED [M].**
An earlier draft said the supplement's classifier consults the base as a struct-vs-enum witness
(`as_usmap.py:86, 112, 170-172`), so a changed base could change its *type decisions*. **That is true
in the code and cannot fire:** the base is consulted only for struct/enum **name membership**, which
§8 puts in the SAFE set. Tested — rebuilt with `--base tools/usmapdump/mappings.usmap` (which differs
from canonical on **160 struct records**) → supplement **byte-identical**. So type decisions are safe
provided the fix honours its own name-set clause.
Rebuild = `as_usmap.py --base <fixed> -o <dir>` then `verify_usmap.py` — **0.9 s, byte-reproducible**
(re-ran it: `200b2519…` / `8114a302…` / identical `as_schema.json`). ⚠ `-o` defaults into the repo.
⚠ **Expected re-baselining, and it is the fix working:** `usmap_lite.U` is name-keyed and already
collapses the 84 `AnimBlueprintGenerated*Data` records to the last-written (0 props), so a fix that
de-dupes keeping the **richest** will make `verify_usmap.py` report `changed >= 1` against the **old**
base. Compare against the **new** base.

---

## 9. The fix — calibrate, don't hardcode

The lesson of §3.2/§3.4 is that **any hardcoded offset here is a liability**, and we now own an
instrument that decides them. So `extract.go` should **auto-calibrate per family at startup and print
the score table** — which is simultaneously the fix and its own permanent control, and means a future
engine update cannot silently re-break it.

```
type-carrying (Struct/Object/Class/Soft*/Weak/Lazy/Interface/Byte) : +0x70   [M] 13,767/13,767 offline
                                                                             13,360/13,360 live
FArrayProperty::Inner            : *(+0x78)   [M] 3,548/3,548 = 100 %  (+0x70: 0/3,548)
FSetProperty::ElementProp        : *(+0x70)   [M]   142/142   = 100 %  (+0x78: 0/142)
FOptionalProperty::ValueProperty : *(+0x70)   [M]     2/2
FMapProperty::KeyProp            : *(+0x70)   [M]   555/555   = 100 %
FMapProperty::ValueProp          : *(+0x78)   [M]   555/555   = 100 %  (+0x80: 0/555, REFUTED)
FEnumProperty::UnderlyingProp    : *(+0x70)   [M] 1,840/1,840 = 100 %  (+0x78: 0/1,840)
FEnumProperty::Enum              : *(+0x78)   [M] 1,840/1,840 = 100 %  (+0x80: 0/1,840)
```

⚠⚠ **CALIBRATE PER FAMILY AND PER MEMBER — never pool.** Map's Key and Value must be scored
separately, and Enum's `UnderlyingProp` and `Enum` separately. A **pooled** "containers" family gives
`+0x78` a score of **96.6 %**, which clears any 90 % gate and would ship a broken Map/Set/Optional
build **CERTIFIED** (§3.2b).

Candidates `{0x68, 0x70, 0x78, 0x80, 0x88}`; a winner must clear 90 % and beat the runner-up 5:1 or
**abort rather than emit a mis-typed usmap**. Discriminators as in §3.2, relaxed for enums (target's
`ClassPrivate` must name a **numeric** property type; `Owner == the enum property`; and
`labelPtr(*(f+slot1))` must yield a `UEnum:` label). ⚠ Note a **map key is named `<X>_Key`**, so a
name-equality gate rejects it by construction — relax that gate for `FMapProperty::KeyProp` or it will
score 0 while being correct.

★ **Free permanent self-check:** correct offsets ⇒ `FEnumProperty` underlying types are **100 %
numeric**; the broken read is **28.5 %** legal. Print this every run.

Plus, in `usmap.go`: never drop / never renumber (`SchemaIdx` = **absolute** slot advancing by
`ArrayDim`; a skipped property leaves a **hole**, which CUE4Parse fails loudly on, instead of silently
re-labelling every later property); `PropertyCount` = total slots, not `len(emit)`; a **recursive**
`writeInnerType` replacing `writeInnerOrByte`; a `nameIdx()` helper killing the silent index-0
aliasing; `ArrayDim` from `+0x30`; the `emitSchema` in-place-sort fix; and **deliberate**
de-duplication of the 84 `AnimBlueprintGenerated*Data` records (keep the richest).
Every remaining fallback must be **counted and printed** — *a run with a silent zero everywhere is the
no-op tell.*

### 9.1 Pre-registered control — CORRECTED

| arm | build | expected | catches |
|---|---|---|---|
| **0** | HEAD unchanged | container-inner accuracy ~29–41 % | the patch is a **no-op** |
| **F** | containers `*(+0x78)` (calibrator's winner) | **→ ~100 %** | the fix works |
| **W** | containers `*(+0x70)` | **drops below arm 0** | **wrong direction** |
| **D** | `ArrayDim` forced to 1 | `ArrayDim != 1` count 66 → 0 | the `+0x30` read is real, not noise |
| **E** | calibrated enum offsets vs assumed `0x78`/`0x80` | must agree, else the calibrator wins | the **unmeasured** enum assumption |

**Pre-registered canaries** (fixed in this document, before any regeneration — not post-hoc):
`DefaultMappingContexts → Array<Struct:DefaultContextSetting>` · `PlayerConfigManager.ActionMappings →
Array<Struct:…>` · `XPRequiredToCompleteLevels → Array<Int>` · `CachedVolumeLevels → real key/value` ·
**`ScreenEffectCollections → Array<Object>` MUST NOT REGRESS** · **`SpawnSelectEndTime → Float` MUST
NOT CHANGE** (negative control; FK-1 wrongly called it a defect) · `Map<Byte,Byte>` 555 → ~0 ·
`EnumProperty` records 0 → **1,813 exactly** (see below) · `ArrayDim != 1` — compare the **COUNT (70)**,
not the rate.

★★ **`EnumProperty == 1,813` is a DISCRIMINATING canary, not an approximation [M].** 1,840 enum
properties are live; **keep-richest emits 1,813 (total properties 43,535); keep-last emits 1,810
(43,282)**. The 27-record difference from live is the de-duplication of the name-colliding
`AnimBlueprintGenerated*Data` records, **not a drop**. So the emitted pair separates the two de-dup
rules at a **3-record margin**, and **1,813 / 43,535 is itself proof the tool implements
keep-richest** — exactly what the §2 name-keying hazard demands. Both figures were confirmed off the
wire by two parties independently, neither fitted to the other.
⚠ **The signal is a jump to EXACTLY the keep-last pair, not any small movement** — both numbers drift
with anim-BP residency.
⚠ **An intermediate "keep-richest retains 4" in an earlier draft was WRONG**: measured, lossy
collapses are **2** under either rule, and the "4" was keep-**first**'s enum loss. The 1,813/1,810
pair is unaffected. *(Third prose-drift instance this session — see §11.)*
⚠ **`ArrayDim != 1` came out 70, not the predicted 66 — and that is not a defect.** The UHT oracle's
75,907-record population includes UFunction params this walk skips. Values
`{2:11, 3:27, 4:12, 5:2, 7:2, 8:7, 9:2, 10:1, 12:4, 20:1, 61:1}` include the pre-registered
`StyleColors[61]` and `BoneIndices[12]`. **Compare counts against a stated population, never rates
across different populations.**

**Non-regression:** the **2,226** enum name→value tables, the **11,344** struct names + supers, the
`StructProperty` type names, all outer property type bytes, and the property NAME sequences must be
preserved. If the patch moves them, it touched something it must not.

> ⚠ **Two corrections to an earlier draft of this section, caught by the verification harness before
> the patch landed — both would have produced a false verdict:**
> - **"all 9,119 `StructProperty` type names" is NOT an invariant.** It is a per-file, all-records
>   count: **9,119** in the `usmapdump`/fresh lineage, **9,421** canonical, **8,462** root. Compare
>   StructProperty type names **pairwise on shared properties**; never gate on a hardcoded 9,119.
> - **"every property NAME sequence byte-identical" cannot be taken literally** — the fix *restores*
>   ~1,810 dropped `EnumProperty` records, so names are **added** by design. Operationalise as: the
>   baseline's per-struct name list must be an ordered **SUBSEQUENCE** of the candidate's (no
>   deletions, renames or reordering); report additions with their outer-type breakdown.
>
> ⚠ **Record-policy note (reconciles §4.1 with §8):** "3,699 inners / 1,516 Byte / 41.0 %" (§4.1) is
> the **all-records** view; "3,516 Array + 555 Map + 142 Set + 2 Optional" (§8) is the **name-keyed,
> last-wins** view — *what CUE4Parse actually sees*. Same file, two policies, both correct. **State
> the policy whenever quoting a container count.**
>
> ⚠ `ScreenEffectCollections` already reads `Array<Byte>` in `9f1b8e55`; the "MUST NOT REGRESS"
> `Array<Object>` value exists only in root / canonical / fresh. Gate it per-baseline, not globally.

⚠ **Trap:** the extractor reads a **live process**, so arms are never on identical input. Run each arm
≥2× and score only on the stable 11,344-struct inventory; treat `AnimBlueprintGenerated*Data` count
differences as expected, not signal.

---

## 10. What FK-14 got right, wrong, and half-right

| FK-14 claim | verdict |
|---|---|
| *"326 property TYPES disagree"* | **CORRECT and reproduced** — 326 / 219 container / 26 Loki-owned, to the digit (a second agent re-derived 301 on a differently-selected pair; classifier difference, same order) |
| *"the failure mode is an index shift, not noise"* | **RIGHT signature, no cause.** Cause now named (§3) |
| *"it is non-deterministic across the board"* | ❌ **REFUTED as a tool property** (§1), and *"across the board"* is wrong — outer classes, struct names, supers, property names and enum values are **0.000 % variant** |
| *"three usmaps exist on disk (1,858,484 / 1,870,768 / 1,876,415 B)"* | ❌ **five** distinct usmaps; every size short by **exactly 12 bytes** — it quoted the `DecompressedSize` header field, not the file size |
| *"the one the extractor loads has never had its schema printed"* | ✅ **CONFIRMED** — and its schema is now **unrecoverable** without a re-run (§7). But **misdirected**: which usmap was used doesn't matter (§4.2) |
| `ULokiPlayerConfigManager` cited as evidence of dump-to-dump disagreement | ❌ **not in the 326**; the class's UHT name is `PlayerConfigManager` (no `Loki`), and **all four dumps read identically**. The shift is **deterministic and permanent**, present in every dump. `tools/re/console_probe.py:1084` already hardcodes a workaround citing FK-14 — right fix, wrong reason |
| `DefaultMappingContexts` = `Array<Int>` vs `Array<DefaultContextSetting>` | ❌ **both wrong or right-by-luck**; truth is `TArray<FDefaultContextSetting>` and **no usmap can express it** (§5.1) |
| `ScreenEffectCollections` = `Array<Byte UEnum:ELokiGameFeatureToggle>` | ❌ **FALSE** — truth is `TArray<UMaterialParameterCollection*>`; **the S88 wall was built on an artifact** (§5.2) |
| *"nothing usmap-derived is trustworthy without a cross-check"* | ⚠ **over-broad.** Half the file is provably stable and correct (§8) |

### The corrected rule (replaces `CLAUDE.md`'s "replicated container types" line)

> **Container inner types and enum underlying types are ~70 % wrong regardless of replication —
> deterministically, in every usmap this project has ever produced. Struct names, property names,
> super-struct links, `StructProperty` type names, scalar types and enum VALUE tables are identical
> across every extraction ever taken and can be trusted.**
> Never take an array **stride** from the usmap. Where a container element type matters, use
> `tools/asdump/out/binds_members.csv` or the UHT `FPropertyParams` oracle in
> `dumps/tutorial-hero/SUPERVIVE-Win64-Shipping.dump.exe`.

---

## 11. Method notes for the project record — three new instrument-artifact instances

This is the **instrument-artifact pattern** again (`memory/supervive-instrument-artifact-pattern.md`),
on a new instrument, with one instance occurring **inside this very investigation**:

1. **A cosmetic annotation was read as data.** The `(UStruct:X)` column in `schema.txt` is
   `labelPtr(ptr(f+0x70))` printed for *every* property type — meaningful for 8 families, **pure
   garbage for containers**, and **the usmap never consumes it**. FK-14's headline `PlayerConfigManager`
   evidence *and* the entire S88 `ELokiGameFeatureToggle` wall both live in that garbage column.
2. **A digest sentence drifted from its source, again.** FK-1's *"silently drops **unknown-typed**
   properties"* names a filter that has fired **zero** times, and cites `SpawnSelectEndTime` as a defect
   when ground truth says the value is **correct**. Neither error was in the code; both were in the
   prose about the code. (Cf. `docs/fk1-stub-claim-recheck.md`, where the same shape produced a false
   published claim.)
3. ★ **An "empty" bucket from a UObject-only labeller was read as a positive statement about what a
   slot contains.** A 42,000-row census concluded `sizeof(FProperty) == 0x70` because containers showed
   `+0x70` → *"empty 100 %"*. That only means **`labelPtr` failed to name it as a UObject** — equally
   consistent with padding, flags, or a link pointer. **The instrument was blind at exactly the point of
   disagreement**, and a companion "exact hit" prediction turned out to be **non-discriminating**
   (it holds under both hypotheses). It was caught only because a parallel agent **measured** what this
   one **inferred**.

★★ **And the pre-registered control is what saved the patch.** The original arm table listed
`+0x78` as the *wrong-direction* arm expected to fail. Had the control been written after the build, it
would have been written to agree with the build, and the **wrong** patch would have shipped
**certified**. The value came from naming the expected direction *before* anyone ran anything.

⇒ **Standing rule this settlement adds: never infer a struct offset by homology from stock UE in this
build. Measure it, with a discriminator that dereferences the candidate and validates the target.**
This build's `UObjectBase` was already known non-stock; `FProperty` now is too.
⇒ ★★ **Second standing rule, from §3.2b: an aggregate score over a heterogeneous population can
CERTIFY a broken patch.** Pooling five container families gave `+0x78` a 96.6 % score — clearing a
90 % gate while silently making every `TMap` read its value as its key and leaving 142 Sets
unresolved. **Score per family, per member. A control that pools is not a control.**

### 11.1 A fifth instance, procedural rather than technical

**A stale context snapshot was acted on as if it were the repo.** During this session the assistant's
auto-loaded memory index still described the Claude memory store as live, and `MEMORY.md` was
**recreated from that snapshot** — but commit `c56e189` (*"docs: migrate the 4 load-bearing memories
into the repo; retire the memory store"*, 2026-08-12 23:55) had **deliberately retired it hours
earlier**, after auditing 37 files and finding 33 stale or duplicated. The recreation was caught only
because the commit appeared in `git log` while committing something else.
⇒ **Rule: an auto-loaded summary, index or memory is a claim about the past, not a reading of the
repo. Verify it against `git log` before acting on it** — exactly as the memory-recall discipline in
`CLAUDE.md` says of any recalled fact that names a file or flag.
⇒ **The Claude memory store is RETIRED for this project.** `docs/` + `CLAUDE.md` are the only sources
of truth; both are version-controlled, git-blameable and revertible, which is the property the store
lacked and the reason it was dropped. **This document is the canonical FK-14 record** — no digest of
it should be maintained anywhere else, because a second copy at a different compression level is how
three of the retractions above were manufactured in the first place.

---

## 12. Status

- **FK-14: SETTLED on diagnosis. The fix is designed and NOT applied.**
- Open, and cheap: the §3.3 layout discriminator (~200 reads) and the §3.4 enum-offset calibration.
  Both are one probe each; neither costs a launch.
- The regeneration is a **regenerate-everything event** (1.3 GB, 69,142 files, plus the AS supplement)
  and deserves its own sitting.
- `pipeline.go:214` should be deleted **regardless** of what else is decided.

**Artifacts (scratch, read-only work):** `scratchpad/fk14-determinism/` (run1–run4 usmaps + schemas,
`probe/probe_v2.txt`, five historical schema blobs, `parse_usmap.py`, `compare.py`, `deep.py`,
`schemadiff.py`, `neighbour.py`, `grade.py`) · `fk14-binary-truth/` (`usmap_offsets.py`, `shift_test.py`,
`oracle_test.py`, `cross_binary.py`, `printer_vs_binary.py`, `blast_radius.py`) · `fk14-provenance/`
(`CANONICAL-MD5-TABLE.md`, `typediff_jul01_jul08.tsv`, `unstable_all4.tsv`) · `fk14-writer-fix/`
(`audit.py`, `audit2.py`, `shift.py`, `uht_prop.py`, `resolve_ctor.py`) · `fk14-safety/` (canonical
usmap backup).
