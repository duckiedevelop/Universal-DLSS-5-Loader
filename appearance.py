"""Settings supported by the bundled RenoDX v7 consumer. Preserve unrelated INI data."""
import json
import math
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent
SCHEMA = json.loads((ROOT / 'customization.json').read_text(encoding='utf-8'))
FIELDS = {f['key']: f for f in SCHEMA['fields']}
SECTION = 'RenoDX.DLSS5'

def defaults():
    return {key: field['default'] for key, field in FIELDS.items()}

def normalize(values):
    if not isinstance(values, dict):
        raise ValueError('Customization must be a settings object.')
    unknown = set(values) - FIELDS.keys()
    if unknown:
        raise ValueError('Unsupported customization: ' + ', '.join(sorted(unknown)))
    result = defaults()
    for key, value in values.items():
        field = FIELDS[key]
        if field['type'] == 'bool':
            if type(value) is not bool:
                raise ValueError(field['label'] + ' must be on or off.')
        else:
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise ValueError(field['label'] + ' must be a finite number.')
            if not field['min'] <= value <= field['max']:
                raise ValueError(f"{field['label']} must be between {field['min']} and {field['max']}.")
            if field['type'] == 'int':
                if value != int(value):
                    raise ValueError(field['label'] + ' must be a whole number.')
                value = int(value)
            else:
                value = float(value)
        result[key] = value
    return result

def read_text(path):
    if not path.exists():
        return ''
    data = path.read_bytes()
    if data.startswith(b'\xff\xfe') or data.startswith(b'\xfe\xff'):
        return data.decode('utf-16')
    try:
        return data.decode('utf-8-sig')
    except UnicodeDecodeError:
        return data.decode('mbcs')

def encode(text, original):
    if original.startswith(b'\xff\xfe'):
        return b'\xff\xfe' + text.encode('utf-16-le')
    if original.startswith(b'\xfe\xff'):
        return b'\xfe\xff' + text.encode('utf-16-be')
    if original.startswith(b'\xef\xbb\xbf'):
        return b'\xef\xbb\xbf' + text.encode('utf-8')
    try:
        original.decode('utf-8')
    except UnicodeDecodeError:
        return text.encode('mbcs')
    return text.encode('utf-8')

def section_values(text):
    values = {}
    in_section = False
    for line in text.splitlines():
        match = re.match(r'^\s*\[([^]]+)\]', line)
        if match:
            in_section = match.group(1).casefold() == SECTION.casefold()
        elif in_section and '=' in line and not line.lstrip().startswith((';', '#')):
            key, value = line.split('=', 1)
            values[key.strip()] = value.strip().split(';', 1)[0].strip()
    return values

def read(path):
    raw = section_values(read_text(path))
    result = defaults()
    notes = []
    for key, field in FIELDS.items():
        if key not in raw:
            continue
        try:
            if field['type'] == 'bool':
                if raw[key].lower() not in ('0', '1', 'false', 'true'):
                    raise ValueError()
                value = raw[key].lower() in ('1', 'true')
            else:
                value = float(raw[key])
            result[key] = normalize({key: value})[key]
        except ValueError:
            notes.append(key + ' is outside this menu\'s supported range; showing the menu default.')
    return result, notes

def render(text, settings):
    values = normalize(settings)
    # v7 reports schema 6. Stamp it so initial migration cannot replace the
    # selected pass/history values. Keep exposure/codec and unrelated keys intact.
    writes = {'ConfigVersion': '6', **{key: ('1' if value else '0') if isinstance(value, bool)
        else format(value, '.6g') for key, value in values.items()}}
    newline = '\r\n' if '\r\n' in text else '\n'
    lines = text.splitlines()
    result = []
    current = False
    found = False
    pending = dict(writes)
    for line in lines:
        header = re.match(r'^\s*\[([^]]+)\]', line)
        if header:
            if current:
                result.extend(key + '=' + value for key, value in pending.items())
                pending.clear()
            current = header.group(1).casefold() == SECTION.casefold()
            found |= current
        if current and '=' in line and not line.lstrip().startswith((';', '#')):
            key = line.split('=', 1)[0].strip()
            canonical = next((k for k in writes if k.casefold() == key.casefold()), None)
            if canonical:
                # Suppress duplicate managed keys instead of leaving ambiguous values.
                if canonical in pending:
                    result.append(canonical + '=' + pending.pop(canonical))
                continue
        result.append(line)
    if not found:
        if result and result[-1]:
            result.append('')
        result.append('[' + SECTION + ']')
    result.extend(key + '=' + value for key, value in pending.items())
    return newline.join(result) + newline
