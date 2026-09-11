# Vtable dumping without RTTI — the second technique FK-3 wrote off

**S102, 2026-07-26.** Offline, read-only, no game launch, no injection.
Tool: `tools/strxref/vtables.py` (companion to `tools/strxref/strxref.py`).
Input: `dumps/merged.dump.exe` only.

```powershell
cd "G:\git\Supervive Revival Project\tools\strxref"
python vtables.py scan          # ~3 s, builds index/vtables.idx + prints validation
python vtables.py name ALokiPlayerState
python vtables.py diff ALokiGameMode          # only the OVERRIDES + NEW virtuals
python vtables.py slotof 0x34AB870            # code RVA -> Class[slot]
python vtables.py who 0x0888CB78              # vtable RVA -> class
python vtables.py classes Loki -n 100
python vtables.py bench / reflect / stats / verify
```

**Validation: 7 checks, 0 failed.** Every headline number below is reproduced by
`vtables.py scan`.

---

## Verdict, up front

**Vtable dumping is revived, and it is stronger than it was before FK-3 retired it —
but for a different reason than the brief anticipated.**

| | |
|---|---|
| Is `.rdata` readable enough to dump vtables? | **Yes.** The LokiAssetManager vtable captured from the LIVE process in June reproduces **8/8 spot-checked slots** from the cold dump. |
| Can vtables be found structurally? | **Only half way.** RTTI stripping removed the separator, so vtables are packed back-to-back and structure alone cannot cut them apart. |
| Can they be named? | **Yes — 3,599 of them, with class names**, from UE's own `IMPLEMENT_CLASS` boilerplate. Not from RTTI, and not from method strings. |
| Was the brief's proposed naming route (a), "name a vtable by its methods' strings", right? | **No. Measured 4.7% top-1.** See below. |
| Was route (b), "match method count/order against a UClass's native function list", right? | **No, and it cannot be** — UFUNCTIONs are not virtuals. Reflection data is still valuable, as a *validator*. |

The technique is **not** "revived but weak". It is genuinely strong: it now yields a
**3,599-entry class→vtable symbol table**, and its binding constraint is far looser
than the string-xref technique's.

---

## 1. Structural scan: what is actually in `.rdata`

`.rdata` = 4,651,520 aligned qword slots. Classified:

| | slots | share |
|---|---:|---:|
| point into `.text` | **933,675** | 20.1% |
| zero | 440,700 | 9.5% |
| other (strings, data, non-image) | 3,277,145 | 70.4% |

The 933,675 text pointers form **104,903 maximal runs**:

| run length | 1 | 2–3 | 4–7 | 8–31 | 32–127 | ≥128 |
|---|---:|---:|---:|---:|---:|---:|
| runs | 75,920 | 18,930 | 982 | 6,275 | 1,580 | 1,216 |

Longest run: **30,247 slots**. That is the whole problem — see next section.

### The RTTI-stripping consequence nobody had written down

MSVC normally emits a pointer to the RTTI *Complete Object Locator* in the qword
**immediately before** each vtable. That qword points into `.rdata`, not `.text`, so
it breaks the run and separates adjacent vtables.

**RTTI is stripped in this build** (`.?AV`/`.?AU` type-descriptor count in `.rdata`:
**0**), so that separator does not exist. Measured consequence: the LokiAssetManager
vtable at `0x0888CB78` sits at **slot 799 of a single 997-slot run** that starts at
`0x0888B280`. The qword before it is another `.text` pointer.

⇒ **Tuning N does not find vtables.** No threshold on run length can, because a run
is a *chain of many vtables*. A pure structural answer to "how many vtables are
there" is not available. This is the real, and previously unrecorded, cost of RTTI
stripping — not unreadable memory.

### The cut has to come from code

A vtable start is exactly an address a constructor loads:
`lea r64,[rip+V]` … `mov [this], r64`. Measured:

* 106,800 distinct `.rdata` LEA targets in `.text`
* **29,501** of them are 8-aligned and land inside a text-pointer run → cut points
* 11,931 of those additionally carry an adjacent `mov [mem],r64`

Cutting the runs at the 29,501 code-referenced points yields **119,260 pieces**:

