import importlib.util
from pathlib import Path
import json
import shutil
import tempfile
import unittest
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location('backend', ROOT / 'backend.py')
b = importlib.util.module_from_spec(spec)
spec.loader.exec_module(b)

class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='dlss5-setup-test-')
        self.folder = Path(self.temp.name) / 'game with spaces \u6e2c\u8a66'
        self.folder.mkdir()
        self.exe = self.folder / 'Game.exe'
        shutil.copy2(ROOT / 'build/Release/LoadTestHost.exe', self.exe)
        self.job = {'game': str(self.exe), 'api': 'DirectX 11 / 12'}

    def tearDown(self):
        self.temp.cleanup()

    def test_install_check_restore_preserves_originals_and_edits(self):
        original = self.folder / 'ReShade.ini'
        original.write_bytes(b'original settings\r\n')
        unrelated = self.folder / 'my-save.txt'
        unrelated.write_bytes(b'untouched')
        self.assertTrue(b.install(self.job)['ok'])
        self.assertTrue((self.folder / 'dlss5-feed.addon64').is_file())
        self.assertFalse(b.check(self.job)['active'])
        self.assertTrue(b.install(self.job)['ok'])
        original.write_bytes(b'my changed installed settings')
        self.assertTrue(b.restore(self.job)['ok'])
        self.assertEqual(original.read_bytes(), b'original settings\r\n')
        self.assertFalse((self.folder / 'dxgi.dll').exists())
        self.assertEqual(unrelated.read_bytes(), b'untouched')
        histories = list(self.folder.glob('.dlss5-setup-history-*'))
        self.assertEqual(len(histories), 1)
        self.assertEqual((histories[0] / 'changed-after-install/ReShade.ini').read_bytes(), b'my changed installed settings')

    def test_foreign_proxy_refused_without_writes(self):
        p = self.folder / 'dxgi.dll'
        p.write_bytes(b'an existing mod loader')
        with self.assertRaisesRegex(RuntimeError, 'existing dxgi'):
            b.install(self.job)
        self.assertEqual(p.read_bytes(), b'an existing mod loader')
        self.assertFalse((self.folder / b.STATE).exists())

    def test_manifest_traversal_refused(self):
        b.install(self.job)
        path = self.folder / b.STATE / 'install.json'
        data = json.loads(path.read_text(encoding='utf-8'))
        data['files']['../unowned.txt'] = {'installed_sha256': '0', 'original_sha256': None}
        b.write_json(path, data)
        with self.assertRaisesRegex(RuntimeError, 'unexpected files'):
            b.restore(self.job)
        self.assertTrue((self.folder / 'dxgi.dll').exists())

    def test_damaged_backup_stops_restore(self):
        original = self.folder / 'ReShade.ini'
        original.write_bytes(b'original')
        b.install(self.job)
        (self.folder / b.STATE / 'originals/ReShade.ini').write_bytes(b'damaged')
        with self.assertRaisesRegex(RuntimeError, 'Backup is missing or changed'):
            b.restore(self.job)
        self.assertTrue((self.folder / 'dxgi.dll').exists())

    def test_running_game_blocks_install(self):
        import subprocess
        p = subprocess.Popen([str(self.exe)], creationflags=subprocess.CREATE_NO_WINDOW)
        try:
            with self.assertRaisesRegex(RuntimeError, 'Close the selected game'):
                b.install(self.job)
        finally:
            p.terminate()
            p.wait(timeout=5)

    def test_partial_install_rolls_back(self):
        from unittest.mock import patch
        original = self.folder / 'ReShade.ini'
        original.write_bytes(b'original')
        replace = b.os.replace
        def fail_once(source, destination):
            if Path(destination).name == 'nvngx_dlss.dll':
                raise OSError('simulated write failure')
            return replace(source, destination)
        with patch.object(b.os, 'replace', side_effect=fail_once):
            with self.assertRaisesRegex(OSError, 'simulated write failure'):
                b.install(self.job)
        self.assertEqual(original.read_bytes(), b'original')
        self.assertFalse((self.folder / 'dxgi.dll').exists())
        self.assertFalse((self.folder / b.STATE / 'install.json').exists())

    def test_x86_payload_and_helper_match(self):
        files = b.files_for('x86', 'DirectX 11 / 12')
        self.assertIn('dlss5-feed.addon32', files)
        self.assertIn('host64/dlss5-feed-host64.exe', files)
        self.assertNotIn('nvngx_dlssnr.dll', files)
        self.assertNotIn('dlss5-feed.addon64', files)

    def test_appearance_written_on_install_and_reloaded_without_losing_unrelated_keys(self):
        import appearance
        settings = appearance.normalize({'NRIntensity': 0.55, 'NRPasses': 2, 'NRResolutionScale': 0.75})
        b.install({**self.job, 'settings': settings})
        path = self.folder / 'ReShade.ini'
        with path.open('a') as f:
            f.write('\n[MY_OTHER_MOD]\nSomething=keep me\n')
        b.apply_settings({**self.job, 'settings': {**settings, 'NRIntensity': 0.4, 'NRAutoMask': True}})
        loaded = b.load_settings(self.job)['settings']
        self.assertEqual(loaded['NRIntensity'], 0.4)
        self.assertEqual(loaded['NRPasses'], 2)
        self.assertEqual(loaded['NRResolutionScale'], 0.75)
        self.assertTrue(loaded['NRAutoMask'])
        self.assertIn('Something=keep me', path.read_text())
        self.assertEqual(b.scan(self.job)['settings'], loaded)
        self.assertTrue(list((self.folder / b.STATE / 'settings-history').glob('*.ini')))

    def test_invalid_appearance_does_not_modify_installed_config(self):
        b.install(self.job)
        path = self.folder / 'ReShade.ini'
        original = path.read_bytes()
        for settings in [{'NRResolutionScale': 75}, {'NRPasses': 1.5}, {'NeuralUplift': 2},
                         {'NRIntensity': float('nan')}, {'UnsupportedMagicToggle': True}]:
            with self.assertRaises(ValueError):
                b.apply_settings({**self.job, 'settings': settings})
            self.assertEqual(original, path.read_bytes())

    def test_x86_settings_write_to_helper_ini_only(self):
        import appearance
        state = {'arch': 'x86'}
        helper = self.folder / 'host64/ReShade.ini'
        helper.parent.mkdir()
        helper.write_text('[GENERAL]\nPreserve=yes\n')
        root_config = self.folder / 'ReShade.ini'
        root_config.write_text('root untouched')
        b.write_appearance(self.folder, state, appearance.normalize({'NRIntensity': 0.7}))
        self.assertEqual(appearance.read(helper)[0]['NRIntensity'], 0.7)
        self.assertIn('Preserve=yes', helper.read_text())
        self.assertEqual(root_config.read_text(), 'root untouched')

    def test_ini_roundtrip_preserves_other_sections_comments_and_managed_key_order(self):
        import appearance
        text = '[GENERAL]\r\nKey=unchanged\r\n[RenoDX.DLSS5]\r\n; my comment\r\nNRIntensity=1\r\nNRIntensity=2\r\nPrivateKey=keep\r\n[INPUT]\r\nKeyOverlay=36\r\n'
        rendered = appearance.render(text, {'NRIntensity': 0.45})
        self.assertEqual(rendered.count('NRIntensity='), 1)
        self.assertIn('; my comment\r\n', rendered)
        self.assertIn('PrivateKey=keep', rendered)
        self.assertIn('KeyOverlay=36', rendered)
        self.assertEqual(appearance.section_values(rendered)['NRIntensity'], '0.45')
        self.assertNotIn('\n', rendered.replace('\r\n', ''))

    def test_d3d9_install_restore_preserves_original_configuration(self):
        config = self.folder / 'dgVoodoo.conf'
        config.write_bytes(b'my original bridge settings')
        self.assertTrue(b.install({**self.job, 'api': 'D3D9'})['ok'])
        self.assertIn('d3d11_fl11_0', config.read_text())
        self.assertIn('DepthCopyBeforeClears=1', (self.folder / 'ReShade.ini').read_text())
        self.assertTrue((self.folder / 'd3d9.dll').is_file())
        self.assertTrue(b.check(self.job)['ok'])
        self.assertTrue(b.restore(self.job)['ok'])
        self.assertEqual(config.read_bytes(), b'my original bridge settings')
        self.assertFalse((self.folder / 'd3d9.dll').exists())
        self.assertFalse((self.folder / 'dxgi.dll').exists())

    def test_d3d9_foreign_wrapper_refused(self):
        wrapper = self.folder / 'd3d9.dll'
        wrapper.write_bytes(b'other wrapper')
        with self.assertRaisesRegex(RuntimeError, 'existing d3d9'):
            b.install({**self.job, 'api': 'D3D9'})
        self.assertFalse((self.folder / b.STATE).exists())
        self.assertEqual(wrapper.read_bytes(), b'other wrapper')

    def test_d3d9_graphics_preference_preserves_prior_options_and_restores(self):
        import graphics_adapter as gpu
        seed = gpu.prepare_preferences([self.exe])
        seed[0]['installed'] = 'GpuPreference=1;VRROptimizeEnable=0;'
        gpu.apply_preferences(seed)
        try:
            b.install({**self.job, 'api': 'D3D9'})
            self.assertEqual(gpu.preference(self.exe), 'GpuPreference=2;VRROptimizeEnable=0;')
            b.restore(self.job)
            self.assertEqual(gpu.preference(self.exe), seed[0]['installed'])
        finally:
            gpu.restore_preferences(seed)

    def test_d3d9_write_failure_restores_graphics_preference(self):
        from unittest.mock import patch
        import graphics_adapter as gpu
        previous = gpu.preference(self.exe)
        replace = b.os.replace
        def fail_once(source, destination):
            if Path(destination).name == 'd3d9.dll':
                raise OSError('simulated wrapper write failure')
            return replace(source, destination)
        with patch.object(b.os, 'replace', side_effect=fail_once):
            with self.assertRaisesRegex(OSError, 'simulated wrapper write failure'):
                b.install({**self.job, 'api': 'D3D9'})
        self.assertEqual(gpu.preference(self.exe), previous)
        self.assertFalse((self.folder / 'dxgi.dll').exists())
        self.assertFalse((self.folder / 'd3d9.dll').exists())

    def test_foreign_graphics_preference_journal_refused(self):
        b.install({**self.job, 'api': 'D3D9'})
        journal = self.folder / b.STATE / 'install.json'
        data = json.loads(journal.read_text(encoding='utf-8'))
        records = data['gpu_preferences'].copy()
        data['gpu_preferences'][0] = {**records[0], 'name': str(self.folder.parent / 'unowned.exe')}
        b.write_json(journal, data)
        try:
            with self.assertRaisesRegex(RuntimeError, 'graphics preference recovery journal'):
                b.restore(self.job)
            self.assertTrue((self.folder / 'd3d9.dll').is_file())
        finally:
            data['gpu_preferences'] = records
            b.write_json(journal, data)
            b.restore(self.job)

    def source_fixture(self):
        self.exe = self.exe.rename(self.folder / 'csgo.exe')
        self.job['game'] = str(self.exe)
        (self.folder / 'bin').mkdir()

    def test_source_repair_preserves_settings_and_prevents_wrong_route(self):
        import appearance
        from unittest.mock import patch
        self.source_fixture()
        b.install({**self.job, 'settings': {'NRIntensity': .6}})
        (self.folder / 'bin/shaderapidx9.dll').write_bytes(b'graphics module marker')
        self.assertTrue(b.scan(self.job)['repair_d3d9'])
        with patch.object(b.game_launch, 'execute') as execute:
            with self.assertRaisesRegex(RuntimeError, 'incompatible graphics setup'):
                b.launch(self.job)
            execute.assert_not_called()
        self.assertTrue(b.repair_d3d9(self.job)['ok'])
        self.assertEqual(b.read_install(self.folder)['api'], 'D3D9')
        self.assertFalse(b.scan(self.job)['repair_d3d9'])
        self.assertEqual(b.load_settings(self.job)['settings']['NRIntensity'], .6)
        self.assertTrue((self.folder / 'd3d9.dll').exists())
        b.restore(self.job)
        self.assertFalse((self.folder / 'd3d9.dll').exists())

    def test_source_wrong_api_refused_before_game_writes(self):
        self.source_fixture()
        (self.folder / 'bin/shaderapidx9.dll').write_bytes(b'graphics module marker')
        self.assertEqual(b.scan(self.job)['hint'], 'D3D9')
        with self.assertRaisesRegex(RuntimeError, 'uses DirectX 9'):
            b.install(self.job)
        self.assertFalse((self.folder / b.STATE).exists())

    def test_repair_invalid_bundle_keeps_previous_setup(self):
        from unittest.mock import patch
        self.source_fixture()
        b.install(self.job)
        (self.folder / 'bin/shaderapidx9.dll').write_bytes(b'graphics module marker')
        original = (self.folder / 'dxgi.dll').read_bytes()
        with patch.object(b, 'files_for', side_effect=RuntimeError('Invalid bridge bundle')):
            with self.assertRaisesRegex(RuntimeError, 'Invalid bridge bundle'):
                b.repair_d3d9(self.job)
        self.assertEqual((self.folder / 'dxgi.dll').read_bytes(), original)
        self.assertEqual(b.read_install(self.folder)['api'], 'DirectX 11 / 12')

    def test_x86_d3d9_uses_matching_wrapper_and_helper(self):
        from unittest.mock import patch
        with patch.object(b, 'target', return_value=(self.exe, 'x86', 'D3D9')):
            b.install({**self.job, 'api': 'D3D9', 'settings': {'NRIntensity': .7}})
            self.assertEqual(b.read_install(self.folder)['arch'], 'x86')
            self.assertEqual(b.load_settings(self.job)['settings']['NRIntensity'], .7)
            self.assertTrue((self.folder / 'dlss5-feed.addon32').exists())
            self.assertFalse((self.folder / 'nvngx_dlssnr.dll').exists())
            b.restore(self.job)
        files = b.files_for('x86', 'D3D9')
        self.assertEqual(files['d3d9.dll'][0], b.ROOT / 'payload/d3d9/x86/d3d9.dll')
        self.assertEqual(files['host64/dlss5-feed-host64.exe'][0], b.ROOT / 'payload/x86/host64/dlss5-feed-host64.exe')

    def test_utf16_settings_preserve_encoding_and_unrelated_values(self):
        import appearance
        config = self.folder / 'host64/ReShade.ini'
        config.parent.mkdir()
        original = '[GENERAL]\r\nOther=\u6e2c\u8a66\r\n[RenoDX.DLSS5]\r\nNRIntensity=1\r\n'
        config.write_bytes(original.encode('utf-16'))
        b.write_appearance(self.folder, {'arch': 'x86'}, appearance.normalize({'NRIntensity': 0.8}))
        self.assertTrue(config.read_bytes().startswith(b'\xff\xfe'))
        self.assertIn('Other=\u6e2c\u8a66', config.read_bytes().decode('utf-16'))
        self.assertEqual(appearance.read(config)[0]['NRIntensity'], 0.8)

if __name__ == '__main__':
    unittest.main()
