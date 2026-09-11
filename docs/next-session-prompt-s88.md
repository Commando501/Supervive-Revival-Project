# Next-session handoff (S88) — DS toggle carrier: match the ServerAuthConfig PAYLOAD framing

Branch `dedicated-server-stub`. Continues S87 (docs/session-87-subobject-framing-rootcause.md). The
subobject-HEADER framing is **SOLVED empirically (N=11)**; one contained **payload** framing step remains.

---

## PASTE-ABLE OPENING PROMPT (for the fresh session)

> Continue the SUPERVIVE dedicated-server toggle-carrier work on branch `dedicated-server-stub`.
> Read first, in order: (1) `docs/next-session-prompt-s88.md` (this file), (2)
> `docs/session-87-subobject-framing-rootcause.md` §"EMPIRICAL bit-injection", (3) memory
> `supervive-dedicated-server-status` (tail = S87).
>
> Where we are: the S86 "package-map desync" wall is BROKEN. The client's subobject **content-block header**
> has an 11-bit extra field (client reads `bStablyNamed` at absolute bit 21); with the stub splicing 11 bits
> after the subobject GUID (`kInjectBits=11`), the `"Unable to read sub-object class"` desync is GONE and the
> client resolves the `LokiServerAuthConfig` component + enters its payload. REMAINING = the client reads the
> `GameFeatureToggles` `TArray<bool>` **payload** in a different bit count than the stub writes (leftover bits
> → spurious `Invalid field 12 in LokiGameState` block → drop; `GameFeatureToggles` num=0 on the client).
>
> Immediate task: measure that payload delta. Make the toggle-seed count command-line-driven
> (`-toggleseed=N`), sweep seed=0/1/75/151 with `-injectbits=11`, and determine whether the payload
> mismatch is a FIXED offset (same leftover for all seeds) or PER-ELEMENT (scales with seed) — seed=0
> (empty array == CDO) should send an empty payload and, with N=11, likely HOLD (isolating the array
> elements as the sole remaining cause). Then match the client's array framing. Confirmed facts are in the
> handoff — don't re-derive (don't re-open the header/N=11 result or the char/PlayerState fixes).
>
> Env: elevated PS, Steam first. Recipe + tooling are in the handoff.

---

## 30-second status

- **Header: SOLVED.** `ALokiGameState::ReplicateSubobjects` (LokiGameStateStub.cpp, guarded by
  `kEnableServerAuthConfig`) writes the full content block to a scratch `FOutBunch` via
  `Channel->ReplicateSubobject`, then re-emits it into the real bunch with `kInjectBits` bits spliced right
  after the subobject GUID. `kInjectBits` default = **11** (also `-injectbits=N` cmdline). At N=11 the client
  reads `bStablyNamed=1` (STABLE branch) — NO `"Unable to read sub-object class"`.
- **Payload: OPEN.** At N=11 the client drops on `Invalid replicated field 12 in LokiGameState` (a spurious
  block after ServerAuthConfig) and RPM shows `GameFeatureToggles` num=0 (toggles not applied). The client
  reads the `TArray<bool>` payload in a different bit count → leftover bits.

## Confirmed facts — DO NOT re-derive (docs/session-87)

- The client's subobject-header extra field is **11 bits**: it reads `bStablyNamed` at **absolute bit 21**
  (decoded from the N=9 spliced block bit21=0 → non-stable branch vs the N=10 block bit21=1 → stable). Sweep
  N=8-13 confirmed N=11 is the only value with `bStablyNamed=1` + no `"sub-object class"`.
- The stub writes a **bit-exact stock UE5.4** content block otherwise (verified S87). The desync is entirely
  SUPERVIVE-client-side framing (its modified engine reads extra bits per subobject).
- The `GameFeatureToggles` prop is a native `TArray<bool>` (151 elements), RepIndex-aligned (boot dump:
  LokiServerAuthConfig ClassReps=3 `[2] GameFeatureToggles`, client-matched). So the header/handle align; the
  divergence is the ARRAY serialization bit count.
- RE of the client's `ReadContentBlockHeader` is **anti-tamper-blocked** (felix/JDK-25 kills Ghidra headless;
  RPM-dumpimage can't read the code pages — execute-only/demand-decrypt). So work this empirically.
- The S85 char field-32 + PlayerState fixes are SOLVED — do not re-open.

## THE IMMEDIATE TASK — toggle-seed sweep to measure the payload delta

### 1. Make the toggle-seed cmdline-driven (small edit, follows the `-injectbits` pattern)

In `unreal-stub/Source/Loki/LokiGameStateStub.cpp`:
- Add next to `GetInjectBits()`:
  ```cpp
  static int32 GetToggleSeed()
  {
      static int32 Cached = []{ int32 v = LOKI_GAME_FEATURE_TOGGLE_COUNT;
          FParse::Value(FCommandLine::Get(), TEXT("toggleseed="), v); return v; }();
      return Cached;
  }
  ```
