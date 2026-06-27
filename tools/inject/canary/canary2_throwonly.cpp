// canary2_throwonly.dll — isolates the C++ exception half of Phase 2.
// No TLS callback; just throw/catch in DllMain with checkpoint markers so we know
// exactly where execution died.
//
// Writes the marker file TWICE: once before the throw ("entered"), once after the catch
// ("caught"). If only "entered" appears, the throw escaped the catch (unwind broken).
// If neither appears, DllMain itself wasn't reached.
//
// Build:
//   clang++ -shared -O2 canary2_throwonly.cpp -o canary2_throwonly.dll -luser32 -lkernel32

#include <windows.h>

static const char* kMarker =
    "G:\\git\\Supervive Revival Project\\tools\\inject\\canary\\canary2_throwonly_loaded.txt";

static void WriteCheckpoint(const char* tag, int value)
{
    HANDLE h = CreateFileA(kMarker, GENERIC_WRITE | FILE_APPEND_DATA,
                           FILE_SHARE_READ, nullptr, OPEN_ALWAYS,
                           FILE_ATTRIBUTE_NORMAL, nullptr);
    if (h == INVALID_HANDLE_VALUE) return;
    SetFilePointer(h, 0, nullptr, FILE_END);
    char buf[160];
    int n = wsprintfA(buf, "%s value=%d\r\n", tag, value);
    DWORD w = 0;
    WriteFile(h, buf, (DWORD)n, &w, nullptr);
    CloseHandle(h);
}

__declspec(noinline) static int try_throw_catch()
{
    try {
        throw 7;
    } catch (int v) {
        return v;
    }
    return -2;
}

BOOL APIENTRY DllMain(HMODULE h, DWORD reason, LPVOID)
{
    if (reason == DLL_PROCESS_ATTACH)
    {
        DisableThreadLibraryCalls(h);
        // Truncate any prior content from previous runs.
        HANDLE t = CreateFileA(kMarker, GENERIC_WRITE, FILE_SHARE_READ, nullptr,
                               CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, nullptr);
        if (t != INVALID_HANDLE_VALUE) CloseHandle(t);

        WriteCheckpoint("step1: DllMain entered", (int)GetCurrentProcessId());
        int caught = try_throw_catch();
        WriteCheckpoint("step2: caught after throw", caught);
    }
    return TRUE;
}
