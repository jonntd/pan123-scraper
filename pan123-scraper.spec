# -*- mode: python ; coding: utf-8 -*-

import sys
import os

# 获取平台特定的可执行文件名
if sys.platform == "win32":
    exe_name = 'pan123-scraper-win'
elif sys.platform == "darwin":
    exe_name = 'pan123-scraper-mac'
else:
    exe_name = 'pan123-scraper-linux'

a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('templates', 'templates'),
        ('static', 'static'),
        ('config.json.example', '.'),
        ('README.md', '.'),
        ('LICENSE', '.'),
    ],
    hiddenimports=[
        'cryptography.fernet',
        'cryptography.hazmat.primitives.kdf.pbkdf2',
        'cryptography.hazmat.primitives.hashes',
        'cryptography.hazmat.backends.openssl',
        'flask',
        'requests',
        'sqlite3',
        'json',
        'logging',
        'threading',
        'queue',
        'time',
        'datetime',
        'hashlib',
        'base64',
        'os',
        'stat',
        'uuid',
        're',
        'urllib.parse',
        'concurrent.futures',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'matplotlib',
        'numpy',
        'pandas',
        'scipy',
        'PIL',
        'cv2',
    ],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=None)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name=exe_name,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # 可以添加图标文件路径
)
