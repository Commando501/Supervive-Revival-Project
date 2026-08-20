# LANE 6 — AUDIT OF THE RM_DROPPOD INSTRUMENT

## ⚠⚠ READ FIRST — THE FILE IS BEING EDITED CONCURRENTLY, AND THE READOUT IS ALREADY WRITTEN

`tools/sigbypass-mod/tutorial_launch.cpp` changed **three times during this audit**: `git diff --stat` read `+23`, then `+448`, then `+464/-3`; md5 went `2f38471190735789…` → `6a5ce4b5b76e96dd…`. Another lane is writing the in-arm pod readout **right now**. All line numbers below are as of md5 `6a5ce4b5b76e96dd58a67cb2a4debcb1`, 14,165 lines — **cite the symbol, verify the line.**

**The blueprint you asked for exists as code already.** Present and uncommitted: `g_dpPodAct` latch (decl 6158-6173, fill 6236-6237 + 6268-6272), `PdFindPropOn` (9778), `PdFmtValue` (9805), `PdPodField` (9873), `PdPodLoc` (9907), `PdPodSweep` (9929), `PdPodCalibrate` (9964), `PdPodOne` (9997), `PdPodDump` (10060), knobs at 9737-9766, call sites at 10151 / 10196 / 10209 / 10234. **Do not write a second one.** What follows answers (1)-(8) and then audits what is there.

---

## (1) `PropOffsetSuper(cls,name)` — tutorial_launch.cpp:2021-2029

```
static uint32_t PropOffsetSuper(uintptr_t cls,const char* name){
    int g=0; while(LooksLikePtr(cls)&&g++<12){
        uintptr_t f=SafeReadable((void*)(cls+0x58),8)?*(uintptr_t*)(cls+0x58):0; int i=0;
        while(LooksLikePtr(f)&&i<300){ if(NameIs(f,name)){ if(SafeReadable((void*)(f+FPROP_OFFSET),4)) return *(uint32_t*)(f+FPROP_OFFSET); } ... }
        cls=SafeReadable((void*)(cls+0x48),8)?*(uintptr_t*)(cls+0x48):0; }
    return 0xFFFFFFFF; }
```

- **Walks both**: per class it walks that class's OWN `ChildProperties` (`cls+0x58`), then advances to `SuperStruct` (`cls+0x48`). **Leaf-first**, so a Blueprint override of a name SHADOWS the native/AS one. [M, from the code]
- **Failure return `0xFFFFFFFF`.** ⚠ `0` is a legal offset, so callers **must** compare against `0xFFFFFFFF`, never truthiness. (`PdPodField` does; `ReadProp` at 3735-3739 returns the sentinel `0xDEADBEEF` instead.)
- **Depth limits — both are SILENT TRUNCATIONS that return "not found":** ≤12 super hops, ≤300 properties per class. **Neither binds here** [M]: `BP_DropPod_Tutorial_C ← BP_DropPod_C ← LokiDropPod ← LokiDropPodBase ← LokiActor ← Actor ← Object` is **7** hops (S130 census chain string), `ALokiDropPod` declares **40** UPROPERTYs (`tools/asdump/out/a/GameMode.DropPhase.LokiDropPod.as.txt`, counted), `AActor` **114** (S130 §11 PropPointers walk).
- **Other failure modes:** a bad `NameId` decode makes `NameIs` return false → silent miss; `f+0x44` unreadable → the loop *continues past the match* and can return a later same-named property. Both read as "not resolved".
- **Constants:** line 26 `CLASS_OFF=0x18, NAME_OFF=0x20, UFUNC_CHILDPROPS=0x58, UFUNC_FUNC=0xE0`; line 27 `FIELD_NEXT=0x18, FPROP_OFFSET=0x44, FPROP_FLAGS=0x38`. `FFIELD_CLASS=0x08`, `FFIELDCLASS_NAME=0x00`, `FPROP_ARRAYDIM=0x30`, `FPROP_ELEMSIZE=0x34`, `FSTRUCTPROP_STRUCT=0x70` at **7984-7991** (numbering pre-edit; now ~8007-8014), with the S126 correction block above them.
  - **Grades:** `FPROP_OFFSET=0x44` / `FPROP_FLAGS=0x38` / `FIELD_NEXT=0x18` / `CHILDPROPS=0x58` are **[M]** — this file's daily working set across dozens of proven calls. `FPROP_ELEMSIZE=0x34` is **[I] by arithmetic**, *upgraded to [M] in flight*: the RM_POOLSPAWN sanity gate printed `16 slot(s) inspected, pointer-sized OK=10, FTransform OK=2, FAILURES=0 => PASS` (`RESULT-poolspawn-cdopoke-s130.txt:108`). `FSTRUCTPROP_STRUCT=0x70` is **[M] via FK-14** (type-carrying families at `+0x70`; `FArrayProperty` is the lone deviant at `+0x78` and is not used here).

