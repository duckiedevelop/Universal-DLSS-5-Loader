# GitHub repository and source packaging

Display name: **Universal DLSS 5 Loader**

Repository: [duckiedevelop/Universal-DLSS-5-Loader](https://github.com/duckiedevelop/Universal-DLSS-5-Loader)

Description: `Windows ImGui app to install, customize, verify, and restore a community DLSS 5 rendering pipeline.`

License: MIT for project code; third-party terms are listed separately.

Suggested topics: `dlss`, `dlss5`, `reshade`, `imgui`, `windows`, `cpp`, `python`, `game-modding`.

## Prepared contents

- Application source and Python backend.
- Dependency preparation scripts, integrity manifests, provenance, and the NVIDIA adapter patch.
- README, actual menu screenshot, license, notices, changelog, and contributor instructions.
- Windows source-build CI, issue template, and pull request template.
- Automated native loader, installer lifecycle, and Steam launch routing tests.

Downloaded runtimes, game files, generated payloads, build outputs, settings, logs, and credentials stay outside the upload. Do not upload the entire working folder: it contains large local dependencies excluded by `.gitignore`.

## Review and package

From the project folder:

```powershell
.\build.ps1
py -3 tools/prepare-github.py
git diff --check
git status --short
```

The packager checks tracked files and non-ignored new files, then creates `dist/Universal-DLSS-5-Loader-source.zip` and a SHA-256 file manifest. It includes current edits and omits Git history. Extract the ZIP before using GitHub's web uploader so files land at the repository root.

The contents check detects common credential patterns, personal absolute paths, compiled binaries, generated folders, and unexpected large files. It is a limited pattern scan, not a guarantee that arbitrary private data or copyrighted content is absent.

The existing local Git repository can also be pushed after selecting a GitHub owner and destination. Review changes before committing; preserve the existing history rather than replacing it. Its author identity comes from the local Git configuration. No remote or GitHub repository is configured by these preparation scripts.

## Build validation

GitHub Actions runs a source-only Windows build with native loader and Steam routing tests. The full local build additionally verifies both payload architectures and runs installer lifecycle tests. Hardware diagnostics and end-to-end game tests are separate; a passing source build does not certify runtime performance or compatibility.

Use the upload manifest and `docs/VALIDATION.md` to review the concrete result before publishing. The packager does not create release tags or distribute downloaded binaries. Source releases require local compilation and dependency preparation; double-click `Launch.cmd` in the project folder to perform first-run preparation automatically.
