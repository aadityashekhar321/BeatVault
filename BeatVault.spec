# -*- mode: python ; coding: utf-8 -*-
import os
import sys

block_cipher = None

project_dir = os.path.abspath(SPECPATH)

datas = [
    (os.path.join(project_dir, 'gui'), 'gui'),
    (os.path.join(project_dir, 'assets'), 'assets'),
]

hiddenimports = [
    'pywebview',
    'webview',
    'webview.platforms.winforms',
    'webview.platforms.edgechromium',
    'clr',
    'static_ffmpeg',
    'yt_dlp',
    'mutagen',
    'mutagen.easyid3',
    'mutagen.id3',
    'mutagen.mp3',
    'requests',
    'spotipy',
    'urllib.request',
    'concurrent.futures',
]

a = Analysis(
    [os.path.join(project_dir, 'main.py')],
    pathex=[project_dir],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter.test', 'unittest', 'email.test'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='BeatVault',
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
    icon=os.path.join(project_dir, 'assets', 'icon.ico'),
)
