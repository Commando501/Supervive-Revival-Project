// decrypt_trigger_probe — S121: does a READ fault decrypt a .text page, or only an EXECUTE fault?
//
// WHY THIS EXISTS. The shipping image's .text is selectively encrypted and pages materialise
// lazily. The repo carried THREE mutually inconsistent statements about the trigger — "on access"
// (dumpimage.go:67), "on execution" (fk3-fk4-settled.md:137), "necessarily only as they execute"
// (fk10-protector-identified.md:264) — and NONE had ever been measured; all three were the same
// inference from the encryption model. See docs/fk18-fk19-multistate-merge-settled.md §12.1.
//
// WHAT IS ALREADY MEASURED (S121, live, read-only):
//   * dark .text pages are COMMIT / PAGE_NOACCESS / MEM_MAPPED — 15,672 EXECUTE_READ + 14,609
//     NOACCESS = 30,281, exactly the .text page count.
//   * PAGE_NOACCESS faults on READ, WRITE **and** EXECUTE. So "only as they execute" is not
//     entailed by the page state; both are architecturally possible and the question is real.
//   * decryption is fault-driven, page-granular (16.1% of multi-page functions are partly
//     decrypted) and monotonic (0 pages reverted in 151 s).
//   * faults are intercepted by a ProcessInstrumentationCallback (runtime.dll+0x8d9040) that
//     rewrites the kernel return address when it equals ntdll!KiUserExceptionDispatcher. NOT a
//     VEH, NOT an ntdll patch — both refuted.
//   * ReadProcessMemory from OUTSIDE does nothing: 0 of 200 dark pages, against 200/200 on
//     decrypted pages. The kernel services RPM without running user-mode code in the target, so
//     the protector's dispatcher never sees a fault. ⇒ THE FAULT MUST BE RAISED IN-PROCESS.
//     That is the entire reason this has to be an injected DLL rather than another tool.
//
// THE STAKE. If a READ fault decrypts, one guarded byte-read per dark page followed by one
// `usmapdump dumpimage` takes .text from ~55% toward ~100% with ZERO gameplay — roughly 14,600
// pages. If only EXECUTE decrypts, that lever does not exist and coverage stays gated on running
// more game code (crash-time capture, Angelscript, exec verbs — §12.2).
//
// DESIGN NOTES, each load-bearing:
//   * SEH only (__try/__except). C++ exceptions are documented-fatal in this process, and the
//     reason recorded for that (a missing function table) was REFUTED this session, so the rule
//     now stands with no known mechanism — which is a reason to be MORE careful, not less.
//   * NO module-image write of any kind. Per S111/S112 a standing .text patch is the measured
//     lethal variable (10/10 armed windows died with one vs 2/30 without). This probe writes
//     nothing anywhere: it reads one byte.
//   * ONE page by default. Agent A's ordering: probe a single page, read the result back, and
//     only then consider looping. -DPROBE_ALL=1 enables the sweep and is OFF unless asked for.
//   * Three controls in the SAME run, because any one of them alone leaves the result
//     uninterpretable:
//       (a) the identical read against an already-decrypted EXECUTE_READ page MUST succeed —
//           proves the probe can read at all;
//       (b) the identical read against an unmapped address MUST fault and leave protection
//           unchanged — proves __except fires and that a fault is distinguishable from success;
//       (c) protections are logged before AND after — and the authoritative readout is an
//           EXTERNAL VirtualQueryEx from another process, because the protector zeroes the
//           in-process TEB instrumentation fields, i.e. in-process stealth state lies.
//   * The marker is opened FILE_APPEND_DATA and flushed per line, so a line survives the process
//     being killed mid-probe — which is a live possibility (see the hazard note).
//
// HAZARD. This raises an access violation inside the protector's own hooked dispatcher, and
// runtime.dll+0x87c910 range-checks CONTEXT.Rip and registers before handing on. A fault whose
// RIP sits in an injected module may be classified as tampering. Treat a dead process as a
// POSSIBLE OUTCOME, not a bug: use a throwaway -NoHook launch, and keep an OS handle open across
// exit so the exit code is captured — `0x0000DEAD` is the protector's own NtTerminateProcess
// sentinel (runtime.dll+0x80f7f0) and is itself an informative result.
//
// Build:  .\build.ps1 -Name decrypt_trigger_probe
// Inject: tools\inject\inject.exe watch-now SUPERVIVE-Win64-Shipping.exe decrypt_trigger_probe.dll
// Marker: docs/decrypt-trigger-marker.txt
#include <windows.h>
#include <cstdint>
#include <cstdio>
#include <cstdarg>
#include <cstring>

