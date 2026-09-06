**VERDICT: largely sound. 3 of 3 re-derived load-bearing claims CONFIRMED. 1 audit finding (A) is now FALSE-of-the-file (fixed by the concurrent lane while the report was being written). 6 smaller defects, 4 items still [I].**

---

## 0. THE FILE MOVED AGAIN — TWICE MORE, DURING THIS AUDIT

The report snapshotted md5 `6a5ce4b5…` / 14,165 lines. I observed `1316e91dbfdc9fbe92341916b6d311f1` / **14,205 lines**, and six commands later `7c6f70dd82c61b6561800effb01b6b5b` / **14,272 lines** — a `sed -n '9794,9822p'` aimed at `PdFindPropOn` (grepped at 9794 minutes earlier) returned the *knob block* instead. **That is at least five distinct states.** The report's warning is correct and understated: **every line number in it is already wrong**, drift measured at +16 (`PdFindPropOn` 9778→9829) to +76 (`PdPodDump` 10060→10136). `PropOffsetSuper` 2021 and `Marker`/`Markerf`/`SafeReadable` 402/403/404 happen to be stable. Cite symbols only.

---

## 1. RE-DERIVATION — the three most load-bearing claims

### LB1 — the `SetBitFunc` bool table (drives finding B) → **CONFIRMED on all four displacements and both `or` masks; the `0xFF` FieldMask prediction is [I] and the report omitted its own best corroborator + all four fold multiplicities**

Ran `scratchpad/s130/tools/boolscan.py --name <n>` against `dumps/s129-poolgate` (13,156 `FBoolPropertyParams` **records**, base `0x7FF7B86D0000`):

| name | record rva | SetBitFunc | decoded | disp | imm | **fold** |
|---|---|---|---|---|---|---|
| `bCanEverReplicate` | `0x07F1FDF0` | `0x02078900` | `mov byte ptr [rcx+0x6c],1` | 0x6C | 1 | **8** |
| `bEnablePooling` | `0x07F21160` | `0x03368BF0` | `mov byte ptr [rcx+0x2d3],1` | 0x2D3 | 1 | 1 |
| `bHidden` | `0x07F1F880` | `0x03368980` | `or byte ptr [rcx+0x68],0x80` | 0x68 | 0x80 | 1 |
| `bAlwaysRelevant` | `0x07F1F730` | `0x032F7100` | `or byte ptr [rcx+0x68],8` | 0x68 | 8 | 2 |

All four addresses and decodings are exactly as reported. Three defects:

