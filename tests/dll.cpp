#include <windows.h>
extern "C" __declspec(dllexport) int FixtureVersion() { return 1; }
BOOL WINAPI DllMain(HINSTANCE module, DWORD reason, LPVOID) {
    if (reason == DLL_PROCESS_ATTACH) {
#ifdef REJECT_ATTACH
        return FALSE;
#else
        DisableThreadLibraryCalls(module);
#endif
    }
    return TRUE;
}
