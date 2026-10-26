# Bundle only the explicit tokenizer assets staged by our build script.
from PyInstaller.utils.hooks import collect_data_files
datas = collect_data_files('nltk')
hiddenimports = ['nltk.chunk.named_entity']
