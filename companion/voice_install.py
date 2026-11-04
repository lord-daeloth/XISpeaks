"""Install the pinned English voice weights on first launch."""
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
from urllib.request import urlopen


def prepare_voices(root):
    folder = root / 'piper_voices'
    folder.mkdir(exist_ok=True)
    source = root / 'data'
    for file in (source / 'piper-model-info').iterdir():
        if not (folder / file.name).exists():
            shutil.copyfile(file, folder / file.name)
    for item in json.loads((source / 'piper-models.json').read_text()):
        target = folder / item['name']
        if target.is_file() and target.stat().st_size == item['size']:
            continue
        print('Downloading', target.name, flush=True)
        with tempfile.NamedTemporaryFile(dir=folder, delete=False) as temporary:
            name = Path(temporary.name)
        try:
            with urlopen(item['url'], timeout=120) as response, name.open('wb') as output:
                shutil.copyfileobj(response, output)
            with name.open('rb') as stream:
                if hashlib.file_digest(stream, 'sha256').hexdigest() != item['sha256']:
                    raise ValueError('Checksum mismatch for ' + target.name)
            name.replace(target)
        finally:
            name.unlink(missing_ok=True)
    catalog = folder / 'catalog.json'
    if not catalog.exists():
        shutil.copyfile(source / 'piper-catalog.json', catalog)


if __name__ == '__main__':
    prepare_voices(Path(__file__).resolve().parents[1])
