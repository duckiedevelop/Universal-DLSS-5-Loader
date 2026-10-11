# Contributing

Build on Windows x64 with Visual Studio 2022, CMake 3.24+, Git, and Python 3.9+.

```powershell
.\build.ps1 -SourceOnly
```

This runs the native loader integration and Steam launch routing tests. For installer lifecycle coverage, prepare the rendering payload and run the full build:

```powershell
.\build.ps1
```

Installer tests use disposable fixtures and temporary game folders. Do not run experiments against another user's game, saves, or graphics preferences. GPU rendering checks are manual and need compatible NVIDIA hardware; their results belong in `docs/VALIDATION.md`, with hardware, versions, workload, and limits stated.

Keep payload verification, recovery journals, backup checks, and restore behavior intact. Changes to dependency versions or hashes must identify the upstream release and record the new provenance. Include relevant tests when changing installation, rollback, settings, or launch behavior.

Do not commit game files, downloaded runtimes, credentials, local settings, diagnostic folders, or compiled outputs. Before submitting a pull request, run:

```powershell
py -3 tools/prepare-github.py --check-only
git diff --check
```

For bug reports, use the GitHub issue template and include the graphics API, app version, Windows version, GPU/driver, and a short reproduction. Remove personal paths and credentials from logs. Never attach proprietary binaries or game files.
