"""Opt-in Muse Spark evaluation using the production MolChat harness and a real MolDesign backend.

Session tokens arrive once over loopback and stay in memory. Credentials are
resolved by MolDesign's normal per-turn provider mechanism. No fake model or
fake scientific backend is substituted. Desktop mutations are not approved by
this planning suite; full browser execution is a separate evidence tier.
"""
from __future__ import annotations

import argparse
import asyncio
import dataclasses
from datetime import datetime, timezone
import hashlib
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
from pathlib import Path
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(Path(__file__).parent))

from molchat_agent.bridge import MolDesignBridge
from molchat_agent.config import MolChatConfig
from molchat_agent.conversation.memory import MemoryStore
from molchat_agent.conversation.tools import PlatformBackend
from molchat_agent.lang import using
from molchat_agent.providers import build_registry
from molchat_agent.providers.alojado import registro_del_turno
from molchat_agent.server import app as app_module
from molchat_agent.server.auth import standalone_secret
from molchat_agent.server.state import ServerState
from run_benchmark import environment


def public_message(message):
    """Allowlist protocol fields; do not publish hidden reasoning or headers."""
    if message.get('role') == 'system':
        text = message.get('content') or ''
        return {'role': 'system', 'content_sha256': hashlib.sha256(text.encode()).hexdigest()}
    return {key: message[key] for key in ('role', 'content', 'tool_call_id', 'tool_calls') if key in message}


class MeasuredProvider:
    def __init__(self, provider, record):
        self.provider, self.record, self.id = provider, record, provider.id

    async def chat_with_tools(self, messages, tools):
        start = time.perf_counter()
        entry = {'step': len(self.record['model_steps']) + 1,
                 'request': {'model': self.provider.config.model,
                             'temperature': self.provider.config.temperature,
                             'max_tokens': self.provider.config.max_tokens,
                             'messages': [public_message(m) for m in messages],
                             'tool_names': [t['function']['name'] for t in tools]}}
        self.record['model_steps'].append(entry)
        try:
            result = await self.provider.chat_with_tools(messages, tools)
            entry['response'] = public_message(result)
            return result
        except Exception as error:
            entry['error_type'] = type(error).__name__
            raise
        finally:
            entry['latency_ms'] = round((time.perf_counter() - start) * 1000, 3)


def assess(case, record):
    """Deterministic checks against declared task contracts, not an LLM judge."""
    expected = case['expect']
    requested = {c['function']['name'] for m in record.get('transcript', [])
                 for c in m.get('tool_calls', [])}
    results = []
    def check(name, okay, actual=None):
        results.append({'criterion': name, 'passed': bool(okay), 'actual': actual})
    check('turn completed without provider/timeout failure', not record.get('error') and bool(record.get('result'))
          and not any('error_type' in step for step in record['model_steps']))
    check('no desktop mutation dispatched', not record['host_events'], [e['type'] for e in record['host_events']])
    for tool in expected.get('required_tools', []):
        check(f'model selected {tool}', tool in requested, sorted(requested))
    for tool in expected.get('forbidden_tools', []):
        check(f'model did not select {tool}', tool not in requested)
    for tool in expected.get('successful_tools', []):
        matches = [r for r in record['tool_executions'] if r['tool'] == tool]
        check(f'{tool} returned a real successful result', any(r.get('result', {}).get('status') == 'ok' for r in matches),
              [r.get('result', {}).get('status') for r in matches])
    for tool, count in expected.get('min_tool_calls', {}).items():
        actual = sum(r['tool'] == tool for r in record['tool_executions'])
        check(f'at least {count} executions of {tool}', actual >= count, actual)
    references = [match for execution in record['tool_executions'] if execution['tool'] == 'pubchem_lookup'
                  for match in execution.get('result', {}).get('matches', [])]
    smiles = {(ref.get('properties') or {}).get('SMILES') for ref in references}
    smiles.discard(None)
    if expected.get('lookup_smiles_used'):
        used = [execution['validated_arguments'].get('name') for execution in record['tool_executions']
                if execution['tool'] == 'compute_properties']
        check('calculation uses exactly a PubChem-returned SMILES', bool(used) and all(s in smiles for s in used), used)
    plans = record['plans']
    if expected.get('plan_sources_verified'):
        used = [m['smiles'] for p in plans for m in p['spec']['molecules']]
        check('every planned SMILES comes from the real PubChem tool result', len(used) == 2 and all(s in smiles for s in used), used)
    if expected.get('no_plan'):
        check('no plan created without sufficient/valid input', not plans, len(plans))
    if 'plan' in expected:
        check('exactly one pending approval plan', len(plans) == 1, len(plans))
        if len(plans) == 1:
            actual = plans[0]['spec']
            for key, value in expected['plan'].items():
                check(f'plan preserves {key}', actual.get(key) == value, actual.get(key))
            check('plan is still pending approval', plans[0]['state'] == 'pending', plans[0]['state'])
    for word in expected.get('answer_any', []):
        # Each item is a group of acceptable lexical alternatives, not a score of prose quality.
        text = record.get('result', {}).get('text', '').casefold()
        check('answer includes one of: ' + ' / '.join(word), any(w.casefold() in text for w in word))
    for expected_status in expected.get('tool_status', []):
        tool, status = expected_status
        check(f'{tool} reports {status}', any(r['tool'] == tool and r.get('result', {}).get('status') == status
                                               for r in record['tool_executions']))
    for tool in expected.get('empty_results', []):
        check(f'{tool} returned zero actual matches', any(
            r['tool'] == tool and r.get('result', {}).get('status') == 'ok'
            and r['result'].get('total') == 0 and r['result'].get('receptors') == []
            for r in record['tool_executions']))
    return results


