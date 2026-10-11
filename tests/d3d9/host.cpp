// Disposable DirectX 9 renderer; exercises the full 32-bit bridge on real hardware.
#include <windows.h>
#include <d3d9.h>
#include <dxgi.h>
#include <cstdio>
#include <cstring>
extern "C" {
    __declspec(dllexport) DWORD NvOptimusEnablement = 1;
    __declspec(dllexport) DWORD AmdPowerXpressRequestHighPerformance = 1;
}

int WINAPI wWinMain(HINSTANCE instance, HINSTANCE, PWSTR, int) {
    FILE* log{}; fopen_s(&log, "bridge-host.txt", "w");
    auto record = [&](const char* name, HRESULT hr) { if (log) { fprintf(log, "%s: 0x%08lx\n", name, hr); fflush(log); } };
    IDXGIFactory* factory{};
    if (SUCCEEDED(CreateDXGIFactory(__uuidof(IDXGIFactory), reinterpret_cast<void**>(&factory)))) {
        IDXGIAdapter* adapter{};
        for (UINT i = 0; SUCCEEDED(factory->EnumAdapters(i, &adapter)); ++i) {
            DXGI_ADAPTER_DESC desc{}; adapter->GetDesc(&desc);
            if (log) { fprintf(log, "DXGI adapter %u vendor %04x\n", i, desc.VendorId); fflush(log); }
            adapter->Release();
        }
        factory->Release();
    }
    WNDCLASSW wc{}; wc.lpfnWndProc = DefWindowProcW; wc.hInstance = instance; wc.lpszClassName = L"D3D9BridgeTest";
    RegisterClassW(&wc);
    HWND window = CreateWindowW(wc.lpszClassName, L"Disposable D3D9 rendering fixture", WS_OVERLAPPEDWINDOW,
        0, 0, 640, 360, nullptr, nullptr, instance, nullptr);
    auto api = Direct3DCreate9(D3D_SDK_VERSION);
    if (!api) { record("Direct3DCreate9 failed", E_FAIL); return 1; }
    UINT adapter{};
    for (UINT i = 0; i < api->GetAdapterCount(); ++i) {
        D3DADAPTER_IDENTIFIER9 id{};
        api->GetAdapterIdentifier(i, 0, &id);
        if (log) { fprintf(log, "adapter %u: %s vendor %04lx\n", i, id.Description, id.VendorId); fflush(log); }
        if (id.VendorId == 0x10de || strstr(id.Description, "NVIDIA")) adapter = i;
    }
    D3DPRESENT_PARAMETERS pp{}; pp.Windowed = TRUE; pp.hDeviceWindow = window; pp.SwapEffect = D3DSWAPEFFECT_DISCARD;
    pp.BackBufferWidth = 640; pp.BackBufferHeight = 360; pp.BackBufferFormat = D3DFMT_X8R8G8B8;
    pp.EnableAutoDepthStencil = TRUE; pp.AutoDepthStencilFormat = D3DFMT_D24S8; pp.PresentationInterval = D3DPRESENT_INTERVAL_IMMEDIATE;
    IDirect3DDevice9* device{};
    auto hr = api->CreateDevice(adapter, D3DDEVTYPE_HAL, window, D3DCREATE_HARDWARE_VERTEXPROCESSING, &pp, &device);
    record("CreateDevice", hr);
    if (FAILED(hr)) { api->Release(); return 2; }
    struct Vertex { float x, y, z, rhw; DWORD color; };
    unsigned frames{};
    const ULONGLONG deadline = GetTickCount64() + 45000;
    while (GetTickCount64() < deadline) {
        MSG message{};
        while (PeekMessageW(&message, nullptr, 0, 0, PM_REMOVE)) { TranslateMessage(&message); DispatchMessageW(&message); }
        const float offset = float(frames % 120);
        Vertex vertices[]{{50 + offset, 40, .5f, 1, 0xffff8000}, {460, 300, .5f, 1, 0xff00ff80}, {90 + offset, 300, .5f, 1, 0xff8000ff}};
        device->Clear(0, nullptr, D3DCLEAR_TARGET | D3DCLEAR_ZBUFFER, 0xff102030, 1.f, 0);
        device->BeginScene(); device->SetFVF(D3DFVF_XYZRHW | D3DFVF_DIFFUSE);
        device->DrawPrimitiveUP(D3DPT_TRIANGLELIST, 1, vertices, sizeof(Vertex)); device->EndScene();
        hr = device->Present(nullptr, nullptr, nullptr, nullptr);
        if (FAILED(hr)) { record("Present failed", hr); break; }
        ++frames; Sleep(16);
    }
    if (log) fprintf(log, "frames presented: %u\n", frames);
    device->Release(); api->Release(); DestroyWindow(window);
    if (log) fclose(log);
    return FAILED(hr) || !frames ? 3 : 0;
}