static const char* kMarkerPath =
    "G:\\git\\Supervive Revival Project\\docs\\decrypt-trigger-marker.txt";

#ifndef PROBE_ALL
#define PROBE_ALL 0
#endif
#ifndef PROBE_DELAY_MS
#define PROBE_DELAY_MS 8000
#endif

static void Marker(const char* m) {
    HANDLE h = CreateFileA(kMarkerPath, FILE_APPEND_DATA,
                           FILE_SHARE_READ | FILE_SHARE_WRITE, nullptr,
                           OPEN_ALWAYS, FILE_ATTRIBUTE_NORMAL, nullptr);
    if (h == INVALID_HANDLE_VALUE) return;
    DWORD w = 0;
    WriteFile(h, m, (DWORD)strlen(m), &w, nullptr);
    FlushFileBuffers(h);           // survive a kill mid-probe
    CloseHandle(h);
}
static void Markerf(const char* f, ...) {
    char b[1024];
    va_list a; va_start(a, f);
    _vsnprintf_s(b, sizeof(b), _TRUNCATE, f, a);
    va_end(a);
    Marker(b);
}

static const char* ProtName(DWORD p) {
    switch (p & 0xFF) {
        case PAGE_NOACCESS:          return "NOACCESS";
        case PAGE_READONLY:          return "READONLY";
        case PAGE_READWRITE:         return "READWRITE";
        case PAGE_WRITECOPY:         return "WRITECOPY";
        case PAGE_EXECUTE:           return "EXECUTE";
        case PAGE_EXECUTE_READ:      return "EXECUTE_READ";
        case PAGE_EXECUTE_READWRITE: return "EXECUTE_READWRITE";
        case PAGE_EXECUTE_WRITECOPY: return "EXECUTE_WRITECOPY";
        case 0:                      return "<none/free>";
        default:                     return "<other>";
    }
}

struct PageInfo { DWORD state, protect, type; };
static bool QueryPage(uintptr_t a, PageInfo& out) {
    MEMORY_BASIC_INFORMATION m{};
    if (!VirtualQuery((LPCVOID)a, &m, sizeof(m))) return false;
    out.state = m.State; out.protect = m.Protect; out.type = m.Type;
    return true;
}

// The whole experiment, in one function: read ONE byte under SEH and report whether it faulted.
static bool TryReadByte(uintptr_t addr, unsigned char& val) {
    __try {
        val = *(volatile unsigned char*)addr;
        return true;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return false;
    }
}

static void ProbeOne(const char* label, uintptr_t addr, uintptr_t modBase) {
    PageInfo before{}, after{};
    bool okB = QueryPage(addr, before);
    unsigned char v = 0xAB;
    bool read = TryReadByte(addr, v);
    bool okA = QueryPage(addr, after);
    Markerf("[%s] addr=0x%llX rva=0x%llX\n"
            "        before: %s state=0x%X type=0x%X\n"
            "        read  : %s  byte=0x%02X\n"
            "        after : %s state=0x%X type=0x%X   %s\n",
            label, (unsigned long long)addr,
            (unsigned long long)(addr - modBase),
            okB ? ProtName(before.protect) : "<query failed>", before.state, before.type,
            read ? "SUCCEEDED (no fault)" : "FAULTED (__except taken)", read ? v : 0,
            okA ? ProtName(after.protect) : "<query failed>", after.state, after.type,
            (okB && okA && before.protect != after.protect) ? "<<< PROTECTION CHANGED" : "");
}

