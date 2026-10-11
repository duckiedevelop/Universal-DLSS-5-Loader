# Changelog

## 0.3.3

- Rename the window, menu heading, and startup message to Universal DLSS 5 Loader.
- Add double-click Build.cmd and automatic first-launch preparation from Launch.cmd.
- Add the MIT license, third-party notices, contributor instructions, and GitHub issue templates.
- Fix payload preparation after cloning: check generated files instead of assuming tracked manifests mean the payload exists.
- Add a source-only build and a Windows GitHub Actions workflow.
- Add checked source archive generation for GitHub uploads.
- Preserve the existing local change removing online-client name/folder filtering from the installer.

## 0.3.2

- Add verified dgVoodoo DirectX 9 bridge payloads and automatic legacy CS:GO API detection.
- Repair managed legacy installations while retaining neural settings and backup history.
- Record and restore per-program high-performance GPU preferences for hybrid systems.
- Verify an x86 DirectX 9 fixture sharing frames with the NVIDIA helper.

## 0.3.1

- Route Steam games through their detected installation manifests.
- Retain legacy CS:GO's `-insecure` launch option.
- Set the correct working directory for standalone launches.

## 0.3.0

- Add per-game customization, authored look presets, and persistent draft controls.
- Preserve unrelated INI sections, comments, and encoding when applying settings.
- Verify customized Natural and Cinematic settings in GPU diagnostics.

## 0.2.0

- Add the ReShade, Feeder, and RenoDX pipeline with offline installation, backup, rollback, and restore.
- Add actual neural feature creation/evaluation diagnostics and explicit NVIDIA adapter selection.

## 0.1.0

- Add the native ImGui interface and LoadLibrary test harness.

Detailed historical evidence is retained in `MODLOG.md` and `docs/VALIDATION.md`.
