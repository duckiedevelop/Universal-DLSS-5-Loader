"""Get host build inputs from NVIDIA's public SDK, retaining its license."""
import json
from pathlib import Path
import urllib.request
ROOT = Path(__file__).resolve().parent
target = ROOT / 'third_party/feeder/external/ngx'
commit = '374959484e79a640feaba44c93ac8cfb0a03f5b5'
tree = json.load(urllib.request.urlopen(f'https://api.github.com/repos/NVIDIA/DLSS/git/trees/{commit}?recursive=1'))
for item in tree['tree']:
    name = item['path']
    if not (name.startswith('include/') or name == 'lib/Windows_x86_64/x64/nvsdk_ngx_d.lib' or name == 'LICENSE.txt'):
        continue
    if item['type'] != 'blob':
        continue
    dest = target / ('libs/nvsdk_ngx_d.lib' if name.endswith('.lib') else Path(name).name)
    dest.parent.mkdir(parents=True, exist_ok=True)
    url = f'https://raw.githubusercontent.com/NVIDIA/DLSS/{commit}/{name}'
    dest.write_bytes(urllib.request.urlopen(url, timeout=60).read())
print('NVIDIA SDK commit ' + commit)
(target / 'sdk-commit.txt').write_text(commit + '\n')