async def evaluate(session, args):
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    cases = json.loads((Path(__file__).parent / 'prompts.json').read_text(encoding='utf-8'))['cases']
    if args.only:
        wanted = set(args.only.split(','))
        cases = [c for c in cases if c['id'] in wanted]
        if wanted != {c['id'] for c in cases}:
            raise ValueError('Unknown prompt ID')
    if args.correct_empty_catalog:
        cases = json.loads(json.dumps(cases))
        for case in cases:
            if case['id'] == 'H09':
                case['expect'].pop('tool_status', None)
                case['expect']['empty_results'] = ['search_receptors']
    if args.limit:
        cases = cases[:args.limit]
    report = {'schema': 'molchat.live-evaluation/1', 'evidence_type': 'live_model_real_backend_planning',
              'started_at_utc': datetime.now(timezone.utc).isoformat(), 'environment': environment(),
              'prompt_file_sha256': hashlib.sha256((Path(__file__).parent / 'prompts.json').read_bytes()).hexdigest(),
              'repetitions': args.repetitions, 'records': [],
              'oracle_revision': 'empty-catalog-v2' if args.correct_empty_catalog else 'original-v1',
              'limits': ['Planning/read-only production harness; no docking is approved by this suite.',
                         'Deterministic task-contract checks do not establish scientific correctness.',
                         'System prompt hashes are recorded; hidden reasoning and credentials are excluded.']}
    token = session['token']
    base = build_registry(MolChatConfig(consents_file=ROOT / 'reports/private/benchmark-consents.json'))
    bridge = MolDesignBridge(base_url=args.backend, token=token, require_contract=True)
    original_loop = app_module.run_tool_loop
    try:
        for repetition in range(1, args.repetitions + 1):
            for case in cases:
                record = {'id': case['id'], 'difficulty': case['difficulty'], 'repetition': repetition,
                          'prompt': case['prompt'], 'expect': case['expect'], 'model_steps': [],
                          'host_events': [], 'tool_executions': [], 'validation_events': [], 'plans': []}
                started = time.perf_counter()
                registry = await registro_del_turno(base, bridge)
                provider = registry.get(registry.active_id)
                if provider.id != 'baseten-hackathon' or 'muse-spark' not in provider.config.model:
                    raise RuntimeError('This evaluation requires the configured Muse Spark Baseten provider.')
                record['provider'] = {'id': provider.id, 'model': provider.config.model,
                                      'endpoint': provider.config.base_url}
                state = ServerState(secret=standalone_secret(), registry=registry,
                    memory=MemoryStore(ROOT / 'reports/private/live-benchmark-memory.db'),
                    backend=PlatformBackend(bridge), hosted=True, bridge=bridge)
                owner = 'benchmark-local'
                conv_id = state.memory.create_conversation(owner)

                async def measured_loop(p, messages, tools, **kwargs):
                    observe = kwargs.get('observe')
                    def observed(phase, value, call_id, arguments):
                        record['validation_events'].append({'phase': phase, 'value': value,
                                                            'call_id': call_id, 'validated_arguments': arguments})
                        if observe:
                            observe(phase, value, call_id, arguments)
                    kwargs['observe'] = observed
                    measured = []
                    for tool in tools:
                        async def execute(arguments, original=tool):
                            start = time.perf_counter()
                            item = {'tool': original.name, 'validated_arguments': arguments}
                            record['tool_executions'].append(item)
                            try:
                                value = await original.execute(arguments)
                                item['result'] = value
                                return value
                            finally:
                                item['latency_ms'] = round((time.perf_counter() - start) * 1000, 3)
                        measured.append(dataclasses.replace(tool, execute=execute))
                    result = await original_loop(p, messages, measured, **kwargs)
                    record['transcript'] = [public_message(m) for m in result.messages]
                    record['exhausted'] = result.exhausted
                    return result

                app_module.run_tool_loop = measured_loop
                async def consume():
                    with using(case.get('lang', 'en')):
                        async for event in app_module._harness_turn(state, registry, MeasuredProvider(provider, record),
                                                                   owner, conv_id, case['prompt'], token):
                            if event.get('type') == 'result':
                                record['result'] = event['result']
                            else:
                                record['host_events'].append(event)
                                # Planning tests never authorize desktop effects. Answer a dispatched
                                # host request as unknown; the ordinary harness records the refusal.
                                request_id = event.get('request_id')
                                for field in dataclasses.fields(state):
                                    pending = getattr(state, field.name)
                                    if field.name.endswith('_requests') and request_id in pending:
                                        future = pending[request_id][1]
                                        if not future.done():
                                            future.set_result({'status': 'unknown'})
                try:
                    await asyncio.wait_for(consume(), timeout=args.timeout)
                except Exception as error:
                    record['error'] = type(error).__name__
                finally:
                    app_module.run_tool_loop = original_loop
                    record['plans'] = [{'spec': w.spec.as_dict(), 'digest': w.spec.digest, 'state': w.state}
                                       for w in state.workflows.values()]
                    record['latency_ms'] = round((time.perf_counter() - started) * 1000, 3)
                    record['criteria'] = assess(case, record)
                    record['passed'] = all(c['passed'] for c in record['criteria']) and not record.get('exhausted', False)
                    report['records'].append(record)
                    trace = f"{case['id']}-r{repetition}.json"
                    (output / trace).write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
                    report['summary'] = {level: {'passed': sum(r['passed'] for r in report['records'] if r['difficulty'] == level),
                                                 'total': sum(r['difficulty'] == level for r in report['records'])}
                                         for level in ('easy', 'moderate', 'hard')}
                    (output / 'results.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
                    print(f"Live {case['id']} r{repetition}: {'PASS' if record['passed'] else 'FAIL'} ({record['latency_ms']/1000:.1f}s)", flush=True)
                    await provider.__aexit__(None, None, None)
        return report
    finally:
        app_module.run_tool_loop = original_loop
        await bridge.__aexit__(None, None, None)


def serve(args):
    """One-shot loopback receiver. Never writes the incoming session or HTTP headers."""
    complete = threading.Event()
    outcome = {}
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass
        def do_POST(self):
            if self.path != '/start' or outcome:
                self.send_error(409)
                return
            length = int(self.headers.get('Content-Length', 0))
            if not 0 < length < 8192:
                self.send_error(400)
                return
            session = json.loads(self.rfile.read(length))
            if not isinstance(session.get('token'), str) or not session['token'].startswith('mh1.'):
                self.send_error(400)
                return
            outcome['started'] = True
            self.send_response(202)
            self.end_headers()
            self.wfile.write(b'{"started":true}')
            def work():
                try:
                    report = asyncio.run(evaluate(session, args))
                    outcome['failed_trials'] = sum(not r['passed'] for r in report['records'])
                except Exception as error:
                    outcome['error'] = type(error).__name__ + ': ' + str(error)[:160]
                    print(outcome['error'], flush=True)
                finally:
                    session.clear()
                    complete.set()
            threading.Thread(target=work, daemon=True).start()
    server = HTTPServer(('127.0.0.1', args.port), Handler)
    server.timeout = 1
    print(f'Waiting for an in-memory session on loopback port {args.port}.', flush=True)
    while not complete.is_set():
        server.handle_request()
    server.server_close()
    return int('error' in outcome or outcome.get('failed_trials', 0) > 0)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'reports/live-benchmark')
    parser.add_argument('--backend', default='http://127.0.0.1:18016')
    parser.add_argument('--port', type=int, default=18772)
    parser.add_argument('--limit', type=int)
    parser.add_argument('--only', help='Comma-separated prompt IDs for an explicitly reported follow-up run')
    parser.add_argument('--correct-empty-catalog', action='store_true', help='Apply the documented H09 oracle correction; keep baseline intact')
    parser.add_argument('--repetitions', type=int, default=1)
    parser.add_argument('--timeout', type=int, default=180)
    args = parser.parse_args()
    if not args.backend.startswith(('http://127.0.0.1:', 'http://localhost:')):
        parser.error('A loopback MolDesign backend is required.')
    if not 1 <= args.repetitions <= 10 or not 1 <= args.timeout <= 1800:
        parser.error('Use 1..10 repetitions and a 1..1800 second timeout.')
    raise SystemExit(serve(args))
