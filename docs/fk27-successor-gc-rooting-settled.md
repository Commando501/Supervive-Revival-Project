# FK-27's successor — how GC rooting ACTUALLY works in this build, and how to do it

**S123, 2026-08-15. Settled offline + read-only RPM. Zero launches, zero injections, zero `.text`
writes. The game and `ags` were running at the menu throughout and were left running.**

Primary evidence: `scratchpad/fk27/EVIDENCE.md` (live measurements), `scratchpad/fk27/gc-mark-re.md`
(GC side, disassembly), `scratchpad/fk27/addtoroot-re.md` (`AddToRoot` side, disassembly),
`scratchpad/fk27/skeptic-review.md` (adversarial review — **it refuted several pieces of evidence
below while confirming the conclusions; read it before citing any single number**).
Instrument: `tools/re/rootset_census.py`.

---

## 0. What this does and does not change

**FK-27 stays closed.** "Poking `EInternalObjectFlags::RootSet` keeps a shim-loaded asset alive" is
DEAD, and nothing here reopens it. What FK-27 never had was the **mechanism** — it closed on outcome
(3 armed windows, leads 0.15 s / 2.9 s / 33.1 s, destroyed every time). The mechanism is now settled,
and with it comes **a working rooting recipe the project did not have.**

## 1. The model [M], three independent sources agreeing

**There are two unrelated reasons an object survives GC here, and conflating them is the trap.**

### (a) The disregard-for-GC pool — excluded by INDEX, not by any flag

`GUObjectArray` (the `FUObjectArray` global) is at **RVA `0x9E38920`**. Live:

```
+0x00 ObjFirstGCIndex             = 39295
+0x04 ObjLastNonGCIndex           = 39294
+0x08 MaxObjectsNotConsideredByGC = 45000      (configured budget; 39,295 actually allocated)
+0x0C OpenForDisregardForGC       = 0          (window closed)
+0x10 FChunkedFixedUObjectArray ObjObjects { Objects, PreAlloc=NULL, MaxElements=2162688,
                                             NumElements=207719, MaxChunks=33, NumChunks=4 }
```

⚠ **The project's long-standing constant `RVA_OBJOBJECTS = 0x9E38930`** (`tutorial_launch.cpp:23`,
`item_watch.py:60`, ~20 shim sources) is `FUObjectArray + 0x10` — the *inner* `ObjObjects` member.
Correct for its use, but it is why nobody had the disregard fields: they sit **0x10 below** the
address everything anchors on.

All three whole-array GC sweeps iterate `[ObjFirstGCIndex, NumElements)`, never from 0
(`0x01259162` loads START, `0x0125916D` loads END). The engine names the sole exception itself:
`GatherUnreachableObjects` (`0x01250A40`) does `cmovne r9d, ebx` to set START = 0 when `GExitPurge`
(`.data 0x9D29118`) is set. `MarkObjectsAsUnreachable` hand-injects `GGCObjectReferencer` at
`0x0129B3F9` *precisely because* the pool is otherwise never visited.

⇒ **Nothing below index 39,295 is ever traversed, marked, or freed.** Bit 30 on a pool object is a
consequence of when it was allocated, not the cause of its survival.

### (b) Real roots — a REGISTRY, with the flag as bookkeeping

`UObject::AddToRoot` does **two** things, in this order:
1. inserts the object's `InternalIndex` into a global **`TSet<int32>` at `.data 0x99D3CA0`**, under
   the `RTL_CRITICAL_SECTION` at `.data 0x9E23BF0`;
2. atomically ORs `0x40000000` into `FUObjectItem.Flags`.

The root gather — `.text 0x1259020`, which the game names `L"GC.MarkRootObjectsAsReachable"`
(`.rdata 0x771D048`) — takes that lock, copies the `TSet` to a `TArray<int32>`, and `ParallelFor`s
over the **indices**. The mark body (`0x123E3B0`) contains **no bit-30 predicate**.

⇒ **The container is the input. The flag is a mirror.** An `InterlockedOr` writes the mirror and
never enters the gather, which is exactly why FK-27's poke was inert — and there is a *second*,
independent reason: mark body B skips on `test eax, 0x4E100000`.

### ★★★★★ Set-identity confirmation [M]

