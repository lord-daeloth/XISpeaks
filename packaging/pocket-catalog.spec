from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_submodules, copy_metadata
root=Path(SPECPATH).parent
datas=collect_data_files('pocket_tts')+collect_data_files('librosa')+copy_metadata('pocket-tts')
datas += [(str(root/'companion/pocket-public-18m.yaml'),'.')]
g=Analysis([str(root/'voice_editor/app.py')],pathex=[str(root/p) for p in ('voice_editor','companion','scripts','piper_trainer')],datas=datas,
    hiddenimports=collect_submodules('pocket_tts')+['librosa.effects'],excludes=['RealtimeTTS','piper','onnxruntime','pytest','matplotlib','IPython','tensorboard','transformers'])
gui=EXE(PYZ(g.pure),g.scripts,[],exclude_binaries=True,name='XISpeaks-Pocket-Catalog',console=False,upx=False)
coll=COLLECT(gui,g.binaries,g.datas,name='XISpeaks-Pocket-Catalog',upx=False)
