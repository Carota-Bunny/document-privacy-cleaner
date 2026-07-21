# -*- mode: python ; coding: utf-8 -*-
# Copyright (C) 2026 Carota-Bunny
# SPDX-License-Identifier: AGPL-3.0-only

from pathlib import Path


ROOT = Path(SPECPATH)

a = Analysis(
    [str(ROOT / "main.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "pandas",
        "numpy",
        "pyarrow",
        "scipy",
        "torch",
        "matplotlib",
        "IPython",
        "notebook",
        "jupyter",
        "cv2",
        "sklearn",
    ],
    noarchive=False,
    optimize=1,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="文档隐私清理器",
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
    icon=[str(ROOT / "assets" / "app.ico")],
    version=str(ROOT / "version_info.txt"),
)
