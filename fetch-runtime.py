"""Download the pinned community SF-v2 runtime; verify both archive and DLL."""
from pathlib import Path
import hashlib
import io
import json
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parent
URL = 'https://github.com/RankFTW/rhi-repo/releases/download/dlssnr-310.8.SF-v2/nvngx_dlssnr_310.8.SF-v2.zip'
ARCHIVE_SHA = '1da35941894994eb087e017577829e492454e9bae3a6a9397027069ceb74955c'
DLL_SHA = '6eb209e764f39872625debd6abaf45e2bb6322f6f270f781f70c059ae30b3927'

def main():
    print('Downloading pinned DLSS NR 310.8 SF-v2 community runtime...', flush=True)
    with urllib.request.urlopen(URL, timeout=90) as response:
        archive = response.read()
    if hashlib.sha256(archive).hexdigest() != ARCHIVE_SHA:
        raise RuntimeError('Archive hash mismatch; no runtime installed.')
    with zipfile.ZipFile(io.BytesIO(archive)) as z:
        members = [n for n in z.namelist() if Path(n).name.lower() == 'nvngx_dlssnr.dll']
        if len(members) != 1:
            raise RuntimeError('Archive does not contain exactly one NR DLL.')
        dll = z.read(members[0])
    if hashlib.sha256(dll).hexdigest() != DLL_SHA:
        raise RuntimeError('DLL hash mismatch: ' + hashlib.sha256(dll).hexdigest() + '; no runtime installed.')
    destination = ROOT / 'runtime' / 'nvngx_dlssnr.dll'
    destination.parent.mkdir(exist_ok=True)
    destination.write_bytes(dll)
    provenance = {'source': URL, 'archive_sha256': ARCHIVE_SHA, 'dll_sha256': DLL_SHA,
                  'variant': '310.8 SF-v2 community-modified runtime',
                  'authenticode': 'Unsigned: embedded NVIDIA signature removed by community modification.',
                  'hash_reference': 'https://github.com/2600th/dlss5-video-player/blob/main/packaging/runtime-lock.json',
                  'archive_hash_reference': 'https://github.com/deepbeepmeep/Wan2GP/blob/main/docs/DLSS5.md'}
    (ROOT / 'runtime' / 'provenance.json').write_text(json.dumps(provenance, indent=2) + '\n')
    print(f'Verified {len(dll):,} bytes: {destination}', flush=True)

if __name__ == '__main__':
    main()