## (2) `PdTypeOf` (now 8290) and the pointer-resolver question

`PdTypeOf(prop,type,tsz,sname,ssz)` returns **the FFieldClass FName as a string** — `"IntProperty"`, `"BoolProperty"`, `"StructProperty"`, `"ObjectProperty"`, `"EnumProperty"`, … — via `*(prop+0x08)` → `+0x00`. For `StructProperty` only, it additionally fills `sname` with the `UScriptStruct` FName from `*(prop+0x70)` (`"Vector"`, `"Transform"`). It returns **nothing else** — no size, no enum, no offset; the caller reads `FPROP_OFFSET`/`FPROP_ELEMSIZE` itself (`PdWalkParams`, 8304).

**Before this session there was NO helper returning an FProperty POINTER for a NAMED property on a CLASS.** `PropOffsetSuper` returns only the offset; `ParamOffset` (1407) walks a *UFunction param chain* (cap `i<40`, no super walk); `ResolveFuncOnClass`/`ResolveFuncSuper` return UFunctions. **The concurrent lane has now added exactly that helper**: `PdFindPropOn(cls,name,&off,&elem,type,tsz,sname,ssz,owner,osz)` at **9778**, returning `uintptr_t prop` (0 = not found), same 12-super walk, prop cap raised to **400**, and it also reports the **owning class name** — which `PropOffsetSuper` cannot, and which is what makes a shadowed name visible. **Use it; do not write another.**

## (3) BOOL PROPERTIES — and the calibration you asked me to confirm

**Existing practice before this session: there was NO reflected-bool decoder.** Every bool in the file is a raw byte read at a by-name offset — e.g. 4004 `PropOffsetSuper(cls,"TrainingActive") … *(uint8_t*)(obj+o)==1`, and `PdCdoOne` (9563+) reads `*(uint8_t*)(o+0x6C)` at a **hardcoded** `KPDCDOOFF`. **No code in this file has ever read `FBoolProperty`'s mask fields.**

**Layout in this build:** `FBoolProperty` adds `FieldSize/ByteOffset/ByteMask/FieldMask` at **`FProperty+0x70..+0x73`**. Grade: **[I]** — stock UE5 layout resting on FK-14's **[M]** `sizeof(FProperty)==0x70`. The new code declares them at 9760-9763 and its `plausible` guard (`fs 1..8 && bm!=0 && fm!=0 && bo<=8`, 9821) falls back to `raw!=0` with a printed warning. That is the right shape, but **it has no positive control** (see finding **E** below).

### ✅ CONFIRMED — both calibration names ARE reflected UPROPERTYs, and I have their exact predicted masks

`bCanEverReplicate` and `bEnablePooling` are **native `AActor` UHT `FBoolPropertyParams` records** — both name literals are present in `dumps/tutorial-hero/…dump.exe` (`bCanEverReplicate` @ `.rdata 0x7F22F60`, `bEnablePooling` @ `0x7F237D0`, **1 occurrence each**, whole-file byte search). UHT-registered properties are constructed into the owning `UClass`'s `ChildProperties` FField chain — **[I, strong]**, not [M], because nothing has read one by name in this build.

