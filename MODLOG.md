# Universal DLSS 5 Loader development history

Project: Universal DLSS 5 Loader. The entries below record earlier versions and their validation at the time.

GitHub source preparation: renamed the menu/window branding, added the owner-selected MIT license and third-party notices, replaced the machine-specific README with build/use instructions and an actual menu screenshot, and added Windows source-build CI and source archive checks. Corrected fresh-clone payload detection, relocated CMake cache handling, and Python path escaping. Full local CTest and clean-extraction source builds passed; see `docs/VALIDATION.md`. No publication or release tag was created.

Requested scope: native Dear ImGui GUI, basic LoadLibrary injector, research and runtime acquisition. Route: x64 Windows LoadLibraryW remote thread; no manual mapping or bypasses. Rendering integration is explicitly absent because the DLL requires API calls and game frame resources.

Tools: VS 2022 Community / MSVC 19.44, CMake, pinned Dear ImGui v1.92.9b. Runtime: SF-v2 community modification, hashes in `runtime/provenance.json` and `docs/RESEARCH.md`.

Read-only hardware recon: RTX 4050 Laptop GPU; NVIDIA Windows driver 32.0.16.1692. Research found the official support and the community runtime differ by GPU generation. Exact archive/DLL hashes were reconciled against release metadata and an independent runtime lock after a failed initial DLL hash check.

Only disposable project-owned test hosts are used for injector verification. No game installation, save/profile, graphics setting, registry entry or external account is changed.

Completed verification: Release build with no compiler warnings, CTest integration suite passed, hidden ImGui/D3D11 interface smoke test exited 0, included 310.8.2.0 unsigned NR runtime loaded and verified in the disposable host. Found Toolhelp's Unicode module-path loss during tests; fixed full paths via `K32GetModuleFileNameExW` before checking file identity. No actual neural rendering/game output was tested. Detailed result: `docs/VALIDATION.md`.

## Version 0.2: full pipeline app

User requested a functional app using GitHub projects and chose to test the games personally ("No ill test"). Replaced frontend with DLSS 5 Setup: browse game, inspect, offline install, check binary integrity/recent NR logs, restore, launch, and genuine GPU test. Sources: jlrouzies-fr/DLSS5-Feeder, ReShade official site, RHI runtime/consumer assets, LumeniteFX. Bundled x64 and x86 DirectX 11/12 and OpenGL payloads; Vulkan and D3D9 bridges remain outside this app's supported scope.

Runtime validation now proves actual feature 18 creation/evaluation on RTX 4050. Upstream host landed on Intel and failed; rebuilt it with explicit NVIDIA DXGI adapter selection. Source base 7b41f5f3e57c260dec6012695c258e876fdfe6c5; patch tools/nvidia-host.patch; NVIDIA SDK 374959484e79a640feaba44c93ac8cfb0a03f5b5. Consumer RenoDX v7.0.0-rc8; feeder release 1.18.0-beta.2; ReShade 6.8.0; DLSS SR 310.9.1; NR SF-v2 310.8.2.0.

Backend recovery journal written before game file replacements; originals hashed/backed up, all payload inputs checked, write failures rolled back. Restore validates backups, retains post-install edits and leaves unrelated files intact. Tests passed for these behaviors. ImGui front-to-back GPU workflow passed and GUI was visually inspected. Final executable build/Release/Dlss5Setup.exe; Launch.cmd updated. No user game was changed or launched.

## Version 0.3: customization

Added a Customize DLSS 5 tab with shared customization.json schema, supported strength/tone/detail/skin/color/mask controls, model styles, resolution scale, passes, chained history and model preset hint. Adjustable authored presets: Balanced, Subtle, Characters/story, Scenery/racing, Fast action. Backend appearance.py validates bounds and merges only managed keys into the RenoDX section, preserving unrelated text/comments/encoding. Installed x86 game controls go to host64/ReShade.ini; x64 controls go to root ReShade.ini. Existing settings can be loaded; new installs use the selected controls; Apply requires a closed game and retains previous INI versions. Draft controls persist across app restarts.

Actual GPU test confirmed modified values at 75% model resolution and two passes, plus Natural and Cinematic styles, with 300/300 evaluations on RTX 4050. Evidence docs/customization-gpu-evidence.txt. Twelve backend tests passed, including invalid/no-write settings, UTF-16 preservation, per-game round-trip and x86 routing. Menu visually inspected and rebuilt. User's selected Tomb Raider path was read by startup inspection; no agent write/launch occurred in that game. The user continues game testing.

## Version 0.3.1: Steam launch fix

User's old CS:GO in official insecure mode reported launch-from-Steam error. Launcher previously used os.startfile(EXE), omitting Steam context and game working directory. New game_launch.py matches Steam installation manifests and uses normal Steam launch URIs, retaining/adding -insecure for csgo.exe. Actual selected folder is registered by appmanifest_4465480.acf; appmanifest_730.acf belongs to CS2. The existing steam_appid.txt and csgo/steam.inf still say 730, so neither was treated as authoritative or edited. Standalone launches now have correct cwd and no shell. Seven new routing tests passed. Built 0.3.1 and tested hidden UI startup; user remains responsible for game testing, so no game was launched or modified by agent.

## Version 0.3.2: legacy CS:GO startup repair

User reported instant exit after the corrected Steam launch. Read-only CDB analysis of the fresh crash dump found c0000005 in D3D12Core through D3D9on12's first Present, with shaderapidx9 in the caller stack. Steam logs confirm app 4465480 and -insecure, so this is a graphics startup failure. Source's EXE does not directly import its rendering API, and the earlier app missed the DirectX 9 engine module and installed only the DirectX 11/12 route.

Added official dgVoodoo 2.87.5, archive SHA-256 verified against GitHub release metadata, in separate x86/x64 bridge payloads. Configured D3D11 output, 1GB emulated VRAM and depth copying. Existing base hashes remain intact so old installations still restore. Added automatic Source/CSGO API detection, a repair action preserving neural settings and backup history, and rejection of the incompatible legacy route before installation/launch. UI rebuilt as 0.3.2 with DirectX 9 and repair controls; hidden startup and Setup capture were inspected.

The first disposable x86 D3D9 renderer ran on Intel and could not share frames with the NVIDIA helper. A DXGI ordinal override was unsuitable because Optimus changes adapter order per process. The installer now records and sets Windows high-performance graphics preferences per EXE/helper, preserving other options; rollback/Restore recover prior values and retain subsequent user edits. Verified with an x86 fixture without an Optimus export: 1398 frames presented in 45 seconds, exit 0, protocol v11 shared frames, genuine feature 18 creation and evaluation with success counts 1/60/600. Evidence docs/d3d9-gpu-evidence.txt and docs/csgo-d3d9-validation.md. All three CTest suites passed, including 21 installer tests and seven Steam routing tests.

Applied the reversible graphics repair to the user's existing managed CS:GO setup in response to their crash report. Rechecked all binaries, retained exact neural settings, and verified the game EXE, steam_appid.txt and steam.inf hashes were unchanged. Only the selected game/helper graphics preferences were changed and backed up. Old setup history remains in the game folder. No game was launched by the agent: the user's CS:GO end-to-end test is still pending. Repair result docs/csgo-repair-result.json. Restored the project-owned GPU-preference fixture afterward and removed its temporary preference entries.
