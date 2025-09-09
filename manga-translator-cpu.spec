# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_data_files

# Collect data files dynamically instead of using a hardcoded path
py3langid_datas = collect_data_files('py3langid')
unidic_datas = collect_data_files('unidic_lite')

a = Analysis(
    ['desktop-ui/main.py'],
    pathex=[],
    binaries=[],
    datas=py3langid_datas + unidic_datas,
    hiddenimports=['pydensecrf.eigen'],
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
    name='app',
    debug=True,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='manga-translator-cpu',
)