Live, the registry's **allocated** members (walking the `TSparseArray` allocation bitmap) are
**exactly** the high-index bit-30 objects an independent flag census over 200,475 objects finds:

```
SET IDENTITY   registry=32  census=32  intersection=32
  in registry but not census : none
  in census but not registry : none
```

The 32: `LokiGameEngine`, `OnlineEngineInterfaceImpl`, engine default textures (`DefaultTexture`,
`DefaultBokeh`, `MiniFont`, `PreintegratedSkinBRDF`, the `STBlueNoise` pair,
`WeightMapPlaceholderTexture`), `SC_Master` / `Master` / the three `MasterSubmix`es, `CanvasObject`,
`DebugCanvasObject`, `CrowdManager`, `World LVL_LobbyV2_Persistent`,
`LokiInternalAbilitySystemGlobals`, `ImageCache`, `BP_InputData_C`, two `BodySetup`, four
`BP_MainMenu_SceneRotator_C`. Textbook `AddToRoot()` callers, every one.

### bit 30 == RootSet [M/I, strong]

Three offline confirmations (`AddToRoot` passes `mov edx,0x40000000`; `IsRooted` returns
`Flags>>30 & 1`; the root mask `0x4E100000` contains it) **plus** one live control that raises stock
enum numbering from a guess to a measurement: **bit 24 `ClusterRoot` ⟺ `ClusterRootIndex < 0` at
100.000% over 200,437 objects, 0 FP, 0 FN.** ⇒ `KGCROOTBIT` was never wrong.

---

## 2. ★★★★★ THE RECIPE — how to root a shim-loaded UObject

**There are TWO levels and they take different arguments — do not conflate them.**

| level | add | remove | signature |
|---|---|---|---|
| **`UObject`** (use this) | `AddToRoot` **`.text +0x489F9B0`** | `RemoveFromRoot` **`.text +0x48B4BD0`** | `void __fastcall (UObject*)` |
| **`FUObjectItem`** (only if you already hold the item) | `SetRootFlags` **`.text +0x129AC90`** | `ClearRootFlags` **`.text +0x1243B50`** | `bool __fastcall (FUObjectItem*, uint32)` — flags in `edx`, result in `al` |

All four are real out-of-line bodies with **fold multiplicity 1**, byte-identical in `merged2` and
`tuthero`. The fold check is controlled: each entry-byte sequence occurs **1×** in `.text`, against
the known 91-way-folded `execFoo` thunk `0x5254180` at **907×**.

```c
// FUObjectItem level, MS x64:
((bool(*)(void*, uint32_t))(base + 0x129AC90))(item, 0x40000000);
```

⚠ **`IsRooted` (`.text +0x48B2200`) is NOT a valid verifier** — it reads only the flag, so it returns
true for precisely the failure being diagnosed. Use the registry receipt below.

No reflection route exists (exact-name scan over 18,325 UHT functions: 1 hit,
`ALokiCharacter::IsRooted`, an unrelated movement status effect). `UGCObjectReferencer` is compiled
in but is dominated — it needs a live vtable UE calls from GC threads every pass.

⇒ **A plain direct call from an injected DLL. No `.text` write, no PI hook, no native-call primitive,
thread-safe via its own lock.**

### ⚠⚠ THE TRAP — the existing poke POISONS the fix

`SetRootFlags` early-outs on `if (Flags & 0x4E100000) skip the insert`. **Any object the shim has
already `InterlockedOr`'d looks "already a root", so a subsequent correct `AddToRoot` call skips
`GRoots.Add` and silently does nothing.** `KGCROOT` is therefore not merely dead code — it actively
blocks its own replacement. **Call `RemoveFromRoot` first, or disable the poke.**

### ★ Free RPM receipt, verified — use this, never `IsRooted`

```
liveRootCount = *(int32*)(base+0x99D3CA8) - *(int32*)(base+0x99D3CD4)      // ArrayNum - NumFreeIndices
```
Reads **32** live and matches the census exactly. Both `SetRootFlags` and `ClearRootFlags` compute
that same expression — two independent derivations. It must move **+1 per rooted object**.

---

## 3. What this corrects, stated at the right size

