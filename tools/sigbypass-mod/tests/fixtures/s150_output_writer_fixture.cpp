// S150 output-ownership test fixture (test-owned; not a production component).
//
// A Windows GUI-subsystem process so a native `& $exe @args` invocation returns
// while the fixture stays alive, exactly like the real detached game launch.
// It writes a durable CreateNew PID receipt, then (after an optional delay)
// writes ASCII payloads to its inherited/redirected stdout and stderr handles,
// then stays alive for a hold interval. Invalid arguments fail before the PID
// receipt is written, and only test-owned (.superpowers) receipt paths are
// accepted.
//
// Arguments (all required):
//   --pid-file <path>       CreateNew receipt path (must contain ".superpowers")
//   --delay-ms <n>          delay before writing the std payloads
//   --hold-ms <n>           stay-alive interval after writing
//   --stdout-ascii <b64>    base64 of the ASCII stdout payload
//   --stderr-ascii <b64>    base64 of the ASCII stderr payload

#include <windows.h>
#include <shellapi.h>
#include <string>
#include <vector>
#include <cstdint>
#include <cwchar>
#include <cwctype>

#pragma comment(lib, "shell32.lib")

namespace {

bool Base64Decode(const std::string& in, std::vector<unsigned char>& out) {
    auto value = [](char c) -> int {
        if (c >= 'A' && c <= 'Z') { return c - 'A'; }
        if (c >= 'a' && c <= 'z') { return c - 'a' + 26; }
        if (c >= '0' && c <= '9') { return c - '0' + 52; }
        if (c == '+') { return 62; }
        if (c == '/') { return 63; }
        return -1;
    };
    out.clear();
    int buffer = 0;
    int bits = 0;
    for (char c : in) {
        if (c == '=') { break; }
        if (c == '\r' || c == '\n' || c == ' ' || c == '\t') { continue; }
        const int v = value(c);
        if (v < 0) { return false; }
        buffer = (buffer << 6) | v;
        bits += 6;
        if (bits >= 8) {
            bits -= 8;
            out.push_back(static_cast<unsigned char>((buffer >> bits) & 0xFF));
        }
    }
    return true;
}

std::string WideToUtf8(const std::wstring& value) {
    if (value.empty()) { return std::string(); }
    const int needed = WideCharToMultiByte(CP_UTF8, 0, value.c_str(),
        static_cast<int>(value.size()), nullptr, 0, nullptr, nullptr);
    if (needed <= 0) { return std::string(); }
    std::string out(static_cast<size_t>(needed), '\0');
    WideCharToMultiByte(CP_UTF8, 0, value.c_str(), static_cast<int>(value.size()),
        &out[0], needed, nullptr, nullptr);
    return out;
}

std::string NarrowAscii(const std::wstring& value) {
    std::string out;
    out.reserve(value.size());
    for (wchar_t c : value) { out.push_back(static_cast<char>(c & 0x7F)); }
    return out;
}

std::string JsonEscape(const std::string& value) {
    std::string out;
    for (char c : value) {
        if (c == '\\' || c == '"') { out.push_back('\\'); out.push_back(c); }
        else if (c == '\n') { out += "\\n"; }
        else if (c == '\r') { out += "\\r"; }
        else if (c == '\t') { out += "\\t"; }
        else { out.push_back(c); }
    }
    return out;
}

std::wstring ToLowerAscii(const std::wstring& value) {
    std::wstring out = value;
    for (auto& c : out) {
        if (c >= L'A' && c <= L'Z') { c = static_cast<wchar_t>(c - L'A' + L'a'); }
    }
    return out;
}

bool WriteAllToHandle(HANDLE handle, const std::vector<unsigned char>& bytes) {
    if (handle == nullptr || handle == INVALID_HANDLE_VALUE) { return false; }
    size_t written = 0;
    while (written < bytes.size()) {
        DWORD chunk = 0;
        const size_t remaining = bytes.size() - written;
        const DWORD toWrite = remaining > 0x40000 ? 0x40000 : static_cast<DWORD>(remaining);
        if (!WriteFile(handle, bytes.data() + written, toWrite, &chunk, nullptr)) { return false; }
        if (chunk == 0) { return false; }
        written += chunk;
    }
    FlushFileBuffers(handle);
    return true;
}

}  // namespace

