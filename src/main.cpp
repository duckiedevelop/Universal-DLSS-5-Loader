#include "loader.h"
#include <d3d11.h>
#include <commdlg.h>
#include <shellapi.h>
#include "imgui.h"
#include "imgui_stdlib.h"
#include "imgui_impl_win32.h"
#include "imgui_impl_dx11.h"
#include <algorithm>
#include <filesystem>
#include <fstream>
#include <future>
#include <chrono>
#include "json.hpp"

extern IMGUI_IMPL_API LRESULT ImGui_ImplWin32_WndProcHandler(HWND, UINT, WPARAM, LPARAM);
namespace {
ID3D11Device* device{};
ID3D11DeviceContext* d3dContext{};
IDXGISwapChain* swapchain{};
ID3D11RenderTargetView* renderTarget{};
UINT resizeWidth{}, resizeHeight{};
bool makeTarget() {
    ID3D11Texture2D* back{};
    if (FAILED(swapchain->GetBuffer(0, IID_PPV_ARGS(&back)))) return false;
    const HRESULT result = device->CreateRenderTargetView(back, nullptr, &renderTarget);
    back->Release(); return SUCCEEDED(result);
}
bool captureUi() {
    ID3D11Texture2D *back{}, *staging{};
    if (FAILED(swapchain->GetBuffer(0, IID_PPV_ARGS(&back)))) return false;
    D3D11_TEXTURE2D_DESC desc{}; back->GetDesc(&desc);
    desc.Usage = D3D11_USAGE_STAGING; desc.BindFlags = 0; desc.MiscFlags = 0; desc.CPUAccessFlags = D3D11_CPU_ACCESS_READ;
    if (FAILED(device->CreateTexture2D(&desc, nullptr, &staging))) { back->Release(); return false; }
    d3dContext->CopyResource(staging, back); back->Release();
    D3D11_MAPPED_SUBRESOURCE mapped{};
    if (FAILED(d3dContext->Map(staging, 0, D3D11_MAP_READ, 0, &mapped))) { staging->Release(); return false; }
    BITMAPFILEHEADER header{}; header.bfType = 0x4d42; header.bfOffBits = sizeof(header) + sizeof(BITMAPINFOHEADER);
    header.bfSize = header.bfOffBits + desc.Width * desc.Height * 4;
    BITMAPINFOHEADER info{}; info.biSize = sizeof(info); info.biWidth = static_cast<LONG>(desc.Width);
    info.biHeight = -static_cast<LONG>(desc.Height); info.biPlanes = 1; info.biBitCount = 32; info.biCompression = BI_RGB;
    std::ofstream file(std::filesystem::path(loader::executableDirectory()) / "ui-preview.bmp", std::ios::binary);
    file.write(reinterpret_cast<char*>(&header), sizeof(header)); file.write(reinterpret_cast<char*>(&info), sizeof(info));
    std::vector<unsigned char> row(desc.Width * 4);
    for (UINT y = 0; y < desc.Height; ++y) {
        auto* source = static_cast<unsigned char*>(mapped.pData) + y * mapped.RowPitch;
        for (UINT x = 0; x < desc.Width; ++x) {
            row[x * 4] = source[x * 4 + 2]; row[x * 4 + 1] = source[x * 4 + 1];
            row[x * 4 + 2] = source[x * 4]; row[x * 4 + 3] = source[x * 4 + 3];
        }
        file.write(reinterpret_cast<char*>(row.data()), static_cast<std::streamsize>(row.size()));
    }
    d3dContext->Unmap(staging, 0); staging->Release(); return file.good();
}
void cleanup() {
    if (renderTarget) { renderTarget->Release(); renderTarget = nullptr; }
    if (swapchain) { swapchain->Release(); swapchain = nullptr; }
    if (d3dContext) { d3dContext->Release(); d3dContext = nullptr; }
    if (device) { device->Release(); device = nullptr; }
}
bool createDevice(HWND window) {
    DXGI_SWAP_CHAIN_DESC desc{};
    desc.BufferCount = 2; desc.BufferDesc.Format = DXGI_FORMAT_R8G8B8A8_UNORM;
    desc.BufferUsage = DXGI_USAGE_RENDER_TARGET_OUTPUT; desc.OutputWindow = window;
    desc.SampleDesc.Count = 1; desc.Windowed = TRUE; desc.SwapEffect = DXGI_SWAP_EFFECT_DISCARD;
    D3D_FEATURE_LEVEL level{};
    const D3D_FEATURE_LEVEL levels[] = {D3D_FEATURE_LEVEL_11_0, D3D_FEATURE_LEVEL_10_0};
    HRESULT result = D3D11CreateDeviceAndSwapChain(nullptr, D3D_DRIVER_TYPE_HARDWARE, nullptr, 0,
        levels, 2, D3D11_SDK_VERSION, &desc, &swapchain, &device, &level, &d3dContext);
    if (FAILED(result)) {
        cleanup();
        result = D3D11CreateDeviceAndSwapChain(nullptr, D3D_DRIVER_TYPE_WARP, nullptr, 0,
            levels, 2, D3D11_SDK_VERSION, &desc, &swapchain, &device, &level, &d3dContext);
    }
    return SUCCEEDED(result) && makeTarget();
}
LRESULT WINAPI windowProc(HWND hwnd, UINT message, WPARAM wp, LPARAM lp) {
    if (ImGui_ImplWin32_WndProcHandler(hwnd, message, wp, lp)) return 1;
    switch (message) {
    case WM_SIZE:
        if (wp != SIZE_MINIMIZED) { resizeWidth = LOWORD(lp); resizeHeight = HIWORD(lp); }
        return 0;
    case WM_GETMINMAXINFO:
        reinterpret_cast<MINMAXINFO*>(lp)->ptMinTrackSize = {760, 620}; return 0;
    case WM_SYSCOMMAND: if ((wp & 0xfff0) == SC_KEYMENU) return 0; break;
    case WM_DESTROY: PostQuitMessage(0); return 0;
    }
    return DefWindowProcW(hwnd, message, wp, lp);
}
std::wstring browse(HWND owner) {
    wchar_t file[32768]{};
    OPENFILENAMEW dialog{}; dialog.lStructSize = sizeof(dialog); dialog.hwndOwner = owner;
    dialog.lpstrFilter = L"Game executable (*.exe)\0*.exe\0";
    dialog.lpstrTitle = L"Select the real game executable";
    dialog.lpstrFile = file; dialog.nMaxFile = 32768;
    dialog.Flags = OFN_FILEMUSTEXIST | OFN_PATHMUSTEXIST | OFN_NOCHANGEDIR;
    return GetOpenFileNameW(&dialog) ? file : L"";
}
#include "manager_ui.h"

void style() {
    ImGui::StyleColorsDark();
    auto& s = ImGui::GetStyle();
    s.WindowPadding = ImVec2(20, 18); s.FramePadding = ImVec2(9, 6);
    s.ItemSpacing = ImVec2(10, 8); s.FrameRounding = 4; s.ChildRounding = 4;
    s.Colors[ImGuiCol_WindowBg] = ImVec4(0.07f, 0.08f, 0.095f, 1);
    s.Colors[ImGuiCol_Button] = ImVec4(0.19f, 0.30f, 0.20f, 1);
    s.Colors[ImGuiCol_ButtonHovered] = ImVec4(0.26f, 0.42f, 0.27f, 1);
    s.Colors[ImGuiCol_ButtonActive] = ImVec4(0.30f, 0.50f, 0.30f, 1);
    s.Colors[ImGuiCol_Header] = ImVec4(0.19f, 0.30f, 0.20f, 1);
}
}
int WINAPI wWinMain(HINSTANCE instance, HINSTANCE, PWSTR command, int show) {
    const bool smokeGpu = std::wstring(command).find(L"--smoke-gpu") != std::wstring::npos;
    const bool captureSetup = std::wstring(command).find(L"--capture-setup") != std::wstring::npos;
    const bool capture = captureSetup || std::wstring(command).find(L"--capture-ui") != std::wstring::npos;
    const bool smoke = capture || smokeGpu || std::wstring(command).find(L"--smoke-ui") != std::wstring::npos;
    ImGui_ImplWin32_EnableDpiAwareness();
    WNDCLASSEXW wc{sizeof(wc), CS_CLASSDC, windowProc, 0, 0, instance, nullptr, nullptr, nullptr, nullptr,
        L"Dlss5LoaderWindow", nullptr};
    wc.hCursor = LoadCursor(nullptr, IDC_ARROW);
    if (!RegisterClassExW(&wc)) return 1;
    HWND window = CreateWindowW(wc.lpszClassName, L"Universal DLSS 5 Loader", WS_OVERLAPPEDWINDOW,
        CW_USEDEFAULT, CW_USEDEFAULT, 1000, 830, nullptr, nullptr, instance, nullptr);
    if (!window || !createDevice(window)) {
        cleanup(); if (window) DestroyWindow(window); UnregisterClassW(wc.lpszClassName, instance);
        if (!smoke) MessageBoxW(nullptr, L"Could not initialize the Direct3D 11 interface.", L"Universal DLSS 5 Loader", MB_ICONERROR);
        return 2;
    }
    IMGUI_CHECKVERSION(); ImGui::CreateContext(); ImGui::GetIO().IniFilename = nullptr;
    style();
    const float dpi = ImGui_ImplWin32_GetDpiScaleForHwnd(window);
    ImGui::GetStyle().ScaleAllSizes(dpi); ImGui::GetStyle().FontScaleDpi = dpi;
    const bool platformReady = ImGui_ImplWin32_Init(window);
    const bool rendererReady = ImGui_ImplDX11_Init(device, d3dContext);
    if (!platformReady || !rendererReady) {
        if (rendererReady) ImGui_ImplDX11_Shutdown();
        if (platformReady) ImGui_ImplWin32_Shutdown();
        ImGui::DestroyContext(); cleanup(); DestroyWindow(window); UnregisterClassW(wc.lpszClassName, instance); return 3;
    }
    ShowWindow(window, smoke ? SW_HIDE : show); UpdateWindow(window);
    bool done{}; int frames{}, exitCode{};
    {
        App app;
        if (capture) app.selectedTab = captureSetup ? 1 : 2;
        if (smokeGpu) app.start("gpu-test");
        while (!done) {
            MSG msg{};
            while (PeekMessageW(&msg, nullptr, 0, 0, PM_REMOVE)) {
                TranslateMessage(&msg); DispatchMessageW(&msg); if (msg.message == WM_QUIT) done = true;
            }
            if (done) break;
            if (IsIconic(window)) { Sleep(20); continue; }
            if (resizeWidth && resizeHeight) {
                if (renderTarget) { renderTarget->Release(); renderTarget = nullptr; }
                d3dContext->OMSetRenderTargets(0, nullptr, nullptr);
                const HRESULT result = swapchain->ResizeBuffers(0, resizeWidth, resizeHeight, DXGI_FORMAT_UNKNOWN, 0);
                resizeWidth = resizeHeight = 0;
                if (FAILED(result) || !makeTarget()) { exitCode = 4; break; }
            }
            ImGui_ImplDX11_NewFrame(); ImGui_ImplWin32_NewFrame(); ImGui::NewFrame();
            app.draw(window); ImGui::Render();
            const float background[4] = {0.07f, 0.08f, 0.095f, 1};
            d3dContext->OMSetRenderTargets(1, &renderTarget, nullptr);
            d3dContext->ClearRenderTargetView(renderTarget, background);
            ImGui_ImplDX11_RenderDrawData(ImGui::GetDrawData());
            if (capture && frames >= 11 && !app.task.valid() && !captureUi()) { exitCode = 8; break; }
            const HRESULT present = swapchain->Present(1, 0);
            if (FAILED(present)) { exitCode = 5; break; }
            if (smoke && ++frames >= 12 && !app.task.valid()) { exitCode = app.lastOk ? 0 : 6; done = true; }
        }
    }
    ImGui_ImplDX11_Shutdown(); ImGui_ImplWin32_Shutdown(); ImGui::DestroyContext();
    cleanup(); DestroyWindow(window); UnregisterClassW(wc.lpszClassName, instance);
    return exitCode;
}