| piece size | 1 | 2–3 | 4–7 | 8–31 | 32–127 | 128–511 | ≥512 |
|---|---:|---:|---:|---:|---:|---:|---:|
| pieces | 77,287 | 22,257 | 3,655 | 11,163 | 3,773 | 1,116 | 9 |
| of which **named** (§3) | 2 | 1 | 0 | 2 | **2,608** | **984** | 6 |

**Read that table before quoting a vtable count.** Naming lands almost entirely in
the 32–511 range: **69.1%** of 32–127-slot pieces and **88.2%** of 128–511-slot
pieces are named UObject classes. Below 32 slots, essentially nothing is — those
~103k small pieces are function pointers inside ordinary data structures, plus
non-UObject C++ vtables. The single 30,247-slot piece survives uncut and is a
function-pointer *table*, not a vtable.

**Named vtable slot counts**: min 1, p25 **91**, median **99**, p75 **134**,
p90 **247**, max **586**. `UObject`'s own vtable is 88 slots, which is the floor.

Honest bound: a piece's length is an **upper bound**. The next cut is the next
*code-referenced* vtable start, so a vtable whose constructor page this dump never
decrypted leaves no cut and its predecessor absorbs it. 89,759 pieces begin at a run
head with **no** code reference at all — their starts are unproven, and `vtables.py`
flags them.

---

## 2. Ground truth: the cold dump reproduces the live capture

`docs/lokiassetmanager-vtable-dump.md` was captured 2026-06-28 from the **running
process** with `usmapdump vtdump`. Re-read from `dumps/merged.dump.exe`:

```
slot   0  want 0x52A7AB0  got 0x52A7AB0  OK      slot  95  want 0x34CA500  got ... OK
slot  47  want 0x12CC100  got 0x12CC100  OK      slot  97  want 0x34B6FC0  got ... OK
slot  88  want 0x34CF9F0  got 0x34CF9F0  OK      slot 111  want 0x34C0420  got ... OK
slot  94  want 0x34AB870  got 0x34AB870  OK      slot 127  want 0x34AA740  got ... OK
```

**8/8.** No live process needed for any of this any more.

---

## 3. Naming, without RTTI: UE's boilerplate *is* the symbol table

`IMPLEMENT_CLASS` generates, for every UCLASS:

```cpp
UClass* UFoo::GetPrivateStaticClass() {
    GetPrivateStaticClassBody(StaticPackage()      /* L"/Script/Loki"  */,
                              TEXT("UFoo"),        /* the class name   */ ...,
                              (UClass::ClassConstructorType)InternalConstructor<UFoo>,
                              &UFoo::Super::StaticClass, &UFoo::WithinClass::StaticClass);
}
```

So the pipeline is:

1. **Find `GetPrivateStaticClass`** — structurally, not by name-guessing: a function
   that references a wide `L"/Script/<Module>"` string **and** exactly one other
   wide string shaped like a C++ class name. → **5,089 functions named**
   (1,159 references to `/Script/…` with no class-name string; 16 ambiguous).
2. **`InternalConstructor<UFoo>`** is the **last** `.text` LEA target in that
   function. Verified by shape (`mov r,[rcx]; test r,r`) for 5,038 of 5,077; the
   other 51 fall back to position.
3. **Follow only TAIL branches** (`jmp rel32`, and `jcc rel32` whose next byte is
   `ret`) to the real C++ constructor. **Never follow `call`.**
4. The constructor's **first vtable-candidate LEA** is the class's own vtable.

**Result: 5,061 of 5,077 classes (99.7%) resolved to a vtable — 3,599 distinct
vtables, 773 of them in `/Script/Loki`.**  (5,089 `GetPrivateStaticClass` functions
collapse to 5,077 distinct class names; 12 names occur in two modules.)

### Two things in that pipeline were found by failing first

