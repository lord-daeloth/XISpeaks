from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_submodules, copy_metadata
root=Path(SPECPATH).parent
a=Analysis([str(root/'pocket_studio/app.py')],pathex=[str(root/'pocket_studio'),str(root/'companion')],
    datas=collect_data_files('pocket_tts')+copy_metadata('pocket-tts'),
    hiddenimports=collect_submodules('pocket_tts'),
    excludes=['RealtimeTTS','piper','onnxruntime','librosa','numba','sklearn','pytest','matplotlib','IPython','tensorboard','transformers'])
pyz=PYZ(a.pure)
exe=EXE(pyz,a.scripts,[],exclude_binaries=True,name='XISpeaks-Pocket-Studio',console=False,upx=False)
coll=COLLECT(exe,a.binaries,a.datas,name='XISpeaks-Pocket-Studio',upx=False)
