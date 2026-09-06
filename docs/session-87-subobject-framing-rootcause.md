# S87 (2026-07-22) — DS toggle carrier: the wall is a CLIENT-SIDE subobject content-block framing diff, NOT the NetGUID export

Branch `dedicated-server-stub`. Continues docs/session-85-netcache-chain-diff.md §11-§14 (the parked
LokiServerAuthConfig game-feature-toggle carrier).

## TL;DR — root cause is now QUANTIFIED and the S86 hypothesis is REFUTED

The toggle carrier (`ULokiServerAuthConfig`, a replicated `TArray<bool> GameFeatureToggles` on a
"ServerAuthConfig" default-subobject of the runtime `ALokiGameState`) drops the client with
`ReadContentBlockHeader: Unable to read sub-object class` → `NOT_IN_CACHE [134524993]` →
`Invalid property terminator handle - Handle=8352` → ConnectionLost.

S86 blamed the package-map **NetGUID export** of a dynamic-outer subobject. **That is wrong.** This session
proved, live + from the captured wire, that:

1. **The component's GUID export WORKS** — the client RESOLVES the ServerAuthConfig subobject
   (`SubObj == NULL` is logged **0** times; only the Warning-level `Unable to read sub-object class` fires,
   which requires `SubObj != NULL` at DataChannel.cpp:4780).
2. **The stub writes a bit-exact stock UE5.4 content block.** Captured wire (LSB-first), decoded
   (`tools/re/s87/decode_cb.py`):
   `bit0 bHasRepLayout=1 | bit1 bIsActor=0 | GUID=12 (bits 2-9, dynamic) | bit10 stableBit=1 |
    NumPayloadBits=1592 (bits 11-26) | payload@27`.
   The server took the **STABLE branch** (`WriteBit(1)` at bit 10) — confirmed by both the diagnostic
   (`IsNameStableForNetworking=1`) and the decoded wire.
3. **The client is ~10-11 bits MISALIGNED by the stable bit.** It reads `bStablyNamed=0` at bit ~20-21 and
   decodes the phantom class GUID **134524993** from **bit 22** (decoder reproduces it exactly:
   matches at extra=10/destroy=1 and extra=11/destroy=0, both class@bit22). Stock UE reads **8** bits for
   the subobject reference; the SUPERVIVE client consumes **~10-11 EXTRA bits** deserializing it.

⇒ The wall is a **client-side (modified-engine) subobject content-block deserialization framing** that reads
extra bytes/bits per subobject reference vs stock UE5.4. The stub's actor-level mirrors
(GameState/PC/Character — S70/S73/S85) work because they use the actor-spawn / class-by-path resolution
paths; **the dynamic-subobject content-block path is the first one the stub has ever exercised**, and it
diverges.

## Confirmed facts (do NOT re-derive)

