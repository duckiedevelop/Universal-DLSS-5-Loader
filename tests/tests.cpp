#include "loader.h"
#include <filesystem>
#include <fstream>
#include <iostream>
#include <stdexcept>
namespace fs = std::filesystem;
void check(bool condition, const char* name) {
    if (!condition) throw std::runtime_error(name);
    std::cout << "PASS: " << name << '\n';
}
int wmain(int argc, wchar_t** argv) {
    const fs::path root(loader::executableDirectory());
    PROCESS_INFORMATION pi{}; STARTUPINFOW startup{}; startup.cb = sizeof(startup);
    const auto host = (root / L"LoadTestHost.exe").wstring();
    if (!CreateProcessW(host.c_str(), nullptr, nullptr, nullptr, FALSE, CREATE_NO_WINDOW,
        nullptr, root.c_str(), &startup, &pi)) return 2;
    int code{};
    const auto unicodeDll = root / L"fixture with spaces \u6e2c\u8a66.dll";
    const auto invalid = root / L"invalid-fixture.dll";
    try {
        loader::Process target;
        for (int attempt = 0; attempt < 30 && !target.pid; ++attempt) {
            for (const auto& p : loader::processes()) if (p.pid == pi.dwProcessId) target = p;
            if (!target.pid) Sleep(20);
        }
        check(target.pid != 0 && target.x64, "process enumeration / x64 check");
        fs::copy_file(root / "LoadTestDll.dll", unicodeDll, fs::copy_options::overwrite_existing);
        const auto info = loader::inspect(unicodeDll.wstring());
        check(info.valid && info.sha256.size() == 64, "PE inspection / SHA-256 / Unicode path");
        const auto rejected = loader::inject(target, (root / "RejectTestDll.dll").wstring());
        check(!rejected.ok, "DllMain failure is reported, not treated as success");
        const auto loaded = loader::inject(target, unicodeDll.wstring());
        std::cout << loaded.message << '\n';
        check(loaded.ok, "remote LoadLibraryW / full module path verification");
        const auto duplicate = loader::inject(target, unicodeDll.wstring());
        check(duplicate.ok && duplicate.message.find("already loaded") != std::string::npos, "duplicate load avoids extra reference");
        auto stale = target; ++stale.created;
        check(!loader::inject(stale, unicodeDll.wstring()).ok, "stale process identity rejected");
        { std::ofstream file(invalid, std::ios::binary); file << "not a PE"; }
        check(!loader::inspect(invalid.wstring()).valid, "non-PE file rejected");
        check(!loader::inspect(host).valid, "EXE rejected as a DLL");
        check(!loader::inject(target, (root / "does-not-exist.dll").wstring()).ok, "missing DLL rejected");
        check(!loader::inspect((root / "does-not-exist.dll").wstring()).valid, "missing DLL inspection rejected");
        if (argc == 2) {
            const auto runtime = loader::inspect(argv[1]);
            check(runtime.valid, "actual NR runtime is an x64 PE DLL");
            std::cout << "Runtime " << runtime.version << "; " << runtime.signature << "; SHA-256 " << runtime.sha256 << '\n';
            const auto loadRuntime = loader::inject(target, runtime.path);
            std::cout << loadRuntime.message << '\n';
            check(loadRuntime.ok, "actual NR runtime loads into isolated test host (no rendering performed)");
        }
    } catch (const std::exception& e) { std::cerr << "FAIL: " << e.what() << '\n'; code = 1; }
    const auto eventName = L"Local\\DlssLoaderTestStop-" + std::to_wstring(pi.dwProcessId);
    HANDLE stop = OpenEventW(EVENT_MODIFY_STATE, FALSE, eventName.c_str());
    if (stop) { SetEvent(stop); CloseHandle(stop); }
    if (WaitForSingleObject(pi.hProcess, 5000) == WAIT_TIMEOUT) {
        TerminateProcess(pi.hProcess, 9); WaitForSingleObject(pi.hProcess, 5000);
    }
    CloseHandle(pi.hThread); CloseHandle(pi.hProcess);
    std::error_code ec; fs::remove(unicodeDll, ec); fs::remove(invalid, ec);
    return code;
}
