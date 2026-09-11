# S102 — Validating and naming the project's recorded code addresses

**Date:** 2026-07-26 · **Inputs:** `dumps/merged.dump.exe` (read-only), `docs/**`,
`memory/*.md`, `tools/sigbypass-mod/*.cpp`, `tools/re/*.py`, `CLAUDE.md`, git log
· **No game launch, no injection — 100% offline.**

**Deliverables**

| path | what |
|---|---|
| `docs/symbols.csv` | the symbol database — 683 rows, one per recorded address |
| `tools/strxref/harvest_addrs.py` | sweeps the repo + memory + git log for recorded RVAs |
| `tools/strxref/name_addrs.py` | validates + names them, emits the CSV |
| `tools/strxref/uereflect.py` | **the big one** — recovers 32,066 UE reflection symbols offline |
| `tools/strxref/index/uesymbols.json` | that symbol table (git-ignored, rebuild in ~90 s) |

---

## 1. Headline

**The project's recorded addresses are accurate. Zero confirmed record bugs.**

Of 683 recorded addresses, 56 could be checked against an independent, externally
validated symbol table and **every one that carries a recorded name matches it**.
The 17 rows the pipeline still labels `DISAGREES` were each inspected by hand and
are all artifacts of *my* name-extraction picking a neighbouring token out of the
prose, not errors in the record.

The genuinely new thing is the instrument built to do the checking.

---

## 2. ★ The main result: UE reflection symbols recovered offline

`.rdata` is 99.64% readable (FK-3 is false), and UE's code generator leaves two
pointer tables in it that survive the packer intact. Parsing them yields:

| | count |
|---|---:|
| `Z_Construct_UFunction_<Class>_<Name>` stubs named | **16,998** |
| — name independently re-verified through the `FFunctionParams` chain | **16,996** (0 mismatches) |
| native **exec thunks** named (`.data` registration table) | **16,214** (14,385 distinct names) |
| — with an unambiguous owning class | 13,019 |
| UE classes named | **1,258 / 1,258** |
| **distinct code RVAs named** | **32,066** |

Against a prior baseline of ~617 known addresses out of ~120,000 functions
(~0.5%), this is a **~52× increase** in named code.

### Why it can be trusted — three independent external checks

None of these use the tool's own assumptions.

1. **Class arity.** The `FClassFunctionLinkInfo` run for
   `ULokiAbilitySystemComponent` is 138 qwords = **69 entries**.
   `docs/session-100-gas-api-dump.txt`, captured live months earlier by
   `usmapdump`, records exactly **"69 UFunctions"** for that class.
2. **FunctionFlags.** `FFunctionParams+0x38` holds `FunctionFlags`. Compared to
   the same live dump: **1,557 match, 0 mismatch.**
3. **Exec-thunk addresses.** The `.data` table maps name → the exec thunk, i.e.
   precisely the `UFunction.Func @ +0xE0` value the project's native-call
   primitive invokes. Compared to that dump's `thunk=` column: **1,404 match, 0
   mismatch**, under a *single* 64K-aligned module base recovered from the data
   itself.

### Free by-product: the session-100 module base

That base is **`0x7FF6E7D30000`**. It was never recorded, which made every
absolute address in `session-100-gas-api-dump.txt` unusable. All ~1,566 of them
now convert to RVAs: `RVA = absolute − 0x7FF6E7D30000`.

### Structures, as measured (not from UE source assumptions)

```
.rdata  FClassFunctionLinkInfo[]   { UFunction*(*Create)(), const char* NameUTF8 }   16 B
.data   FFunctionParams            +0x00 OuterFunc(class Z_Construct)
                                   +0x10 const char* NameUTF8
                                   +0x38 uint32 FunctionFlags
.rdata  FClassRegisterCompiledInInfo  +0x00 OuterRegister  +0x08 InnerRegister
                                      +0x10 const TCHAR* Name   <- UTF-16
.data   native registration        +0x00 const char* Name  +0x08 exec thunk
                                   +0x10 secondary fn ptr        stride 0x48
```

---

## 3. Three near-misses — each one nearly became a fourth false-known

