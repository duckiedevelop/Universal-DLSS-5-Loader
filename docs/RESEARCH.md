# Research and decisions, 2026-10-10

This file records the initial loader-only investigation. Version 0.2 subsequently added the complete Feeder/ReShade/RenoDX rendering pipeline and verified neural feature 18 on RTX 4050. Current behavior and validation are in README.md and VALIDATION.md; the initial implementation limits below describe version 0.1.

The requested project is a basic ImGui LoadLibrary injector. Implementation uses C++20, Win32, Toolhelp process/module enumeration and D3D11 for the GUI. No game files, saves, profiles, graphics settings or registry entries are modified. Verification targets are this project's own host processes.

## Findings

- [NVIDIA's September 2026 launch article](https://www.nvidia.com/en-us/geforce/news/dlss-5-3d-guided-neural-rendering/) describes frame color and motion vectors and Streamline integration. Official GPU support covers RTX 50-series. Merely mapping a DLL does not supply these inputs or create/evaluate a neural feature.
- [OptiScaler's DLSSNR module](https://github.com/Dagherbou/OptiScaler_DLSSNR/blob/dlss-neural-rendering/OptiScaler/dlssnr/README.md) identifies `nvngx_dlssnr.dll` as the runtime, NGX feature 18, and describes the necessary evaluate and composition stages. Those are outside a basic LoadLibrary loader.
- [RHI's manifest](https://github.com/RankFTW/RHI/blob/main/dlss_manifest.json) selects SF-v2, numeric 310.8.2, for RTX 20/30/40/50. This machine reports RTX 4050 Laptop GPU and Windows driver version 32.0.16.1692 (616.92). GPU support here is a community claim; actual neural rendering has not been tested.
- No NR DLL was found in the installed driver store, NVIDIA NGX cache or Downloads during the targeted filename search. NVIDIA's public DLSS repository tree did not contain an NR DLL. The chosen community release is pinned explicitly.

## Hash discrepancy resolved

The first archive-hash check failed because of a transcription error in this project's initial hash string; the corrected string matches GitHub's asset digest. The subsequent extracted-DLL check failed against the compatibility hash listed in [OptiShade's installation document](https://github.com/GamingWithGravy/OptiShade/blob/main/optiscaler/INSTALL-DLSSNR.md). That document lists `E67DEE209320CDAFE0E93E45675D7AA34323A53ACC57A72B2E40A181581C989A`.

The actual SF-v2 release ZIP is 116,693,212 bytes and hashes to `1da35941894994eb087e017577829e492454e9bae3a6a9397027069ceb74955c`, matching GitHub's `digest` and [Wan2GP's archive hash](https://github.com/deepbeepmeep/Wan2GP/blob/main/docs/DLSS5.md). Its DLL hashes to `6eb209e764f39872625debd6abaf45e2bb6322f6f270f781f70c059ae30b3927`. An independent [runtime lock](https://github.com/2600th/dlss5-video-player/blob/main/packaging/runtime-lock.json) specifies exactly this archive, extracted DLL hash, 165,830,144-byte size, 310.8.2.0 version and unsigned signature state. The downloader pins those values; it does not silently accept mismatches.

## Practical limit

The loader can confirm only module loading. To achieve visible NR output, choose an offline game and a graphics/upscaler bridge, then verify NGX initialization/evaluation and image output in that game. No universal compatibility claim is justified by this project or its tests.
