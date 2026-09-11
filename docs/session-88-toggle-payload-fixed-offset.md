# S88 (2026-07-23) — DS toggle carrier: the payload delta is a FIXED offset; root cause is the client reading the subobject content-block as GameState field-cache entries (NOT array framing)

Branch `dedicated-server-stub`. Continues docs/session-87-subobject-framing-rootcause.md (header solved empirically
at `injectbits=11`; the remaining `GameFeatureToggles` `TArray<bool>` payload framing was the open item).

## TL;DR

The S88 task was: measure the payload delta (FIXED offset vs PER-ELEMENT) and then match the client's array
framing. **Result:**

1. **The payload mismatch is a FIXED offset, NOT per-element — PROVEN.** With `injectbits=11`, seeds 1 / 75 / 151
   (1, 75, 151 array elements) all drop at the **identical** `Invalid replicated field 12 in LokiGameState`,
   while seed=0 (empty array == CDO) HOLDS (enters game state, no error). A per-element delta would scale the
   failure with element count; a fixed one lands identically. It's fixed.
2. **The array element framing is NOT the cause.** Splicing bits into the `TArray<bool>` payload
   (`-paybits=16 -payat=25`, re-encoding `NumPayloadBits`) left the failure **completely unchanged** (still field
   12) — the drop happens *before* the payload is consumed.
3. **The real divergence is the subobject content-block deserialization.** The client reads the ServerAuthConfig
   content-block payload **as GameState field-cache entries** and never resolves the subobject. So the "header
   solved at N=11" from S87 only *moved* the error (from "sub-object class" to "field 12"); the subobject is
   never actually instantiated (no `Instantiating sub-object` / `SubObj` line ever logs). **No bit-splice can
   populate the toggles** because the client isn't parsing the block as the component's array.

The clean fix requires either RE'ing the client's `UActorChannel::ReadContentBlockPayload` /
`FObjectReplicator::ReceivedBunch` (anti-tamper-blocked, S87) or delivering the toggles via a different
mechanism (registered-subobject-list, or the `MulticastSetGameFeatureToggle` RPC). Bit-injection on the
content block is a dead end.

## What was built this session (all committed, guarded, inert at baseline)

- **`-toggleseed=N`** cmdline on the stub (`LokiGameStateStub.cpp` `GetToggleSeed()`) — seeds `N` toggles so the
  array size can be swept without rebuilding. seed=0 ⇒ empty == CDO.
- **`-postbits=M -postpat=P`** — splice `M` bits right AFTER the content-block stable bit, BEFORE the re-encoded
  `NumPayloadBits` (`GetPostBits()`; the emit block in `ReplicateSubobjects`).
- **`-paybits=N -payat=D -paypat=P`** — splice `N` bits (N<0 removes) into the RepLayout payload at payload
  bit-offset `D`, re-encoding `NumPayloadBits` (`GetPayBits()`/`GetPayAt()`/`GetPayPattern()`).
- **`tools/re/s87/decode_payload.py`** — decodes a `SPLICED BLOCK` end-to-end: header (with the N=11 injected
  field) + `NumPayloadBits` + the `TArray<bool>` element stream, verifying the stub's wire is self-consistent.
  VALIDATED: the full-151 wire decodes to `arrayHandle=3, ArrayNum=151, 151 contiguous elements, consumed=1592
  = NumPayloadBits (MATCH)`.
- **`tools/re/s87/sweep_seed.ps1`** — one full robust DS cycle (kill → stub with args → delete stale client log
  → launch-redirect → poll gated on THIS cycle's SPLICE → capture SPLICE/BLOCK/ENTER/errCount/OutField/FIRSTERR
  to `C:\Temp\SweepResults.txt`). `sweep_post.ps1` / `sweep_combo.ps1` loop it over value lists.
  ⚠ STALE-LOG GOTCHA (fixed): the client `Loki.log` persists between launches; the poll MUST delete it each
  cycle and gate results on the stub's per-cycle `SPLICE` line, else it reads the previous cycle's field-12.

## The stock UE5.4 wire (verified from source + live decode)

`ULokiServerAuthConfig.GameFeatureToggles` (`TArray<bool>`, 151 elems, RepIndex 2 ⇒ handle 3). The stub writes
a **bit-perfect stock UE5.4** content block (RepLayout.cpp:2744-2789, DataChannel.cpp). Content block:
```
bit0  bHasRepLayout          (1 when there's a RepLayout payload; 0 for the empty-array case)
bit1  bIsActor=0
GUID  SerializeIntPacked64   (subobject NetGUID.ObjectId = 12)
+11   injected bits          (S87 empirical; client reads bStablyNamed at absolute bit 21)
1     stable bit = 1
NumPayloadBits SerializeIntPacked
payload (NumPayloadBits):
  1   lead bDoChecksum bit = 0   (Development EDITOR build has ENABLE_PROPERTY_CHECKSUMS on; client agrees — the
                                  GameState's own 43-prop payload has the same lead bit and reads fine)
  8   arrayHandle=3 (SerializeIntPacked)
  16  ArrayNum uint16 (Writer << uint16 — RAW 16 bits, a UE quirk, NOT packed)
  N×  per element: elemHandle SerializeIntPacked + 1 bool bit   (handles 1..127 = 9b, 128..151 = 17b)
  8   array-end handle 0 (SerializeIntPacked)
  8   object-end handle 0 (SerializeIntPacked)
```
Full-151 payload = 1 + 8 + 16 + 1551 + 8 + 8 = 1592 bits. Element cost is genuinely per-element, but that is
irrelevant — see below.

