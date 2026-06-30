# Next session prompt — SUPERVIVE Revival dedicated-server stub, session 8

Paste the section between the `---` lines below as the first message of
the new session. It bootstraps the agent fully without re-reading dozens
of files.

---

We're continuing the SUPERVIVE Revival dedicated-server-stub chapter on
branch `dedicated-server-stub` at `G:\git\Supervive Revival Project`.
This is **session 8** of the chapter. Sessions 1–7 captured the
protocol surface, built a working `browse_hook.dll` that hooks
`UEngine::Browse` and rewrites `FURL.Host` to `127.0.0.1`, scaffolded a
UE5.4 stub server that listens on UDP 7777 with the correct
`GameNetDriver` + `StatelessConnectHandlerComponent`, and PROVED via a
diagnostic UDP listener that **the client crashes before sending its
first byte** — strictly in `FMallocBinned2.realloc` when UE's FString
destructor tries to free our static-buffer Host pointer. Today's job
is to fix that ONE crash so the engine actually reaches the wire.

START BY (in this order):
  cd "G:\git\Supervive Revival Project"
  git status
  git log --oneline -8
  # Then read:
  #   docs/dedicated-server-stub.md   (the whole chapter; jump to "Session 7"
  #     section at the bottom — that's where you pick up)
  #   tools/sigbypass-mod/browse_hook.cpp  (current v10 hook implementation;
  #     this is what gets modified)
  # The hero-roster-blocker memory auto-loads and has session 7's
  # writeup at the very top — read that.

THE EXACT BLOCKER:

`browse_hook` v10 sets `FURL.Host.Data` to a `static wchar_t
g_redirect_host[]` array inside our DLL's data segment. UE's FString
destructor unconditionally calls `FMemory::Free(Data)` which routes to
`FMallocBinned2::Realloc(Data, 0, ...)`. Realloc's canary check fails
because our pointer isn't in an FMallocBinned2 bin, fatal error fires
(`canary == 0x0 != 0xe3`), process exits. ALL of this happens BEFORE
the engine sends its first UDP packet — confirmed in session 7 with a
PowerShell listener bound on :7777 that received zero packets.

The fix is browse_hook **v11**: allocate the Host buffer through UE's
own allocator so the destructor's Free path doesn't fail canary.

THE RECON YOU NEED:

The naive approach (find FMallocBinned2's vtable via `vtslot`, locate
Malloc slot) is DEAD: session 7 confirmed `findptr` and `callxref`
return zero hits for both `FMallocBinned2::Realloc` (mod-RVA `0xFE25A9`)
and `FMallocBinned2::Free` (mod-RVA `0xFDFE70`). Both function bodies
exist in the binary but nothing references them — they're inlined and
devirtualized at every call site. The vtable approach doesn't exist
here.

Use the byte-pattern approach instead:

  1. Inlined `FMemory::Malloc` compiles to this x64 pattern in shipping:

       48 8B 05 ?? ?? ?? ??     ; mov rax, [rip+disp]    ; load GMalloc
       48 85 C0                  ; test rax, rax
       74 ??                     ; jz <init-path>
       48 8B 00                  ; mov rax, [rax]         ; load vtable
       ... mov regs for args ...
       FF 60 ??                  ; jmp [rax+slot]         ; tail call

  2. Scan the main module's executable pages for this 3-instruction
     prefix. Collect every distinct `[rip+disp]` target.
  3. The most-common target is GMalloc (it's used by EVERY allocation
     in UE; thousands of hits). Other less-common targets are unrelated
     globals.
  4. The slot offset in `FF 60 ??` is 8 * Malloc's vtable index. UE5
     FMalloc's vtable has Malloc at an index we'll learn from this
     scan.

usmapdump doesn't currently have a byte-pattern command. You'll
probably want to add a `pattern` subcommand (or write a small
sibling Go tool) — see `tools/usmapdump/scan.go` and `helpers.go` for
the read-page-by-page substrate already there. Reusing that
infrastructure is much faster than starting from scratch. Once you
have the scanner, dump the top-10 most-common targets; GMalloc should
be 100×–1000× more common than the next.

After identifying GMalloc:
  - `usmapdump peek <pid> 0x<GMalloc_addr> 8`  → read the FMalloc*
  - The first 8 bytes of the FMalloc instance are the vtable pointer
  - `usmapdump peek <pid> 0x<vtable_addr> 80` → dump the vtable
  - Cross-reference with one of the inlined call sites' `FF 60 XX` to
    figure out which slot is Malloc

THE FIX (browse_hook v11):

In `tools/sigbypass-mod/browse_hook.cpp`:

  - Add a worker-time recon step that finds GMalloc + Malloc slot
    (you can either bake the addresses as constants once known, or do
    runtime scanning inside the DLL)
  - Allocate the Host buffer via
    `GMalloc->Malloc(size_in_bytes, alignment)` where alignment is
    typically 16 (the default for `wchar_t[]`)
  - Copy `"127.0.0.1\0"` into it and use it as `FURL.Host.Data`

