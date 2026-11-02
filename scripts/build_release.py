"""Build a clean, offline Windows addon ZIP using the development virtualenv."""
import hashlib
import argparse
from importlib import metadata
import json
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'companion'), str(ROOT / 'scripts')]
from registry import Registry, VOICES
from service import DEFAULTS
from import_npc_catalog import import_catalog
from release_sources import collect_sources
from release_overrides import export_overrides, apply_overrides

REVISION = 'f3ff3571791e39611d31c381e3a41a3af07b4987'


def distributable(relative):
    """Only build artifacts; never include runtime settings, backups or caches."""
    parts = relative.parts
    if parts[:2] in (('source', 'maintainer'), ('source', 'voice_studio')):
        return False
    if parts[0] == 'companion':
        return len(parts) > 1 and (parts[1] == '_internal' or relative.as_posix() in (
            'companion/XISpeaks-Companion.exe', 'companion/config.example.json'))
    return parts[0] in ('source', 'licenses') or relative.as_posix() in (
        'XISpeaks.lua', 'voice_ui.lua', 'README.txt', 'START-XISpeaks.cmd', 'LICENSE')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--registry', type=Path, help='Read corrections from this NPC database (default: project npcs.sqlite3)')
    parser.add_argument('--catalog-only', action='store_true', help='Omit saved NPC corrections')
    parser.add_argument('--curated', action='store_true', help='Use tracked release_npc_overrides.json, ignoring local databases')
    parser.add_argument('--output', type=Path, default=ROOT / 'dist/XISpeaks-windows-x64.zip', help='Destination ZIP')
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--freeze-only', action='store_true', help='Build the executable without assembling the release ZIP')
    mode.add_argument('--package-only', action='store_true', help='Assemble an already-frozen build; rebuild first if companion code changed')
    args = parser.parse_args()
    if args.curated and (args.registry or args.catalog_only):
        parser.error('--curated cannot be combined with --registry or --catalog-only')
    from huggingface_hub import hf_hub_download
    import nltk
    assets = ROOT / 'build/assets'
    assets.mkdir(parents=True, exist_ok=True)
    nltk.download('punkt_tab', download_dir=str(assets / 'nltk_data'), raise_on_error=True, quiet=True)
    hub = assets / 'models/hub/models--hexgrad--Kokoro-82M'
    snapshot = hub / 'snapshots' / REVISION
    files = ['config.json', 'kokoro-v1_0.pth', 'README.md'] + [f'voices/{voice}.pt' for voice in VOICES]
    for name in files:
        source = Path(hf_hub_download('hexgrad/Kokoro-82M', name, revision=REVISION))
        target = snapshot / name
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists() or target.stat().st_size != source.stat().st_size:
            shutil.copyfile(source, target)
    (hub / 'refs').mkdir(exist_ok=True)
    (hub / 'refs/main').write_text(REVISION)
    rubberband = ROOT / 'tools/rubberband-4.0.0-gpl-executable-windows'
    if not (rubberband / 'rubberband.exe').exists():
        raise RuntimeError('Run setup-rubberband.ps1 before building')
    shutil.copytree(rubberband, assets / 'tools' / rubberband.name, dirs_exist_ok=True)
    seed = assets / 'seed.sqlite3'
    if seed.exists():
        seed.unlink()
    registry = Registry(seed, dict(DEFAULTS, voices={}))
    try:
        print(import_catalog(registry, json.loads((ROOT / 'data/npc_associations.json').read_text(encoding='utf-8'))), flush=True)
        if not args.catalog_only:
            source = args.registry or ROOT / 'npcs.sqlite3'
            saved = ROOT / 'data/release_npc_overrides.json'
            if args.curated:
                count = apply_overrides(registry, json.loads(saved.read_text(encoding='utf-8')))
            elif source.is_file():
                overrides = export_overrides(source, registry)
                count = apply_overrides(registry, overrides)
                saved.write_text(json.dumps(overrides, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
            elif args.registry:
                raise FileNotFoundError(source)
            elif saved.is_file():
                count = apply_overrides(registry, json.loads(saved.read_text(encoding='utf-8')))
            else:
                count = 0
            print(f'Included {count} saved NPC corrections (no history or global settings)', flush=True)
        with registry.db:
            registry.db.execute("DELETE FROM metadata WHERE key='legacy_imported'")
    finally:
        registry.close()
    if not args.package_only:
        subprocess.run([sys.executable, '-m', 'PyInstaller', '--noconfirm', '--distpath', str(ROOT / 'dist/frozen'),
                        '--workpath', str(ROOT / 'build/pyinstaller'), str(ROOT / 'packaging/companion.spec')], check=True, cwd=ROOT)
    if args.freeze_only:
        return
    # Assets must be refreshed even when the executable itself is reused.
    shutil.copyfile(seed, ROOT / 'dist/frozen/companion/_internal/seed.sqlite3')
    release = ROOT / 'dist/XISpeaks'
    release.mkdir(parents=True, exist_ok=True)
    shutil.copytree(ROOT / 'dist/frozen/companion', release / 'companion', dirs_exist_ok=True)
    for name in ('XISpeaks.lua', 'voice_ui.lua'):
        shutil.copyfile(ROOT / 'addon/XISpeaks' / name, release / name)
    shutil.copyfile(ROOT / 'packaging/START-XISpeaks.cmd', release / 'START-XISpeaks.cmd')
    shutil.copyfile(ROOT / 'packaging/README.txt', release / 'README.txt')
    shutil.copyfile(ROOT / 'LICENSE', release / 'LICENSE')
    # Example only: no config or user database is shipped at the writable paths.
    (release / 'companion/config.example.json').write_text(json.dumps(dict(DEFAULTS, voices={}), indent=2))
    licenses = release / 'licenses'
    licenses.mkdir(exist_ok=True)
    shutil.copyfile(Path(sys.base_prefix) / 'LICENSE.txt', licenses / 'Python-LICENSE.txt')
    packages = []
    for dist in metadata.distributions():
        packages.append({'name': dist.metadata['Name'], 'version': dist.version, 'license': dist.metadata.get('License-Expression') or dist.metadata.get('License'), 'homepage': dist.metadata.get('Home-page'), 'project_urls': dist.metadata.get_all('Project-URL')})
        for entry in dist.files or []:
            if any(word in entry.name.lower() for word in ('license', 'copying', 'notice')):
                source = Path(dist.locate_file(entry))
                if source.is_file():
                    target = licenses / dist.metadata['Name'] / str(entry).replace('../', '').replace('..\\', '')
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(source, target)
    (licenses / 'packages.json').write_text(json.dumps(packages, indent=2), encoding='utf-8')
    shutil.copyfile(snapshot / 'README.md', licenses / 'Kokoro-model-card.md')
    shutil.copytree(ROOT / 'data', release / 'source/data', dirs_exist_ok=True)
    for directory in ('companion', 'addon', 'scripts', 'packaging', 'tests'):
        shutil.copytree(ROOT / directory, release / 'source' / directory, dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    for name in ('LICENSE', 'requirements.txt', 'setup.ps1', 'setup-rubberband.ps1', 'README.md', 'config.example.json', 'run.cmd', 'install-addon.ps1'):
        shutil.copyfile(ROOT / name, release / 'source' / name)
    collect_sources(ROOT / 'build/upstream-source')
    shutil.copytree(ROOT / 'build/upstream-source', release / 'source/upstream', dirs_exist_ok=True)
    # Explicit allowlist avoids accidentally distributing private settings or test WAVs.
    archive = args.output.resolve()
    archive.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as output:
        for path in sorted(release.rglob('*')):
            relative = path.relative_to(release)
            if path.is_file() and distributable(relative):
                output.write(path, str(Path('XISpeaks') / path.relative_to(release)))
    with archive.open('rb') as source:
        digest = hashlib.file_digest(source, 'sha256').hexdigest()
    archive.with_suffix('.zip.sha256').write_text(f'{digest}  {archive.name}\n')
    print(f'Release: {archive} ({archive.stat().st_size / 1024**2:.1f} MiB)', flush=True)


if __name__ == '__main__':
    main()
