// nulldll — ARM D of the S111 injection-hazard ladder. A DLL that does NOTHING.
//
// WHY IT EXISTS. The `-NoHook` control (docs/s111-nohook-control.md) established that the protector
// kill (runtime.dll+1, EXECUTE, no registered module) is caused by OUR INJECTION and not by the
// game: 0 deaths in 11 launches x 320 s with nothing injected, versus ~28 % of launches dying inside
// 60 s with shims injected (p = 0.036). What it could NOT say is WHICH part of injecting provokes
// it. Three candidates were still confounded:
//
//     (a) the manually-mapped image itself
//     (b) the self-restoring `.text` jz-NOP  (catalog_store_fix)
//     (c) the ProcessInternal prologue writes (pi8 / loadout_fix / missions_fix)
//
// This file isolates (a). It is manually mapped exactly like a real shim — same injector, same
// relocations, same RtlAddFunctionTable path — and then does NOTHING AT ALL: DllMain returns TRUE
// immediately. No thread, no patch, no hook, no scan, no file I/O, no imports beyond the one the
// manual mapper needs.
//
//     arm D dies at ~30 %  => manual mapping ITSELF is the trigger. No amount of shim-logic tuning
//                             helps; the fix has to be a different loading strategy (or far fewer
//                             injected images).
//     arm D dies at ~0 %   => mapping is innocent, and the trigger is (b) or (c) — which arm E
//                             (+jz only) then splits.
//
// ⚠ Run it with `launch-redirect.ps1 -Hook <this dll>`, which injects EXACTLY ONE DLL and no
//   secondaries. Deploying it as catalog_store_fix.dll would NOT work as a control: the launcher
//   would still inject the four secondaries on top, and those carry (b) and (c).
//
// Build: registered in build.ps1's $DefaultSet-independent path; `.\build.ps1 -Name nulldll`
//        (clang++ -shared -O2 nulldll.cpp -o nulldll.dll -lkernel32)
// Marker: none, deliberately — writing one would be file I/O this control must not perform.

#include <windows.h>

BOOL APIENTRY DllMain(HMODULE h, DWORD reason, LPVOID) {
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(h);   // the only call, and it is the manual mapper's own contract
    }
    return TRUE;
}

// The manual mapper looks for these on some paths; they must exist but must never do anything.
extern "C" __declspec(dllexport) void* start_mod()          { return nullptr; }
extern "C" __declspec(dllexport) void  uninstall_mod(void*) { }
