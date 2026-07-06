# PyInstaller spec file.
# Build on your own Windows machine with:  pyinstaller build.spec
# Output .exe will appear in dist/PersonalAssistant/

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[('.env', '.')],
    hiddenimports=[
        'faster_whisper',
        'openwakeword',
        'pystray._win32',
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    cipher=block_cipher,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='PersonalAssistant',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,   # no terminal window; set True temporarily if debugging
    icon=None,       # point this at a .ico file if you make a custom icon
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    name='PersonalAssistant',
)