**The strong empirical support for that [I]:** `PropOffsetSuper` **already resolves native engine UPROPERTYs in flight** — `RootComponent` (AActor) + `RelativeLocation` (USceneComponent) at 7171/7174, which produced `control actor = 0x1D011F0A030 loc=(-3206.4,5070.5,100.0)` (`RESULT-poolspawn-cdopoke-s130.txt:145`), and `TeamDropPodClass` on the **Angelscript** class `LokiDropShip` → `TeamDropPodClass@0x478` (`RESULT-routeE-after-poke-s130.txt:68`, resolved at 9520). **[M] both native and Angelscript UPROPERTYs are in `ChildProperties` in this build.** They were object/struct properties, not bools — which is the residual gap the calibration closes.

**★ I decoded the exact expected values offline, so the calibration is now four-way and pre-registerable.** `scratchpad/s130/tools/boolscan.py --name <n>` disassembles each record's `SetBitFunc` (13,156 Bool records; the tool reproduces its gold value per `scratchpad/s130/tools/README.md`):

| name | `SetBitFunc` | disp | kind | predicted `FieldMask` |
|---|---|---|---|---|
| `bCanEverReplicate` | `0x02078900 mov byte [rcx+0x6c],1` | **0x6C** | **standalone byte** | **0xFF** |
| `bEnablePooling` | `0x03368BF0 mov byte [rcx+0x2d3],1` | **0x2D3** | standalone byte | 0xFF |
| `bHidden` | `0x03368980 or byte [rcx+0x68],0x80` | **0x68** | **bitfield** | **0x80** |
| `bAlwaysRelevant` | `0x032F7100 or byte [rcx+0x68],8` | **0x68** | **bitfield** | **0x08** |

⇒ **`bHidden` + `bAlwaysRelevant` are a ready-made TWO-SIDED control for the bool metadata**: same `Offset_Internal` (0x68), *different* `ByteMask` (0x80 vs 0x08). No constant-garbage read can pass that. `bCanEverReplicate`/`bEnablePooling` calibrate the *offset* path against S130's independently-measured 0x6C/0x2D3.
⚠ **`boolscan.py`'s `mask=` column is the instruction IMMEDIATE, not `FieldMask`** — it reads `0x1` for the two `mov` cases, where the real field mask is `0xFF`. Do not copy that column into a prediction.

**And the AS bools are standalone bytes too** [M, from AS bytecode `this+N` displacements in `GameMode.DropPhase.LokiDropPod.as.txt`]: `bPilotHasPodControl` **+1116**, `bIsTeamLeaderPod` **+1117** — adjacent distinct offsets, so Angelscript does not pack bools into bitfields. `*(uint8_t*)` is correct for `bIsTeamLeaderPod`; predicted `FieldMask` **0xFF**.

## (4) `DpCensus` / `DPV_` — ✅ `POD && ACTOR` is correct, and I verified the 7→9 split

- Flags: 6127 `DPV_KNOWN=1, DPV_PLANE=2, DPV_POD=4, DPV_SHIP=8, DPV_ACTOR=16`. `DpEvalClass` (6178-6193) walks ≤12 supers doing `strstr` for Plane/Pod/Ship and **`strcmp(n,"Actor")==0`** — exact, with an in-code comment explaining why substring would take `ActorComponent`.
- **`DPV_ACTOR` is reliable and there is NO order dependence.** The latch side-effect at 6252 (`if(v&DPV_ACTOR && !g_dpAnyActorCls) g_dpAnyActorCls=cls;`) reads `v` *after* `DpClassVerdict` has fully computed it (6251); the memo (6194-6207) caches the complete verdict word, never a partial one. `g_dpAnyActorCls` is a **consumer** of the bit, not a producer.
- **✅ [M] the S130 "DropPod +2" is 1 actor + 1 AnimInstance, NOT 2 actors** — `RESULT-routeE-after-poke-s130.txt:223-225`:
  `after-E1 *** NEW *** 0x1D1A4DA2740 'ABP_DropPod_C' chain=ABP_DropPod_C<-AnimInstance<-Object`
  `after-E1 *** NEW *** 0x1D015C87910 'BP_DropPod_Tutorial_C' chain=…<-LokiActor<-Actor<-Object`
