# Next-session handoff (S89) — DS toggle carrier: the content-block route is a WALL; pivot to the RPC route

Branch `dedicated-server-stub`. Continues S88 (docs/session-88-toggle-payload-fixed-offset.md). The S88 task
(measure the toggle payload delta, then match the array framing) is **complete on the measurement** and
**closed on the array-framing approach**: it is a WALL, for a reason deeper than array framing.

---

## PASTE-ABLE OPENING PROMPT

> Continue the SUPERVIVE dedicated-server toggle-carrier work on branch `dedicated-server-stub`.
> Read first: (1) `docs/next-session-prompt-s89.md` (this file), (2) `docs/session-88-toggle-payload-fixed-offset.md`,
> (3) memory `supervive-dedicated-server-status` (tail = S88).
>
> S88 result: the `GameFeatureToggles` payload delta is a FIXED offset (proven), but the array framing is NOT
> the cause. The SUPERVIVE client reads the ServerAuthConfig content-block payload AS GameState field-cache
> entries and NEVER resolves the subobject (postbits + paybits both march the client's read up the GameState
> field-index list; at postbits=0 it reads net-index 12 = the ServerAuthConfig NetGUID). So NO bit-splice on the
> content block can populate the toggles. The content-block subobject route is a dead end without RE'ing the
> client's read path (anti-tamper-blocked).
>
> Pivot: deliver the toggles via the component's `MulticastSetGameFeatureToggle` RPC (LokiServerAuthConfig net
> func [3], NetMulticast/Reliable) — RPCs use `ReceivedRPC` (a different client read path than content-block
> properties) and may be accepted where the property array isn't. Step 1 (RE the RPC signature) is DONE:
> `void MulticastSetGameFeatureToggle(TEnumAsByte<ELokiGameFeatureToggle> Toggle, bool bValue)` — a per-toggle
> reliable-multicast setter (Outer LokiServerAuthConfig, confirmed via RPM). Step 2 = mirror those 2 params on
> the stub's UFUNCTION + call it server-side (multicast) per toggle after the client joins, and check whether the
> readiness spam stops / `GameFeatureToggles num` rises. Fallback routes + all levers are in the handoff.
>
> Env: elevated PS, Steam first. To resume DS work: flip `kEnableServerAuthConfig=true` (LokiGameStateStub.h) +
> `forceTutorialMatch=true` (interactive.go), rebuild the stub. Recipe in the S88 doc.

---

## 30-second status

- **FIXED vs per-element: FIXED (answered).** injectbits=11, seeds 1/75/151 all → identical "Invalid replicated
  field 12 in LokiGameState"; seed=0 (empty==CDO) HOLDS.
- **Array framing is NOT the cause.** paybits splice left field-12 unchanged; the drop is before the payload.
- **Root cause: the client reads the subobject content-block as GameState field-cache entries, never resolving
  the component** (no "Instantiating sub-object" logs). Both postbits and paybits shift which GameState field the
  client lands on, monotonically up the field list. No bit-injection alignment holds, and even a clean alignment
  would discard the array ⇒ toggles can never reach 151 via a content block.

## Do NOT re-derive (S88 confirmed)

- Don't re-sweep the array elements / paybits / postbits for a "clean hold" — the response is chaotic and, more
  fundamentally, the client isn't parsing the block as the component's array at all.
- Don't re-open "header solved at N=11" as if it resolved the subobject — it only MOVED the error string.
- The stub writes a bit-perfect stock UE5.4 content block (decode_payload.py MATCH) — the divergence is 100%
  client-side (modified, anti-tamper).

## THE PIVOT — the MulticastSetGameFeatureToggle RPC route (recommended)

