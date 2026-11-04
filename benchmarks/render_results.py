"""Render public tables and scientific plots from measured JSON, never hardcoded scores."""
from __future__ import annotations

import argparse
import csv
from collections import Counter
import hashlib
import json
from pathlib import Path
import statistics

HERE = Path(__file__).resolve().parent


def render(published: Path):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.ticker import MaxNLocator
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 11,
                         'axes.spines.top': False, 'axes.spines.right': False,
                         'axes.titleweight': 'bold', 'svg.fonttype': 'none',
                         'figure.facecolor': '#ffffff', 'axes.facecolor': '#ffffff'})
    figures = published / 'figures'
    figures.mkdir(parents=True, exist_ok=True)
    synthetic = json.loads((published / 'synthetic/results.json').read_text(encoding='utf-8'))
    live = json.loads((published / 'live/results.json').read_text(encoding='utf-8'))
    records = live['records']
    levels = ['easy', 'moderate', 'hard']
    labels = ['Easy', 'Moderate', 'Hard']
    colors = ['#23677a', '#b56a22', '#76549a']
    def save(fig, name):
        for ext in ('svg', 'png'):
            fig.savefig(figures / f'{name}.{ext}', dpi=170, bbox_inches='tight',
                        metadata={'Creator': 'MolChat benchmark'})
        plt.close(fig)
    fig, ax = plt.subplots(figsize=(8.4, 4.7), layout='constrained')
    for i, (level, color) in enumerate(zip(levels, colors)):
        rs = [r for r in records if r['difficulty'] == level]
        passed = sum(r['passed'] for r in rs)
        total = len(rs)
        ax.bar(i, 100 * passed / total if total else 0, color=color, width=.58)
        ax.text(i, (100 * passed / total if total else 0) + 2, f'{passed}/{total}', ha='center', weight='bold')
    ax.set(xticks=range(3), xticklabels=labels, ylim=(0, 112), ylabel='Task contracts passed (%)',
           title='Muse Spark: initial run in the real MolDesign environment')
    ax.set_yticks([0, 25, 50, 75, 100])
    ax.grid(axis='y', alpha=.16)
    ax.set_axisbelow(True)
    fig.text(.01, -.035, 'Read-only queries and approval-pending plans. Two trials per fixed prompt; no docking accuracy metric.', fontsize=9)
    save(fig, 'live-by-difficulty')
    fig, ax = plt.subplots(figsize=(8.4, 4.7), layout='constrained')
    samples = [[r['latency_ms'] / 1000 for r in records if r['difficulty'] == level] for level in levels]
    ax.boxplot(samples, tick_labels=labels, showfliers=False, medianprops={'color': '#222222', 'linewidth': 2})
    for i, values in enumerate(samples):
        offsets = [((n % 7) - 3) * .035 for n in range(len(values))]
        ax.scatter([i + 1 + o for o in offsets], values, color=colors[i], alpha=.7, s=20, zorder=3)
    ax.set(ylabel='Wall time per prompt (seconds)', title='Latency includes model requests and real tool calls')
    ax.grid(axis='y', alpha=.16)
    save(fig, 'live-latency')
    metrics = {}
    for s in synthetic['scenarios']:
        c = s['counts_by_repetition'][0]
        m = metrics.setdefault(s['metric'], {'passed': 0, 'total': 0})
        m['passed'] += c['passed']
        m['total'] += sum(c.values())
    fig, ax = plt.subplots(figsize=(9.1, 5.1), layout='constrained')
    keys = list(metrics)
    ax.barh(range(len(keys)), [metrics[k]['passed'] for k in keys], color='#23677a')
    for i, key in enumerate(keys):
        ax.text(metrics[key]['passed'] + .8, i, f"{metrics[key]['passed']}/{metrics[key]['total']}", va='center')
    ax.set(yticks=range(len(keys)), yticklabels=[k.replace('_', ' ').capitalize() for k in keys],
           xlabel='Existing regression checks (one repetition)', title='Harness guarantees: keyless regression evidence')
    ax.xaxis.set_major_locator(MaxNLocator(integer=True))
    ax.set_xlim(0, max(m['total'] for m in metrics.values()) * 1.22)
    ax.invert_yaxis()
    ax.grid(axis='x', alpha=.16)
    ax.set_axisbelow(True)
    save(fig, 'harness-by-metric')
    notebook_path = published / 'capsule/notebook.json'
    if notebook_path.exists():
        notebook = json.loads(notebook_path.read_text(encoding='utf-8'))
        fig, ax = plt.subplots(figsize=(8.7, 4.1), layout='constrained')
        for index, molecule in enumerate(notebook['molecules']):
            value = molecule['vina_kcal_mol']
            if value is None:
                ax.text(-11.7, index, 'Not docked: the stop rule was already met', va='center', color='#555555')
            else:
                ax.barh(index, value, height=.5, color='#23677a' if index == 0 else '#47754a')
                ax.text(value - .15, index, f'{value:g}', ha='right', va='center', weight='bold')
        threshold = notebook['rule']['threshold_kcal_mol']
        ax.axvline(threshold, color='#9a4422', linestyle='--', linewidth=1.5, label=f'Approved threshold: {threshold:g}')
        ax.set(yticks=range(len(notebook['molecules'])),
               yticklabels=[f"{m['n']}. {m['name']}" for m in notebook['molecules']],
               xlim=(-13, .3), xlabel='Recorded Vina score (kcal/mol)', title='A real run stopped before the third candidate')
        ax.invert_yaxis()
        ax.set_ylim(len(notebook['molecules']) - .4, -.6)
        ax.legend(loc='lower right', fontsize=9)
        ax.grid(axis='x', alpha=.16)
        ax.set_axisbelow(True)
        fig.text(.01, -.045, 'Both docked poses passed physical checks. These tool outputs do not establish biological activity.', fontsize=9)
        save(fig, 'vmat2-execution')
    lines = ['# Measured results', '',
             'Generated by `python benchmarks/render_results.py` from the published JSON. '
             'Each pass means every predeclared automated task-contract criterion passed; it is not a human assessment of scientific prose.', '',
             '| Level | Distinct prompts | Trials passed | Median wall time | Min–max |',
             '|---|---:|---:|---:|---:|']
    for level, label, values in zip(levels, labels, samples):
        rs = [r for r in records if r['difficulty'] == level]
        lines.append(f"| {label} | {len({r['id'] for r in rs})} | {sum(r['passed'] for r in rs)}/{len(rs)} | {statistics.median(values):.2f} s | {min(values):.2f}–{max(values):.2f} s |")
    followup_path = published / 'followup/results.json'
    if followup_path.exists():
        followup = json.loads(followup_path.read_text(encoding='utf-8'))
        lines += ['', 'The initial score is preserved. H09 had an incorrect empty-catalogue expectation; H12 exposed missing time-budget fields. '
                  'The follow-up below uses the repaired source and the documented H09 criterion correction. It is not merged into the 72 initial trials.', '',
                  '| Follow-up | Passed | What changed | Traces |', '|---|---:|---|---|']
        for name, change in [('H09', 'Corrected evaluator: successful query with zero matches'),
                              ('H12', 'Repaired model-facing time-budget schema')]:
            rs = [r for r in followup['records'] if r['id'] == name]
            links = ' · '.join(f"[r{r['repetition']}](published/followup/{name}-r{r['repetition']}.json)" for r in rs)
            lines.append(f"| {name} | {sum(r['passed'] for r in rs)}/{len(rs)} | {change} | {links} |")
    lines += ['', '![Live task contracts](published/figures/live-by-difficulty.svg)', '',
              '![Latency distribution](published/figures/live-latency.svg)', '',
              '## Every prompt and trial', '',
              '| Prompt | Level | Trial | Result | Wall time | Failed criteria | Trace |',
              '|---|---|---:|---|---:|---|---|']
    for r in records:
        failures = '; '.join(c['criterion'].replace('|', '/') for c in r['criteria'] if not c['passed'])
        if r.get('exhausted'):
            failures += '; model step budget exhausted'
        name = f"{r['id']}-r{r['repetition']}.json"
        lines.append(f"| {r['id']} | {r['difficulty']} | {r['repetition']} | {'PASS' if r['passed'] else 'FAIL'} | {r['latency_ms']/1000:.2f} s | {failures or '—'} | [JSON](published/live/{name}) |")
    requested = Counter(call['function']['name'] for r in records for message in r.get('transcript', [])
                        for call in message.get('tool_calls', []))
    executed = Counter(call['tool'] for r in records for call in r['tool_executions'])
    lines += ['', '## What the model requested and what actually ran', '',
              'These are tool calls in the initial live planning suite, not docking jobs. '
              '`propose_iteration` creates an unapproved card. Descriptor and catalogue operations are read-only. '
              'A matching call count does not prove that every plan field was correct; H12 demonstrates that distinction.', '',
              '| Tool | Requested by Muse Spark | Actually executed after validation |', '|---|---:|---:|']
    for tool in sorted(requested.keys() | executed.keys()):
        lines.append(f"| `{tool}` | {requested[tool]} | {executed[tool]} |")
    lines += ['', 'Malformed or unauthorized requests are exercised separately by the keyless tool-protocol, '
              'approval and adversarial scenario groups. They are not passed off as adversarial successes by the live model.', '',
              '## Keyless harness checks', '',
              '![Harness checks](published/figures/harness-by-metric.svg)', '',
              '| Metric | Checks passed, first repetition |', '|---|---:|']
    for key, m in metrics.items():
        lines.append(f"| {key.replace('_', ' ')} | {m['passed']}/{m['total']} |")
    lines += ['', f"Repetitions: {synthetic['repetitions']}. Per-run totals: " +
              ', '.join(f"{c['passed']}/{sum(c.values())}" for c in synthetic['summary']['checks_per_repetition']) + '.', '',
              'Durations measure this machine and these dependencies. Repeated trials share a machine and are not independent population samples. '
              'No confidence interval or percentile is claimed from two trials per prompt.', '']
    (HERE / 'RESULTS.md').write_text('\n'.join(lines), encoding='utf-8')
    with (published / 'live/trials.csv').open('w', newline='', encoding='utf-8') as handle:
        writer = csv.writer(handle)
        writer.writerow(['prompt', 'difficulty', 'repetition', 'passed', 'latency_ms', 'model_steps', 'tool_executions'])
        for r in records:
            writer.writerow([r['id'], r['difficulty'], r['repetition'], r['passed'], r['latency_ms'], len(r['model_steps']), len(r['tool_executions'])])
    summary = {'schema': 'molchat.evidence-summary/1',
        'synthetic': {'source': 'published/synthetic/results.json', 'repetitions': synthetic['repetitions'],
                      'checks_per_repetition': synthetic['summary']['checks_per_repetition']},
        'live_initial': {'source': 'published/live/results.json', 'distinct_prompts': len({r['id'] for r in records}),
                         'trials': len(records), 'by_difficulty': live['summary'],
                         'requested_tool_calls': dict(requested), 'executed_tool_calls': dict(executed)},
        'browser_campaigns': [], 'validation': 'published/validation.json', 'findings': 'FINDINGS.md'}
    if followup_path.exists():
        summary['live_followup'] = {'source': 'published/followup/results.json',
            'trials': len(followup['records']), 'passed': sum(r['passed'] for r in followup['records']),
            'oracle_revision': followup['oracle_revision'], 'not_merged_with_initial_score': True}
    for folder in ('capsule', 'capsule-reproduction'):
        notebook_file = published / folder / 'notebook.json'
        if not notebook_file.exists():
            continue
        nb = json.loads(notebook_file.read_text(encoding='utf-8'))
        archive = published / folder / 'delivery.zip'
        summary['browser_campaigns'].append({'case': nb['case'], 'source': f'published/{folder}/README.md',
            'delivery': f'published/{folder}/delivery.zip', 'delivery_sha256': hashlib.sha256(archive.read_bytes()).hexdigest(),
            'molecules': [{'name': m['name'], 'status': m['status_code'], 'vina_kcal_mol': m['vina_kcal_mol'],
                           'physical_controls': m['physical_controls']} for m in nb['molecules']]})
    (HERE / 'results.json').write_text(json.dumps(summary, indent=2) + '\n', encoding='utf-8')
    manifest = {'schema': 'molchat.benchmark-artifacts/1', 'files': []}
    for file in sorted(published.rglob('*')):
        if file.is_file() and file != published / 'MANIFEST.json':
            manifest['files'].append({'path': file.relative_to(published).as_posix(), 'bytes': file.stat().st_size,
                                      'sha256': hashlib.sha256(file.read_bytes()).hexdigest()})
    (published / 'MANIFEST.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--published', type=Path, default=HERE / 'published')
    args = parser.parse_args()
    render(args.published)
