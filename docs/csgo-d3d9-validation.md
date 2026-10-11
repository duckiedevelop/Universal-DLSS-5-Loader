# Legacy CS:GO startup repair

The 2026-10-10 15:21:43 crash dump reports access violation c0000005 in
`D3D12Core!VersionedDeviceData::IsD3D12DDIVersionOrLater`. The present stack
passes through `d3d9on12!D3D12TranslationLayer::ImmediateContextInternal::Present`,
`d3d9!CBaseDevice::Present`, Steam's `gameoverlayrenderer`, and `shaderapidx9`.
It establishes a failure in the native DirectX 9-on-12 presentation path; it does
not establish that DLSS or ReShade alone caused the driver fault.

Steam's gameprocess log confirms normal app 4465480 launches with
`csgo.exe -steam -worldwide -insecure`, followed by exit code 100. The selected
game is x86 Source/DirectX 9. Its previous managed setup installed only the
DirectX 11/12 ReShade route, without the required D3D9 translation wrapper.

The [Feeder instructions](https://github.com/jlrouzies-fr/DLSS5-Feeder/blob/main/README.md)
specify dgVoodoo → D3D11 for D3D9 games. The official
[dgVoodoo release](https://github.com/dege-diosg/dgVoodoo2/releases/tag/v2.87.5)
archive was checked against GitHub's published SHA-256; provenance is in
`d3d9-source.json`. Base payload manifests remain unchanged so existing
installations can still be restored.

Actual GPU verification used a disposable x86 DirectX 9 renderer on this laptop,
not CS:GO. With default GPU selection, dgVoodoo ran on Intel and the NVIDIA
helper failed to open shared frame handles (80070057). Selecting dgVoodoo by a
DXGI ordinal was unsuitable because the process's adapter order changes on
Optimus. Per-program Windows high-performance graphics preferences resolved
this without patching the game executable or changing system-wide GPU settings.

The test without an Optimus export, using only the installed graphics preference,
presented 1398 frames over 45 seconds and exited 0. The feeder connected with
protocol v11, created its shared frame set, and delivered frames. The helper
confirmed `neural feature active (feature 18 created and evaluated)`. Its
ReShade log confirmed successful feature 18 evaluation at counts 1, 60 and 600.
Selected excerpts are in `d3d9-gpu-evidence.txt`.

This verifies the DirectX 9 → D3D11 → x64 helper → neural rendering path on the
RTX 4050. CS:GO itself still needs the user's launch and gameplay test, as they
previously chose to perform game testing personally.
