# Third-party components

The root MIT license covers this project's code. It does not replace upstream licenses or grant rights to downloaded runtimes, game files, SDKs, or other third-party components.

| Component | Version or revision used | Source and retained terms |
| --- | --- | --- |
| Dear ImGui | 1.92.9b | [Upstream](https://github.com/ocornut/imgui/tree/v1.92.9b); downloaded into `third_party/imgui`, retaining `LICENSE.txt`. |
| nlohmann/json | 3.12.0 | [Upstream](https://github.com/nlohmann/json); vendored header and MIT license in `third_party/json`. |
| DLSS5-Feeder | 1.18.0-beta.2; helper source `7b41f5f3e57c260dec6012695c258e876fdfe6c5` | [Upstream](https://github.com/jlrouzies-fr/DLSS5-Feeder); copied MIT notice in `third_party/licenses/DLSS5-Feeder-MIT.txt`. Preparation retains the upstream checkout and its additional notices. |
| NVIDIA DLSS SDK | `374959484e79a640feaba44c93ac8cfb0a03f5b5` | [Upstream](https://github.com/NVIDIA/DLSS); `prepare-sdk.py` retains `LICENSE.txt` beside downloaded host build inputs. |
| ReShade | 6.8.0 with addon support | [Upstream](https://reshade.me); acquired by `prepare-packages.py`, under upstream terms. |
| RenoDX consumer | 7.0.0-rc8 | [Release](https://github.com/RankFTW/rhi-repo/releases/tag/renodx-dlss5-7.0.0-rc8); acquired locally, under upstream terms. |
| DLSS SR runtime | 310.9.1 | [Release](https://github.com/RankFTW/rhi-repo/releases/tag/dlss-310.9.1); excluded from source control. |
| DLSS NR runtime | 310.8 SF-v2 / 310.8.2.0 | [Community release](https://github.com/RankFTW/rhi-repo/releases/tag/dlssnr-310.8.SF-v2); modified and unsigned; excluded from source control. Archive and DLL hashes are in `runtime/provenance.json`. |
| LumeniteFX | Hash-checked `mainline` archive | [Upstream](https://github.com/umar-afzaal/LumeniteFX); downloaded locally, under upstream terms. |
| ReShade shader includes | `slim` branch | [Upstream](https://github.com/crosire/reshade-shaders/tree/slim); downloaded locally with hashes recorded in `packages/sources.json`. |
| dgVoodoo | 2.87.5 | [Release](https://github.com/dege-diosg/dgVoodoo2/releases/tag/v2.87.5); local archive and bridge files are excluded. Provenance is in `docs/d3d9-source.json`. |

`tools/nvidia-host.patch` contains the local helper change for explicit NVIDIA adapter selection. Keep Feeder's upstream notices with any permitted distribution of that derived helper.

The source archive deliberately omits downloaded dependencies, SDK inputs, compiled executables, and rendering payloads. Review each upstream component's actual terms before distributing any application bundle. Project code was developed with OpenAI Codex assistance; this preparation session used GPT-6. The project emblem in `docs/images/logo.png` was supplied by the project owner. No audio is included.