1. **`item_watch.py:738`'s "CHIMERA" label is wrong and should go.** `RootSet + current mark` is
   described there as "a CHIMERA — 0.03% of the natural population"; it is the **normal, continuous
   state of every genuinely rooted non-permanent object** (all 32, always). The instrument emitted
   that label about the shim's object, which had the correct flag word the whole time.
2. **`s110-item-watch-gc-mechanism.md` §4c's "root-set objects are *excluded* from marking"** pooled
   39,275 never-traversed pool objects with 32 always-marked real roots and reported the pool's
   property as the root set's. S110's `6 of 4915` is today's 32.
   ⚠ **Sized correctly** (adversarial review): S110 §3/§4d **already recorded** rooted objects being
   re-marked (`40000004 → 40000002`), so what is overturned is **one sentence in §4c plus a
   docstring** — not the document. None of it rescues the shim or reopens FK-27.
3. **`KANIMREF` is re-framed, not replaced.** Parking the asset in a live `UPROPERTY` is not a
   workaround for a broken mechanism — it is the *same* mechanism real roots use (be reachable by
   the traversal). It remains correct and should stay the default until a real `AddToRoot` call is
   flown.
4. **FK-28's rotating bits 0/1/2 are explained at code level:** `.data 0x99D36A0 / A4 / A8` hold the
   Reachable / Unreachable / MaybeUnreachable **values**, rotated O(1) per pass (`0x01258F70` at
   pass start, `0x012398C2` / `0x01239B76` at end) rather than the population being rewritten.

## 4. Evidence that was REFUTED and must not be recycled

The adversarial review confirmed all four conclusions and **refuted the argument offered for two of
them.** Recorded so nobody cites the bad version:

* ⛔ **"Zero free slots below 39,295, P ≈ 1e-676 if uniform" is NOT valid evidence for the pool.**
  The free slots are not scattered — 5,705 of 7,282 form one contiguous run starting at the
  boundary, so the uniformity model the probability was computed against is refuted by the data.
  Worse, `[45000..169999]` (125,000 slots, 3.2× the prefix) *also* has zero holes and is not rooted,
  so the signature is not specific; and "no holes below the first hole" is circular. **The boundary
  rests on `ObjFirstGCIndex` read directly, and on the 20 unflagged pool objects that are never
  marked and never collected — not on hole density.**
* ⛔ **"32/32 rooted vs 40/40 ordinary always carried the current value" is void as stated.**
  `dominant_reach_bit()` is a lagging majority vote (~15 s lag) whose polarity **inverts** during a
  mark ramp, so it measured "marked LAST", not "re-marked". At a 0.5 s period the same objects read
  **0/32** — meeting the pre-registered refutation criterion — and at 0.4 s, 32/32. The conclusion
  survives on far better evidence: **raw low nibbles, 9 rotations, 32/32, zero exceptions, single-bit
  at all 1,417 samples.** Use the raw nibbles; the derived boolean is gone from the probe.
* ⚠ **"Roots are marked first" is [I], n = 1 of 9 passes.** 8 of 9 complete in under 0.4 s with no
  observable ramp. The single ramped pass gave roots 32/32 vs index-matched ordinary 17/32
  (Fisher p = 3.6e-6) — the best evidence anyone has, and still one observation.
* ⚠ **The `PERMANENT` control row is a TAUTOLOGY**, not a finding: pool objects carry no low bits, so
  "never carried the current value" is guaranteed. It is a sanity check and is now labelled as one.

## 5. Instrument defects found and fixed

`tools/re/rootset_census.py` had 10 defects; the load-bearing ones are fixed and the rest annotated
in-file. Two are worth generalising:

* ★★ **Recording a DERIVED BOOLEAN instead of the RAW VALUE destroyed the evidence.** The tracker
  stored "carries the currently-dominant bit" rather than the flag word, so when the comparator's
  polarity inverted there was nothing left to re-analyse. **Record raw; derive afterwards.**
* ⚠ The first sample was counted as a rotation, inflating every run by one (so an earlier
  "3 rotations" was 2). The boundary check compared *index distance* and printed a scary
  "DISAGREE by 7038 slots" when the real disagreement was **20 objects**.

### ⚠⚠ My own instrument-artifact instance, logged (46th)

