"""Offline installer, rollback, and genuine NGX test for the ImGui application."""
from pathlib import Path
import ctypes
from ctypes import wintypes
import hashlib
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import time
import appearance
import game_launch
import graphics_adapter

ROOT = Path(__file__).resolve().parent
STATE = '.dlss5-setup'

def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()

def safe(base, relative):
    base = base.resolve()
    result = (base / relative).resolve()
    if not result.is_relative_to(base) or result == base:
        raise RuntimeError('Invalid path in installation manifest.')
    return result

def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    os.replace(tmp, path)

def pe(path):
    with path.open('rb') as f:
        dos = f.read(64)
        if len(dos) != 64 or dos[:2] != b'MZ':
            raise RuntimeError('Select a Windows game executable.')
        nt = struct.unpack_from('<I', dos, 60)[0]
        f.seek(nt)
        header = f.read(24)
        if len(header) != 24 or header[:4] != b'PE\0\0':
            raise RuntimeError('Invalid executable header.')
        machine = struct.unpack_from('<H', header, 4)[0]
        flags = struct.unpack_from('<H', header, 22)[0]
        optional = f.read(2)
        if flags & 0x2000:
            raise RuntimeError('Select the game EXE, not a DLL.')
        if machine not in (0x14c, 0x8664):
            raise RuntimeError('This build supports x86 and x64 games.')
        if len(optional) != 2 or struct.unpack('<H', optional)[0] != (0x20b if machine == 0x8664 else 0x10b):
            raise RuntimeError('Executable architecture/header mismatch.')
        # API detection is only a hint: engines may load graphics DLLs at runtime.
        f.seek(0)
        data = f.read(32 * 1024 * 1024).lower()
    api = 'OpenGL' if b'opengl32.dll' in data else 'Vulkan' if b'vulkan-1.dll' in data else 'D3D9' if b'd3d9.dll' in data and b'd3d11.dll' not in data else 'DirectX 11 / 12'
    return ('x64' if machine == 0x8664 else 'x86'), api

def target(job):
    value = job.get('game', '')
    if not value:
        raise RuntimeError('Choose your game executable first.')
    exe = Path(value).resolve(strict=True)
    if exe.suffix.lower() != '.exe':
        raise RuntimeError('Choose the real game .exe.')
    arch, hint = pe(exe)
    # Source keeps its graphics imports in engine modules, not in the small EXE.
    if exe.name.lower() == 'csgo.exe' and (exe.parent / 'bin/shaderapidx9.dll').is_file():
        hint = 'D3D9'
    return exe, arch, hint

