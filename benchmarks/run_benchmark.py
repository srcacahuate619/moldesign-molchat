"""Run existing regression tests as a reproducible, keyless harness benchmark.

No model or scientific engine is contacted. Pytest assertions remain the oracle;
this script only selects, repeats, aggregates and exports their evidence.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import re
import statistics
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
HERE = Path(__file__).resolve().parent


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sanitize(text: str) -> str:
    text = text.replace(str(ROOT), '[repository]').replace(ROOT.as_posix(), '[repository]')
    text = text.replace(str(ROOT).replace('\\', '\\\\'), '[repository]')
    text = text.replace(str(Path.home()), '[home]').replace(Path.home().as_posix(), '[home]')
    return re.sub(r'[A-Za-z]:[\\/][^\s<>"\']+', '[local-path]', text).replace(platform.node(), '[host]')


def environment() -> dict:
    def git(*args):
        return subprocess.check_output(['git', *args], cwd=ROOT, text=True).strip()
    versions = {}
    for name in ('pytest', 'httpx', 'rdkit', 'reportlab', 'pypdf', 'starlette'):
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            versions[name] = None
    files = sorted({*ROOT.glob('src/**/*.py'), *ROOT.glob('tests/**/*.py'),
                    *HERE.glob('*.py'), *HERE.glob('*.json')})
    # Results themselves are not inputs; the inventory makes an uncommitted run attributable.
    inputs = {p.relative_to(ROOT).as_posix(): sha(p) for p in files
              if p.name not in {'results.json'} and 'published' not in p.parts}
    return {'git_commit': git('rev-parse', 'HEAD'),
            'tracked_worktree_dirty': bool(git('status', '--porcelain', '--untracked-files=no')),
            'python': platform.python_version(), 'platform': platform.system(),
            'architecture': platform.machine(), 'packages': versions,
            'input_sha256': hashlib.sha256(json.dumps(inputs, sort_keys=True).encode()).hexdigest(),
            'inputs': inputs}


def run(output: Path, repetitions: int) -> int:
    config = json.loads((HERE / 'scenarios.json').read_text(encoding='utf-8'))
    groups = config['scenarios']
    selectors = [selector for group in groups for selector in group['tests']]
    if len(selectors) != len(set(selectors)):
        raise ValueError('Duplicate test selectors would inflate the benchmark.')
    output.mkdir(parents=True, exist_ok=True)
    report = {'schema': 'molchat.benchmark/1', 'evidence_type': 'synthetic_regression',
              'started_at_utc': __import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat(),
              'environment': environment(), 'repetitions': repetitions,
              'scenario_file_sha256': sha(HERE / 'scenarios.json'), 'runs': [], 'scenarios': []}
    env = dict(os.environ)
    env['PYTHONPATH'] = os.pathsep.join([str(ROOT / 'src'), str(ROOT), env.get('PYTHONPATH', '')])
    any_failure = False
    for repetition in range(1, repetitions + 1):
        xml = output / f'pytest-{repetition}.xml'
        temp = ROOT / 'reports' / 'benchmark-tmp' / f'run-{time.time_ns()}'
        temp.parent.mkdir(parents=True, exist_ok=True)
        cmd = [sys.executable, '-m', 'pytest', '-q', *selectors,
               f'--basetemp={temp}', f'--junitxml={xml}', '-o', 'junit_family=xunit2']
        start = time.perf_counter()
        completed = subprocess.run(cmd, cwd=ROOT, env=env, capture_output=True, text=True, encoding='utf-8', errors='replace')
        elapsed = time.perf_counter() - start
        # Test output may include machine paths. Publish a path-neutral transcript.
        transcript = completed.stdout + completed.stderr
        transcript = sanitize(transcript)
        (output / f'pytest-{repetition}.txt').write_text(transcript, encoding='utf-8')
        checks = []
        if xml.exists():
            for case in ET.parse(xml).iter('testcase'):
                parts = case.get('classname', '').split('.')
                file_index = next((i for i, part in enumerate(parts) if part.startswith('test_')), len(parts) - 1)
                source = '/'.join(parts[:file_index + 1]) + '.py'
                if file_index + 1 < len(parts):
                    source += '::' + '::'.join(parts[file_index + 1:])
                status = ('failed' if case.find('failure') is not None or case.find('error') is not None
                          else 'skipped' if case.find('skipped') is not None else 'passed')
                checks.append({'test': source + '::' + case.get('name', ''), 'status': status,
                               'duration_s': float(case.get('time', 0))})
            # Remove host-specific XML attributes/text, retain assertions and durations.
            raw = sanitize(xml.read_text(encoding='utf-8'))
            xml.write_text(raw, encoding='utf-8')
        report['runs'].append({'repetition': repetition, 'exit_code': completed.returncode,
                               'wall_s': round(elapsed, 6), 'checks': checks})
        any_failure |= completed.returncode != 0
        print(f'Synthetic repetition {repetition}: {sum(c["status"] == "passed" for c in checks)}/{len(checks)} passed; {elapsed:.2f}s', flush=True)
        # Preserve a real generated synthetic ZIP, rather than manufacturing a demo.
        for archive in temp.glob('**/entrega.zip'):
            if 'wrong_digest' in str(archive):
                destination = output / 'synthetic-delivery.zip'
                destination.write_bytes(archive.read_bytes())
                break
    for group in groups:
        samples = []
        counts = []
        for result in report['runs']:
            matching = [c for c in result['checks'] if any(
                c['test'] == s or c['test'].startswith(s + '[') or
                ('::' not in s and c['test'].startswith(s + '::')) for s in group['tests'])]
            counts.append({status: sum(c['status'] == status for c in matching)
                           for status in ('passed', 'failed', 'skipped')})
            samples.append(sum(c['duration_s'] for c in matching))
        complete = all(sum(c.values()) > 0 for c in counts)
        report['scenarios'].append({**group, 'collected': complete, 'counts_by_repetition': counts,
            'passed': complete and all(c['failed'] == c['skipped'] == 0 for c in counts),
            'test_duration_s': {'median': round(statistics.median(samples), 6),
                                'min': round(min(samples), 6), 'max': round(max(samples), 6)}})
    report['summary'] = {'scenarios_passed': sum(s['passed'] for s in report['scenarios']),
                         'scenarios_total': len(groups),
                         'checks_per_repetition': [{s: sum(c['status'] == s for c in r['checks'])
                                                    for s in ('passed', 'failed', 'skipped')} for r in report['runs']]}
    any_failure |= not all(s['passed'] for s in report['scenarios'])
    delivery = output / 'synthetic-delivery.zip'
    if delivery.exists():
        from molchat_agent.workflows.deliverable import verify_deliverable
        errors = verify_deliverable(delivery.read_bytes())
        report['delivery'] = {'file': delivery.name, 'sha256': sha(delivery), 'verification_errors': errors,
                              'warning': 'Synthetic scores and placeholder video; not a scientific experiment.'}
        any_failure |= bool(errors)
    (output / 'results.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    with (output / 'scenarios.csv').open('w', newline='', encoding='utf-8') as handle:
        writer = csv.writer(handle)
        writer.writerow(['scenario', 'difficulty', 'metric', 'passed', 'median_test_s', 'min_test_s', 'max_test_s'])
        for s in report['scenarios']:
            writer.writerow([s['id'], s['difficulty'], s['metric'], s['passed'],
                             *[s['test_duration_s'][k] for k in ('median', 'min', 'max')]])
    return int(any_failure)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'reports' / 'benchmark-run')
    parser.add_argument('--repetitions', type=int, default=3)
    args = parser.parse_args()
    if not 1 <= args.repetitions <= 20:
        parser.error('--repetitions must be 1..20')
    sys.path.insert(0, str(ROOT / 'src'))
    raise SystemExit(run(args.output.resolve(), args.repetitions))