- In `ALokiGameState::BeginPlay` change (currently line ~74):
  ```cpp
  ServerAuthConfig->SeedAllToggles(/*bValue=*/true, GetToggleSeed());   // was LOKI_GAME_FEATURE_TOGGLE_COUNT
  ```
  (`ULokiServerAuthConfig::SeedAllToggles` does `GameFeatureToggles.Init(bValue, Count)`; Count=0 ⇒ empty
  array == the client's CDO ⇒ no delta ⇒ WriteSubObjectInBunch emits an empty payload, DataChannel.cpp:5447.)

Flip `kEnableServerAuthConfig=true` (LokiGameStateStub.h) + `forceTutorialMatch=true` (interactive.go), then
build ONCE. After that, sweep seed WITHOUT rebuilding via the stub cmdline (`-toggleseed=N -injectbits=11`).

### 2. Sweep and interpret

Adapt `tools/re/s87/sweep.ps1` (it currently sweeps `-injectbits`; change it to fix `-injectbits=11` and sweep
`-toggleseed` over `@(0,1,75,151)`), or run each manually (recipe below). For each seed, record the client
error + whether the connection HOLDS + the stub's `SPLICED BLOCK` bytes.

- **seed=0 HOLDS (no drop, GameState enters, no "field 12")** ⇒ the header is fully solved and the ONLY
  remaining issue is the array-element serialization. (But toggles stay num=0 — empty array — so this is a
  DIAGNOSTIC, not the fix.)
- **Fixed vs per-element:** if the client's failure offset is the SAME for seed=1/75/151 ⇒ a FIXED framing
  diff (a leading array-count field or a trailing marker read differently) ⇒ splice a fixed bit adjustment
  into the payload. If it SCALES with seed ⇒ a PER-ELEMENT diff (each bool framed differently) ⇒ match the
  per-element format.
- Decode the stub's `SPLICED BLOCK` for each seed with `tools/re/s87/decode_cb.py` (extend it to walk past the
  header into `NumPayloadBits` + the array) to see the stub's exact array wire; compare against where the
  client fails.

### 3. Match the client's array framing (the fix)

Once the delta is known: extend the splice in `ReplicateSubobjects` to also adjust the PAYLOAD (inject/remove
bits in the array region) **and re-encode `NumPayloadBits`** accordingly (it's a `SerializeIntPacked` right
after the stable bit; the scratch block is `bHasRepLayout,bIsActor,GUID,stable,NumPayloadBits,payload`).
SUCCESS = no "field 12", connection HOLDS in LVL_Tutorial, `GameFeatureToggles` num=151 on the client
(`tools/re/s87/gft_num.py` — update PID + the ServerAuthConfig addresses from `tools/re/obj_by_class.py`), and
the 112× `"feature toggles were not ready"` spam STOPS.

## Environment / how to run

Elevated PowerShell, **Steam running first** (else Auth Failure 14005).

1. Flip `kEnableServerAuthConfig=true` (LokiGameStateStub.h) + `forceTutorialMatch=true` (interactive.go).
2. Build the stub (kill `UnrealEditor-Cmd` first — LNK1104 otherwise):
   `cmd /c '"H:\Unreal Engine\UE_5.4\Engine\Build\BatchFiles\Build.bat" LokiEditor Win64 Development -Project="G:\git\Supervive Revival Project\unreal-stub\Loki.uproject" -WarningsAsErrors > C:\Temp\build.log 2>&1'`
   (~5-10 s incremental; exit 0.)
3. Start the stub on 7777 with the sweep args (⚠ `-abslog` MUST be absolute + SPACE-FREE):
   `Start-Process 'H:\Unreal Engine\UE_5.4\Engine\Binaries\Win64\UnrealEditor-Cmd.exe' -ArgumentList '"G:\git\Supervive Revival Project\unreal-stub\Loki.uproject"','/Engine/Maps/Entry?listen','-game','-server','-Port=7777','-nullrhi','-NoSplash','-Unattended','-injectbits=11','-toggleseed=0','-abslog=C:\Temp\Ds.log' -WindowStyle Hidden`
   Confirm bind via `Get-NetUDPEndpoint -LocalPort 7777`.
4. Launch the client: `.\configs\launch-redirect.ps1 -NoHook` (returns early; game boots + connects in ~1-2 min).
   ⚠ The client does NOT auto-re-arm after a DS failure — RELAUNCH the game for each sweep value (kill
   `SUPERVIVE-Win64-Shipping` first). Restarting only the stub is not enough.
5. Client log: `C:\Users\eastr\AppData\Local\SUPERVIVE\Saved\Logs\Loki.log` (fresh per launch). Grep
   `sub-object class|terminator handle|Invalid replicated field|ReceiveProperties FAILED|Entering game state
   LokiGameState`. Stub log = the `-abslog` path; grep `SPLICE (S87)` + `SPLICED BLOCK`.
6. Client PID/base for RPM: `$g=Get-Process SUPERVIVE-Win64-Shipping; "{0} 0x{1:X}" -f $g.Id,[int64]$g.MainModule.BaseAddress`.

## Tooling inventory (all present)

- `unreal-stub/Source/Loki/LokiGameStateStub.cpp` — `ReplicateSubobjects` splice + `GetInjectBits()`/
  `GetInjectPattern()` cmdline hooks + the `SPLICE`/`SPLICED BLOCK` diagnostics. Add `GetToggleSeed()` here.
- `tools/re/s87/decode_cb.py` — offline UE `SerializeIntPacked` decoder for the `SPLICED BLOCK` bytes (extend
  to walk the payload/array). `tools/re/s87/sweep.ps1` — the sweep loop (repoint to `-toggleseed`).
- `tools/re/s87/gft_num.py` / `gft_scan.py` — RPM readers for `GameFeatureToggles` num (offset scan).
- `tools/re/obj_by_class.py <PID> <BASE> LokiServerAuthConfig` — list the live component instances.
- `dumps/rcb/` — a post-desync dumpimage (RCB code NOT captured — anti-tamper; kept for a future
  VirtualProtectEx-based dump or JDK≤23 Ghidra attempt).

## Revert to baseline when done

`kEnableServerAuthConfig=false` (LokiGameStateStub.h) + `forceTutorialMatch=false` (interactive.go) restore
the committed baseline (functional main menu + S85c spectator). All S87 splice/diagnostic code stays behind
`kEnableServerAuthConfig` (inert at baseline). Kill `SUPERVIVE-Win64-Shipping`, `UnrealEditor-Cmd`, `ags`.
