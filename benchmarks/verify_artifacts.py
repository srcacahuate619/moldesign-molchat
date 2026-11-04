"""Verify published evidence bytes, reference inputs, and every delivery ZIP."""
from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from molchat_agent.workflows.deliverable import verify_deliverable


def main():
    published = Path(__file__).parent / 'published'
    manifest = json.loads((published / 'MANIFEST.json').read_text(encoding='utf-8'))
    errors = []
    for entry in manifest['files']:
        path = (published / entry['path']).resolve()
        if not path.is_relative_to(published.resolve()) or not path.is_file():
            errors.append(entry['path'] + ': missing or unsafe path')
            continue
        blob = path.read_bytes()
        if len(blob) != entry['bytes'] or hashlib.sha256(blob).hexdigest() != entry['sha256']:
            errors.append(entry['path'] + ': artifact hash mismatch')
        if path.suffix == '.zip':
            errors.extend(entry['path'] + ': ' + error for error in verify_deliverable(blob))
            with zipfile.ZipFile(io.BytesIO(blob)) as archive:
                delivery = json.loads(archive.read('MANIFEST.json'))
                for piece in delivery['pieces']:
                    if piece['kind'] != 'preparation_package':
                        continue
                    raw = archive.read(piece['path'])
                    # Synthetic fixtures deliberately exercise opaque byte transport.
                    # Real capsule packages must also pass their own nested file hashes.
                    if 'capsule' not in entry['path'] and not entry['path'].startswith('release-check/'):
                        continue
                    with zipfile.ZipFile(io.BytesIO(raw)) as inner:
                        names = [name for name in inner.namelist() if name.endswith('/manifest.json')]
                        if len(names) != 1 or inner.testzip() is not None:
                            errors.append(entry['path'] + ': Preparation archive is invalid')
                            continue
                        nested = json.loads(inner.read(names[0]))
                        prefix = names[0].rsplit('/', 1)[0] + '/'
                        for item in nested['files']:
                            if item.get('estado') != 'REGISTRADO':
                                continue
                            member = prefix + item['path']
                            if member not in inner.namelist() or hashlib.sha256(inner.read(member)).hexdigest() != item['sha256']:
                                errors.append(entry['path'] + ': Preparation component hash mismatch')
    # Reject stale published prompt references without re-scoring old results.
    live = json.loads((published / 'live/results.json').read_text(encoding='utf-8'))
    if hashlib.sha256((Path(__file__).parent / 'prompts.json').read_bytes()).hexdigest() != live['prompt_file_sha256']:
        errors.append('The scored prompt suite was modified after measurement.')
    indexed = {entry['path'] for entry in manifest['files']}
    actual = {p.relative_to(published).as_posix() for p in published.rglob('*')
              if p.is_file() and p != published / 'MANIFEST.json'}
    if indexed != actual:
        errors.append('Artifact manifest does not cover the exact published file set.')
    for error in errors:
        print(error)
    print(f"Evidence verification: {len(manifest['files'])} files, {len(errors)} error(s).")
    return bool(errors)


if __name__ == '__main__':
    raise SystemExit(main())
