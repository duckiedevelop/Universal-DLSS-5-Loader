"""Stage a pinned official dgVoodoo DirectX 9 bridge without changing base payloads."""
import hashlib
import json
from pathlib import Path
import re
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parent
URL = 'https://github.com/dege-diosg/dgVoodoo2/releases/download/v2.87.5/dgVoodoo2_87_5.zip'
SHA256 = '5ffde6927f7355ca3fdd5d785b581256a8e6539fa13e395a891ade6ba1040850'

def main():
    archive = ROOT / 'packages/dgVoodoo2_87_5.zip'
    archive.parent.mkdir(exist_ok=True)
    if not archive.exists():
        request = urllib.request.Request(URL, headers={'User-Agent': 'DLSS5ProjectBuild/1.0'})
        with urllib.request.urlopen(request, timeout=90) as response:
            archive.write_bytes(response.read())
    data = archive.read_bytes()
    if hashlib.sha256(data).hexdigest() != SHA256:
        raise RuntimeError('Official dgVoodoo archive SHA-256 mismatch.')
    with zipfile.ZipFile(archive) as z:
        config = z.read('dgVoodoo.conf').decode('utf-8').replace('\r\r\n', '\n').replace('\r\n', '\n')
        for key, value in {'OutputAPI': 'd3d11_fl11_0', 'DisableAndPassThru': 'false',
                           'VideoCard': 'internal3D', 'VRAM': '1GB', 'dgVoodooWatermark': 'false'}.items():
            section = 'General' if key == 'OutputAPI' else 'DirectX'
            pattern = r'(?ms)(^\[' + section + r'\]\n(?:(?!^\[).)*?^' + key + r'[^\S\n]*=[^\S\n]*)[^\r\n]*'
            config, count = re.subn(pattern, lambda m: m[1] + value, config)
            if count != 1:
                raise RuntimeError('Unexpected dgVoodoo configuration key: ' + key)
        for arch in ('x86', 'x64'):
            folder = ROOT / 'payload/d3d9' / arch
            folder.mkdir(parents=True, exist_ok=True)
            (folder / 'd3d9.dll').write_bytes(z.read('MS/' + arch + '/D3D9.dll'))
            (folder / 'dgVoodoo.conf').write_text(config, encoding='utf-8')
            reshade = (ROOT / 'payload' / arch / 'ReShade.ini').read_text()
            reshade = reshade.replace('DepthCopyBeforeClears=0', 'DepthCopyBeforeClears=1')
            (folder / 'ReShade.ini').write_text(reshade, encoding='utf-8')
            manifest = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(folder.iterdir()) if p.is_file()}
            (folder.parent / (arch + '-manifest.json')).write_text(json.dumps(manifest, indent=2) + '\n')
    (ROOT / 'docs/d3d9-source.json').write_text(json.dumps({'url': URL, 'sha256': SHA256,
        'version': '2.87.5', 'upstream_instructions': 'https://github.com/jlrouzies-fr/DLSS5-Feeder/blob/main/README.md'}, indent=2) + '\n')
    print('Verified official dgVoodoo 2.87.5; x86/x64 DirectX 9 bridges ready.')

if __name__ == '__main__':
    main()
