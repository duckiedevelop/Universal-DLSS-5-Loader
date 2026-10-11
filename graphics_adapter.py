"""Identify NVIDIA and reversibly set Windows graphics preferences per program."""
import ctypes
from ctypes import wintypes
import os
import uuid
import winreg

PREFERENCES = r'Software\Microsoft\DirectX\UserGpuPreferences'

def preference(path):
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, PREFERENCES) as key:
            value, kind = winreg.QueryValueEx(key, str(path))
            if kind != winreg.REG_SZ:
                raise RuntimeError('Unexpected Windows graphics preference type; no settings changed.')
            return value
    except FileNotFoundError:
        return None

def prepare_preferences(paths):
    result = []
    for path in paths:
        previous = preference(path)
        values = [s for s in (previous or '').split(';') if s and not s.startswith('GpuPreference=')]
        installed = ';'.join(['GpuPreference=2', *values]) + ';'
        result.append({'name': str(path), 'previous': previous, 'installed': installed})
    return result

def apply_preferences(records):
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, PREFERENCES) as key:
        for entry in records:
            winreg.SetValueEx(key, entry['name'], 0, winreg.REG_SZ, entry['installed'])

def restore_preferences(records):
    if not records:
        return
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, PREFERENCES) as key:
        for entry in records:
            try:
                current = preference(entry['name'])
            except RuntimeError:
                continue
            if current != entry['installed']:
                continue  # Retain subsequent user changes.
            if entry['previous'] is None:
                winreg.DeleteValue(key, entry['name'])
            else:
                winreg.SetValueEx(key, entry['name'], 0, winreg.REG_SZ, entry['previous'])

class LUID(ctypes.Structure):
    _fields_ = [('LowPart', wintypes.DWORD), ('HighPart', wintypes.LONG)]

class Desc(ctypes.Structure):
    _fields_ = [('Description', wintypes.WCHAR * 128), ('VendorId', wintypes.UINT),
                ('DeviceId', wintypes.UINT), ('SubSysId', wintypes.UINT), ('Revision', wintypes.UINT),
                ('DedicatedVideoMemory', ctypes.c_size_t), ('DedicatedSystemMemory', ctypes.c_size_t),
                ('SharedSystemMemory', ctypes.c_size_t), ('AdapterLuid', LUID), ('Flags', wintypes.UINT)]

def method(obj, index, result, *args):
    table = ctypes.cast(obj, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
    return ctypes.WINFUNCTYPE(result, ctypes.c_void_p, *args)(table[index])

def nvidia_name():
    dxgi = ctypes.WinDLL(os.path.join(os.environ['SystemRoot'], 'System32', 'dxgi.dll'))
    guid_type = ctypes.c_ubyte * 16
    iid = guid_type.from_buffer_copy(uuid.UUID('770aae78-f26f-4dba-a829-253c83d1b387').bytes_le)
    factory = ctypes.c_void_p()
    create = dxgi.CreateDXGIFactory1
    create.argtypes = [ctypes.POINTER(guid_type), ctypes.POINTER(ctypes.c_void_p)]
    create.restype = wintypes.LONG
    if create(ctypes.byref(iid), ctypes.byref(factory)) < 0:
        raise RuntimeError('Could not enumerate graphics adapters for the DirectX 9 bridge.')
    try:
        enum = method(factory, 12, wintypes.LONG, wintypes.UINT, ctypes.POINTER(ctypes.c_void_p))
        for index in range(32):
            adapter = ctypes.c_void_p()
            hr = enum(factory, index, ctypes.byref(adapter))
            if hr == -2005270526:  # DXGI_ERROR_NOT_FOUND
                break
            if hr < 0:
                raise RuntimeError('DXGI adapter enumeration failed.')
            try:
                desc = Desc()
                hr = method(adapter, 10, wintypes.LONG, ctypes.POINTER(Desc))(adapter, ctypes.byref(desc))
                if hr >= 0 and desc.VendorId == 0x10de and not desc.Flags & 2:
                    return desc.Description
            finally:
                method(adapter, 2, wintypes.ULONG)(adapter)
    finally:
        method(factory, 2, wintypes.ULONG)(factory)
    raise RuntimeError('No NVIDIA adapter found for the DirectX 9 DLSS bridge.')