The client's toggle readiness fires from `LokiServerAuthConfig::OnRep_GameFeatureToggles`, but the component also
has a replicated net function `MulticastSetGameFeatureToggle` (NetMulticast, Reliable — schema [3]). RPCs are
delivered via `FObjectReplicator::ReceivedRPC` (`ReceivedBunch`'s function branch), a DIFFERENT read path than
the RepLayout/content-block property path that's failing. If the client accepts the RPC, calling it server-side
with the toggle data may mark toggles ready without ever replicating the array.

1. **RE the RPC's real parameter signature — ✅ DONE (S89, live RPM reflection, no anti-tamper).**
   `void ULokiServerAuthConfig::MulticastSetGameFeatureToggle(TEnumAsByte<ELokiGameFeatureToggle> Toggle, bool bValue)`
   — NetMulticast, Reliable, Native (FunctionFlags 0x00024CC0); 2 params / 2-byte frame / void return; param0
   `Toggle` ByteProperty(enum ELokiGameFeatureToggle)@frame 0, param1 `bValue` BoolProperty@frame 1; Outer =
   LokiServerAuthConfig (confirmed). It's a PER-TOGGLE setter (reliable multicast). Wire per call = 1 byte
   (Toggle) + 1 bit (bValue). Tool: `tools/re/ufunc_params.py <PID> <BASE> <UFuncAddr>` (find the addr via
   `find_uclass.py <PID> <BASE> MulticastSetGameFeatureToggle Function`). Mirror these exact params on the stub's
   UFUNCTION (`uint8`/`TEnumAsByte<ELokiGameFeatureToggle> Toggle, bool bValue`) so the sent wire matches; the
   client deserializes per its OWN reflection.
2. **Call it from the stub** (server → client multicast) once per toggle (or bulk), from the GameState/component
   after the client joins. Watch the client: does `feature toggles were not ready` stop + `GameFeatureToggles
   num` rise (`tools/re/s87/gft_num.py`, update PID + addrs via `tools/re/obj_by_class.py`)?
3. Note: the RPC is on the COMPONENT (subobject), so it still travels on the GameState channel as a subobject
   content block with a function field — verify the client accepts a subobject RPC (it may have the same
   subobject-resolution issue). If it does, this route is also blocked and you're down to RE (below).

## Fallback routes

- **RE the client's `UActorChannel::ReadContentBlockPayload` / `FObjectReplicator::ReceivedBunch` field loop**
  to learn the exact subobject framing the client expects. S87/S88 blocked: felix/JDK-25 kills Ghidra headless;
  RPM-dumpimage can't read the demand-decrypt/execute-only RCB pages. Unblock via a **JDK ≤ 23** for Ghidra
  headless (only jdk-25 + jre1.8 installed here — jre1.8 too old for Ghidra 12), OR a **VirtualProtectEx-based
  dumper** to force-read execute-only pages. Then `tools/ghidra_scripts/FindReadContentBlock.java`.
- **Accept S70 spectator as the DS ceiling.** The spectator-in-tutorial milestone holds with
  `kEnableServerAuthConfig=false`; the toggle carrier was only to stop the readiness spam / unblock further
  match progression.

## Tooling built S88 (all present, guarded/inert at baseline)

- `LokiGameStateStub.cpp`: `-toggleseed=N`, `-postbits=M -postpat=P`, `-paybits=N -payat=D -paypat=P` cmdline
  levers + the payload splice in `ReplicateSubobjects` (re-encodes NumPayloadBits). All behind
  `kEnableServerAuthConfig`.
- `tools/re/s87/decode_payload.py` — full content-block + TArray<bool> payload decoder (validated).
- `tools/re/s87/sweep_seed.ps1` (one robust cycle; ⚠ deletes the client Loki.log each cycle + gates on the
  per-cycle stub SPLICE line — the stale-log fix), `sweep_post.ps1` (loops postbits), `sweep_combo.ps1` (loops
  post:pay pairs). Results → `C:\Temp\SweepResults.txt`.

## Env at handoff

Baseline restored: `kEnableServerAuthConfig=false` + `forceTutorialMatch=false` (functional main menu + S85c
spectator). Stub rebuilt inert. All processes stopped. To resume: flip both flags true, rebuild the stub
(`Build.bat LokiEditor Win64 Development -Project=...\Loki.uproject`, kill UnrealEditor-Cmd first), start the
stub on 7777 with the levers, launch `configs\launch-redirect.ps1 -NoHook`.
