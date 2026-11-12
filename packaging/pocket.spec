from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_submodules, copy_metadata
root=Path(SPECPATH).parent
datas=collect_data_files('pocket_tts')+collect_data_files('librosa')+copy_metadata('pocket-tts')
datas += [(str(root/'companion/pocket-public-18m.yaml'),'.')]
a=Analysis([str(root/'companion/windows_pocket.py')],pathex=[str(root/p) for p in ('companion','scripts','piper_trainer')],
    datas=datas,hiddenimports=collect_submodules('pocket_tts')+collect_submodules('scipy._external')+['librosa.effects'],
    excludes=['RealtimeTTS','piper','onnxruntime','pytest','matplotlib','IPython','tensorboard','transformers'])
pyz=PYZ(a.pure)
exe=EXE(pyz,a.scripts,[],exclude_binaries=True,name='XISpeaks-Pocket-Companion',console=True,upx=False)
g=Analysis([str(root/'voice_editor/app.py')],pathex=[str(root/p) for p in ('voice_editor','companion','scripts','piper_trainer')],datas=datas,
    hiddenimports=collect_submodules('pocket_tts')+['librosa.effects'],excludes=['RealtimeTTS','piper','onnxruntime','pytest','matplotlib','IPython','tensorboard','transformers'])
gui=EXE(PYZ(g.pure),g.scripts,[],exclude_binaries=True,name='XISpeaks-Pocket-Catalog',console=False,upx=False)
coll=COLLECT(exe,gui,a.binaries,a.datas,g.binaries,g.datas,name='XISpeaks-Pocket-Companion',upx=False)
