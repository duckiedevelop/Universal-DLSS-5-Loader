"""Check Git upload candidates and create a source-only ZIP from current files."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parent.parent
ARCHIVE_ROOT = 'Universal-DLSS-5-Loader'
REQUIRED = {'README.md', 'LICENSE', 'THIRD_PARTY_NOTICES.md', 'Build.cmd', 'Launch.cmd', 'Run.ps1', '.gitignore',
            '.gitattributes', 'build.ps1', '.github/workflows/build.yml'}
LOCAL_FOLDERS = {'build', 'dist', 'out', 'runtime-cache', 'packages', 'lab',
                 'jobs', 'diagnostics', '__pycache__', '.vs', '.idea', '.vscode'}
BINARY_EXTENSIONS = {'.exe', '.dll', '.lib', '.obj', '.pdb', '.addon32',
                     '.addon64', '.zip', '.7z', '.rar', '.pak', '.vpk', '.dat',
                     '.pyc', '.pyo', '.dmp'}
SECRET_PATTERNS = [
    re.compile(rb'(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})'),
    re.compile(rb'(?:sk-(?:proj-|ant-)?[A-Za-z0-9_-]{24,})'),
    re.compile(rb'(?:AKIA|ASIA)[A-Z0-9]{16}'),
    re.compile(rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),
    re.compile(rb'(?im)^\s*(?:FAL_KEY|ANTHROPIC_API_KEY|OPENAI_API_KEY|GITHUB_TOKEN|AWS_SECRET_ACCESS_KEY)\s*[=:]\s*[\"\']?[A-Za-z0-9_./+=:-]{16,}'),
]
LOCAL_PATH = re.compile(rb'(?i)(?:[A-Z]:[\\/]+Users[\\/]+|/Users/|/home/)[A-Za-z0-9_.-]+')


def git(*args):
    return subprocess.check_output(['git', '-C', str(ROOT), *args])


def candidates():
    names = git('ls-files', '-z', '--cached', '--others', '--exclude-standard')
    return sorted(set(names.decode('utf-8').strip('\0').split('\0')))


def check_files(names):
    failures = []
    records = []
    missing = REQUIRED - set(names)
    failures.extend('Required file missing: ' + name for name in sorted(missing))
    for name in names:
        relative = PurePosixPath(name)
        path = ROOT / name
        if path.is_symlink() or not path.resolve().is_relative_to(ROOT):
            failures.append('External/symlink path: ' + name)
            continue
        if not path.is_file():
            failures.append('Tracked file missing: ' + name)
            continue
        if (any(part in LOCAL_FOLDERS for part in relative.parts)
                or name.startswith(('payload/x64/', 'payload/x86/', 'payload/d3d9/x64/',
                                    'payload/d3d9/x86/', 'third_party/feeder/', 'third_party/imgui/'))
                or relative.name.startswith('.env')
                or relative.name in {'settings.json', 'setup.log', 'old-app-block.txt'}
                or path.suffix.lower() in BINARY_EXTENSIONS | {'.log', '.pem', '.key'}):
            failures.append('Local, secret, generated, or binary file selected: ' + name)
        if path.stat().st_size > 5 * 1024 * 1024:
            failures.append('Unexpected large source file (>5 MiB): ' + name)
            continue
        data = path.read_bytes()
        if any(pattern.search(data) for pattern in SECRET_PATTERNS):
            failures.append('Possible credential in: ' + name)
        if path.suffix.lower() not in {'.png', '.jpg', '.jpeg', '.bmp'}:
            if LOCAL_PATH.search(data):
                failures.append('Personal absolute path in: ' + name)
            if re.search(rb'(?i)decompiled (?:with|by)', data):
                failures.append('Decompiler header in: ' + name)
        records.append({'path': name, 'bytes': len(data),
                        'sha256': hashlib.sha256(data).hexdigest()})
    if failures:
        raise RuntimeError('\n'.join(failures))
    return records


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check-only', action='store_true')
    args = parser.parse_args()
    names = candidates()
    records = check_files(names)
    print(f'Upload check passed: {len(records)} source files; no detected credentials, '
          'personal absolute paths, compiled outputs, or downloaded payloads.')
    print('This pattern check is not a guarantee; review new files and upstream terms before publishing.')
    if args.check_only:
        return
    output = ROOT / 'dist'
    output.mkdir(exist_ok=True)
    archive = output / (ARCHIVE_ROOT + '-source.zip')
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as bundle:
        for name in names:
            bundle.write(ROOT / name, ARCHIVE_ROOT + '/' + name)
    # Verify that the completed archive contains exactly the approved inputs.
    with zipfile.ZipFile(archive) as bundle:
        if bundle.testzip() is not None:
            raise RuntimeError('Source archive failed its CRC check.')
        for record in records:
            data = bundle.read(ARCHIVE_ROOT + '/' + record['path'])
            if hashlib.sha256(data).hexdigest() != record['sha256']:
                raise RuntimeError('Source changed while packaging: ' + record['path'])
    report = {'archive': archive.name, 'sha256': hashlib.sha256(archive.read_bytes()).hexdigest(),
              'file_count': len(records), 'files': records}
    (output / 'source-upload-manifest.json').write_text(
        json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print('Created ' + str(archive))
    print('SHA-256: ' + report['sha256'])


if __name__ == '__main__':
    main()