**"Never follow `call`" is the whole correctness argument.** An earlier version
followed calls out of the constructor. MSVC compiles `D::D()` as *call `B::B()`*
(which installs **B's** vtable) *then install D's vtable*. Following calls therefore
walks into the base constructor and assigns derived classes their base's vtable:
that version produced only **1,442 distinct vtables for 4,729 classes**. Restricting
to tail branches lifted it to 3,599.

**The `jcc` tail test.** UE emits `InternalConstructor` in two shapes. One ends with
`jcc <ctor>; ret` (a genuine tail branch). The other is
`mov rax,[rcx]; test rax,rax; jz <epilogue>; …; call <ctor>; lea rax,[vtable]; mov [rbx],rax`
— here the `jcc` is a **forward null-check skip**, and following it lands in the
middle of the next function. That single confusion is what made `UMissionsModel`
miss. Requiring the byte after the `jcc` to be `ret`/`int3` fixes it.

### Parameter sensitivity — the rule is not tuned into existence

Two knobs: which candidate to pick, and how far into the constructor to look.

| config | resolved | distinct | GT hits | class/base pairs | median shared slots | ≥50% |
|---|---:|---:|---:|---:|---:|---:|
| **first**, win 0x80 | 5052 | 3594 | 5/5 | 4025 | 97.9% | 100.0% |
| **first**, win 0x200 | 5065 | 3603 | **5/5** | 4035 | 97.9% | **100.0%** |
| **first**, win 0x800 | 5067 | 3605 | 5/5 | 4038 | 97.9% | 99.9% |
| lastd0, win 0x200 | 5065 | 2199 | 4/5 | 3913 | 95.6% | 97.5% |
| lastd0, win 0x800 | 5067 | 1357 | 3/5 | 2951 | 84.4% | 62.7% |

"first" is flat across a 16× window sweep; the alternative degrades monotonically.
That is the signature of a rule that matches the codegen rather than the data.

### Accuracy, measured two independent ways

**(i) Against live captures from earlier sessions** — five class↔vtable pairs recorded
in `docs/` from CDO scans, never produced by this tool:

| class | expected | got | |
|---|---|---|---|
| `ULokiAssetManager` | `0x0888CB78` | `0x0888CB78` | OK |
| `ALokiPlayerState` | `0x08A2D718` | `0x08A2D718` | OK |
| `UMissionsModel` | `0x088ADED0` → **`0x08AADED0`** | `0x08AADED0` | OK, **record corrected** |
| `UAssetRegistryImpl` | `0x079D5328` | `0x079D5328` | OK |
| `ULocalPlayer` | `0x08117130` | `0x08117130` | OK |

**(ii) Inheritance-similarity control.** A derived vtable must share most of its
base's slots — only overrides differ. Inheritance comes from `schema.txt` (UHT
reflection), which this tool otherwise never reads.

> **4,032 class/base pairs, median shared-slot fraction 97.9%, 4,031 of 4,032 share
> ≥50% (100.0%).** Random pairs would share ~0%.

---

## 4. ⚠ Two record corrections

**(a) `docs/lokiassetmanager-vtable-dump.md:584` — `UMissionsModel` vtable
`+0x88ADED0` is a transcription typo for `+0x8AADED0`** (`8A`→`88`). Adjudicated
three ways, all measurement:

