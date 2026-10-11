"""Build an offline payload from the verified upstream installation in the lab."""
import hashlib
import json
from pathlib import Path
import shutil
import zipfile

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'payload'

def copy(source, destination):
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)

def main():
    native = ROOT / 'lab/native64'
    for source in native.rglob('*'):
        if not source.is_file():
            continue
        rel = source.relative_to(native)
        if rel.parts[0] == 'reshade-shaders' or rel.name in ['dxgi.dll', 'dlss5-feed.addon64', 'renodx-dlss5.addon64',
            'nvngx_dlssnr.dll', 'nvngx_dlss.dll', 'ReShade.ini', 'ReShadePreset.ini']:
            copy(source, OUT / 'x64' / rel)
    for source in (OUT / 'x64').rglob('*'):
        if source.is_file() and source.name not in ['dxgi.dll', 'renodx-dlss5.addon64', 'nvngx_dlssnr.dll', 'nvngx_dlss.dll']:
            copy(source, OUT / 'x86' / source.relative_to(OUT / 'x64'))
    with zipfile.ZipFile(ROOT / 'packages/ReShade_Setup_6.8.0_Addon.exe') as z:
        entry = next(n for n in z.namelist() if Path(n).name.lower() == 'reshade32.dll')
        (OUT / 'x86/dxgi.dll').write_bytes(z.read(entry))
    copy(ROOT / 'lab/dlss5-feed.addon32', OUT / 'x86/dlss5-feed.addon32')
    # x86 clients need exactly the matching helper protocol; this rebuilt helper
    # keeps that protocol and explicitly chooses NVIDIA on hybrid laptops.
    for destination in [OUT / 'x86/host64', ROOT / 'diagnostics/host64']:
        for name in ['dxgi.dll', 'renodx-dlss5.addon64', 'nvngx_dlssnr.dll', 'nvngx_dlss.dll']:
            copy(native / name, destination / name)
        copy(ROOT / 'third_party/feeder/host/dlss5-feed-host64.exe', destination / 'dlss5-feed-host64.exe')
        (destination / 'ReShade.ini').write_text(
            '[GENERAL]\nEffectSearchPaths=.\\\nTextureSearchPaths=.\\\n[OVERLAY]\nTutorialProgress=4\n'
            '[RenoDX.DLSS5]\nEnableHooks=2\nNeuralUplift=1\nNREnableUpscaling=0\nNRStyle=0\nNRToggleKey=0\nNRScreenshotKey=0\n')
    # No feeder addon belongs in an x86 game root's x64 payload.
    stray = OUT / 'x86/dlss5-feed.addon64'
    if stray.exists():
        stray.unlink()
    # Arm NR at the first frame, with one neural pass and safe default style.
    with (OUT / 'x64/ReShade.ini').open('a') as f:
        f.write('\n[RenoDX.DLSS5]\nEnableHooks=2\nNeuralUplift=1\nNREnableUpscaling=0\nNRStyle=0\nNRToggleKey=117,0,0,0\n')
    for arch in ['x64', 'x86']:
        manifest = {}
        for p in sorted((OUT / arch).rglob('*')):
            if p.is_file():
                manifest[p.relative_to(OUT / arch).as_posix()] = hashlib.sha256(p.read_bytes()).hexdigest()
        (OUT / (arch + '-manifest.json')).write_text(json.dumps(manifest, indent=2) + '\n')
    print('Offline payload staged: x64 and x86; GPU diagnostic host included.')

if __name__ == '__main__':
    main()