def ensure_closed(exe):
    """Compare full process image paths, so launcher names cannot hide a running game."""
    psapi = ctypes.WinDLL('psapi', use_last_error=True)
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
    pids = (wintypes.DWORD * 65536)()
    length = wintypes.DWORD()
    if not psapi.EnumProcesses(pids, ctypes.sizeof(pids), ctypes.byref(length)):
        raise RuntimeError('Could not inspect running processes; installation stopped.')
    expected = os.path.normcase(str(exe))
    for pid in pids[:length.value // ctypes.sizeof(wintypes.DWORD)]:
        handle = kernel.OpenProcess(0x1000, False, pid)
        if not handle:
            continue
        try:
            name = ctypes.create_unicode_buffer(32768)
            size = wintypes.DWORD(len(name))
            if kernel.QueryFullProcessImageNameW(handle, 0, name, ctypes.byref(size)) and os.path.normcase(os.path.realpath(name.value)) == expected:
                raise RuntimeError('Close the selected game before installing or restoring.')
        finally:
            kernel.CloseHandle(handle)

def files_for(arch, api):
    data = json.loads((ROOT / 'payload' / (arch + '-manifest.json')).read_text())
    result = {}
    for name, expected in data.items():
        source = safe(ROOT / 'payload' / arch, name)
        if digest(source) != expected:
            raise RuntimeError('Bundled component changed or is missing: ' + name)
        destination = 'opengl32.dll' if api == 'OpenGL' and name == 'dxgi.dll' else name
        result[destination] = (source, expected)
    if api == 'D3D9':
        bridge = ROOT / 'payload/d3d9'
        extra = json.loads((bridge / (arch + '-manifest.json')).read_text())
        for name, expected in extra.items():
            source = safe(bridge / arch, name)
            if digest(source) != expected:
                raise RuntimeError('Bundled DirectX 9 component changed or is missing: ' + name)
            result[name] = (source, expected)
    return result

def read_install(directory):
    path = directory / STATE / 'install.json'
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding='utf-8'))
    if data.get('schema') != 1 or data.get('arch') not in ('x86', 'x64') or data.get('api') not in ('DirectX 11 / 12', 'OpenGL', 'D3D9'):
        raise RuntimeError('Installation journal is invalid; no files changed.')
    allowed = json.loads((ROOT / 'payload' / (data['arch'] + '-manifest.json')).read_text())
    if data['api'] == 'OpenGL':
        allowed['opengl32.dll'] = allowed.pop('dxgi.dll')
    elif data['api'] == 'D3D9':
        allowed.update(json.loads((ROOT / 'payload/d3d9' / (data['arch'] + '-manifest.json')).read_text()))
    if not isinstance(data.get('files'), dict) or any(name not in allowed or entry.get('installed_sha256') != allowed[name]
        for name, entry in data['files'].items()):
        raise RuntimeError('Installation journal contains unexpected files; no files changed.')
    prefs = data.get('gpu_preferences', [])
    selected = Path(data.get('exe', '')).resolve()
    allowed_preferences = {str(selected), str(safe(directory, 'host64/dlss5-feed-host64.exe'))}
    if selected.parent != directory.resolve() or not isinstance(prefs, list) or len(prefs) > 2 or any(
        not isinstance(p, dict) or p.get('name') not in allowed_preferences or
        not isinstance(p.get('installed'), str) or not p['installed'].startswith('GpuPreference=2;') or
        (p.get('previous') is not None and not isinstance(p['previous'], str)) for p in prefs):
        raise RuntimeError('Invalid graphics preference recovery journal; no files changed.')
    return data

def scan(job):
    exe, arch, hint = target(job)
    state = read_install(exe.parent)
    result = {'ok': True, 'message': f'{exe.name}: {arch}. Graphics hint: {hint}. ' +
            ('DLSS 5 setup installed. Use Check after playing to read the rendering logs.' if state else 'Ready to install. Close the game first.'),
            'arch': arch, 'hint': hint, 'installed': bool(state)}
    result['repair_d3d9'] = bool(state and hint == 'D3D9' and state['api'] != 'D3D9')
    if result['repair_d3d9']:
        result['message'] = 'DirectX 9 game detected, but its installed setup lacks the translation bridge. Click Repair DirectX 9 setup before launching.'
    if state:
        result['settings'], notes = appearance.read(appearance_path(exe.parent, state))
        if notes:
            result['message'] += ' ' + ' '.join(notes)
    steam = game_launch.steam_install(exe)
    if steam:
        result['message'] += f" Steam app: {steam['name']} ({steam['appid']})."
    return result

def appearance_path(directory, state):
    return safe(directory, 'host64/ReShade.ini' if state['arch'] == 'x86' else 'ReShade.ini')

def write_appearance(directory, state, settings):
    config = appearance_path(directory, state)
    original = config.read_bytes() if config.exists() else None
    text = appearance.render(appearance.read_text(config), settings)
    # Preserve the entire previous INI, including settings adjusted in-game.
    previous = directory / STATE / 'settings-history' / (time.strftime('%Y%m%d-%H%M%S') + '-' + str(time.time_ns()) + '.ini')
    if original is not None:
        previous.parent.mkdir(parents=True, exist_ok=True)
        previous.write_bytes(original)
    tmp = config.with_name(config.name + '.dlss5-settings')
    try:
        tmp.write_bytes(appearance.encode(text, original or b''))
        os.replace(tmp, config)
    finally:
        if tmp.exists():
            tmp.unlink()

def load_settings(job):
    exe, _, _ = target(job)
    state = read_install(exe.parent)
    if not state:
        raise RuntimeError('Install DLSS 5 first. You can choose a look before installation.')
    settings, notes = appearance.read(appearance_path(exe.parent, state))
    return {'ok': True, 'settings': settings, 'message': 'Loaded this game\'s current neural rendering settings.' + (' ' + ' '.join(notes) if notes else '')}