- Diagnostic at REAL replication time (`ALokiGameState::ReplicateSubobjects` override, guarded by
  `kEnableServerAuthConfig`): `ServerAuthConfig IsNameStable=1 IsSupported=1 IsReplicated=1 |
   compGUID=12 dynamic | classGUID=25 static | GameState IsNameStable=0 GSGUID=10 dynamic`.
  ⇒ server-side **predicate incoherence** (self `IsNameStableForNetworking`=1 via bNetAddressable, but
  `IsFullNameStableForNetworking`=0 because the runtime GameState outer isn't name-stable ⇒ **dynamic** GUID).
  This is real but is **not the fault** — the export/resolution succeeds; the fault is the client's read framing.
- Content-block header is **bit-symmetric** in stock UE5.4 (verified from DataChannel.cpp:4429/4562 + a
  5-agent engine-source workflow): `{bHasRepLayout, bIsActor, packed NetGUID, stableBit}` — no
  UE_BUILD_SHIPPING/TEST/EngineNetVer/CVar gate changes the count.
- `NET_ENABLE_CHECKSUMS 0` (CoreNet.h:734) ⇒ `NET_CHECKSUM`/`NET_CHECKSUM_OR_END` are **no-ops everywhere**.
- `ExportNetGUID` writes to a **separate** `CurrentExportBunch` (PackageMapClient.cpp:1320), not the content
  block ⇒ no inline bytes injected by the export.
- Client `EngineNetworkVersion: 34` (stock UE5.4 latest); stub is stock 5.4 ⇒ **no version mismatch**.
- `ULokiIpConnection` overrides only `InitHandler` (handshake) ⇒ does not touch bunch/export byte framing.
- `SubObj == NULL` never logged ⇒ the component resolves; the export is NOT the wall.

## Tooling built this session

- `ALokiGameState::ReplicateSubobjects` override (LokiGameStateStub.{h,cpp}) — logs name-stability + NetGUIDs
  at replication time AND hex-dumps the exact content-block bits it writes for ServerAuthConfig (guarded).
- `tools/re/s87/decode_cb.py` — offline decoder: parses the LSB-first content-block hex, replays the stock read
  (`SerializeIntPacked`/`64`: 8-bit groups, bit0=continuation, 7 data bits), and searches read-offsets to
  locate where the client's phantom class GUID (134524993) decodes ⇒ pins the ~10-11 bit shift.

## Two guid-staticness fixes TESTED and FALSIFIED (this session)

**Fix #1 — make the GameState name-stable (`ALokiGameState::SetNetAddressable()`).** REGRESSED. DIAG showed
the component AND GameState both went STATIC (compGUID=25 static, GameState IsNameStable=1 GSGUID static). The
connection stopped CRASHING (held 2+ min, client loaded LVL_Tutorial + all hero GameplayCues) BUT: no
"Entering game state LokiGameState", no live match GameState actor (obj_by_class), and **GameFeatureToggles
num=0** on every client ServerAuthConfig (RPM). ⇒ a STATIC GameState does NOT hydrate as a live replica; the
client resolves it to its own local/CDO GameState and the fresh subobject content block is **never read** —
which is why it didn't crash. NOT because static subobjects read cleanly. Reverted.

**Fix #2 — static COMPONENT only, GameState left DYNAMIC** (`ULokiServerAuthConfig::IsFullNameStableForNetworking()
-> true`, a virtual override — Object.h:1010 — so `FNetGUIDCache::IsDynamicObject` is false ⇒ static component
guid without touching the GameState). DIAG confirmed the decoupling: **compGUID=25 STATIC, GameState GSGUID=10
DYNAMIC**. Result: the client read the **IDENTICAL** phantom class GUID **134524993** and dropped — SAME
failure. ⇒ **the client's ~10-11 extra subobject-read bits are INTRINSIC to its subobject content-block
protocol, NOT guid-static/dynamic-dependent** (both guid 12 and 25 pack to 8 bits ⇒ identical framing ⇒
identical misread). Reverted.

## Next: the fix REQUIRES matching the client's subobject framing (RE the client)

The desync is a fundamental SUPERVIVE modification to the subobject content-block deserialization (extra
~10-11 bits per subobject reference, independent of guid staticness). The stub writes stock UE5.4. The ONLY
fixes:

1. **RE the client's `UActorChannel::ReadContentBlockHeader` / `UPackageMapClient::InternalLoadObject`** from
   the Ghidra deobf dump (`dumps/toggles/SUPERVIVE-deobf.exe`, IAT rebuilt; xref the committed string
   "Unable to read sub-object class" @ its .rdata address) to read out the exact extra field. Hypotheses to
   check: (a) the client reads an inline ExportFlags byte (+8 bits) + a couple bits for EVERY subobject
   reference (i.e. it treats content-block subobjects like export-bunch entries); (b) a per-subobject
   integrity/version field (anti-cheat). Then WRITE those bits from the server via a HAND-ROLLED content
   block in `ALokiGameState::ReplicateSubobjects` (the injection point already exists). Note: the two
   `UActorChannel::ReplicateSubobject` overloads and `WriteContentBlockHeader` are NOT virtual, but
   `WriteContentBlockHeader`/`WriteContentBlockPayload` are `ENGINE_API` (callable) — so build the header +
   splice the extra bits + write the payload manually (reproduce `UActorChannel::ReplicateSubobject`'s payload
   generation, DataChannel.cpp:4115, using the component's `FObjectReplicator`).
2. **Empirical bit-injection loop** (if RE stalls): since the decode pins the client reading bStablyNamed at
   ~bit 20-21 (vs stock bit 10), hand-roll the content block writing N extra bits (N=8..12, various patterns)
   after the GUID and iterate on which N + pattern makes the client read bStablyNamed=1 (stable branch) and
   `ReceiveProperties` succeed. `tools/re/s87/decode_cb.py` + the CONTENT BLOCK dump verify each attempt offline
   before a live run.
3. Map-placed stably-named carrier (structural; needs IoStore/map edit) — only if readiness turns out to be
   global (S86b argued it fires on the client's GameState component OnRep, so likely NOT viable).

## S87 cont. — RE of the client's ReadContentBlockHeader: BLOCKED by anti-tamper (both routes)

Attempted to read out the exact extra field by RE'ing the client's `UActorChannel::ReadContentBlockHeader`.
Both routes hit the packer:

**Ghidra headless — BLOCKED by felix/JDK-25.** `analyzeHeadless` over `Ghidra/SuperVive` (program
`SUPERVIVE-deobf.exe`) with a new `tools/ghidra_scripts/FindReadContentBlock.java` (finds the function via the
committed "sub-object class" string xref, decompiles it + callees). Two batch gotchas fixed first: the
`> log` redirect must live INSIDE the wrapper .bat (else Ghidra's `launch.bat` `for /f in ("%cmdcmdline%")`
double-click check chokes on the `>` → "was unexpected at this time"). Then felix 7.0.5's
`Felix.handleJavaVersionChange` NPEs on JDK 25 ("dataFile is null" / "data file must be inside the data dir")
— CONSISTENTLY here (not intermittent), whether the osgi cache is fresh or restored. Only jdk-25 + jre1.8 are
installed (jre1.8 too old for Ghidra 12). So the Java-script bundle system can't init → no headless decompile.

**Felix-free capstone — BLOCKED by demand-decrypt.** Built `tools/re/s87/{find_rcb,lea_index,validate_dump}.py`
(capstone + PE parse; find committed RCB log strings, index every LEA-rip target, resolve direct + pointer-slot
refs). The RCB strings ARE committed (deobf rva `0x802881c` "…sub-object class. Actor: %s", `0x802858a`
"…stably named bit", `0x8028e9e` "Instantiating sub-object", etc.) but **NO dump has any code reference to
them** — deobf, merged (union of menu/roster/store/missions/loadout/accountpass), nor the in-match toggles
dump. Took a FRESH `dumpimage` of the LIVE client right after triggering the desync (kEnableServerAuthConfig=
true → the ServerAuthConfig content block runs RCB's error branch → "Unable to read sub-object class" logged
this session) → `dumps/rcb/SUPERVIVE-Win64-Shipping.dump.exe` (65.98%, IB=0x7FF79D3B0000). STILL zero refs to
any RCB string. Validation: `"Entering game state"` (ran at travel) IS captured (pointer-slot LEA), but
`"sub-object class"` (ran LATER, at the desync) is NOT — so it is NOT a re-encryption-by-age effect; RCB's
code pages are simply **unreadable via ReadProcessMemory** (demand-decrypt gap or execute-only page
protection) even though the function demonstrably executed. My LEA scan is validated (it finds the toggle-fmt
string ref that the S85 Ghidra pass used).

⇒ The RE is blocked by the packer through every automated tool available here (felix for Ghidra headless;
RPM-based dumpimage for capstone). RCB's `.text` never lands in a readable dump.

**Recommended next path — EMPIRICAL bit-injection (sidesteps the RE entirely):** hand-roll the ServerAuthConfig
content block in `ALokiGameState::ReplicateSubobjects` (the injection point already exists): write
`bHasRepLayout=1`, `bIsActor=0`, `*Bunch << ServerAuthConfig` (the GUID), then **N test bits**, then the stable
bit `WriteBit(1)`, then the payload. Generate the payload via a scratch FOutBunch from the component's
`FObjectReplicator` (`Channel->FindOrCreateReplicator(ServerAuthConfig)` → replicate props into it), then
`Bunch->SerializeIntPacked(payloadBits)` + append. Sweep N=8..12 and a few bit patterns; the client succeeds
when it reads `bStablyNamed=1` and `ReceiveProperties` completes (no "Unable to read sub-object class", no
ConnectionLost, and GameFeatureToggles num=151 on the client via `tools/re/s87/gft_num.py`). `tools/re/s87/
decode_cb.py` + the CONTENT-BLOCK byte dump verify each attempt offline before a live run. The decode already
pins the client reading bStablyNamed at ~bit 20-21 vs stock bit 10, so N≈10-11 is the starting point.
Alternative RE routes if needed: a VirtualProtectEx-based dumper (to read execute-only pages), or the Ghidra
GUI (interactive felix, if it works there) — but the GUI still needs RCB captured in a readable dump first.

**Tooling left for next session:** `tools/ghidra_scripts/FindReadContentBlock.java`, `tools/re/s87/{find_rcb,
lea_index,validate_dump,run_ghidra.bat}.py`, `dumps/rcb/` (fresh post-desync dump, git-ignored). Ghidra
headless invocation that gets past the batch gotcha: `tools/re/s87/run_ghidra.bat` (redirect inside; felix still
NPEs — needs a JDK ≤ 23).

## S87 cont. — EMPIRICAL bit-injection: the subobject-HEADER framing is SOLVED (N=11); payload remains

Since the RE was anti-tamper-blocked, landed the fix empirically. In `ALokiGameState::ReplicateSubobjects`
(guarded), write the FULL content block into a scratch `FOutBunch` via `Channel->ReplicateSubobject`, then
re-emit it into the real bunch with **N test bits spliced in right after the subobject GUID** (before the
stable bit). N + pattern are command-line-driven (`-injectbits=N -injectpattern=P` on the stub) so the sweep
needs no rebuild. The stub also dumps the spliced block for offline `decode_cb.py` verification.

**Sweep N=8-13 (pattern=0), client-side result:**
| N | client failure | reading |
|---|---|---|
| 8 | `Invalid field 2 in LokiGameState` | header way off |
| 9 | `Unable to read sub-object class` + `FAILED LokiServerAuthConfig` | bStablyNamed=0 (non-stable) |
| 10 | `FAILED LokiGameState` (terminator 2400) | bStablyNamed=1 by coincidence (bit21=payload[0]=1), payload off by 1 |
| **11** | `Invalid field 12 in LokiGameState`, **NO "sub-object class"** | **bStablyNamed=1 (stable branch) — HEADER SOLVED** |
| 12 | (stub didn't replicate that run) | — |
| 13 | `Unable to read sub-object class (SubObj==NULL)` | far off |

**HEADER SOLVED at N=11.** Decoding the N=9 and N=10 spliced blocks pins it exactly: the client reads
`bStablyNamed` at **absolute bit 21** (N=9 bit21=0 → non-stable; N=10 bit21=1 → stable). So the client's
subobject-header extra field is **11 bits** (guid ends at bit 10, +11 = bStablyNamed at bit 21). With
`-injectbits=11` the client reads `bStablyNamed=1`, takes the STABLE branch, resolves the component, reads the
payload length, and enters the `LokiServerAuthConfig` payload — the `"Unable to read sub-object class"` desync
is GONE. This is the mechanism that eluded S86; empirically nailed without the RE.

**REMAINING = the subobject PAYLOAD framing.** With N=11 the drop is `Invalid replicated field 12 in
LokiGameState` (a SPURIOUS content block after ServerAuthConfig) and RPM confirms `GameFeatureToggles` num=0 on
the client (toggles NOT applied). ⇒ the client reads the `GameFeatureToggles` `TArray<bool>` payload in a
DIFFERENT bit count than the stub writes, leaving leftover bits the content-block loop misreads. This is a
SECOND framing difference, in the array serialization (SUPERVIVE's modified engine again).

**Next (payload):** (a) DIAGNOSTIC — make the toggle-seed count command-line-driven (`-toggleseed=`), sweep
0/1/75/151, and measure how the leftover-bit count scales with element count ⇒ the per-element bit delta ⇒ the
array framing difference (seed=0 = empty==CDO should send an empty payload and, with N=11, may hold — confirming
the issue is purely the array elements). (b) then match the client's array framing (splice into the payload +
re-encode NumPayloadBits, or write the array the way the client reads it). (c) or the RE, if the anti-tamper
dump can be beaten (execute-only pages). `kInjectBits` default is now **11** (the header solution); the splice +
`GetInjectBits/GetInjectPattern` cmdline hooks + `tools/re/s87/sweep.ps1` stay as tooling.

## Reverted to baseline at handoff

`kEnableServerAuthConfig=false` (LokiGameStateStub.h) + `forceTutorialMatch=false` (interactive.go) restored
(committed baseline: functional main menu + S85c spectator). Both guid-staticness experiments removed; the
`ReplicateSubobjects` diagnostic + byte-capture override STAYS (guarded, inert at baseline) as reusable
tooling. `tools/re/s87/decode_cb.py` (content-block decoder) + `tools/re/s87/gft_num.py`/`gft_scan.py` (RPM
GameFeatureToggles readers) kept.

## Env at handoff

`forceTutorialMatch=true` (interactive.go) and `kEnableServerAuthConfig=true` (LokiGameStateStub.h) are
flipped ON for DS work — **revert both to false** to restore the committed baseline (functional main menu +
S85c spectator). Stub build recipe: `Build.bat LokiEditor Win64 Development -Project=...\Loki.uproject`
(kill UnrealEditor-Cmd first). Stub run: `-abslog=C:\Temp\Ds*.log` (absolute + space-free). Client:
`configs\launch-redirect.ps1 -NoHook` (does NOT auto-re-arm after a DS failure — relaunch to retry).
