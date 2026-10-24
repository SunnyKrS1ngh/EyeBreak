# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

SRC = Path('src/eyebreak')

a = Analysis(
    ['src/eyebreak/__main__.py'],
    pathex=['src'],
    binaries=[],
    datas=[
        # Bundle the alert sound
        (str(SRC / 'sounds' / 'faah.mp3'), 'eyebreak/sounds'),
    ],
    hiddenimports=[
        # pystray backend on Windows
        'pystray._win32',
        # Pillow image formats used by icon generation
        'PIL._imaging',
        'PIL.Image',
        'PIL.ImageDraw',
        # ctypes for winmm
        'ctypes',
        'ctypes.util',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='EyeBreak',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='NONE',
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='EyeBreak',
)