def apply_settings(job):
    settings = appearance.normalize(job.get('settings', {}))
    exe, _, _ = target(job)
    ensure_closed(exe)
    state = read_install(exe.parent)
    if not state or state['phase'] != 'installed':
        raise RuntimeError('Install DLSS 5 before applying customization.')
    if state['arch'] == 'x86':
        ensure_closed(safe(exe.parent, 'host64/dlss5-feed-host64.exe'))
    write_appearance(exe.parent, state, settings)
    return {'ok': True, 'settings': settings, 'message': 'Saved customization for ' + exe.name + '. Start the game to use it. Previous settings are backed up.'}

def install(job):
    selected = appearance.normalize(job['settings']) if 'settings' in job else None
    exe, arch, hint = target(job)
    ensure_closed(exe)
    api = job.get('api', 'DirectX 11 / 12')
    if api not in ('DirectX 11 / 12', 'OpenGL', 'D3D9'):
        raise RuntimeError('This installer supports DirectX 9, DirectX 11/12 and OpenGL. Vulkan requires a different bridge.')
    if hint == 'D3D9' and exe.name.lower() == 'csgo.exe' and api != 'D3D9':
        raise RuntimeError('Legacy CS:GO uses DirectX 9. Select DirectX 9 in Graphics API, or use Repair DirectX 9 setup.')
    directory = exe.parent
    state = read_install(directory)
    if state:
        if state['api'] != api:
            raise RuntimeError('The existing setup uses a different graphics API. Restore originals first, or use Repair DirectX 9 setup when offered.')
        return check(job)
    files = files_for(arch, api)
    bridge_gpu = graphics_adapter.nvidia_name() if api == 'D3D9' else None
    prefs = graphics_adapter.prepare_preferences([exe, safe(directory, 'host64/dlss5-feed-host64.exe')]
        if arch == 'x86' else [exe]) if bridge_gpu else []
    proxy = 'opengl32.dll' if api == 'OpenGL' else 'dxgi.dll'
    if (directory / proxy).exists():
        raise RuntimeError(f'An existing {proxy} loader is present. Restore/remove it with its own tool first so loaders do not conflict.')
    if api == 'D3D9' and (directory / 'd3d9.dll').exists():
        raise RuntimeError('An existing d3d9.dll loader is present. Restore/remove it with its own tool first.')
    # Keep existing shader effects and unrelated files, but never stack neural consumers.
    for p in directory.glob('*'):
        if p.is_file() and (p.suffix.lower() in ('.addon', '.addon64', '.addon32') or p.name.lower() in ('winmm.dll', 'dinput8.dll')):
            raise RuntimeError(f'Existing mod loader/addon {p.name} detected. Use a clean game folder for this setup.')
    backup = directory / STATE
    if backup.exists():
        raise RuntimeError('An unfinished setup backup exists. Click Restore before installing again.')
    backup.mkdir()
    manifest = {'schema': 1, 'exe': str(exe), 'arch': arch, 'api': api, 'phase': 'installing', 'installed_at': time.time(), 'files': {}}
    if prefs:
        manifest['gpu_preferences'] = prefs
        manifest['d3d9_gpu'] = bridge_gpu
    try:
        # Write the full recovery journal before the first game file is replaced.
        for name, (source, expected) in files.items():
            dest = safe(directory, name)
            original = None
            if dest.exists():
                if not dest.is_file():
                    raise RuntimeError('Destination is not a regular file: ' + name)
                original = digest(dest)
                saved = safe(backup / 'originals', name)
                saved.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(dest, saved)
            manifest['files'][name] = {'original_sha256': original, 'installed_sha256': expected}
        write_json(backup / 'install.json', manifest)
        if prefs:
            graphics_adapter.apply_preferences(prefs)
        for name, (source, _) in files.items():
            dest = safe(directory, name)
            dest.parent.mkdir(parents=True, exist_ok=True)
            # os.replace swaps a complete file atomically on the same volume.
            tmp = dest.with_name(dest.name + '.dlss5-installing')
            shutil.copy2(source, tmp)
            os.replace(tmp, dest)
        manifest['phase'] = 'installed'
        write_json(backup / 'install.json', manifest)
        if selected is not None:
            write_appearance(directory, manifest, selected)
    except Exception:
        if (backup / 'install.json').exists():
            restore({'game': str(exe), 'rollback': True})
        else:
            # No game writes have happened at this point. Retain originals for review.
            write_json(backup / 'install.json', manifest)
        raise
    result = {'ok': True, 'message': f'Installed the full DLSS 5 pipeline for {exe.name} ({arch}). Launch normally, press Home for controls, then use Check after playing. Original files are backed up.'}
    if prefs:
        result['message'] += ' Windows graphics preference set to high performance for the game and helper; Restore also restores the previous preference.'
    result['settings'], _ = appearance.read(appearance_path(directory, manifest))
    return result