## The empirical result (all live, harness-verified)

| sweep | config | client outcome |
|---|---|---|
| seed | seed=0 (empty) | **HOLD** — enters `LokiGameState`, errCount=0 (bHasRepLayout=0, NumPayloadBits=0) |
| seed | seed=1 / 75 / 151 | `Invalid replicated field 12 in LokiGameState` — **identical ⇒ FIXED offset** |
| paybits | seed=151, paybits=16 payat=25 | field 12 **UNCHANGED** ⇒ array payload is NOT the cause |
| postbits | 0 / 1 / 6 / 7 | field 12 / 48 / 28 / 56 |
| postbits | 2 / 3 / 4 / 5 | ReadField err on OutField `LastDayNightChangeTime` / `bCanBeDamaged` / `Owner` / `ReplicatedWorldTimeSecondsDouble` |
| combo | post=5, pay=-16/-8/0/+8/+16 | OutField `ServerState` → `SpectatorClass` → `ReplicatedWorldTimeSecondsDouble` → `bGetPreventMovement`[15] → `WinningTeam`[18] |

**Interpretation.** The failure is always inside the *GameState's* `FObjectReplicator::ReceivedBunch` (channel 5,
RepObj `LokiGameState`), reading a **field-cache entry** (`ReadFieldHeaderAndPayload`) — not inside a
ServerAuthConfig subobject block. Both `postbits` (bits before `NumPayloadBits`) and `paybits` (bits in the
array) shift *which GameState field net-index the client lands on*, monotonically marching up the GameState
field list (`ServerState`→`SpectatorClass`→…→`WinningTeam`). At `postbits=0` the client reads net-index **12**,
which is exactly the ServerAuthConfig subobject's **NetGUID=12**. ⇒ the client is consuming the ServerAuthConfig
content-block's bytes as a continuation of the GameState property/field stream. It never resolves the component
(`Instantiating sub-object` never logs), so even a "clean" alignment would discard the array — the toggles
(`GameFeatureToggles num`) can never reach 151 this way.

seed=0 HOLDS only because `bHasRepLayout=0` ⇒ `NumPayloadBits=0` ⇒ there is no payload for the client to misread.

## Why this is a wall (and what's NOT the fix)

- NOT the array element framing (paybits-insensitive at the point of failure).
- NOT a single post-stable field width (postbits response is chaotic — the packed `NumPayloadBits`/handle
  encodings make each +1 bit non-linear; no `postbits` in 0..8 aligns, and combos at postbits=5 just slide the
  landing without ever terminating).
- The stub writes a valid, self-consistent stock UE5.4 content block (decoder MATCH). The divergence is entirely
  in the SUPERVIVE client's (modified, anti-tamper-protected) content-block/subobject read path.

## Recommended next avenues (in priority order)

1. **Deliver toggles WITHOUT a subobject content block.** The client's readiness fires from
   `LokiServerAuthConfig::OnRep_GameFeatureToggles` on the GameState's `ServerAuthConfig` component, so the data
   must reach that component — but maybe not via a content block:
   - **`MulticastSetGameFeatureToggle` RPC** (the component's `[3]` net func, NetMulticast/Reliable). RPCs go
     through `ReceivedRPC` (a different read path than content-block properties) and may be accepted where the
     property array isn't. Needs the RPC's real parameter signature RE'd (the stub currently declares it
     empty). This is the most promising route.
   - Registered-subobject-list (`AActor::bReplicateUsingRegisteredSubObjectList=true` + `AddReplicatedSubObject`)
     — but in the standard (non-Iris) net driver this still emits content blocks, so it likely won't change the
     wire. Verify before investing.
2. **RE the client's `ReadContentBlockPayload` / `ReceivedBunch` field-loop** to learn the exact subobject
   framing the client expects. S87 was blocked (felix/JDK-25 kills Ghidra headless; RPM-dumpimage can't read the
   demand-decrypt/execute-only RCB pages). Unblock via: install a **JDK ≤ 23** for Ghidra headless, or build a
   **VirtualProtectEx-based dumper** to read execute-only pages. Then `tools/ghidra_scripts/FindReadContentBlock.java`.
3. **Accept the S70 spectator as the DS ceiling.** The toggle carrier was an enhancement to stop the
   "feature toggles were not ready" spam / unblock further match progression; the spectator-in-tutorial
   milestone (S70) holds WITHOUT it (`kEnableServerAuthConfig=false`).

## Env at handoff

Reverted to baseline: `kEnableServerAuthConfig=false` (LokiGameStateStub.h) + `forceTutorialMatch=false`
(interactive.go) restore the committed baseline (functional main menu + S85c spectator). All S88 levers
(`-toggleseed`/`-postbits`/`-paybits`) + the splice + diagnostics stay behind `kEnableServerAuthConfig` (inert
at baseline). `tools/re/s87/{decode_payload,sweep_seed,sweep_post,sweep_combo}.{py,ps1}` kept. Recipe unchanged
(elevated PS, Steam first; stub `-injectbits=11 -toggleseed=N -postbits=M -paybits=K -abslog=...`, client
`launch-redirect.ps1 -NoHook`).
