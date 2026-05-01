# build.spec
block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        (
            'model_cache/all-MiniLM-L6-v2',
            'sentence_transformers_cache/all-MiniLM-L6-v2'
        ),
        (
            'web/dist',
            'web/dist'
        ),
    ],
    hiddenimports=[
        'pyaudiowpatch',
        'qdrant_client',
        'qdrant_client.http',
        'qdrant_client.http.models',
        'sentence_transformers',
        'deepgram',
        'langchain_groq',
        'google.generativeai',
        'pypdf',
        'nest_asyncio',
        'numpy',
        'fastapi',
        'uvicorn',
        'websockets',
        'PyQt6.QtWebEngineCore',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='AI_Meeting_Assistant',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,   # No console window in production. Set True temporarily to debug.
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='AI_Meeting_Assistant',
)
