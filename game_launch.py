"""Use the store's normal launch flow; never rewrite Steam identity or game binaries."""
from pathlib import Path
import os
import re
import subprocess
from urllib.parse import quote

def steam_install(exe):
    """Match the selected game directory to its Steam manifest, not steam_appid.txt."""
    exe = exe.resolve()
    for game_root in exe.parents:
        if game_root.parent.name.casefold() != 'common' or game_root.parent.parent.name.casefold() != 'steamapps':
            continue
        steamapps = game_root.parent.parent
        for manifest in steamapps.glob('appmanifest_*.acf'):
            try:
                text = manifest.read_text(encoding='utf-8-sig')
                values = {}
                for key, value in re.findall(r'"(appid|name|installdir)"\s*"((?:\\.|[^"\\])*)"', text):
                    values.setdefault(key, value.replace(r'\\', '\\').replace(r'\"', '"'))
                appid = values.get('appid', '')
                if not re.fullmatch(r'[1-9][0-9]{0,9}', appid):
                    continue
                directory = values.get('installdir', '')
                if not directory or Path(directory).name != directory:
                    continue
                expected = (steamapps / 'common' / directory).resolve()
                if os.path.normcase(str(expected)) == os.path.normcase(str(game_root)):
                    return {'appid': appid, 'name': values.get('name', directory), 'root': str(game_root)}
            except (OSError, UnicodeError):
                continue
        break
    return None

def is_legacy_csgo(exe):
    return exe.name.casefold() == 'csgo.exe'

def options(exe, value):
    if not isinstance(value, str) or len(value) > 4096 or any(ord(c) < 32 for c in value):
        raise ValueError('Launch options must be a single line of at most 4096 characters.')
    value = value.strip()
    if is_legacy_csgo(exe):
        # Use Valve's supported insecure mode for this graphics mod, including
        # when saved launch options contain only -console or -novid.
        if not re.search(r'(?:^|\s)-insecure(?:\s|$)', value, re.I):
            value = '-insecure' + (' ' + value if value else '')
    return value

def plan(exe, mode='auto', args=''):
    if mode not in ('auto', 'steam', 'direct'):
        raise ValueError('Invalid launch method.')
    install = steam_install(exe)
    args = options(exe, args)
    if is_legacy_csgo(exe):
        if not install:
            raise RuntimeError('This CS:GO EXE is not in a recognized Steam install. Select the real EXE from its Steam installation.')
        mode = 'steam'
    if mode == 'steam' or (mode == 'auto' and install):
        if not install:
            raise RuntimeError('No matching Steam manifest. Choose Direct EXE for a standalone game, or browse to its Steam install.')
        appid = install['appid']
        uri = f'steam://run/{appid}//{quote(args, safe="")}/' if args else f'steam://rungameid/{appid}'
        return {'method': 'steam', 'uri': uri, 'appid': appid, 'name': install['name'], 'args': args}
    return {'method': 'direct', 'exe': str(exe), 'cwd': str(exe.parent), 'args': args}

def execute(value):
    if value['method'] == 'steam':
        os.startfile(value['uri'])
        return 'Launch requested through Steam for ' + value['name'] + ' (app ' + value['appid'] + ').' + (
            ' Options: ' + value['args'] if value['args'] else '')
    # CreateProcess receives a command line directly. No cmd/PowerShell shell is used.
    command = subprocess.list2cmdline([value['exe']]) + (' ' + value['args'] if value['args'] else '')
    subprocess.Popen(command, executable=value['exe'], cwd=value['cwd'])
    return 'Launch requested for ' + Path(value['exe']).name + '.'