def restore(job):
    exe, _, _ = target(job)
    ensure_closed(exe)
    directory = exe.parent
    manifest = read_install(directory)
    if not manifest:
        return {'ok': True, 'message': 'No managed installation to restore.'}
    if manifest['arch'] == 'x86':
        ensure_closed(safe(directory, 'host64/dlss5-feed-host64.exe'))
    backup = directory / STATE
    # Validate every original before making changes; never partially restore damaged backups.
    for name, entry in manifest['files'].items():
        safe(directory, name)
        if entry['original_sha256']:
            saved = safe(backup / 'originals', name)
            if not saved.is_file() or digest(saved) != entry['original_sha256']:
                raise RuntimeError('Backup is missing or changed: ' + name + '. Restore stopped.')
    changed_dir = backup / 'changed-after-install'
    restored = []
    for name, entry in manifest['files'].items():
        dest = safe(directory, name)
        if dest.is_file():
            current = digest(dest)
            if current not in (entry['installed_sha256'], entry['original_sha256']):
                saved = safe(changed_dir, name)
                saved.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(dest, saved)
        if entry['original_sha256']:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(safe(backup / 'originals', name), dest)
        elif dest.exists():
            if not dest.is_file():
                raise RuntimeError('A managed destination became a directory: ' + name)
            dest.unlink()
        tmp = dest.with_name(dest.name + '.dlss5-installing')
        if tmp.is_file():
            tmp.unlink()
        restored.append(name)
    graphics_adapter.restore_preferences(manifest.get('gpu_preferences', []))
    write_json(backup / 'restored.json', manifest)
    (backup / 'install.json').unlink()
    # Keep all backups and edits in a history directory; no recursive deletion.
    history = directory / (STATE + '-history-' + time.strftime('%Y%m%d-%H%M%S') + '-' + str(os.getpid()))
    backup.rename(history)
    return {'ok': True, 'message': f'Restored original files and removed {len(restored)} managed components. Backups and any changed settings were preserved in {history.name}.'}

def repair_d3d9(job):
    exe, arch, hint = target(job)
    if hint != 'D3D9':
        raise RuntimeError('Repair is only offered for a detected DirectX 9 game.')
    ensure_closed(exe)
    state = read_install(exe.parent)
    if state and state['arch'] == 'x86':
        ensure_closed(safe(exe.parent, 'host64/dlss5-feed-host64.exe'))
    # Verify the replacement bundle before restoring the previous installation.
    files_for(arch, 'D3D9')
    graphics_adapter.nvidia_name()
    for name in ('dxgi.dll', 'd3d9.dll'):
        if (exe.parent / name).exists() and (not state or name not in state['files']):
            raise RuntimeError('An existing ' + name + ' loader is present. Repair stopped before changing files.')
    settings = appearance.read(appearance_path(exe.parent, state))[0] if state else job.get('settings', {})
    if state and state['api'] != 'D3D9':
        restore(job)
    result = install({**job, 'api': 'D3D9', 'settings': settings})
    result['message'] = 'DirectX 9 setup repaired with dgVoodoo → DirectX 11. Your neural rendering settings were preserved. Launch through Steam with -insecure; press Home for controls.'
    return result