- **[M] the `pod` bucket is contaminated by design.** Enumerating the 7 non-archetype pod rows of `C0-BEFORE` (lines 61-66 + 25 + 32): **3 actors** (`BP_DropPod_Tutorial_C` ×3) + **2 AnimInstances** (`ABP_DropPod_C` ×2) + **2 widgets** (`WBP_UI_DropPodControls`, `WBP_UI_DropPodIndicator_Animated`) = 7, matching `DropPod=7` exactly. None of the four non-actors carries a leaf `Actor` in its chain ⇒ `POD && ACTOR` selects exactly the 3. Same for `DropPlane=4`, of which only 1 is an actor.

## (5) COST — ✅ no second sweep needed; the latch is already at the right line

`DpCensus` measured **1,219 / 1,406 / 1,531 ms** per sweep in `RESULT-routeE-after-poke-s130.txt:67/225/288`, and `PdCdoFlags` (9637) adds its own one-pass walk twice per arm at **~2,000-2,300 ms** (CLAUDE.md). A third sweep for the readout would be a self-inflicted multi-second game-thread hitch.

**The correct latch point is inside `DpCensus`'s inner loop, after `c.hits++` and after the archetype `continue`** — and that is precisely where it now sits, **line 6268-6272**, with the reset at **6236-6237**. Both are right:
- after `continue` at 6263 ⇒ CDOs/`_GEN_VARIABLE` are excluded automatically;
- reset on **every** census (not just `record`) ⇒ the latch always describes the most recent sweep, and `g_dpPodLatchWhen` names which one.

## (6) SAFE READS

| helper | line | precondition | can it fault? |
|---|---|---|---|
| `SafeReadable(a,sz)` | 404 | none | **TOCTOU** — `VirtualQuery` then the caller reads. A page decommitted in between faults. Also rejects a read spanning two regions even if both are committed (false negative). |
| `LooksLikePtr(v)` | 427 | none | no — pure arithmetic (`≥0x10000`, `<2^48`, 8-aligned) |
| `GetFNameStr(id,out,cap)` | 428 | `g_modBase` set | no — every read guarded; returns false on any miss |
| `NameId(obj)` / `ClassOf(obj)` | 436 / 438 | none | no — guarded; **return 0 on failure, which is indistinguishable from a real 0** |
| `GcAlive(obj)` | 1973-1981 | `g_modBase` set | no. Tests: `LooksLikePtr` ∧ vtable inside the image ∧ `NamePrivate != 0`. **Call it before touching any latched pointer.** |
| `PhChainHas(cls,sub,out,sz)` | 5512 | none | no — ≤12 hops, `GetFNameStr`-guarded |
| `Marker`/`Markerf` | 402 / 403 | none | no |

**SEH convention [M]:** `SEH_FILTER(ep)` = `SehCap` when `KFAULTINFO`, else `SehDump` (1010/1012); `DP_FAULT` = `FaultStr()` or a compiled-out string (6115/6117). Every ladder body is wrapped: `DoDropPod` (10192) and `DoPoolSpawn` (11417) each `__try { …LadderStep(); } __except(SEH_FILTER(GetExceptionInformation())){ … g_done=1; }`. **Anything you add inside a ladder step inherits that guard.** ⚠ `PdFinalReport` (10200) and `SpFinalReport` (11427) are called from the **worker** at 13918/13944 (and the `SpFinalReport` equivalents) with **NO `__try`** — see finding **F**.
⚠ **`FaultStr()`/`DP_FAULT` is a PROCESS-WIDE last-fault view** (comment at 8280+): printing it in a summary written later decorates one call with another's exception record. E1 already snapshots its own into `g_pdE1Flt`.

