# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for AegisHealth edge agent

import sys
from pathlib import Path

backend = Path(SPECPATH)
sys.path.insert(0, str(backend))

a = Analysis(
    ['agents/agent.py'],
    pathex=[str(backend)],
    binaries=[],
    datas=[],
    hiddenimports=[
        'torch',
        'grpc',
        'grpc._cython.cygrpc',
        'pandas',
        'numpy',
        'sklearn',
        'sklearn.utils._cython_blas',
        'sklearn.neighbors._typedefs',
        'sklearn.neighbors._quad_tree',
        'sklearn.tree._utils',
        'opacus',
        'app',
        'app.data',
        'app.data.preprocessor',
        'app.data.loader',
        'app.ml',
        'app.ml.lstm_model',
        'app.ml.trainer',
        'app.ml.dp_engine',
        'app.core',
        'app.core.config',
        'app.grpc',
        'app.grpc.federated_pb2',
        'app.grpc.federated_pb2_grpc',
        'agents',
        'agents.grpc_client',
        'agents.local_trainer',
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
    a.binaries,
    a.datas,
    [],
    name='aegishealth-agent',
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
)
