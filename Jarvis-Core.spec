# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['src/gui/main_window.py'],
    pathex=[],
    binaries=[],
    datas=[('config/settings.json', 'config'), ('config/app_paths.yaml', 'config'), ('config/prompts/system_prompt.txt', 'config/prompts'), ('.env', '.env')],
    hiddenimports=[],
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
    a.binaries,
    a.datas,
    [],
    name='Jarvis-Core',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['/home/ubuntu/jarvis-core/jarvis_icon.ico'],
)