## (7) OUTPUT — the marker file, and the line cap is REAL and MEASURED

- Path: `docs\tutorial-launch-marker.txt` (line 22).
- `Marker()` (402) opens **`FILE_APPEND_DATA` / `OPEN_ALWAYS`** — it appends and has **no length cap**; the handle is opened and closed per call, so everything written is already flushed to disk when the process dies.
- **The truncation is at `Worker()` entry, line 13016**: `CreateFileA(..., CREATE_ALWAYS, ...)` — so **every injection wipes the file** (FK-25). `configs/fk24-stage.ps1:280` copies it off after each stage into `docs/fk24-stage-<Label>-<n>-<tag>.txt`; the stager also reads the marker **before** injecting (`:317`, `:320`).
  ⚠ A **manual** `tools/inject/inject.exe mmap <pid> <dll>` — the S130 recipe for the 2nd/3rd DLL — **bypasses that copy-off entirely.** Copy the marker by hand between manual maps.
- **✅ THE LINE CAP IS `Markerf`, 511 CHARS, AND TRUNCATION SILENTLY EATS THE TRAILING `\r\n`.** `char b[512]` + `_vsnprintf_s(...,_TRUNCATE,...)`. Confirmed against the artifact: `RESULT-routeE-after-poke-s130.txt:208` is **1,138** chars = **two** truncated `Markerf`s concatenated, splitting at index **1,022 = 2 × 511**, mid-word (`…stores the asC` `[PD] sig SpawnDropPo…`), from the two calls at 8893 and `PdWalkParams`. **`Marker()` with a long literal is uncapped** — that is why the 785/1138-char literal blocks survive intact. ⇒ **for anything over ~450 chars use `Marker` with a literal, or split into several `Markerf`s.**

## (8) BUILD

```powershell
cd "G:\git\Supervive Revival Project\tools\sigbypass-mod"
.\build.ps1 -Name tutorial_launch -Variant poolspawn-cdopoke
.\build.ps1 -Name tutorial_launch -Variant poolspawn-cdoctrl
.\build.ps1 -Name tutorial_launch -Variant droppod-pe-cdopoke
.\build.ps1 -Name tutorial_launch -Variant droppod-pe-cdoctrl
.\build.ps1 -Name tutorial_launch -Variant dropplane-b1only     # ← key is HYPHENATED
```
Outputs to `build\`; **`-InPlace` writes beside the sources (where the injectors load from)**. Filename rule is `build.ps1:875` — `variant -replace '-','_'` ⇒ `build\tutorial_launch_poolspawn_cdopoke.dll`, `…_dropplane_b1only.dll`. **The doc's `dropplane_b1only` is the FILE stem; the `-Variant` key is `dropplane-b1only`.**

Definitions (`build.ps1`): `poolspawn-cdoctrl` :511, `poolspawn-cdopoke` :512, `droppod-pe-cdoctrl` :380, `droppod-pe-cdopoke` :381, `dropplane-b1only` :268.

**✅ THE `-Variant`-WITHOUT-`-Name` TRAP IS FIXED — the note in your brief is stale.** `build.ps1:81-83` now `throw`s (S125 guard). It cannot silently build the default set any more.

**`.text` sha256 is NOT computed by build.ps1 and NOT by verify_dll.py.** The snippet is `docs/fk13-routeb-test-card.md:283-292`:
```python
import hashlib,struct
d=open(r'build\tutorial_launch_poolspawn_cdopoke.dll','rb').read()
pe=struct.unpack_from('<I',d,0x3C)[0]; n=struct.unpack_from('<H',d,pe+6)[0]
so=pe+24+struct.unpack_from('<H',d,pe+20)[0]
for i in range(n):
    b=so+i*40; nm=d[b:b+8].rstrip(b'\0').decode()
    vsz,va,rsz,raw=struct.unpack_from('<IIII',d,b+8)
    if nm=='.text': print('.text sha256', hashlib.sha256(d[raw:raw+rsz]).hexdigest()[:16], rsz,'B')
