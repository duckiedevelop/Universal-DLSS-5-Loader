"""Stage pinned components from their upstream release assets."""
import hashlib
import io
import json
from pathlib import Path
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'packages'
OUT.mkdir(exist_ok=True)
ASSETS = [
 ('https://github.com/jlrouzies-fr/DLSS5-Feeder/releases/download/v1.18.0-beta.2/DLSS5-Feeder-1.18.0-beta.2.zip',
  '4d459f902d5a8faace03c6909962334e800a58b73e0aee49eb1b30a3572f43dc', 'DLSS5-Feeder-1.18.0-beta.2.zip'),
 ('https://github.com/RankFTW/rhi-repo/releases/download/renodx-dlss5-7.0.0-rc8/renodx-dlss5_7.0.0-rc8.zip',
  'c0821162ebcc24db29dfd1ad6e45214e9f118e40de510f05f0981e0c9ea70639', 'renodx-dlss5_7.0.0-rc8.zip'),
 ('https://github.com/RankFTW/rhi-repo/releases/download/dlss-310.9.1/nvngx_dlss_310.9.1.zip',
  'aaba83b288bd145c3808e8d7a0ba03cc8c8676d18ad984b1bfa6563046a3ba37', 'nvngx_dlss_310.9.1.zip'),
 ('https://reshade.me/downloads/ReShade_Setup_6.8.0_Addon.exe',
  'afe4c8f13048306307983b8b3d41d5bf00a86820440b0e57dea10950e1176445', 'ReShade_Setup_6.8.0_Addon.exe'),
 ('https://codeload.github.com/umar-afzaal/LumeniteFX/zip/refs/heads/mainline',
  'f86404ea393fbb839d65721d3889cb3c43ee9025bef994cc4e36e3daa2989443', 'LumeniteFX-mainline.zip'),
]

def main():
    records = []
    for url, expected, name in ASSETS:
        path = OUT / name
        if not path.exists():
            print('Downloading ' + name, flush=True)
            request = urllib.request.Request(url, headers={'User-Agent': 'DLSS5ProjectBuild/1.0'})
            with urllib.request.urlopen(request, timeout=90) as response:
                data = response.read()
        else:
            data = path.read_bytes()
        actual = hashlib.sha256(data).hexdigest()
        if expected and expected != actual:
            raise RuntimeError(name + ': SHA-256 mismatch')
        path.write_bytes(data)
        records.append({'name': name, 'url': url, 'sha256': actual})
        print(name + ' ' + actual, flush=True)
    for name in ['ReShade.fxh', 'ReShadeUI.fxh', 'DrawText.fxh']:
        url = 'https://raw.githubusercontent.com/crosire/reshade-shaders/slim/Shaders/' + name
        data = urllib.request.urlopen(url, timeout=30).read()
        (OUT / name).write_bytes(data)
        records.append({'name': name, 'url': url, 'sha256': hashlib.sha256(data).hexdigest()})
    (OUT / 'sources.json').write_text(json.dumps(records, indent=2) + '\n')
    with zipfile.ZipFile(OUT / 'DLSS5-Feeder-1.18.0-beta.2.zip') as z:
        # Explicit extraction under this new directory; never extract arbitrary paths.
        base = (ROOT / 'lab').resolve()
        base.mkdir(exist_ok=True)
        for item in z.infolist():
            dest = (base / item.filename).resolve()
            if not dest.is_relative_to(base):
                raise RuntimeError('Unsafe archive path')
            if item.is_dir():
                dest.mkdir(parents=True, exist_ok=True)
            else:
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(z.read(item))

if __name__ == '__main__':
    main()
