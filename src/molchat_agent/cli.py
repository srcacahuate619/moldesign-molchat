"""Minimal two-stage CLI: propose -> review -> execute."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
import sys

from .bridge import MolDesignBridge
from .capabilities import CAPABILITIES
from .executor import AgentExecutor, save_report
from .meta import MetaPlanner
from .plan import Plan


def _load_plan(path: str) -> Plan:
    source = Path(path)
    if source.stat().st_size > 1_000_000:
        raise ValueError("El archivo del plan excede 1 MB")
    return Plan.from_dict(json.loads(source.read_text(encoding="utf-8")))


def _write_new(path: str, payload: dict, *, force: bool = False) -> None:
    destination = Path(path)
    if destination.exists() and not force:
        raise FileExistsError(f"El archivo ya existe: {destination}. Usa --force si deseas reemplazarlo")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="molchat-agent", description="MolChat Agent (fase 1)")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("catalog", help="Herramientas y riesgos permitidos")

    propose = commands.add_parser("plan", help="Pedir a Muse Spark un plan de sólo lectura")
    propose.add_argument("goal", help="Objetivo científico sin datos confidenciales")
    propose.add_argument("--out", default="plan.json")
    propose.add_argument("--force", action="store_true")

    inspect = commands.add_parser("inspect", help="Mostrar pasos, riesgos y SHA-256")
    inspect.add_argument("plan_file")

    execute = commands.add_parser("execute", help="Ejecutar un plan revisado contra MolDesign")
    execute.add_argument("plan_file")
    execute.add_argument("--out", default="report.json")
    execute.add_argument("--force", action="store_true")
    execute.add_argument("--approve-digest", help="SHA-256 exacto de un plan revisado")
    execute.add_argument("--approve-step", action="append", default=[],
                         help="ID de paso sensible aprobado por el investigador")

    speech = commands.add_parser("transcribe-local", help="Transcribir audio mediante Whisper de MolDesign")
    speech.add_argument("wav_file")
    speech.add_argument("--lang", choices=["es", "en"], default="es")
    return parser


async def _dispatch(args: argparse.Namespace) -> int:
    if args.command == "catalog":
        print(json.dumps([c.as_catalog_entry() for c in CAPABILITIES.values()],
                         ensure_ascii=False, indent=2))
        return 0
    if args.command == "plan":
        print("Aviso: el objetivo se enviará a Meta Model API; evita datos privados.", file=sys.stderr)
        async with MetaPlanner() as planner:
            plan = await planner.plan(args.goal)
        _write_new(args.out, plan.as_dict(), force=args.force)
        print(f"Plan escrito: {args.out}\nHuella: {plan.digest}\nRevisa con 'inspect' antes de ejecutarlo.")
        return 0
    if args.command == "inspect":
        plan = _load_plan(args.plan_file)
        print(f"Objetivo: {plan.goal}\nPlan: {plan.digest}")
        for step in plan.steps:
            cap = CAPABILITIES[step.capability]
            print(f"{step.id}: {step.capability} [{cap.risk}] {json.dumps(step.arguments, ensure_ascii=False)}")
        return 0
    if args.command == "execute":
        if Path(args.out).exists() and not args.force:
            raise FileExistsError("El reporte ya existe; usa --force si deseas reemplazarlo")
        plan = _load_plan(args.plan_file)
        async with MolDesignBridge.from_env() as bridge:
            report = await AgentExecutor(bridge).execute(
                plan, approval_digest=args.approve_digest, approved_steps=set(args.approve_step)
            )
        save_report(report, args.out)
        print(f"Estado: {report.state}; informe: {args.out}; huella: {report.plan_digest}")
        return 0 if report.state == "completed" else 2
    if args.command == "transcribe-local":
        filename = Path(args.wav_file)
        if filename.stat().st_size > 15_000_000:
            raise ValueError("El audio supera 15 MB")
        async with MolDesignBridge.from_env() as bridge:
            print(await bridge.transcribe_local(filename.read_bytes(), lang=args.lang))
        return 0
    raise AssertionError("Comando no implementado")


def main() -> None:
    try:
        status = asyncio.run(_dispatch(build_parser().parse_args()))
    except (ValueError, RuntimeError, OSError, KeyError, json.JSONDecodeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        status = 2
    raise SystemExit(status)


if __name__ == "__main__":
    main()