Recording these because the brief asked me not to add a third FK, and all three
were caught only by insisting on an independent check.

**(a) Off-by-one across the whole symbol table.** `FClassFunctionLinkInfo{fn,name}`
and `FNameNativePtrPair{name,fn}` are *locally indistinguishable* — both are runs
of alternating (code-ptr, string-ptr) qwords. Only the run's **phase** separates
them. My first scan assumed name-first and produced 16,458 entries in which every
name was attached to the **next** function's stub. It looked perfectly plausible.
Caught by the arity check (69) and by the stub bytes disassembling to the textbook
`Z_Construct` body. The `FFunctionParams` name re-verification now guards this
permanently: a phase error makes all 16,996 names mismatch.

**(b) Class names invented by a "nearest string" heuristic.** It confidently
labelled `APawn` as `ELegendPosition` and `AActor` as `Engine`. Replaced with the
exact `+0x10` structural rule. Coverage went 732 → **1,258 / 1,258**, and the
false names disappeared. *Root cause of the original 732: class names are
**UTF-16**, and the scan was ASCII-only — literally the same trap that created
FK-4.*

**(c) Three fabricated "record bugs".** `docs/tutorial-playability-plan.md` — an
*active* plan doc — appeared to have three wrong addresses:

| recorded | reflection said |
|---|---|
| `GetTrainingManager  native+0x5483C00` | `ALokiTeamState_TeamOnly::GetDropLeader` |
| `TryShowPrompt       native+0x52FD980` | `ALokiCharacter::AuthRemoveAbilityPoint` |
| `GetSkillState       native+0x44157D0` | `UAbilitySystemComponent::GetUserAbilityActivationInhibited` |

**All three records are CORRECT.** MSVC `/OPT:ICF` folds byte-identical
functions, so one address is the registered entry for several UFunctions; the
recorded name was present, just not first in the list. Measured: **469 of 15,068
exec thunks (3.1%) carry more than one name**, and folding is independently
confirmed (306 short thunks sampled → only 284 distinct bodies, one shared 7
ways). Had I reported these, the project would have "fixed" three correct
addresses.

> **Operational note.** ICF is worth knowing about generally: an RVA is not a
> unique function identity in this build. `symbols.csv` marks these
> `EXACT-AMBIG` and lists every folded name.

---

## 4. The 683 recorded addresses

Harvested from 584 files (119 MB) plus every git commit message. Anchored
(`base+0x…`) 78 · label-adjacent 152 · bare in-range literals 584 · appearing in
shim/probe **source** (load-bearing, hardcoded) 119.

### Verdicts

| verdict | n | meaning |
|---|---:|---|
| `ENTRY-OK` | 226 | the RVA is itself a function entry |
| `INTERIOR` | 213 | inside a function — correct for patch/gate sites |
| `UNVERIFIABLE` | 225 | in `.text` but its 4 KB page is **all-zero in this dump** |
| `NOT-CODE` | 19 | in `.rdata`/`.data` — vtables, CDOs, params structs |

### Name checks

| check | n |
|---|---:|
| `AGREES` | 67 |
| `NO-NAME-EVIDENCE` | 124 |
| `CLASS-ONLY-EVIDENCE` | 3 |
| `DISAGREES` | 17 — **all inspected, all my extractor's fault, none a record bug** |
| `NO-RECORDED-NAME` | 228 — the record never named it |
| `n/a` | 244 — unverifiable / not code |

- **56** matched an exact reflection symbol.
- **352** got **exact** function bounds from the recovered unwind table.
- **40** addresses that the record left unnamed now have a proposed name
  (e.g. `0x12C5060 → UObject::FinishDestroy`, `0x2036544 → FChunkCacheWorker`,
  `0x20502D1 → Pak_Mount`, `0x2044473 → SkipOptionalPakFiles`).

### Harvest precision — stated, not hidden

Addresses written as `base+0x…`, adjacent to a label, or hardcoded in shim/probe
source are unambiguous. Bare hex literals in prose are not: the sweep keeps any
value ≥ 1 MB that lands in `.text` and is not introduced by a rejected key
(`flags=`, `kType_`, `ufunc=`, …). Some slip through — `0x0100000` in
`tools/re/find_guobjectarray.py` is an RPM buffer *size*, and the two
`ClientRestart`/`ServerVerifyViewTarget` flag words above are the same shape.

