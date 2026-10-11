# Universal DLSS 5 Loader verification, 2026-10-10

## Version 0.3.3 single-folder launch

Added `Build.cmd`, `Run.ps1`, and automatic first-run preparation through `Launch.cmd`. All source, generated dependencies, and build outputs stay in the same project directory. The launch script checks the generated files referenced by both architecture manifests before opening the app and invokes the full build when any required component is absent.

The 0.3.3 Release build completed without warnings and passed the native loader integration suite, 21 installer lifecycle tests, and seven Steam launch routing tests. `Launch.cmd -SmokeUi` passed from the project root, and a new setup capture confirmed the 0.3.3 menu. Source upload checks passed. These tests do not add new hardware or end-to-end game compatibility claims.

## GitHub source preparation

Renamed the native window, menu heading, and startup message to Universal DLSS 5 Loader. Rebuilt the Release application without compiler warnings after correcting Windows path escaping for the selected Python interpreter. The build now refreshes a CMake cache from a previous project location and checks generated payload files before deciding whether preparation is necessary.

The full local build verified all x86/x64 DirectX 9 and base payload hashes and passed all three CTest suites: native loader integration checks, 21 installer lifecycle tests, and seven Steam launch routing tests. The hidden setup capture exited 0; its actual rendering is included as `docs/images/menu.png`. The user's saved app settings were restored after capturing an empty selection.

The prepared source archive was extracted into a clean project directory without build files, rendering payloads, SDK inputs, or downloaded ImGui. `build.ps1 -SourceOnly` downloaded the pinned ImGui tag, compiled the application without warnings, and passed the native loader and Steam routing suites. Full dependency preparation from an empty cache and GitHub-hosted CI have not been run in this session.

Upload candidates passed the source packager's common-credential, local-path, binary, and large-file checks. A separate scan of all 82 historical Git blobs found no matching credential patterns or PE/ZIP signatures. These are limited pattern checks. The ZIP omits Git history, generated payloads, runtimes, build outputs, local settings, and logs. No GitHub repository, remote, release, or push was created during preparation. Earlier local edits were preserved.

## Version 0.3.1 launch correction

Fixed the EXE-only launcher to route installed Steam games through the normal Steam protocol. The real manifest for this user's csgo legacy directory identifies app 4465480. The separate app 730 manifest identifies CS2. The planned launch URI is steam://run/4465480//-insecure/. No Steam/game identity or ownership checks were changed. For standalone games, CreateProcess now uses the game's directory as cwd and passes options directly without a shell.

Seven new tests passed: manifest selection despite an obsolete steam_appid hint, preserving insecure and URL-encoding arguments, nested/space-containing installation paths, routing to Steam instead of direct launch, direct working-directory handling without a shell, refusing unmatched CS:GO folders instead of falling back to CS2, and invalid-control-character rejection. Release build and hidden UI startup passed. Game launch itself remains for the user's testing.

References: [Valve's Steam API launch-context documentation](https://partner.steamgames.com/doc/sdk/api) and [Steam launch command-line format](https://partner.steamgames.com/doc/api/ISteamApps#GetLaunchCommandLine).

## Version 0.3 customization

Release build passed without warnings. Twelve backend tests passed, including customization round trips, preserved comments/unrelated sections and UTF-16 text, invalid-setting rejection without writes, and x86 settings routed to host64. The customization tab was rendered and visually inspected; its controls scroll so Apply remains accessible on laptop displays.

The customized GPU test completed 300/300 evaluations with overall strength 0.55, color 0.7, local tone 0.8, detail 0.65, skin detail 0.2, automatic mask enabled, Natural style, model resolution 0.75, two passes and chained history disabled. Fresh consumer logs confirm each selected value. A separate Cinematic-style test also completed 300/300 evaluations with feature 18 active. Diagnostic configuration was restored afterward. Exact evidence is in customization-gpu-evidence.txt; the manual check is tests/test_customization_gpu.py.

Control mapping references: bundled Feeder source src/dlss5-feed32.cpp and the bundled RenoDX consumer's own saved settings/logs. [Upstream Feeder controls](https://github.com/jlrouzies-fr/DLSS5-Feeder/blob/7b41f5f3e57c260dec6012695c258e876fdfe6c5/src/dlss5-feed32.cpp) document the original strength/style controls; [the video player's setup documentation](https://github.com/2600th/dlss5-video-player/blob/main/docs/DLSS5_SETUP.md) describes schema 6 and the resolution multiplier. NRGlobalTone is absent from the current consumer's serialized settings, so this menu uses NRLocalTone. No standalone UI/HUD protection switch is advertised because Feeder does not guarantee separate HUD input.

Look presets are authored collections of these settings. No genre-specific model, quality guarantee or game compatibility claim is attached to them. No user's game settings were changed by the agent; install/apply tests used temporary folders, and model tests used the project's diagnostic host.

The Release build of build/Release/Dlss5Setup.exe passed without compiler warnings. CTest passed both suites, including seven backend lifecycle tests for Unicode paths, original-file restoration and retained edits, idempotence, foreign-loader refusal, altered manifests/backups, running games, rollback after a simulated write failure, and the x86 helper/component layout.

The ImGui app's --smoke-gpu workflow exited 0. Its backend ran a real 640x360 DLAA test on RTX 4050, with 300/300 evaluations succeeded. Fresh RenoDX logs confirm neural feature 18 creation and evaluation. This verifies actual neural model execution rather than merely loading a DLL.

The unmodified upstream helper selected Intel UHD Graphics and failed NGX initialization. A local source patch enumerates DXGI adapters and explicitly passes NVIDIA to D3D12CreateDevice. The rebuilt helper selects NVIDIA GeForce RTX 4050 Laptop GPU, driver 616.92, without changing Windows graphics preferences or driver settings.

The consumer log contains:
    feature 18 created via the signed snippet after DLSS/DLAA for NR input 640x360 -> output 640x360
    inline feature 18 evaluation succeeded

"Signed snippet" is the consumer's wording. The supplied SF-v2 NR runtime is unsigned; Windows Authenticode reports NotSigned. Its numeric version is 310.8.2.0 and SHA-256 is 6eb209e764f39872625debd6abaf45e2bb6322f6f270f781f70c059ae30b3927.

The app log records:
    GPU test passed: NVIDIA GeForce RTX 4050 Laptop GPU. 300/300 evaluations succeeded; DLSS 5 neural feature 18 created and evaluated.

The rendered GUI was captured from its D3D11 backbuffer and visually inspected. The clipped Restore label was shortened after inspection. The final executable's hidden-window startup check passed.

Limits: the workload is synthetic and small. It does not establish game-resolution performance, image quality or every graphics API's interop behavior. The x86 payload layout is verified, but no x86 or OpenGL game was run. The user elected to perform game testing; no user game was installed or launched. No anti-cheat/DRM bypass or driver/registry/profile change was made.