static DWORD WINAPI Run(LPVOID) {
    Sleep(PROBE_DELAY_MS);   // let the process settle; the menu decrypts for a few seconds

    uintptr_t modBase = (uintptr_t)GetModuleHandleA(nullptr);
    Marker("\n================ decrypt_trigger_probe ================\n");
    Markerf("module base 0x%llX  PROBE_ALL=%d\n", (unsigned long long)modBase, (int)PROBE_ALL);

    // Locate .text from the PE headers rather than assuming the documented RVA/size.
    auto* dos = (IMAGE_DOS_HEADER*)modBase;
    auto* nt  = (IMAGE_NT_HEADERS64*)(modBase + dos->e_lfanew);
    auto* sec = IMAGE_FIRST_SECTION(nt);
    uintptr_t textVA = 0, textSz = 0;
    for (int i = 0; i < nt->FileHeader.NumberOfSections; ++i) {
        if (!memcmp(sec[i].Name, ".text", 5)) {
            textVA = modBase + sec[i].VirtualAddress;
            textSz = sec[i].Misc.VirtualSize;
            break;
        }
    }
    if (!textVA) { Marker("FATAL: .text not found\n"); return 0; }
    Markerf(".text 0x%llX size 0x%llX\n",
            (unsigned long long)textVA, (unsigned long long)textSz);

    // Census + pick the targets. First NOACCESS page = treatment; first EXECUTE_READ = control (a).
    uintptr_t firstDark = 0, firstLit = 0;
    size_t dark = 0, lit = 0, other = 0;
    for (uintptr_t a = textVA; a < textVA + textSz; ) {
        MEMORY_BASIC_INFORMATION m{};
        if (!VirtualQuery((LPCVOID)a, &m, sizeof(m))) break;
        uintptr_t rb = (uintptr_t)m.BaseAddress, rs = (uintptr_t)m.RegionSize;
        uintptr_t s = rb > textVA ? rb : textVA;
        uintptr_t e = (rb + rs < textVA + textSz) ? rb + rs : textVA + textSz;
        if (e > s) {
            size_t npg = (size_t)((e - s) / 0x1000);
            if ((m.Protect & 0xFF) == PAGE_NOACCESS) { dark += npg; if (!firstDark) firstDark = s; }
            else if ((m.Protect & 0xFF) == PAGE_EXECUTE_READ) { lit += npg; if (!firstLit) firstLit = s; }
            else other += npg;
        }
        a = rs ? rb + rs : a + 0x1000;
    }
    Markerf("census: EXECUTE_READ %llu pages | NOACCESS %llu pages | other %llu pages\n",
            (unsigned long long)lit, (unsigned long long)dark, (unsigned long long)other);
    Markerf("targets: firstDark=0x%llX  firstLit=0x%llX\n",
            (unsigned long long)firstDark, (unsigned long long)firstLit);
    if (!firstDark) { Marker("no NOACCESS page in .text — nothing to test.\n"); return 0; }

    // --- ORDER CORRECTED after S121 run 1. ---
    // Run 1 ran the controls first, as specified, and control (b) -- a DELIBERATE read of an
    // unmapped address -- KILLED THE PROCESS: the marker stops at its header, __except never
    // returned, and the death left NO artifact (no crashpad handoff, no Fatal error line, no
    // UECC dir, no minidump). So a deliberate AV raised from an injected module is silently
    // fatal here, and putting the guaranteed-fault control BEFORE the treatment guarantees the
    // experiment never runs at all. That is a harness bug, not a property of the question.
    //
    // New order: (a) safe control -> TREATMENT -> (b) known-lethal control, last.
    // The treatment is decisive on its own now, because the readout is binary:
    //   * "TREAT dark ... SUCCEEDED / after: EXECUTE_READ"   => READ DECRYPTS.
    //   * the ABOUT-TO-READ line written and then the process dies => the read FAULTED, and run 1
    //     established that a fault is fatal => EXECUTE-ONLY.
    // The marker is flushed per line, so the answer survives the kill either way.
    Marker("\n--- CONTROL (a): read an ALREADY-DECRYPTED page. Must SUCCEED. ---\n");
    if (firstLit) ProbeOne("CTRL-a lit", firstLit, modBase);
    else Marker("[CTRL-a] no EXECUTE_READ page found — control unavailable, result will be weak\n");

    // --- TREATMENT. One dark page. The whole experiment. ---
    Marker("\n--- TREATMENT: read ONE PAGE_NOACCESS .text page. ---\n");
    Markerf("[TREAT dark] ABOUT TO READ 0x%llX (rva 0x%llX).\n"
            "        If the marker ENDS HERE the read FAULTED and the fault was fatal => EXECUTE-ONLY.\n",
            (unsigned long long)firstDark, (unsigned long long)(firstDark - modBase));
    ProbeOne("TREAT dark", firstDark, modBase);
    Marker("[TREAT dark] SURVIVED the read.\n");

    // Re-query a moment later: decryption could be asynchronous.
    Sleep(250);
    PageInfo late{};
    if (QueryPage(firstDark, late))
        Markerf("[TREAT dark] +250ms recheck: %s\n", ProtName(late.protect));

    // Control (b) LAST: run 1 proved it lethal, and it is only meaningful if we got this far.
    Marker("\n--- CONTROL (b), LAST because run 1 proved it lethal: read an UNMAPPED address. ---\n");
    ProbeOne("CTRL-b unmapped", modBase + 0x40000000ULL, modBase);
    Marker("[CTRL-b] SURVIVED -- so __except does return here, and the treatment was fully controlled.\n");

    Marker("\nVERDICT KEY:\n"
           "  CTRL-a SUCCEEDED + CTRL-b FAULTED  => the instrument works; read TREAT.\n"
           "  TREAT SUCCEEDED / protection -> EXECUTE_READ  => READ DECRYPTS (~14,600 pages).\n"
           "  TREAT FAULTED   / protection unchanged        => EXECUTE-ONLY; lever does not exist.\n");

#if PROBE_ALL
    Marker("\n--- SWEEP (PROBE_ALL=1): one byte per NOACCESS page ---\n");
    size_t touched = 0, flipped = 0;
    for (uintptr_t a = textVA; a < textVA + textSz; ) {
        MEMORY_BASIC_INFORMATION m{};
        if (!VirtualQuery((LPCVOID)a, &m, sizeof(m))) break;
        uintptr_t rb = (uintptr_t)m.BaseAddress, rs = (uintptr_t)m.RegionSize;
        if ((m.Protect & 0xFF) == PAGE_NOACCESS) {
            for (uintptr_t p = rb; p < rb + rs && p < textVA + textSz; p += 0x1000) {
                unsigned char v; TryReadByte(p, v); ++touched;
                PageInfo pi{}; if (QueryPage(p, pi) && (pi.protect & 0xFF) != PAGE_NOACCESS) ++flipped;
            }
        }
        a = rs ? rb + rs : a + 0x1000;
    }
    Markerf("sweep: touched %llu pages, %llu changed protection\n",
            (unsigned long long)touched, (unsigned long long)flipped);
#endif

    Marker("=== probe complete ===\n");
    return 0;
}

BOOL WINAPI DllMain(HINSTANCE h, DWORD reason, LPVOID) {
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(h);
        CreateThread(nullptr, 0, Run, nullptr, 0, nullptr);
    }
    return TRUE;
}
