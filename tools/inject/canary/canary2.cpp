// canary2.dll — Phase 2 mapper test: TLS callbacks + C++ exceptions.
//
// Purpose: prove that our manual mapper correctly
//   (a) invokes TLS callbacks before DllMain, and
//   (b) registers the exception unwind table so C++ throw/catch works.
//
// How success is unambiguous: the marker file ends with
//   "canary2 OK: tls_cb=1, throw_caught=7 (expect 1,7)"
// Anything else (e.g. tls_cb=0) tells us exactly which feature is broken.
//
// Build (from this folder, clang on PATH):
//   clang++ -shared -O2 -EHsc canary2.cpp -o canary2.dll ^
//           -luser32 -lkernel32 -lvcruntime
//
// Marker:
//   G:\git\Supervive Revival Project\tools\inject\canary\canary2_loaded.txt

#include <windows.h>

static volatile int g_tls_called      = 0;
static volatile int g_exception_value = -1;

// Explicit TLS callback. The compiler-generated TLS init (for thread_local globals) is
// fragile to optimize-away if those globals aren't referenced — an explicit callback is
// the most reliable way to force a real .tls/.CRT$XLB entry.
static VOID NTAPI MyTlsCallback(PVOID /*hModule*/, DWORD reason, PVOID /*reserved*/)
{
    if (reason == DLL_PROCESS_ATTACH)
        g_tls_called = 1;
}

// Place the callback pointer into the TLS callback list (special section .CRT$XLB).
// _tls_used is the linker symbol that emits the IMAGE_TLS_DIRECTORY data dir; we
// reference it via g_tls_used_ref so the linker keeps it.
#pragma section(".CRT$XLB", long, read)
extern "C" __declspec(allocate(".CRT$XLB"))
PIMAGE_TLS_CALLBACK g_tls_cb = MyTlsCallback;

extern "C" const IMAGE_TLS_DIRECTORY _tls_used;
const IMAGE_TLS_DIRECTORY* g_tls_used_ref = &_tls_used;

// A non-inlined throw/catch so the compiler can't elide it. Returns the caught value.
__declspec(noinline) static int try_throw_catch()
{
    try {
        throw 7;
    } catch (int v) {
        return v;
    }
    return -2;
}

static const char* kMarker =
    "G:\\git\\Supervive Revival Project\\tools\\inject\\canary\\canary2_loaded.txt";

BOOL APIENTRY DllMain(HMODULE hModule, DWORD reason, LPVOID /*reserved*/)
{
    if (reason == DLL_PROCESS_ATTACH)
    {
        DisableThreadLibraryCalls(hModule);
        g_exception_value = try_throw_catch();

        HANDLE h = CreateFileA(kMarker, GENERIC_WRITE, FILE_SHARE_READ, nullptr,
                               CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, nullptr);
        if (h != INVALID_HANDLE_VALUE)
        {
            char buf[192];
            int n = wsprintfA(buf,
                "canary2 OK: tls_cb=%d, throw_caught=%d (expect 1,7) in PID %lu\r\n",
                g_tls_called, g_exception_value, GetCurrentProcessId());
            DWORD written = 0;
            WriteFile(h, buf, (DWORD)n, &written, nullptr);
            CloseHandle(h);
        }
    }
    return TRUE;
}
