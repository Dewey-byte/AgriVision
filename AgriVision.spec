# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_submodules
from PyInstaller.utils.hooks import collect_all

datas = [('models/banana-cls.pt', 'models'), ('models/best.pt', 'models'), ('models/yolov8n_banana.pt', 'models'), ('models/yolov9s_banana.pt', 'models'), ('models/yolov9t_banana.pt', 'models'), ('yolov8n.pt', '.'), ('ui/styles', 'ui/styles'), ('web/frontend/dist', 'web/frontend/dist'), ('web/api/data', 'web/api/data')]
binaries = []
hiddenimports = ['multipart']
hiddenimports += collect_submodules('web')
hiddenimports += collect_submodules('uvicorn')
tmp_ret = collect_all('ultralytics')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['pkg_resources'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='AgriVision',
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
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='AgriVision',
)