I read the root registry's `TSparseArray.ArrayNum` (**49,307**) as its member count, ignoring
`FirstFreeIndex`/`NumFreeIndices` **in the same hex dump I was reading**. From that I derived three
false conclusions — that pool objects were in the registry, that ~4,306 members lacked bit 30, and
that "the flag is a mirror" was too simple — and sent all three to the offline agent as a challenge
to its *correct* result. `Num()` of a sparse container is **never** `ArrayNum`.

## 6. ★★★★★ SUFFICIENCY — `KeepFlags == 0`, so the registry is the ENTIRE root seed

The last open item is closed, offline **and** live. `KeepFlags` is not a threaded stack argument —
`CollectGarbage` (`0x01243CE0`) parks it in a static global:

```
0x01243D6C  mov dword ptr [rip+0x8be15d6], edi   ; -> .data 0x9E25348  KeepFlags
0x01243D72  mov byte  ptr [rip+0x8be15d4], bl    ; -> .data 0x9E2534C  bPerformFullPurge
0x01243D8B  lea rcx, [rip+0x8be152e]             ; -> .data 0x9E252C0  static GC state object
```
`0x9E25348 - 0x9E252C0 = 0x88`, and the incremental driver reads the same field as `[rbx+0x88]`
(`0x01259CFE`) — so the global **is** `state->KeepFlags`.

Four independent measurements agree:
1. **8/8** direct `CollectGarbage` sites and **2/2** `TryCollectGarbage` sites do `xor ecx, ecx`.
   *Tool control:* the same tracer pointed at `0x0129AC90` reports **12 distinct** arg1 forms, so it
   is not merely defaulting to `xor`.
2. **Zero stored pointers** to either entry point anywhere in the image ⇒ no indirect caller can pass
   anything else.
3. `[.data 0x9E25348] == 0` in **both** cold images (two different process lifetimes).
4. **[M] LIVE, this session:** `*(int32*)(base+0x9E25348)` = **0**, with the control that 89 of 160
   bytes in the surrounding GC state object are non-zero — so the region is live and the zero is a
   real read, not an unmapped page.

`0` = `RF_NoFlags` (`GARBAGE_COLLECTION_KEEPFLAGS` with `GIsEditor` constant-folded false). And the
conclusion does not even rest on the gate: body B's inner test is `test dword ptr [rax], ecx` with
`[rax] == 0`, which can never be true. **Dead either way.**

⇒ **Mark body B never runs, the root `TSet` is the entire seed, and inserting into it is
SUFFICIENT — not merely necessary.**

### Writer census complete

A **fourth** writer of `0x99D3CA0` exists — `0x0123E0E1` — with the *opposite* insert polarity (it
inserts every keep-flagged object) and a domain of `[0, N)` **including the pool**. It is the body of
the `'GC.OnDisregardForGCSetDisabled'` `ParallelFor` (driver `0x012596A0`, `xor r9d,r9d` ⇒ START 0),
which fires only when disregard-for-GC is *disabled*. This build has it **enabled**
(`MaxObjectsNotConsideredByGC = 45000`), so it has never run — independently bounded by the live
0-of-4,915 measurement, which that pass would have broken.

## 7. Open

* The recipe has **not been flown.** Everything above is offline disassembly plus live-verified
  *reads*; the *call* is untested. The receipt in §2 is how to test it in one armed window.
* `fn 0x01259D72`'s caller is genuinely coverage-blocked (no `E8`/`E9`, no stored pointer —
  presumably in one of the 13,642 undecrypted pages). It no longer matters for this result.

## 8. ⚠⚠ A trap that will recur on ANY `TSet` in this image

`Num()` of a `TSparseArray` is `ArrayNum - NumFreeIndices`, which the engine itself computes at
`0x011D44EE` (`sub edx, [rcx+0x34]`). Reading `ArrayNum` alone gave **49,307** where the truth was
**32**. Two properties make the wrong read *self-validating*, which is why it survived scrutiny:

* the inline `FF×16` allocation bitmap is **dead storage** once `NumBits > 128` (proved by
  `0x011D4533 cmove r10, rax`), so it looks like "everything allocated";
* a **freed** sparse slot satisfies every field-range sanity check *by construction* — stale
  `Value`s are real former indices, and the free-list link occupies the same bytes as `HashNextId`.

So "88% of the values are live object indices" and "every `HashIndex` < `HashSize`" both pass on
garbage. **Always walk the allocation bitmap; never trust the slot array.**
