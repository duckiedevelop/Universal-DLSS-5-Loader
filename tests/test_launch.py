from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import game_launch as launch

class SteamLaunchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='dlss5-launch-test-')
        self.steamapps = Path(self.temp.name) / 'Steam/steamapps'
        self.game = self.steamapps / 'common/csgo legacy'
        self.game.mkdir(parents=True)
        self.exe = self.game / 'csgo.exe'
        self.exe.touch()
        (self.steamapps / 'appmanifest_4465480.acf').write_text(
            '"AppState" { "appid" "4465480" "name" "Counter-Strike:Global Offensive" "installdir" "csgo legacy" }')
        (self.steamapps / 'appmanifest_730.acf').write_text(
            '"AppState" { "appid" "730" "name" "Counter-Strike 2" "installdir" "Counter-Strike Global Offensive" }')

    def tearDown(self):
        self.temp.cleanup()

    def test_manifest_beats_old_steam_appid_hint(self):
        (self.game / 'steam_appid.txt').write_text('730')
        value = launch.plan(self.exe)
        self.assertEqual(value['appid'], '4465480')
        self.assertEqual(value['uri'], 'steam://run/4465480//-insecure/')
        self.assertEqual((self.game / 'steam_appid.txt').read_text(), '730')

    def test_insecure_is_retained_and_options_are_url_encoded(self):
        value = launch.plan(self.exe, 'auto', '-insecure -console -novid')
        self.assertEqual(value['args'].count('-insecure'), 1)
        self.assertIn('-insecure%20-console%20-novid', value['uri'])
        value = launch.plan(self.exe, 'direct', '-console')
        self.assertEqual(value['method'], 'steam')
        self.assertEqual(value['args'], '-insecure -console')

    def test_nested_steam_executable_and_spaces(self):
        exe = self.game / 'bin/Win32/Another.exe'
        exe.parent.mkdir(parents=True)
        exe.touch()
        self.assertEqual(launch.plan(exe)['uri'], 'steam://rungameid/4465480')

    def test_steam_request_does_not_start_the_game_exe_directly(self):
        with patch.object(launch.os, 'startfile') as request, patch.object(launch.subprocess, 'Popen') as direct:
            launch.execute(launch.plan(self.exe))
            request.assert_called_once_with('steam://run/4465480//-insecure/')
            direct.assert_not_called()

    def test_direct_launch_has_game_working_directory_and_no_shell(self):
        exe = Path(self.temp.name) / 'Standalone/My Game.exe'
        exe.parent.mkdir()
        exe.touch()
        value = launch.plan(exe, 'direct', '-windowed')
        with patch.object(launch.subprocess, 'Popen') as process:
            launch.execute(value)
            self.assertEqual(process.call_args.kwargs['cwd'], str(exe.parent))
            self.assertEqual(process.call_args.kwargs['executable'], str(exe))
            self.assertNotIn('shell', process.call_args.kwargs)

    def test_csgo_without_matching_manifest_is_not_launched_as_cs2(self):
        (self.steamapps / 'appmanifest_4465480.acf').unlink()
        with self.assertRaisesRegex(RuntimeError, 'recognized Steam install'):
            launch.plan(self.exe)

    def test_control_characters_are_rejected(self):
        with self.assertRaises(ValueError):
            launch.plan(self.exe, args='-console\n-other')

if __name__ == '__main__':
    unittest.main()
