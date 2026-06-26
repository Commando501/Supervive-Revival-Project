// canary.dll — a deliberately harmless injection test payload.
//
// Purpose: prove two things about SUPERVIVE-Win64-Shipping.exe that only a REAL
// injection can show (the read-only `inject diag` cannot):
//   1. an UNSIGNED DLL actually loads via LoadLibrary (README claimed it's blocked),
//   2. the packer's anti-debug does NOT close the game when a foreign module appears.
//
// It does EXACTLY ONE observable thing: on DLL_PROCESS_ATTACH it writes a one-line
// timestamp to a text file, then returns. No threads, no hooks, no network, no
// persistence, no other API calls. Read it — that is the whole behavior.
//
// Build (from this folder), with clang on PATH:
//   clang++ -shared -O2 canary.cpp -o canary.dll -luser32 -lkernel32
//
// Out-of-band proof file (so we don't depend on the game's own console):
//   G:\git\Supervive Revival Project\tools\inject\canary\canary_loaded.txt

#include <windows.h>

static const char* kMarkerPath =
    "G:\\git\\Supervive Revival Project\\tools\\inject\\canary\\canary_loaded.txt";

static void WriteMarker()
{
    HANDLE h = CreateFileA(kMarkerPath, GENERIC_WRITE, FILE_SHARE_READ, nullptr,
                           CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, nullptr);
    if (h == INVALID_HANDLE_VALUE)
        return;

    SYSTEMTIME st;
    GetLocalTime(&st);
    char buf[160];
    int n = wsprintfA(buf,
        "canary DllMain ran in PID %lu at %04d-%02d-%02d %02d:%02d:%02d\r\n",
        GetCurrentProcessId(),
        st.wYear, st.wMonth, st.wDay, st.wHour, st.wMinute, st.wSecond);

    DWORD written = 0;
    WriteFile(h, buf, (DWORD)n, &written, nullptr);
    CloseHandle(h);
}

BOOL APIENTRY DllMain(HMODULE hModule, DWORD reason, LPVOID /*reserved*/)
{
    if (reason == DLL_PROCESS_ATTACH)
    {
        DisableThreadLibraryCalls(hModule); // we want nothing on thread attach/detach
        WriteMarker();
    }
    return TRUE;
}
