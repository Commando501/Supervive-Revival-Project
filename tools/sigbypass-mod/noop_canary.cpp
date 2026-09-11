// noop_canary.cpp -- the smallest possible manually-mapped payload.
//
// WHY (S109, 2026-08-04). The shims-at-menu discriminator showed our instrumentation
// provokes both packer death families: 3 of 3 shim runs died at the MENU in 23-65 s,
// while 4 of 4 clean `-NoHook` runs survived 86.2 minutes. See docs/s109-dump-forensics.md
// section 12.
//
// That result cannot distinguish TWO things, because `-NoHook` skips both of them:
//     (a) the ACT of manually mapping a DLL into the process (inject.exe watch-now), and
//     (b) what the shims subsequently DO -- .text patches, ProcessInternal hooks,
//         thread creation, native calls.
//
// This DLL isolates (a). It is mapped by the identical mechanism as every real shim, and
// then does NOTHING: no hook, no patch, no thread, no native call, no page-protection
// change, no scan. Its entire body is one appended marker line.
//
//     dies    -> the ACT of manual-mapping provokes the packer. Every shim is implicated
//                by construction and the whole injection technique needs rethinking.
//     survives-> mapping alone is safe; it is shim BEHAVIOUR that provokes it, and the
//                next bisect is over what the shims do (the .text patch is the prime
//                suspect -- catalog_store_fix's self-restoring jz-NOP is the only thing
//                in the default set that writes to the game's code).
//
// ★ The marker write is NOT decoration -- it is the mandatory positive control. Without
// proof the DLL was actually mapped, a survival is indistinguishable from a clean run,
// which is exactly the instrument artifact this whole session exists to clean up
// (memory/supervive-instrument-artifact-pattern). A run whose marker does not grow is
// VOID, never SURVIVED.
//
// CONSTRAINTS honoured (CLAUDE.md "What NOT to do"):
//   * NO C++ exception machinery -- the packer's vectored exception filter kills the
//     process on any throw/unwind. Nothing here throws; the build is scanned for
//     __CxxFrameHandler3 / _CxxThrowException.
//   * No .text patch, so nothing for the ~3-5 min code-integrity check to catch.
//   * Marker uses FILE_APPEND_DATA + OPEN_ALWAYS (appends), NOT CREATE_ALWAYS -- so
//     successive runs accumulate instead of truncating each other (that truncation is
//     FK-25, and it has already cost this project attributable runs).
//
// Build: clang++ -shared -O2 noop_canary.cpp -o build/noop_canary.dll -lkernel32

#include <windows.h>
#include <stdio.h>
#include <string.h>

static const char* kMarkerPath =
    "G:\\git\\Supervive Revival Project\\docs\\noop-canary-marker.txt";

static void Marker(const char* m) {
    HANDLE h = CreateFileA(kMarkerPath, FILE_APPEND_DATA,
                           FILE_SHARE_READ | FILE_SHARE_WRITE, nullptr,
                           OPEN_ALWAYS, FILE_ATTRIBUTE_NORMAL, nullptr);
    if (h == INVALID_HANDLE_VALUE) return;
    DWORD w = 0;
    WriteFile(h, m, (DWORD)strlen(m), &w, nullptr);
    CloseHandle(h);
}

BOOL WINAPI DllMain(HINSTANCE hInst, DWORD reason, LPVOID) {
    if (reason == DLL_PROCESS_ATTACH) {
        SYSTEMTIME st;
        GetLocalTime(&st);
        char b[320];
        _snprintf_s(b, sizeof(b), _TRUNCATE,
                    "[NOOP] mapped %04d-%02d-%02d %02d:%02d:%02d.%03d  pid=%lu"
                    "  self=%p  exe=%p  -- does nothing else\r\n",
                    st.wYear, st.wMonth, st.wDay, st.wHour, st.wMinute,
                    st.wSecond, st.wMilliseconds, (unsigned long)GetCurrentProcessId(),
                    (void*)hInst, (void*)GetModuleHandleA(nullptr));
        Marker(b);
    }
    // DLL_THREAD_ATTACH / DETACH / PROCESS_DETACH: deliberately ignored.
    return TRUE;
}
