"""Manual GPU check: prove selected controls reach the bundled consumer. No game touched."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import appearance
import backend

folder = backend.ROOT / 'diagnostics/host64'
config = folder / 'ReShade.ini'
original = config.read_bytes()
try:
    values = appearance.normalize({'NRIntensity': 0.55, 'NRColorStrength': 0.7, 'NRLocalTone': 0.8,
        'NRLocalStructure': 0.65, 'NRSkinStructure': 0.2, 'NRAutoMask': True, 'NRStyle': 1,
        'NRResolutionScale': 0.75, 'NRPasses': 2, 'NRChainedHistory': False})
    config.write_text(appearance.render(appearance.read_text(config), values), encoding='utf-8', newline='')
    print(backend.gpu_test({})['message'], flush=True)
    log = (folder / 'ReShade.log').read_text(errors='replace')
    for marker in ['intensity=0.550000', 'color_strength=0.700000', 'style=1', 'local_tone=0.8',
                   'structure=0.65', 'skin=0.2', 'auto_mask=1', 'passes=2', 'resolution_scale=0.75', 'chained_history=0']:
        if marker not in log:
            raise RuntimeError('Control not confirmed in the fresh consumer log: ' + marker)
    print('Verified strength, color, tone, detail, skin, mask, Natural style, resolution, passes and history.', flush=True)
    evidence = backend.ROOT / 'docs/customization-gpu-evidence.txt'
    relevant = [line for line in log.splitlines() if any(k in line for k in
        ['active settings:', 'pass 1 model:', 'effective settings:', 'feature 18 created', 'evaluation succeeded'])]
    evidence.write_text('\n'.join(relevant) + '\n', encoding='utf-8')
    # Verify the Cinematic option independently with default single-pass work.
    values = appearance.normalize({'NRStyle': 2, 'NRIntensity': 0.6})
    config.write_text(appearance.render(appearance.read_text(config), values), encoding='utf-8', newline='')
    print(backend.gpu_test({})['message'], flush=True)
    log = (folder / 'ReShade.log').read_text(errors='replace')
    if 'style=2' not in log:
        raise RuntimeError('Cinematic style was not confirmed by the consumer.')
    with evidence.open('a', encoding='utf-8') as f:
        f.write('\nCinematic style test:\n')
        f.write('\n'.join(line for line in log.splitlines() if any(k in line for k in
            ['active settings:', 'pass 1 model:', 'effective settings:', 'evaluation succeeded'])) + '\n')
    print('Verified Cinematic style on this runtime/driver.', flush=True)
finally:
    config.write_bytes(original)