Measured proxy for how many are real addresses: of rows in a decrypted page,
**81%** of bare-only records (210/259) and **79%** of strong records (142/180)
land inside a recovered unwind-table function. The two rates being equal says the
bare-literal channel is not markedly noisier than the anchored one — but treat
`record_kind = bare` rows with a single source as unconfirmed.

### The 225 unverifiable are a coverage limit, not a defect

Their `.text` page was never decrypted in `merged.dump.exe`. That is 33% of the
recorded set against a 47.7% zero-page rate image-wide — recorded addresses skew
toward code the game actually runs, as expected. **This is not evidence the
addresses are wrong.** It lifts by dumping from more game states (especially
in-match) and re-running `usmapdump mergedumps`.

---

## 5. Incidental confirmations

- `ServerVerifyViewTarget = 0x80220CC2` and `ClientRestart = 0x01020CC2`, recorded
  in `memory/supervive-dedicated-server-status.md`, are **exactly** the
  `FunctionFlags` the offline table extracts for
  `APlayerController::ServerVerifyViewTarget` / `::ClientRestart`. (They are flag
  words, not addresses — two `symbols.csv` rows are that harvest artifact.)
- `0x52B3400` = exec thunk `ULokiAssetStatics::GetDefaultCosmeticsBundleIdForHeroId`,
  with `0x55899C0` its native impl — exactly as
  `docs/next-session-prompt-skins-render.md` recorded.
- `0x562EA00`, the hero-resolve probe target, references
  `'Failed to load hero asset with ID %s'` — confirms the subsystem.
- The whole `ALokiTrainingSkill` block in `tutorial-playability-plan.md`
  (`TryTestSkill`, `MarkTestCompleted`, `CancelTest`, `CanTestSkill`,
  `ShouldTestSkill`, `IsDisabledForConfig`) and the
  `ULokiGameModeDropPlaneComponent` block (`AddPlayerToDropPlane`, `SetDropPlane`,
  `GeneratePlanePoints`) verify **exactly**.

---

## 6. What remains blocked

1. **`.text` demand-decrypt is still the binding constraint.** 47.7% of `.text`
   pages are zero, so 225 recorded addresses cannot be checked at all and
   string-based naming is capped. *Not structural* — dump from more states
   (especially in a match) and re-merge.
2. **No name → C++ implementation.** The tables give exec thunks and
   `Z_Construct` stubs. The exec thunk calls the implementation, but the third
   pointer in the `.data` record is it only **33.8%** of the time (measured over
   2,621 samples), so nothing is claimed. Recovering implementations needs real
   call-target decoding inside each thunk.
3. **Most functions reference no strings.** `ProcessInternal` (`0x13454A0`),
   `FindVM` (`0x57AB180`), `FPrimaryAssetId::ToString` (`0x12F4230`) touch zero
   literals. String-xref names the subset that logs; it is not a general
   disassembler.
4. **RTTI is stripped**, so vtables give shape and slot targets but no class names.
5. **ICF** means an RVA is not a unique identity for 3.1% of exec thunks.

---

## 7. Reproduce

```powershell
cd "G:\git\Supervive Revival Project\tools\strxref"
python strxref.py --rebuild      # ~20 s, string + xref index
python uereflect.py              # ~90 s -> index/uesymbols.json  (32,066 symbols)
python harvest_addrs.py          # sweep the repo for recorded RVAs
python name_addrs.py             # -> docs/symbols.csv
```

`symbols.csv` columns: `rva, section, recorded_name, proposed_name,
proposed_class, confidence, verdict, name_check, fn_entry, fn_offset, fn_tier,
fn_extent, n_strings, evidence, why, record_kind, n_sources, sources,
recorded_alts, sample_context`.

`confidence`: `EXACT` (verified reflection symbol) · `EXACT-AMBIG` (ICF-folded,
several names) · `HIGH`/`MED`/`LOW` (inferred from strings) · `CLASS-ONLY`
(delegate literal — class certain, method not).
