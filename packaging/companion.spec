from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, collect_submodules
root = Path(SPECPATH).parent
paths = [str(root / name) for name in ('companion','piper_trainer','scripts')]
datas = collect_data_files('piper',includes=['espeak-ng-data/**']) + collect_data_files('librosa')
a = Analysis([str(root/'companion/windows_piper.py')], pathex=paths, datas=datas,
    binaries=collect_dynamic_libs('onnxruntime'), hiddenimports=['piper.espeakbridge','librosa.effects'] + collect_submodules('scipy._external'),
    excludes=['torch','RealtimeTTS','tkinter','pytest','matplotlib','piper.train'])
pyz = PYZ(a.pure)
exe = EXE(pyz,a.scripts,[],exclude_binaries=True,name='XISpeaks-Companion',console=True,upx=False)
coll = COLLECT(exe,a.binaries,a.datas,name='XISpeaks-Companion',upx=False)