def check(job):
    exe, _, _ = target(job)
    manifest = read_install(exe.parent)
    if not manifest:
        raise RuntimeError('No managed installation found. Install first.')
    missing = [name for name in manifest['files'] if not safe(exe.parent, name).is_file()]
    if missing:
        raise RuntimeError('Missing installed files: ' + ', '.join(missing[:5]))
    changed = []
    for name, entry in manifest['files'].items():
        if Path(name).suffix.lower() in ('.dll', '.addon64', '.addon32', '.exe') and digest(safe(exe.parent, name)) != entry['installed_sha256']:
            changed.append(name)
    if changed:
        raise RuntimeError('Installed binaries were changed: ' + ', '.join(changed))
    dirs = [exe.parent, exe.parent / 'host64']
    logs = '\n'.join(p.read_text(errors='replace') for d in dirs for p in (d / 'ReShade.log', d / 'dlss5-feed.log', d / 'dlss5-feed-host.log')
        if p.exists() and p.stat().st_mtime >= manifest.get('installed_at', 0))
    active = bool(re.search(r'feature 18 evaluation succeeded|neural feature active|neural model \(feature 18\) loaded', logs, re.I))
    return {'ok': True, 'message': 'All installed components verified. ' +
            ('Neural rendering was active in the last recorded session.' if active else 'No neural rendering activity confirmed yet. Launch the game on the NVIDIA GPU, check Home for shader/depth settings, then try Check again.'), 'active': active}

def gpu_test(job):
    folder = ROOT / 'diagnostics/host64'
    host = folder / 'dlss5-feed-host64.exe'
    start = time.time()
    process = subprocess.run([str(host), '--test', '--hide'], cwd=folder,
        creationflags=subprocess.CREATE_NO_WINDOW, timeout=90, capture_output=True)
    paths = [folder / 'dlss5-feed-host.log', folder / 'ReShade.log']
    if any(not p.is_file() or p.stat().st_mtime < start - 1 for p in paths):
        raise RuntimeError('GPU test did not produce fresh logs.')
    log = paths[0].read_text(errors='replace')
    reshade = paths[1].read_text(errors='replace')
    success = process.returncode == 0 and '300/300 evaluates succeeded' in log and 'feature 18 evaluation succeeded' in reshade
    if not success:
        lines = [x for x in (log + '\n' + reshade).splitlines() if re.search(r'failed|unavailable|error|not supported|not an NVIDIA', x, re.I)]
        raise RuntimeError('GPU neural rendering test failed. ' + ('\n'.join(lines[-4:]) or f'Helper exit code {process.returncode}; see diagnostics/host64 logs.'))
    adapter = re.search(r'explicitly selected NVIDIA adapter: ([^\r\n]+)', log)
    return {'ok': True, 'message': 'GPU test passed: ' + (adapter.group(1) if adapter else 'NVIDIA GPU') +
            '. 300/300 evaluations succeeded; DLSS 5 neural feature 18 created and evaluated.'}

def launch(job):
    exe, _, hint = target(job)
    state = read_install(exe.parent)
    if state and hint == 'D3D9' and exe.name.lower() == 'csgo.exe' and state['api'] != 'D3D9':
        raise RuntimeError('Legacy CS:GO has an incompatible graphics setup. Click Repair DirectX 9 setup before launching.')
    if state:
        check(job)
    value = game_launch.plan(exe, job.get('launch_mode', 'auto'), job.get('launch_options', ''))
    message = game_launch.execute(value)
    return {'ok': True, 'message': message + ' Press Home for the ImGui/ReShade controls.'}

def main():
    if len(sys.argv) != 2:
        raise RuntimeError('The GUI passes a job file to this backend.')
    job = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
    actions = {'scan': scan, 'install': install, 'restore': restore, 'check': check, 'gpu-test': gpu_test, 'launch': launch,
               'load-settings': load_settings, 'apply-settings': apply_settings, 'repair-d3d9': repair_d3d9}
    try:
        result = actions[job['action']](job)
    except Exception as e:
        result = {'ok': False, 'message': str(e)}
    write_json(Path(job['result']), result)
    return 0 if result['ok'] else 1

if __name__ == '__main__':
    sys.exit(main())
