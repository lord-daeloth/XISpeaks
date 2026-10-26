from pathlib import Path
from PyInstaller.utils.hooks import collect_all, copy_metadata, collect_submodules, collect_data_files

root = Path(SPECPATH).parent
datas = [(str(root / 'build/assets'), '.')]
binaries = []
hiddenimports = ['RealtimeTTS.engines.kokoro_engine', 'RealtimeTTS.text_to_stream', 'nltk']
hiddenimports += collect_submodules('scipy._external')
for package in ('language_tags', 'csvw', 'segments', 'stream2sentence'):
    datas += collect_data_files(package)
for package in ('kokoro', 'misaki', 'en_core_web_sm', 'espeakng_loader', 'phonemizer', 'spacy', 'thinc', 'librosa'):
    data, binary, hidden = collect_all(package)
    datas += data
    binaries += binary
    hiddenimports += hidden
for package in ('kokoro', 'en_core_web_sm', 'transformers', 'RealtimeTTS'):
    datas += copy_metadata(package, recursive=True)

a = Analysis([str(root / 'companion/launcher.py')], pathex=[str(root / 'companion')],
    hookspath=[str(root / 'packaging/hooks')],
    binaries=binaries, datas=datas, hiddenimports=hiddenimports,
    excludes=['tensorflow', 'matplotlib', 'IPython', 'notebook', 'pytest', 'lupa'],
    module_collection_mode={'kokoro': 'pyz+py', 'transformers': 'pyz+py', 'librosa': 'pyz+py'})
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='XISpeaks-Companion',
    console=True, upx=False)
coll = COLLECT(exe, a.binaries, a.datas, name='companion', upx=False)