- ⚠ **Fold multiplicity dropped.** `bCanEverReplicate`'s `SetBitFunc = 0x02078900` is **fold=8** — it is shared by 8 Bool records. The report printed that RVA bare, in a project whose own rule is *"always print fold multiplicity next to a folded RVA."* It does not damage the disp (all 8 folded records share `+0x6C` by construction) but the address **does not identify the property**.
- ⚠⚠ **`bHidden` is a 5-way ambiguous NAME image-wide** — `selected: 5`, at disps `0x68` (or,0x80), `0x30` (`or dword…,0x400`), `0x50`, `0xf0`, `0x8`. The report presented one row as *"`bHidden`"* with no note that four other classes ship the same name. The in-arm lookup is still safe (leaf-first from an AActor-derived pod hits AActor's), but the offline justification as written is not sufficient.
- ★ **The discriminator the report needed and did not cite — I measured it:** `SizeOfOuter` at `record+0x34` reads **`0x390` for all four** AActor rows and `0x110` / `0x58` for the foreign `bHidden`s. That pins ownership without `propowner.py`.

**On the `FieldMask = 0xFF` prediction — [I], and I found the missing evidence:** `gflags` at `record+0x18` reads `0x0000004C` for both `mov`-style rows and `0x0000000C` for both `or`-style rows. Low 5 bits `0x0C` = the Bool selector `boolscan` filters on; **the differing bit is `0x40` = `EPropertyGenFlags::NativeBool`**. So the *native-bool-ness* is [M] from the image; `FieldMask = ByteMask = 255` for native bools is [I] from stock `FBoolProperty::SetBoolSize` semantics, **not read out of this binary**.
⚠ **Do not assert `0xFF` in `PdPodCalibrate`.** If this engine instead derives the mask from the byte the `SetBitFunc` wrote, the value is **`0x01`**, and an in-arm assertion of `0xFF` would declare a correct decoder broken. Assert only the two `or` cases (`0x68`/`0x80` vs `0x68`/`0x08`) — those are robust under either semantics — and **print** the `mov` masks rather than testing them.

### LB2 — `Markerf` truncates at 511 chars and eats the trailing CRLF → **CONFIRMED byte-exactly**

`tutorial_launch.cpp:402-403`:
```
static void Marker(const char* m){…CreateFileA(kMarkerPath,FILE_APPEND_DATA,…,OPEN_ALWAYS,…);…WriteFile(h,m,(DWORD)strlen(m),&w,nullptr);CloseHandle(h);}
static void Markerf(const char* f,...){char b[512];…_vsnprintf_s(b,sizeof(b),_TRUNCATE,f,a);…Marker(b);}
```
`RESULT-routeE-after-poke-s130.txt:208` is **1,138 chars**; `fold -w 511` splits it **511 / 511 / 116**, and `cut -c1000-1060` reads `…his bit, stores the asC` `[PD] sig SpawnDropPodForTeam(E1 RE-REA` — the mid-word join at index 1022 = 2×511 is real. `Marker` with a literal is uncapped, confirmed by the two 785-char lines (128, 149). The rule *"over ~450 chars use `Marker` with a literal"* stands.

### LB3 — `DropPod +2` is 1 actor + 1 AnimInstance, and the `pod` bucket is 3+2+2 → **CONFIRMED (one citation over-includes a row)**

`RESULT-routeE-after-poke-s130.txt:223-225` verbatim:
```
[DP] after-E1 *** NEW *** 0x1D1A4DA2740 'ABP_DropPod_C'  chain=ABP_DropPod_C<-AnimInstance<-Object
[DP] after-E1 *** NEW *** 0x1D015C87910 'BP_DropPod_Tutorial_C'  chain=…<-LokiActor<-Actor<-Object
[DP] after-E1 CENSUS summary: DropPlane=4 DropPod=9 DropShip=1 objects=13 new=2 …
```
`C0-BEFORE` non-archetype pod rows are lines **25, 32, 61, 62, 64, 65, 66** = 3 × `BP_DropPod_Tutorial_C` (actor) + 2 × `ABP_DropPod_C` (AnimInstance) + 2 widgets = **7**, matching `DropPod=7`. `DropPlane=4` = lines 23, 27, 28, 63, of which 1 is an actor.
⚠ The report writes *"lines 61-66 + 25 + 32"* — that range includes **line 63, `BP_DropPlane_Straight_Tutorial_C`, which is not a pod**. 8 cited rows for a 7-row set. Counts right, citation wrong.
The selector is real: `tutorial_launch.cpp:6221 if(strcmp(n,"Actor")==0) v|=DPV_ACTOR;` inside `DpEvalClass`'s ≤12-hop `+0x48` walk, and the pod-actor latch at **6304** `if((v&DPV_POD)&&(v&DPV_ACTOR)&&…)` runs on the memoised full verdict. **No order dependence — confirmed.**

---

## 2. THE ONE THING THAT IS NOW FALSE

⛔ **Finding A — "RM_POOLSPAWN gets no pod dump at all, the largest gap" — is STALE. `PdPodDump` is now called from the poolspawn ladder, at exactly the four points the report recommended:**
```
11516: PdPodDump("after-P1 (pooled DEFERRED spawn -- no InitializeDropPod)", 1);
11531: PdPodDump("after-P2 (pooled NON-deferred spawn -- no InitializeDropPod)", 0);
11546: PdPodDump("after-P3 (ORDINARY non-pooled spawn -- no InitializeDropPod)", 0);
11571: PdPodDump("P4-AFTER (worker, post-settle)", 0);   // inside SpFinalReport
```
(line numbers at md5 `1316e91d…`). The within-run negative control the report argued for **exists**, and the source comment now states the same rationale. Likewise stale: *"PodMeshComponent … is not in `PdPodOne`'s list"* — it is (`PdPodField(pod,cls,"PodMeshComponent",0xFFFFFFFF,…)`), alongside `bHasStartedGameplay`, `bIsLocalPlayerPilot`, `bPilotHasPodControl`, `bCanEverReplicate`, `Owner`. And the flag enum is now `…DPV_ACTOR=16, DPV_RIDE=32` — the report's 5-flag enumeration is missing `DPV_RIDE`.

**Findings B, C, D, F are all still TRUE of the file** (verified: `PdPodCalibrate` checks only the two offsets; `boring` includes `!strcmp(val,"0")`; `isNew` diffs `g_dpBefore[]` with a `g_dpBeforeN==0` guard but never reads `g_dpBeforeOverflow`; **`Worker` contains zero `__try`/`__except` between its declaration and EOF**, so `PdFinalReport`/`SpFinalReport` — which now each run a `DpCensus` *plus* a `PdPodDump` — are unguarded).

---

## 3. OTHER CLAIMS CHECKED

| claim | verdict |
|---|---|
| `PropOffsetSuper` walks own-props then `+0x48` super, leaf-first, ≤12/≤300, returns `0xFFFFFFFF`, falls through on unreadable `+0x44` | **CONFIRMED verbatim**, `tutorial_launch.cpp:2021-2029` |
| `PdFindPropOn` — 12 supers, **400** props, returns owner class name, `0` = not found | **CONFIRMED**, body at 9829-9852 |
| AS displacements 1117→`0x45D`, 1120→`0x460`, 1144→`0x478`, 1200→`0x4B0`, 1592→`0x638` | **CONFIRMED** from the disassembly appendix (`GameMode.DropPhase.LokiDropPod.as.txt:418/421/428/822/950`) |
| `PilotPlayerState` native on `ALokiDropPodBase` | **CONFIRMED**, `binds_members.csv:42260` exact |
| `build.ps1:81-83` now `throw`s on `-Variant` without `-Name`; CLAUDE.md's warning is stale | **CONFIRMED** (`if ($Variant -and -not $Name -and -not $All) { throw … }`) |
| variant keys at `build.ps1:268/380/381/511/512`; `dropplane-b1only` is the key, `dropplane_b1only` the stem | **CONFIRMED**; the `-replace '-','_'` rule is at **:876, not :875** |
| `Worker` truncates the marker with `CREATE_ALWAYS` | **CONFIRMED** (one hit, line 13555) |
| `FPROP_ELEMSIZE=0x34` upgraded [I]→[M] in flight | **CONFIRMED** — `RESULT-poolspawn-cdopoke-s130.txt:108` reads verbatim `…FAILURES=0 => PASS (FPROP_ELEMSIZE=0x34 really is reading ElementSize, not ArrayDim)` |
| `PropOffsetSuper` resolves native engine UPROPERTYs in flight | **CONFIRMED**, `RESULT-poolspawn-cdopoke-s130.txt:145` = `control actor = 0x1D011F0A030 loc=(-3206.4,5070.5,100.0)` |
| census cost 1,219 / 1,406 / 1,531 ms at `:67/:225/:288` | **values CONFIRMED, PAIRING WRONG** — :67=**1531**, :225=**1219**, :288=**1406**. The report sorted the values ascending against an unsorted citation list. Same family as printing bytes next to an address they did not come from, in miniature. |
| the `.text` sha snippet is `docs/fk13-routeb-test-card.md:283-292` | **CONFIRMED**, but the doc's filename is `tutorial_launch_cheatmgr.dll`; the report silently substituted the poolspawn stem while presenting it as a quote |

---

## 4. STILL UNGROUNDED — and what settles each

1. **[I] `FBoolProperty` mask fields at `FProperty+0x70..0x73`, and `FieldMask==0xFF` for native bools.** Nothing in this build has been read. **Settles it:** disassemble the `FBoolProperty` construction path in `merged2` (`SetBoolSize`'s two arms) and read the `255` immediate — or fly the two-sided `or` control only and treat the `mov` masks as observations. `NativeBool` (gflags bit `0x40`) is now [M] and is the strongest available support.
2. **[I] that UHT native bools appear in the FField `ChildProperties` chain at all.** The positive controls that exist are *object/struct* properties (`RootComponent`, `RelativeLocation`, `TeamDropPodClass`) — no bool has ever been resolved by name in this build. The code is honest about it (`calibration UNAVAILABLE … COVERAGE limit … NOT a failure`), the report is not. **Settles it:** the in-arm calibration itself.
3. **[I] `+0x48` is `UStruct::SuperStruct`.** Used by `PropOffsetSuper`, `PdFindPropOn`, `DpEvalClass` and every census in the file; never stated with a source. It reproduces published derivation chains, so it is [I, strong] — but it is unlabelled.
4. **[I] the leaf `PDPOD_OFF_*` layout argument.** The in-file comment grades it correctly ([I], structural, printed *beside* the by-name read with an AGREE/DISAGREE verdict). The report calls the five constants *"correct"* and then re-derives a different five — it verified `PodMeshComponent` (0x638, **not in the constant table**) and did **not** verify `PDPOD_OFF_STARTED = 0x4B8`. I did: `GameMode.DropPhase.LokiDropPod.as.txt:437` `LoadThisR W0:1208 … ALokiDropPod::bHasStartedGameplay (+1208)`, 1208 = 0x4B8. ✓ **5 of 5 now checked.**

## 5. ONE DEFECT NEITHER THE REPORT NOR THE CODE COMMENT CATCHES

`PdFindPropOn` returns the FProperty pointer **unconditionally** on a name match, leaving `*offOut = 0xFFFFFFFF` if `f+0x44` is unreadable — unlike `PropOffsetSuper`, which requires the read to succeed. `PdPodCalibrate` then evaluates `!p1 ? -1 : (o1==KPDCDOOFF ? 1 : 0)`, so **an instrument read failure prints `*** CALIBRATION MISMATCH ***`** — the branch whose own text says *"a wrong offset prints a real-looking number"*. It fails in the safe direction (everything declared UNINTERPRETABLE) but it mislabels an instrument fault as a contradiction, which is the exact distinction the surrounding comment was written to preserve. One condition (`o1!=0xFFFFFFFF`) closes it.