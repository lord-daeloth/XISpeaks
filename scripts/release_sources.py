"""Retain upstream source archives and checksums with the portable release."""
import hashlib
import json
from pathlib import Path
from urllib.request import urlopen


def collect_sources(destination):
    destination.mkdir(parents=True, exist_ok=True)
    urls = {
        'rubberband-4.0.0.tar.bz2': 'https://breakfastquay.com/files/releases/rubberband-4.0.0.tar.bz2',
        'espeakng-loader-0.2.4.zip': 'https://codeload.github.com/thewh1teagle/espeakng-loader/zip/146599e29be31bf17d99f0bcb7dbb2f92aef3d95',
        'espeak-ng-4870adfa.zip': 'https://codeload.github.com/espeak-ng/espeak-ng/zip/4870adfa25b1a32b4361592f1be8a40337c58d6c',
        'libsndfile-1.2.2.zip': 'https://codeload.github.com/libsndfile/libsndfile/zip/refs/tags/1.2.2',
    }
    with urlopen('https://pypi.org/pypi/phonemizer-fork/3.3.2/json') as response:
        info = json.load(response)
    for item in info['urls']:
        if item['packagetype'] == 'sdist':
            urls[item['filename']] = item['url']
    manifest = []
    for name, url in urls.items():
        target = destination / name
        if not target.exists():
            with urlopen(url, timeout=60) as response:
                data = response.read()
            target.write_bytes(data)
        with target.open('rb') as source:
            digest = hashlib.file_digest(source, 'sha256').hexdigest()
        manifest.append(dict(file=name, url=url, sha256=digest))
    (destination / 'manifest.json').write_text(json.dumps(manifest, indent=2))


if __name__ == '__main__':
    collect_sources(Path(__file__).resolve().parents[1] / 'build/upstream-source')
