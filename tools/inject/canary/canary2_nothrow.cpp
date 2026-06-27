// canary2_nothrow.dll — isolates the TLS-callback half of Phase 2.
// Same as canary2.cpp but no throw/catch. If THIS works (marker appears with tls_cb=1)
// but canary2.cpp dies, the THROW is the killer (exception unwinding broken).
//
// Build:
//   clang++ -shared -O2 canary2_nothrow.cpp -o canary2_nothrow.dll -luser32 -lkernel32

#include <windows.h>

static volatile int g_tls_called = 0;

static VOID NTAPI MyTlsCallback(PVOID, DWORD reason, PVOID)
{
    if (reason == DLL_PROCESS_ATTACH)
        g_tls_called = 1;
}

#pragma section(".CRT$XLB", long, read)
extern "C" __declspec(allocate(".CRT$XLB"))
PIMAGE_TLS_CALLBACK g_tls_cb = MyTlsCallback;

extern "C" const IMAGE_TLS_DIRECTORY _tls_used;
const IMAGE_TLS_DIRECTORY* g_tls_used_ref = &_tls_used;

static const char* kMarker =
    "G:\\git\\Supervive Revival Project\\tools\\inject\\canary\\canary2_nothrow_loaded.txt";

BOOL APIENTRY DllMain(HMODULE h, DWORD reason, LPVOID)
{
    if (reason == DLL_PROCESS_ATTACH)
    {
        DisableThreadLibraryCalls(h);
        HANDLE f = CreateFileA(kMarker, GENERIC_WRITE, FILE_SHARE_READ, nullptr,
                               CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, nullptr);
        if (f != INVALID_HANDLE_VALUE) {
            char buf[160];
            int n = wsprintfA(buf,
                "canary2_nothrow OK: tls_cb=%d (expect 1) in PID %lu\r\n",
                g_tls_called, GetCurrentProcessId());
            DWORD w = 0;
            WriteFile(f, buf, (DWORD)n, &w, nullptr);
            CloseHandle(f);
        }
    }
    return TRUE;
}