Then rebuild and retest end-to-end:

  1. Start the UE5.4 stub server (still running from session 6's setup):
       Start-Process -FilePath `
         'H:\Unreal Engine\UE_5.4\Engine\Binaries\Win64\UnrealEditor-Cmd.exe' `
         -ArgumentList '"G:\git\Supervive Revival Project\unreal-stub\Loki.uproject"', `
           '/Engine/Maps/Entry?listen','-game','-server','-log','-Port=7777', `
           '-nullrhi','-NoSplash','-Unattended'
     Wait ~15-20s for engine init. Verify with
     `Get-NetUDPEndpoint -LocalPort 7777`.

  2. (Optional) Re-bind the diagnostic listener — but actually no, with
     a real server you don't need it. The server's Loki.log will show
     incoming connections directly.

  3. Launch the SUPERVIVE client with -Hook:
       .\configs\launch-redirect.ps1 -Hook .\tools\sigbypass-mod\browse_hook.dll

  4. Expected outcome: client reaches LobbyV2 browse, rewrites Host,
     dials our server. Server's Loki.log shows a NEW client connection
     attempt. The StatelessConnect handshake will then either complete
     or fail on the NetCL mismatch (server reports `NetCL: 33043543`,
     client reports `NetCL: 0`). That's blocker #1 from session 6 — fix
     it next by adding `FNetworkVersion::ProcessOverrideCallback` to
     the Loki module's `StartupModule()` (see Loki.cpp, currently just
     IMPLEMENT_PRIMARY_GAME_MODULE).

KEY ADDRESSES + ANCHORS (mod-RVAs in SUPERVIVE-Win64-Shipping.exe;
each session's launch shifts the absolute base but RVAs are stable):

  UEngine::Browse                          0x3EC57D0   (entry; hooked by v10)
  FMallocBinned2::Realloc (body, inlined)  0xFE25A9    (canary at 0xFE25FD)
  FMallocBinned2::Free   (body, inlined)   0xFDFE70
  GGameThreadId slot                       0x9D49158
  "FMallocBinned2 Attempt to realloc..."    0x76A0C20
  "FMallocBinned2 Attempt to free..."       0x76A0AD0
  "GMalloc_CLASS=%d..."                    0x81C3AE2  (debug only)

CHAPTER STATE AT END OF SESSION 7:

  Server-side:  UE5.4 stub server is RUNNING when launched. UDP 7777
                  listens. GameNetDriver + StatelessConnectHandlerComponent
                  loaded. Server's Loki.log waits for incoming
                  connections. The server's NetCL is 33043543 (vs
                  client's 0) — blocker #1 — but that doesn't matter
                  until blocker #2 is fixed because no client packet
                  reaches the server yet.

  Client-side:  browse_hook v10 (`tools/sigbypass-mod/browse_hook.dll`)
                  successfully patches `UEngine::Browse`, reads the FURL,
                  rewrites Host to `127.0.0.1`. Client crashes in
                  FMallocBinned2 before sending any UDP — blocker #2 —
                  which is what this session fixes.

GUARDRAILS (per CLAUDE.md):

- Branch is `dedicated-server-stub`. Commit + push each meaningful step.
  Push needs `gh auth` or system git credential helper; user pushes
  manually if interactive prompts fail.
- Don't mutate the running game without warning the user first.
- The hosts file redirect is already active; don't run
  `configs/launch-redirect.ps1 -Revert` casually.
- Steam must be running before the game launches (else Auth Failure
  14005).
- If the new pattern-scan subcommand to usmapdump produces gigabytes of
  output, redirect to a file or paginate.

TOOLING ALREADY BUILT (do not duplicate):

  tools/usmapdump/usmapdump.exe  (subcommands: info, names, objects,
                                  extract, strings, wstrings, xrefstr,
                                  callxref, findptr, peek, disasm,
                                  vtslot, vtdump, nameid, poke. Add
                                  a `pattern` subcommand for this
                                  session's recon.)
  tools/inject/inject.exe         (manual-map DLL injector; supports
                                  mmap, watch, watch-now, launch
                                  subcommands)
  tools/sigbypass-mod/browse_hook.cpp   (the v10 hook — extend here for v11)
  configs/launch-redirect.ps1     (already has -Hook flag from session 4)
  unreal-stub/                    (the UE5.4 Loki project — Game + Editor
                                  targets built. Loki.exe Game build
                                  has an engine-content asset bug;
                                  use UnrealEditor-Cmd.exe with the
                                  project instead — pattern documented
                                  in docs/dedicated-server-stub.md
                                  Session 6 section.)
  unreal-stub/udp7777-listener.ps1   (diagnostic UDP listener; only
                                  needed if the recon goes sideways
                                  and you want to re-verify the
                                  client sends nothing pre-crash.
                                  Already proven once; can ignore.)

LARGER CONTEXT REMINDER:

The original goal of this multi-chapter project is to make the
SUPERVIVE Missions modal (and other content panels) populate after
the official servers were retired. The diagnostic phase (sessions 1-5
of the chapter prior to this one) established that the menu's empty
state is server-replication-dependent and only a UE5.4 stub server can
deliver the data. Sessions 1-7 of THIS chapter built the trigger
(browse_hook rewrites the engine's Browse URL to our stub) and the
receiver (UE5.4 stub server listening on UDP 7777). Today closes
the last gap so the engine actually connects.

Once the StatelessConnect handshake completes end-to-end, the rest of
the chapter is "write the Loki module's `ALokiPlayerState_Missions`
class and have it replicate mission data on join." That's normal
UE5.4 dev work, not RE work.

If you have any doubt about a step, ask the user before running it —
the chapter has had a lot of trial-and-error and the user has good
intuition about what's safe vs. risky.