int WINAPI WinMain(HINSTANCE, HINSTANCE, LPSTR, int) {
    int argc = 0;
    LPWSTR* argv = CommandLineToArgvW(GetCommandLineW(), &argc);
    if (argv == nullptr) { return 2; }

    std::wstring pidFile;
    std::wstring stdoutB64;
    std::wstring stderrB64;
    bool haveDelay = false;
    bool haveHold = false;
    long delayMs = -1;
    long holdMs = -1;

    for (int i = 1; i + 1 < argc; ++i) {
        const std::wstring flag = argv[i];
        const std::wstring val = argv[i + 1];
        if (flag == L"--pid-file") { pidFile = val; ++i; }
        else if (flag == L"--stdout-ascii") { stdoutB64 = val; ++i; }
        else if (flag == L"--stderr-ascii") { stderrB64 = val; ++i; }
        else if (flag == L"--delay-ms") { delayMs = wcstol(val.c_str(), nullptr, 10); haveDelay = true; ++i; }
        else if (flag == L"--hold-ms") { holdMs = wcstol(val.c_str(), nullptr, 10); haveHold = true; ++i; }
    }
    LocalFree(argv);

    if (pidFile.empty() || !haveDelay || !haveHold || delayMs < 0 || holdMs < 0) { return 3; }
    if (ToLowerAscii(pidFile).find(L".superpowers") == std::wstring::npos) { return 4; }

    // A single "-" token means "write nothing to this stream".
    std::vector<unsigned char> stdoutBytes;
    std::vector<unsigned char> stderrBytes;
    if (stdoutB64 != L"-" && !Base64Decode(NarrowAscii(stdoutB64), stdoutBytes)) { return 5; }
    if (stderrB64 != L"-" && !Base64Decode(NarrowAscii(stderrB64), stderrBytes)) { return 5; }

    // Executable path and size.
    wchar_t modulePath[MAX_PATH * 2];
    const DWORD moduleLen = GetModuleFileNameW(nullptr, modulePath, MAX_PATH * 2);
    if (moduleLen == 0 || moduleLen >= MAX_PATH * 2) { return 6; }
    const std::wstring exePath(modulePath, moduleLen);

    long long exeSize = 0;
    HANDLE exeHandle = CreateFileW(exePath.c_str(), GENERIC_READ,
        FILE_SHARE_READ | FILE_SHARE_WRITE, nullptr, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, nullptr);
    if (exeHandle != INVALID_HANDLE_VALUE) {
        LARGE_INTEGER size;
        if (GetFileSizeEx(exeHandle, &size)) { exeSize = static_cast<long long>(size.QuadPart); }
        CloseHandle(exeHandle);
    }

    // Process creation time as .NET UTC ticks (100ns units, 0001-01-01 epoch).
    FILETIME creation;
    FILETIME dummyExit;
    FILETIME dummyKernel;
    FILETIME dummyUser;
    long long creationTicks = 0;
    if (GetProcessTimes(GetCurrentProcess(), &creation, &dummyExit, &dummyKernel, &dummyUser)) {
        ULARGE_INTEGER u;
        u.LowPart = creation.dwLowDateTime;
        u.HighPart = creation.dwHighDateTime;
        creationTicks = static_cast<long long>(u.QuadPart) + 504911232000000000LL;
    }

    // CreateNew PID receipt; fail if it already exists.
    HANDLE receipt = CreateFileW(pidFile.c_str(), GENERIC_WRITE, FILE_SHARE_READ,
        nullptr, CREATE_NEW, FILE_ATTRIBUTE_NORMAL, nullptr);
    if (receipt == INVALID_HANDLE_VALUE) { return 7; }

    std::string json = "{\"pid\":";
    json += std::to_string(static_cast<unsigned long>(GetCurrentProcessId()));
    json += ",\"creationUtcTicks\":";
    json += std::to_string(creationTicks);
    json += ",\"exePath\":\"";
    json += JsonEscape(WideToUtf8(exePath));
    json += "\",\"exeSize\":";
    json += std::to_string(exeSize);
    json += "}\n";

    DWORD receiptWritten = 0;
    const bool receiptOk = WriteFile(receipt, json.data(),
        static_cast<DWORD>(json.size()), &receiptWritten, nullptr) &&
        receiptWritten == static_cast<DWORD>(json.size());
    FlushFileBuffers(receipt);
    CloseHandle(receipt);
    if (!receiptOk) { return 8; }

    if (delayMs > 0) { Sleep(static_cast<DWORD>(delayMs)); }

    WriteAllToHandle(GetStdHandle(STD_OUTPUT_HANDLE), stdoutBytes);
    WriteAllToHandle(GetStdHandle(STD_ERROR_HANDLE), stderrBytes);

    if (holdMs > 0) { Sleep(static_cast<DWORD>(holdMs)); }
    return 0;
}
