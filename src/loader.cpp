#include "loader.h"
#include <tlhelp32.h>
#include <psapi.h>
#include <bcrypt.h>
#include <wintrust.h>
#include <softpub.h>
#include <algorithm>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <sstream>
#include <stdexcept>
#include <array>

namespace loader {
namespace {
struct Handle {
    HANDLE h{};
    explicit Handle(HANDLE value = nullptr) : h(value) {}
    ~Handle() { if (h && h != INVALID_HANDLE_VALUE) CloseHandle(h); }
    Handle(const Handle&) = delete;
    Handle& operator=(const Handle&) = delete;
    explicit operator bool() const { return h && h != INVALID_HANDLE_VALUE; }
};
std::string error(const char* action, DWORD code = GetLastError()) {
    wchar_t* buffer{};
    FormatMessageW(FORMAT_MESSAGE_ALLOCATE_BUFFER | FORMAT_MESSAGE_FROM_SYSTEM |
        FORMAT_MESSAGE_IGNORE_INSERTS, nullptr, code, 0, reinterpret_cast<wchar_t*>(&buffer), 0, nullptr);
    std::string text = std::string(action) + " (Windows " + std::to_string(code) + ")";
    if (buffer) { text += ": " + utf8(buffer); LocalFree(buffer); }
    while (!text.empty() && (text.back() == '\r' || text.back() == '\n')) text.pop_back();
    return text;
}
std::uint64_t creation(HANDLE h) {
    FILETIME c{}, e{}, k{}, u{};
    if (!GetProcessTimes(h, &c, &e, &k, &u)) return 0;
    return (static_cast<std::uint64_t>(c.dwHighDateTime) << 32) | c.dwLowDateTime;
}
bool x64(HANDLE h) {
    USHORT process{}, native{};
    if (!IsWow64Process2(h, &process, &native)) return false;
    return process == IMAGE_FILE_MACHINE_UNKNOWN && native == IMAGE_FILE_MACHINE_AMD64;
}
struct RemoteModule {
    std::wstring path, name;
    std::uintptr_t base{};
    DWORD size{};
};
std::vector<RemoteModule> modules(DWORD pid) {
    HANDLE raw = INVALID_HANDLE_VALUE;
    for (int i = 0; i < 5; ++i) {
        raw = CreateToolhelp32Snapshot(TH32CS_SNAPMODULE | TH32CS_SNAPMODULE32, pid);
        if (raw != INVALID_HANDLE_VALUE || GetLastError() != ERROR_BAD_LENGTH) break;
        Sleep(20);
    }
    Handle snap(raw);
    if (!snap) throw std::runtime_error(error("Module snapshot"));
    Handle process(OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, FALSE, pid));
    if (!process) throw std::runtime_error(error("OpenProcess for module paths"));
    std::vector<RemoteModule> result;
    MODULEENTRY32W m{}; m.dwSize = sizeof(m);
    if (!Module32FirstW(snap.h, &m)) throw std::runtime_error(error("Module enumeration"));
    do {
        // Toolhelp can return ANSI-lossy paths even through its W entry points.
        // PSAPI reads the original Unicode loader entry and supports long paths.
        std::vector<wchar_t> path(32768);
        const DWORD length = K32GetModuleFileNameExW(process.h, m.hModule, path.data(), static_cast<DWORD>(path.size()));
        if (!length) throw std::runtime_error(error("Read full module path"));
        std::wstring full(path.data(), length);
        result.push_back({full, std::filesystem::path(full).filename().wstring(),
            reinterpret_cast<std::uintptr_t>(m.modBaseAddr), m.modBaseSize});
    } while (Module32NextW(snap.h, &m));
    const DWORD enumerationError = GetLastError();
    if (enumerationError != ERROR_NO_MORE_FILES) throw std::runtime_error(error("Module enumeration", enumerationError));
    return result;
}
bool sameFile(const std::wstring& a, const std::wstring& b) {
    std::error_code ec;
    const bool equivalent = std::filesystem::equivalent(a, b, ec);
    return !ec ? equivalent : _wcsicmp(a.c_str(), b.c_str()) == 0;
}
bool present(DWORD pid, const std::wstring& path) {
    for (const auto& m : modules(pid)) if (sameFile(m.path, path)) return true;
    return false;
}
std::string sha256(const std::wstring& path) {
    BCRYPT_ALG_HANDLE algorithm{};
    BCRYPT_HASH_HANDLE hash{};
    struct Cleanup {
        BCRYPT_ALG_HANDLE& a; BCRYPT_HASH_HANDLE& h;
        ~Cleanup() { if (h) BCryptDestroyHash(h); if (a) BCryptCloseAlgorithmProvider(a, 0); }
    } cleanup{algorithm, hash};
    if (BCryptOpenAlgorithmProvider(&algorithm, BCRYPT_SHA256_ALGORITHM, nullptr, 0) < 0 ||
        BCryptCreateHash(algorithm, &hash, nullptr, 0, nullptr, 0, 0) < 0)
        throw std::runtime_error("SHA-256 provider unavailable.");
    std::ifstream file(std::filesystem::path(path), std::ios::binary);
    if (!file) throw std::runtime_error("Cannot read DLL for hashing.");
    std::array<char, 65536> data{};
    while (file.read(data.data(), data.size()) || file.gcount()) {
        if (BCryptHashData(hash, reinterpret_cast<PUCHAR>(data.data()), static_cast<ULONG>(file.gcount()), 0) < 0)
            throw std::runtime_error("SHA-256 update failed.");
    }
    if (!file.eof()) throw std::runtime_error("DLL read failed during hashing.");
    std::array<UCHAR, 32> digest{};
    if (BCryptFinishHash(hash, digest.data(), static_cast<ULONG>(digest.size()), 0) < 0)
        throw std::runtime_error("SHA-256 finalization failed.");
    std::ostringstream result;
    for (UCHAR b : digest) result << std::hex << std::setw(2) << std::setfill('0') << static_cast<unsigned>(b);
    return result.str();
}
std::string signature(const std::wstring& path) {
    WINTRUST_FILE_INFO file{}; file.cbStruct = sizeof(file); file.pcwszFilePath = path.c_str();
    WINTRUST_DATA data{}; data.cbStruct = sizeof(data); data.dwUIChoice = WTD_UI_NONE;
    data.fdwRevocationChecks = WTD_REVOKE_NONE; data.dwUnionChoice = WTD_CHOICE_FILE;
    data.pFile = &file; data.dwStateAction = WTD_STATEACTION_VERIFY;
    data.dwProvFlags = WTD_CACHE_ONLY_URL_RETRIEVAL;
    GUID action = WINTRUST_ACTION_GENERIC_VERIFY_V2;
    const LONG result = WinVerifyTrust(nullptr, &action, &data);
    data.dwStateAction = WTD_STATEACTION_CLOSE;
    WinVerifyTrust(nullptr, &action, &data);
    if (result == ERROR_SUCCESS) return "Valid Authenticode (offline check)";
    if (result == TRUST_E_NOSIGNATURE) return "Unsigned";
    if (result == TRUST_E_BAD_DIGEST) return "Invalid signature: file modified";
    std::ostringstream s; s << "Not verified (offline): 0x" << std::hex << static_cast<unsigned long>(result);
    return s.str();
}
std::string version(const std::wstring& path) {
    DWORD dummy{}; DWORD size = GetFileVersionInfoSizeW(path.c_str(), &dummy);
    if (!size) return "No version resource";
    std::vector<BYTE> data(size);
    if (!GetFileVersionInfoW(path.c_str(), 0, size, data.data())) return "Unavailable";
    VS_FIXEDFILEINFO* info{}; UINT length{};
    if (!VerQueryValueW(data.data(), L"\\", reinterpret_cast<void**>(&info), &length) ||
        length < sizeof(*info) || info->dwSignature != 0xfeef04bd) return "Unavailable";
    return std::to_string(HIWORD(info->dwFileVersionMS)) + "." + std::to_string(LOWORD(info->dwFileVersionMS)) +
        "." + std::to_string(HIWORD(info->dwFileVersionLS)) + "." + std::to_string(LOWORD(info->dwFileVersionLS));
}
std::wstring validate(const std::wstring& path) {
    if (path.empty()) throw std::runtime_error("Select a DLL first.");
    const auto resolved = std::filesystem::canonical(path);
    if (!std::filesystem::is_regular_file(resolved)) throw std::runtime_error("DLL path must be a file.");
    std::ifstream file(resolved, std::ios::binary);
    IMAGE_DOS_HEADER dos{}; IMAGE_NT_HEADERS64 nt{};
    file.read(reinterpret_cast<char*>(&dos), sizeof(dos));
    const auto length = std::filesystem::file_size(resolved);
    if (!file || dos.e_magic != IMAGE_DOS_SIGNATURE || dos.e_lfanew < sizeof(dos) ||
        static_cast<std::uint64_t>(dos.e_lfanew) + sizeof(nt) > length)
        throw std::runtime_error("File is not a valid Windows PE DLL.");
    file.seekg(dos.e_lfanew);
    file.read(reinterpret_cast<char*>(&nt), sizeof(nt));
    if (!file || nt.Signature != IMAGE_NT_SIGNATURE || nt.FileHeader.Machine != IMAGE_FILE_MACHINE_AMD64 ||
        nt.OptionalHeader.Magic != IMAGE_NT_OPTIONAL_HDR64_MAGIC ||
        !(nt.FileHeader.Characteristics & IMAGE_FILE_DLL))
        throw std::runtime_error("An x64 Windows DLL is required (not x86, ARM64 or an EXE).");
    return resolved.wstring();
}
}
std::string utf8(const std::wstring& value) {
    if (value.empty()) return {};
    int count = WideCharToMultiByte(CP_UTF8, 0, value.data(), static_cast<int>(value.size()), nullptr, 0, nullptr, nullptr);
    std::string result(count, '\0');
    WideCharToMultiByte(CP_UTF8, 0, value.data(), static_cast<int>(value.size()), result.data(), count, nullptr, nullptr);
    return result;
}
std::wstring wide(const std::string& value) {
    if (value.empty()) return {};
    int count = MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, value.data(), static_cast<int>(value.size()), nullptr, 0);
    if (!count) throw std::runtime_error("Invalid UTF-8 path.");
    std::wstring result(count, L'\0');
    MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, value.data(), static_cast<int>(value.size()), result.data(), count);
    return result;
}
std::wstring executableDirectory() {
    std::vector<wchar_t> path(32768);
    DWORD length = GetModuleFileNameW(nullptr, path.data(), static_cast<DWORD>(path.size()));
    return std::filesystem::path(std::wstring(path.data(), length)).parent_path().wstring();
}
std::vector<Process> processes() {
    std::vector<Process> result;
    Handle snap(CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0));
    if (!snap) throw std::runtime_error(error("Process snapshot"));
    PROCESSENTRY32W entry{}; entry.dwSize = sizeof(entry);
    if (Process32FirstW(snap.h, &entry)) do {
        if (entry.th32ProcessID == GetCurrentProcessId()) continue;
        Handle proc(OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, FALSE, entry.th32ProcessID));
        if (!proc) continue;
        Process p; p.pid = entry.th32ProcessID; p.name = entry.szExeFile;
        p.created = creation(proc.h); p.x64 = x64(proc.h);
        std::vector<wchar_t> buffer(32768); DWORD length = static_cast<DWORD>(buffer.size());
        if (QueryFullProcessImageNameW(proc.h, 0, buffer.data(), &length)) p.path.assign(buffer.data(), length);
        if (p.created) result.push_back(std::move(p));
    } while (Process32NextW(snap.h, &entry));
    std::sort(result.begin(), result.end(), [](const auto& a, const auto& b) {
        int cmp = _wcsicmp(a.name.c_str(), b.name.c_str()); return cmp ? cmp < 0 : a.pid < b.pid;
    });
    return result;
}
DllInfo inspect(const std::wstring& path) {
    DllInfo result;
    try {
        result.path = validate(path); result.sha256 = sha256(result.path);
        result.version = version(result.path); result.signature = signature(result.path); result.valid = true;
        if (result.sha256 == "6eb209e764f39872625debd6abaf45e2bb6322f6f270f781f70c059ae30b3927")
            result.note = "Matches published SF-v2 310.8 community runtime hash. Modified binary; hash match is not a security audit.";
        else if (_wcsicmp(std::filesystem::path(result.path).filename().c_str(), L"nvngx_dlssnr.dll") == 0)
            result.note = "NR filename detected; runtime variant not recognized by this project.";
        else result.note = "Generic DLL. Loading does not activate DLSS rendering.";
    } catch (const std::exception& e) { result.note = e.what(); }
    return result;
}
Result inject(const Process& target, const std::wstring& input) {
    try {
        const std::wstring path = validate(input);
        if (target.pid == 0 || target.pid == GetCurrentProcessId()) return {false, "Select a different process."};
        Handle process(OpenProcess(PROCESS_CREATE_THREAD | PROCESS_QUERY_INFORMATION | PROCESS_VM_OPERATION |
            PROCESS_VM_WRITE | PROCESS_VM_READ | SYNCHRONIZE, FALSE, target.pid));
        if (!process) return {false, error("OpenProcess")};
        if (!target.created || creation(process.h) != target.created)
            return {false, "Target exited or PID was reused. Refresh and select the process again."};
        if (!x64(process.h)) return {false, "Target must be an x64 process."};
        if (present(target.pid, path)) return {true, "DLL already loaded; no additional reference added. Rendering activity is unknown."};

        // Resolve the actual owner: LoadLibraryW may be forwarded into KernelBase.
        FARPROC address = GetProcAddress(GetModuleHandleW(L"kernel32.dll"), "LoadLibraryW");
        HMODULE owner{};
        if (!address || !GetModuleHandleExW(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS |
            GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT, reinterpret_cast<LPCWSTR>(address), &owner))
            return {false, error("Resolve LoadLibraryW")};
        wchar_t ownerPath[32768]{};
        if (!GetModuleFileNameW(owner, ownerPath, 32768)) return {false, error("Resolve loader module")};
        std::uintptr_t remoteAddress{};
        const auto offset = reinterpret_cast<std::uintptr_t>(address) - reinterpret_cast<std::uintptr_t>(owner);
        for (const auto& m : modules(target.pid)) {
            if (sameFile(m.path, ownerPath) && offset < m.size)
                remoteAddress = m.base + offset;
        }
        if (!remoteAddress) return {false, "Matching system loader module not found in target."};
        const SIZE_T bytes = (path.size() + 1) * sizeof(wchar_t);
        void* remote = VirtualAllocEx(process.h, nullptr, bytes, MEM_RESERVE | MEM_COMMIT, PAGE_READWRITE);
        if (!remote) return {false, error("VirtualAllocEx")};
        SIZE_T written{};
        if (!WriteProcessMemory(process.h, remote, path.c_str(), bytes, &written) || written != bytes) {
            auto message = error("WriteProcessMemory"); VirtualFreeEx(process.h, remote, 0, MEM_RELEASE);
            return {false, message};
        }
        Handle thread(CreateRemoteThread(process.h, nullptr, 0,
            reinterpret_cast<LPTHREAD_START_ROUTINE>(remoteAddress), remote, 0, nullptr));
        if (!thread) {
            auto message = error("CreateRemoteThread"); VirtualFreeEx(process.h, remote, 0, MEM_RELEASE);
            return {false, message};
        }
        const DWORD wait = WaitForSingleObject(thread.h, 15000);
        if (wait != WAIT_OBJECT_0) {
            // Never free a string that a running loader thread might still read.
            return {false, wait == WAIT_TIMEOUT ?
                "LoadLibraryW still pending after 15 seconds. Path memory retained in target; loading may finish later. Restart target before retrying." :
                error("WaitForSingleObject; path memory retained in target")};
        }
        DWORD code{}; const bool gotCode = GetExitCodeThread(thread.h, &code) != FALSE;
        VirtualFreeEx(process.h, remote, 0, MEM_RELEASE);
        // A thread exit code is 32-bit, but HMODULE is 64-bit. Verify the module by full path.
        if (present(target.pid, path)) return {true, "DLL loaded and verified in target module list. Neural rendering activity is unknown."};
        std::ostringstream message;
        message << "DLL not present after LoadLibraryW. Check dependent DLLs, runtime/GPU compatibility, and DLL initialization.";
        if (gotCode) message << " Thread result: 0x" << std::hex << code << ".";
        for (const auto& m : modules(target.pid))
            if (_wcsicmp(m.name.c_str(), std::filesystem::path(path).filename().c_str()) == 0)
                message << " Observed module: " << utf8(m.path) << ".";
        return {false, message.str()};
    } catch (const std::exception& e) { return {false, e.what()}; }
}
}