```
`verify_dll.py` is the **separate** artifact gate (no C++ EH, no dynamic CRT, DLL shape) — run both.
⚠ **The S130 hashes in `docs/next-session-prompt-s131.md` §6 are now UNREPRODUCIBLE** — the readout adds ~464 lines of live code to the same TU, so every `tutorial_launch` variant's `.text` moves. **Re-baseline the table; do not treat a mismatch as a regression.**

---

## AUDIT OF THE ALREADY-WRITTEN READOUT — 6 findings

**A. ⚠⚠ RM_POOLSPAWN GETS NO POD DUMP AT ALL — the largest gap, and it costs the best control.** All four `PdPodDump` call sites (10151, 10196, 10209, 10234) are in `PdLadderStep`/`PdFinalReport`. `SpLadderStep` (11335) and `SpFinalReport` (11427) have none. This matters twice over:
  1. Your brief asked for it, and **`poolspawn` is the arm with no attribution caveat** — S130's E-verdict reads `E1 RAN BUT IS NOT ATTRIBUTABLE` (E0c unsatisfiable), while `poolspawn-cdopoke` carries `P0c STRONG PASS 0.00 uu on |ref|=8377`. Pods that only exist in the un-attributable arm are a weaker result than pods in the clean one.
  2. ★ **`RM_POOLSPAWN`'s pods are the perfect NEGATIVE CONTROL for `RM_DROPPOD`'s.** `SpawnPoolableActorFromClass*` never calls `InitializeDropPod`, so all three discriminators must read the **class defaults** (`PodTeamIndex = -1`, `CurrPodDestination = (0,0,0)`, `bIsTeamLeaderPod = false`). Same instrument, same class, opposite expected answer. Without it, "the fields changed" has no within-project null.
  **Insert:** `PdPodDump("after-P1",1)` after `DpCensus("after-P1",…)` (11380), same for after-P2 (11394) / after-P3 (11408), and `PdPodDump("P4-AFTER (worker)",0)` after `DpCensus("P4-AFTER",…)` (11432) — each behind the same `KSPMINICENSUS` guard the census uses, or the latch is stale. **Also print `g_spP1Ret`/`g_spP2Ret`/`g_spP3Ret` through `PdPodOne` directly** — RM_POOLSPAWN is the one mode that *holds the returned actor pointer*, so it needs no latch at all and that read is strictly stronger than a census inference.

**B. ⚠⚠ THE BOOL METADATA HAS NO POSITIVE CONTROL — and one is free.** `PdPodCalibrate` (9964) checks only that `bCanEverReplicate`→`0x6C` and `bEnablePooling`→`0x2D3`. It never validates `FBOOLPROP_FIELDSIZE/BYTEOFFSET/BYTEMASK/FIELDMASK` at `+0x70..+0x73`, which are **[I]**, and `bIsTeamLeaderPod` — one of the three headline discriminators — is decoded through them. Add two `PdFindPropOn` calls and assert the table in (3): `bHidden` and `bAlwaysRelevant` must both return `Offset_Internal 0x68` with `ByteMask 0x80` and `0x08`. Same offset, different mask ⇒ two-sided, unfalsifiable by garbage. And assert `bCanEverReplicate`'s own `ByteMask == 0xFF` (its `SetBitFunc` is a full-byte `mov`, not an `or`). **Cost: 2 lookups. Benefit: turns the bool path from [I] to [M] in-arm.**

**C. ⚠ `PdPodSweep`'s `boring` filter suppresses the headline success value.** 9945-9947 skips `val=="0"`, and `PdFmtValue` renders `IntProperty` as `%d` — so **`PodTeamIndex = 0`, the cleanest discriminator, is suppressed inside the sweep**, and the summary line calls the survivors "non-default properties" when the test is a *value* test, not a *default* test. The explicit `PdPodField` line still prints it, so nothing is lost — but reword the summary, or exempt the named discriminators from the filter.

**D. ⚠ `isNew` ignores `g_dpBeforeOverflow`.** `PdPodDump` (10071-10073) diffs against `g_dpBefore[768]` but never consults `g_dpBeforeOverflow`, which `DpCensus` sets and warns about separately. On overflow a pre-existing pod prints `*** NEW ***`. Impact is theoretical here (11 tracked objects vs a 768 cap) — one line to close.

**E. ⚠ `g_dpPodAct[64]` overflow degrades to a SUBSET, and `PdPodDump` says so (10064) — good.** But `g_pdPodS0[64]` (the movement-sample table) shares no such warning path beyond `[sample table FULL — no movement delta]` (10054). Fine as written; just do not read a missing delta as "stationary".

**F. ⚠ `PdFinalReport` / `SpFinalReport` run on the WORKER with no SEH guard.** Called at 13918 / 13944 (and the `Sp` equivalents) outside any `__try`. They now do `DpCensus` **plus** `PdPodDump` — i.e. hundreds of `SafeReadable`-then-read pairs against objects the game thread may be destroying concurrently. `SafeReadable` is TOCTOU; an unhandled AV here kills the process **at the exact moment the final report is being written**. Prior `Marker` lines survive (per-call `CloseHandle`), but the delta table would not. **Wrap both final reports in `__try/__except(SEH_FILTER(GetExceptionInformation()))`** — matching `DoDropPod`/`DoPoolSpawn`.

### Nothing found that would make the readout WRONG
The five field names are all real reflected UPROPERTYs [M]: `bIsTeamLeaderPod`(:178), `PodTeamIndex`(:179), `CurrPodDestination`(:183), `LeaderPod`(:187), `PodMeshComponent`(:204) on `ALokiDropPod` in `GameMode.DropPhase.LokiDropPod.as.txt`; **`PilotPlayerState` is native on `ALokiDropPodBase`** — `tools/asdump/out/binds_members.csv:42260`, `property,0,ALokiPlayerState,PilotPlayerState`. **None is redeclared by the Blueprints** (`bpdump_BP_DropPod_PROPS.txt` / `_Tutorial_PROPS.txt`: zero matches for any of them), so leaf-first shadowing cannot bite.

**The hardcoded `PDPOD_OFF_*` cross-check offsets (9751-9754) are correct** — I re-derived all five independently from the AS disassembly annotations (`LoadThisR`/`ADDSi … ; ALokiDropPod::<name> (+N)`): `bIsTeamLeaderPod` 1117=**0x45D**, `PodTeamIndex` 1120=**0x460**, `CurrPodDestination` 1144=**0x478**, `LeaderPod` 1200=**0x4B0**, `PodMeshComponent` 1592=**0x638**. ⚠ `PodMeshComponent`'s constant is **not defined** at 9751-9754 and the field is not in `PdPodOne`'s list — the s131 doc §1.1 names it; add `0x638` if you want it. Grade: **[M]** as an object-layout displacement (the AS VM loads `this+N` directly); **[I]** as an assertion that `FProperty.Offset_Internal` equals it — which is exactly what the `AS … AGREE/DISAGREE` tally at 9880-9890 measures, so the design is already honest about it.

### Two instrument notes worth keeping
- **A class-name literal's absence from the exe is NOT evidence of absence.** `LokiDropPodBase` and `LokiDropShip` score **0** ASCII occurrences in `dumps/tutorial-hero/…dump.exe` while both classes are live in the S130 census, and their own members (`PilotPlayerState`, `GetDropAboveAmount`, `StartPlayerPodSteering`) sit in a contiguous block at `.rdata 0x8934010-0x8934118`. Do not run a presence test on class names.
- `PodTeamIndex` / `CurrPodDestination` / `bIsTeamLeaderPod` / `PodMeshComponent` score **0** in the image, consistent with CLAUDE.md's "Angelscript names have zero byte occurrences" — but per the note above, treat that as *consistent with*, not *proof of*.