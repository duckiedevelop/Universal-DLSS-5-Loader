#pragma once
#include <windows.h>
#include <cstdint>
#include <string>
#include <vector>

namespace loader {
struct Process {
    DWORD pid{};
    std::uint64_t created{};
    std::wstring name, path;
    bool x64{};
};
struct DllInfo {
    bool valid{};
    std::wstring path;
    std::string version, sha256, signature, note;
};
struct Result { bool ok{}; std::string message; };
std::string utf8(const std::wstring& value);
std::wstring wide(const std::string& value);
std::vector<Process> processes();
DllInfo inspect(const std::wstring& path);
Result inject(const Process& target, const std::wstring& path);
std::wstring executableDirectory();
}
