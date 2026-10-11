#include <windows.h>
#include <string>
int wmain() {
    const auto name = L"Local\\DlssLoaderTestStop-" + std::to_wstring(GetCurrentProcessId());
    HANDLE stop = CreateEventW(nullptr, TRUE, FALSE, name.c_str());
    if (!stop) return 1;
    WaitForSingleObject(stop, 60000); CloseHandle(stop); return 0;
}