| | `0x88ADED0` (recorded) | `0x8AADED0` (correct) |
|---|---|---|
| code references it | **0** | 2 LEAs |
| shares first-40 slots with `UObject`'s vtable | **5%** — impossible for a UObject subclass | **97.5%** |
| length | not a cut piece at all | 88 slots (= `UObject`'s) |
| slot 0 (destructor) | `0x3393150`, unrelated CU | `0x54A44A0`, same CU as `UMissionsModel::GetPrivateStaticClass` `0x54A2BF0` and its `InternalConstructor` `0x54A30C0` |

The historical doc is left as-is; this is the correction of record.

**(b) The S102 recovered `.pdata` gives FRAGMENT bounds, not function bounds.**
`index/pdata_union.csv` is described as "382,282 exact, non-overlapping function
bounds". Measured: **147,176 of the 382,282 ranges begin exactly where the previous
one ends, and 129,033 of those begin at a non-16-aligned address.** x64 allows a
function to own several `RUNTIME_FUNCTION` records (chained `UNWIND_INFO`), and MSVC
aligns real entries to 16 — so an unaligned continuation is a chained fragment.

*Proof, not inference:* `0x12BF4B0` (`ULinkerPlaceholderClass`'s constructor) has raw
bounds `0x12BF4B0..0x12BF4C1` = **17 bytes**, yet its own `jz` at `+0x0C` targets
`0x12BF4FB`. A jump inside a function cannot leave it. Merging unaligned
continuations gives `0x12BF4B0..0x12BF4FD` (77 bytes), which contains the target.

**382,282 fragments → 253,249 functions.** 17.7% of raw ranges are under 32 bytes.
`vtables.py merged_func()` implements the merge; consumers of `strxref.true_func()`
should either merge or state that they are reporting fragment bounds. Using raw
fragment ends cost 519 class resolutions in this tool before the fix.

---

## 5. The two naming routes the brief proposed — both measured, both rejected

### (a) Name a vtable by its methods' strings — **4.7% top-1. It does not work.**

Scored against the 3,599 uniquely-named vtables, using exact merged function bounds:

| span of slots sampled | vtables yielding any `Ident::` token | **top-1 = true class** | in top-3 | anywhere in token set |
|---|---:|---:|---:|---:|
| head (first 60) | 84.7% | **0.2%** | 0.3% | 0.3% |
| tail (last 60) | 12.7% | **4.7%** | 4.7% | 4.8% |
| all | 97.3% | **1.5%** | 4.7% | 4.7% |

Two measured reasons, and they compound:

1. **Virtual methods rarely reference literals.** Over the last-60 slots of 600
   vtables: 35,941 slots scanned, **168 distinct functions reference any string at
   all** (0.5%). Head-span is no better in kind: 894 of 36,000.
2. **A vtable is dominated by inherited slots.** Sampling the *head* is sampling
   `UObject`'s virtuals, which is why head-span scores 0.2% while tail-span — where
   a derived class's own overrides sit — scores 20× better in relative terms and
   still only 4.7% absolute.

The brief predicted this would "work well for UE classes, which log their own names".
It does not. What it *is* good for: **confirming a single high-value slot** once the
boilerplate route has already proposed a name — e.g.
`ULokiAbilitySystemComponent` slot 238 → `'ULokiAbilitySystemComponent::OnGiveAbility was missing…'`.
That is exactly what `strxref.py func` is for, one function at a time.

### (b) Cross-reference reflection data (`schema.txt`, `tools/asdump/out`)

| test | result |
|---|---|
| **name agreement** | **5,056 of 5,077** names recovered from the binary appear in `schema.txt` (**99.6%**). The 21 that don't are all `DEPRECATED_*`. Two completely different extraction paths agreeing at 99.6% is a real control. |
| reflected **property** count vs vtable slot count (5,045 classes) | r = **+0.255** |
| AS-exposed **method** count vs vtable slot count (5,039 classes) | r = **+0.199** |

Both correlations are weak-positive — "bigger classes are bigger" — and nowhere near
identifying. **Structurally they must be**: a UFUNCTION is registered as a static
`exec` thunk in the UClass function map. It is not a C++ virtual and occupies **no
vtable slot**. Matching "vtable method count/order" against a UClass function list
compares two lists that describe different things.

**Reflection data's real value here is as a validator and a dictionary**, and in that
role it is excellent — it is what produced the 4,032-pair inheritance control in §3.

### (c) The `UClass` objects' own vtable

Every `UClass` object is an instance of `UClass`, so they all share **one** vtable:

> **`UClass` vtable = RVA `0x076FF270`, 134 slots** (`UObject` = `0x076EF490`, 88 slots)

Useful for *enumerating* UClass objects in a live process (scan for `[obj+0] == base+0x76FF270`),
useless for naming an individual class. Note the terminology trap in the older doc:
`0x0888CB78` is the vtable of **`ULokiAssetManager` instances** (the singleton and its
CDO), not the vtable of the `UClass` object that describes them.

---

## 6. What this actually buys the project

### 6a. The single most valuable result: `GetLifetimeReplicatedProps` is slot 85

Vtable **slot 85 is `AActor::GetLifetimeReplicatedProps`**, and the strings each
override touches are that class's **replicated property names, in registration
order**. Externally checkable:

| class | slot-85 fn | distinct strings | first few |
|---|---|---:|---|
| `APlayerState` | `0x3CAF390` | **11** | `Score, PlayerId, CompressedPing, bIsSpectator, bOnlySpectator, bIsABot, bIsInactive, bFromPreviousLevel, StartTime, UniqueId, PlayerNamePrivate` |
| `ALokiGameStateBase` | `0x3872030` | **4** | `GameModeClass, SpectatorClass, bReplicatedHasBegunPlay, ReplicatedWorldTimeSecondsDouble` |
| `ALokiGameState` | `0x53868A0` | **43** | `bGetPreventWeaponFire, bGetPreventMovement, SpawnSelectEndTime, WinningTeam, WinningPawn, WinStreak, TeamScores, …` |
| `ALokiPlayerState` | `0x5435F00` | **9** | `HeroClass, PlatformPlayerID, SpectateTeamIndex, ParticipantMatchStartDetails, WalletStorage, …` |
| `ALokiHeroCharacter` | `0x539BA80` | **12** | `AllowUpdatesToVisionGranters, HeroPredropHidden, Armor, Power1, Power2, Gold, Gems, …` |
| `ALokiRespawnBeacon` | `0x544EA40` | **8** | `CaptureTimeSeconds, TeamsLockedOut, bContested, bIsLosingProgress, …` |

Three independent confirmations that this is really `GetLifetimeReplicatedProps`:

* `APlayerState`'s 11 names **are** the vanilla UE 5.4 `DOREPLIFETIME` list, in order.
* `ALokiGameStateBase`'s 4 names **are** `AGameStateBase`'s — and include
  `ReplicatedWorldTimeSecondsDouble`, precisely the S70 live finding that the client
  replicates only the Double, not the deprecated float.
* `ALokiGameState` has **43** — the S70 `ALokiGameState` mirror
  (`LokiGameStateStub.{h,cpp}`) was hand-built with **43 net props**.

That mirror cost a session of live RE. The same list is now one offline command for
**any** class, including ones the DS stub has never been able to instantiate.

### 6b. Documented addresses become `Class[slot]`

`vtables.py slotof <rva>` over the project's recorded function addresses — **15 of 48
turn out to be virtuals with a named owner**:

```
0x34AB870  AddDynamicAsset                UAssetManager[94];  ULokiAssetManager[94]
0x34D32D0  scan wrapper "slot 131"        UAssetManager[131]; ULokiAssetManager[131]   <- confirms the doc
0x34D3380  scan "slot 132"                UAssetManager[132]; ULokiAssetManager[132]   <- confirms the doc
0x55ACB90  "movement A" (S81 CMC work)    ULokiCharacterMovementComponent[153]
0x558BD90  "movement B"                   ALokiHeroCharacter[384]
0x55AC9F0  "movement C"                   ALokiMinionCharacter[384]; ALokiCharacter[384]
0x3C33230  "moonshot C"                   ALokiPlayerController[183]
0x3C421D0  "moonshot D"                   ALokiPlayerController[153]
0x39E90E0  "moonshot E"                   ULocalPlayer[95]
0x39E1460  "moonshot F"                   ULocalPlayer[110]
0x560AFE0  "tutorial launch"              ALokiGameMode[176] (+9 gamemodes)
0x37E5C80  "match setup"                  AGameModeBase[176]                            <- same slot: base vs override
0x0B9E1F0  "moonshot G"                   present in 19,256 vtables = the ICF'd `mov al,1; ret` stub
```

Two of these are new information: `0x560AFE0` and `0x37E5C80` are the **override and
base of the same virtual** (slot 176), and `0x0B9E1F0` is confirmed as a shared stub
rather than a real target. The `AddDynamicAsset` identification, which originally
took a full session (string anchor → log record → `xrefstr` → `vtdump`), is now one
command.

Also actionable: a shim that today hardcodes `base + 0x34AB870` can call
`vtable[94]` off a live object instead — which is what makes it survive a rebase.

### 6c. The five requested classes

`ULokiPlayerConfigManager` and `ULokiRespawnComponent` **do not exist**. The real
classes, located and dumped:

| requested | actual class | vtable | slots | overrides / new virtuals |
|---|---|---|---:|---|
| `ULokiPlayerConfigManager` | **`UPlayerConfigManager`** (no `Loki` prefix; `schema.txt:40990`) | `0x08AD4A40` | 88 | 1 / 0 |
| `ALokiGameMode` | `ALokiGameMode` | `0x08951FA0` | 347 | 12 / 35 |
| `ULokiAbilitySystemComponent` | `ULokiAbilitySystemComponent` | `0x0886E788` | 322 | 39 / 8 |
| `ALokiPlayerState` | `ALokiPlayerState` | `0x08A2D718` | 283 | 12 / 11 |
| `ULokiRespawnComponent` | **`ALokiRespawnBeacon`** (nearest real class; `ULokiRespawnComponent` is not in the binary or in `schema.txt`) | `0x08A4B670` | 252 | 6 / 5 |
| *(ground truth)* | `ULokiAssetManager` | `0x0888CB78` | 176 | 2 / 0 |

`ULokiGameFeatureToggles` (S88–S90) is **not a UCLASS** — it has no
`GetPrivateStaticClass`, no `schema.txt` entry, and its `::Get` at `0x55DB370` is a
static function in no vtable. It is a plain C++ helper. That is why the toggle work
never had a UObject to hook.

`vtables.py diff <Class>` prints only the overrides and new virtuals against the
resolved base — a 30-line diff instead of a 347-slot dump.

---

## 7. Does this supersede `docs/lokiassetmanager-vtable-dump.md`?

**For obtaining a vtable: yes, completely.** That document's method was: run the
game → find the CDO by FName → read its vtable pointer → `usmapdump vtdump` against
the live process → hand-identify slots by prologue shape and by hunting UE_LOG
strings. It produced **one** vtable, 128 slots, over a session, and needed a running
game.

`vtables.py` produces **3,599 named vtables in 3 seconds, offline**, reproduces that
one exactly (8/8 spot-checked slots), reproduces its hand-derived slot 94 / 131 / 132
identifications, and corrects one of its recorded numbers (§4a).

**For everything else in that document: no.** Its live-process material — the
singleton-vs-CDO filter (`ObjectFlags` bit `0x10` at `+0x0C`), the `AssetTypeMap`
walk at `singleton+0x478`, the FName-layout proof, the baked FName index tables, and
the whole Mission/MissionPool scan-asymmetry investigation — is orthogonal and still
current. Nothing here touches a live process.

The one method that document used and this one cannot: reading **live object state**.
Static analysis gives you the vtable; only the running game tells you which object is
the singleton.

---

## 8. Limitations — measured, not assumed

* **Many-to-one is real and irreversible.** 243 vtables carry more than one class.
  MSVC folds identical vtables (ICF), so a class that adds no virtual of its own gets
  its base's vtable *address*. `0x076EF750` is assigned to 330 classes here — and an
  earlier session independently observed **10 distinct CDOs sharing it live**
  (`lokiassetmanager-vtable-dump.md:898`). `vtable → class` cannot be inverted;
  `class → vtable` is fine.
* **Piece length is an upper bound** (see §1). `vtables.py` flags pieces whose start
  is unproven.
* **`.text` demand-decrypt still bites, but far less than for string xref.** Slot
  *targets* land in decrypted pages at **96.8%** overall — but split by kind:
  **inherited slots 97.4%, class-own slots 72.2%** (452,610 and 26,961 slots over
  4,042 class/base pairs), against a `.text` baseline of **52.29%** of pages readable.
  Crucially, a vtable slot gives you a **correct address even when the body is not
  decrypted** — unlike a string xref, where an undecrypted page yields no signal at
  all. `ULokiAbilitySystemComponent`'s own overrides are mostly `[page not decrypted]`
  in this menu-state dump; their addresses are still exact.
* **16 classes unresolved**: 7 whose constructor page was never decrypted and 9 with
  no vtable LEA anywhere in the constructor. Reported explicitly (`conf=NO-CODE` /
  `NONE`), never guessed.
* **Byte-scan, not disassembly.** `lea`/`jmp`/`jcc` detection is regex over raw bytes.
  Every conclusion is corroborated by an independent control rather than trusted.
* **Non-UObject vtables are unnamed.** The 11,163 pieces in the 8–31-slot band are
  real C++ vtables (interfaces, `FTickFunction`, deleters, RHI classes) with no UE
  reflection boilerplate, so nothing names them. The D3D12 crash-class vtables from
  S40 (`0x7B9E188`, `0x7B9DE88`) are in this band.

---

## 9. Reproduce

```powershell
cd "G:\git\Supervive Revival Project\tools\strxref"
python strxref.py --rebuild      # ~20 s, string/xref index (prerequisite)
python vtables.py scan           # ~3 s, prints the 7-check validation block
python vtables.py stats
python vtables.py bench --span tail ; python vtables.py bench --span head
python vtables.py reflect
```

`index/vtables.idx` is 4.4 MB and is git-ignored alongside `strxref.idx`.
