from __future__ import annotations

import argparse
import asyncio
import importlib.util
import json
import platform
import shutil
import sys
from pathlib import Path

from . import __version__
from .editing import SpilbergOrchestrator
from .jobs import JobStore
from .runtime import base_brain_root, ensure_runtime
import os

try:
    import imageio_ffmpeg
    ffmpeg_dir = Path(imageio_ffmpeg.get_ffmpeg_exe()).parent
    os.environ["PATH"] = f"{ffmpeg_dir}{os.pathsep}{os.environ.get('PATH', '')}"
except ImportError:
    pass


def _emit(payload: object) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))


def _doctor() -> dict[str, object]:
    root = ensure_runtime()
    packages = {name: bool(importlib.util.find_spec(module)) for name, module in {
        "pydantic": "pydantic",
        "opencv": "cv2",
        "numpy": "numpy",
        "whisper": "whisper",
        "yt_dlp": "yt_dlp",
        "imageio_ffmpeg": "imageio_ffmpeg",
    }.items()}
    workspace = root / "doctor"
    orchestrator = SpilbergOrchestrator(str(workspace))
    executables: dict[str, object] = {}
    for name in ("ffmpeg", "whisper", "yt-dlp", "auto-editor"):
        try:
            executables[name] = {"available": True, "path": orchestrator._resolve_executable(name)}
        except FileNotFoundError:
            executables[name] = {"available": False, "path": None}
    brain = {path.name: path.is_file() and path.stat().st_size > 0 for path in base_brain_root().glob("*")}
    ready = all(packages.values()) and all(item["available"] for item in executables.values()) and all(brain.values())
    return {
        "version": __version__,
        "system": platform.platform(),
        "python": sys.version.split()[0],
        "runtime": str(root),
        "packages": packages,
        "executables": executables,
        "brain": brain,
        "capabilities": {
            "local_first": True,
            "external_openai_api_required": False,
            "fixed_median_anchor": True,
            "human_approval_gate": True,
            "automatic_broll": False,
            "dynamic_face_tracking": False,
            "social_publishing": False,
        },
        "ready": ready,
    }


async def _run(args: argparse.Namespace) -> int:
    store = JobStore()
    if args.command == "doctor":
        report = _doctor()
        _emit(report)
        return 0 if report["ready"] else 1
    if args.command == "prepare":
        state = store.create(Path(args.video), args.client, args.platform, args.count)
        state = store.prepare(state["job_id"], Path(args.transcript) if args.transcript else None, args.model)
        _emit({"job": state, "job_dir": str(store.job_dir(state["job_id"]))})
        return 0
    if args.command == "status":
        _emit(store.load_state(args.job_id))
        return 0
    if args.command == "submit-plan":
        _emit(store.submit_plan(args.job_id, Path(args.plan)))
        return 0
    if args.command == "approve":
        _emit(store.approve(args.job_id, args.approval_text))
        return 0
    if args.command == "finish":
        _emit(await store.finish(args.job_id))
        return 0
    if args.command == "deliver":
        _emit(store.record_delivery(args.job_id, args.provider, args.file_id, args.url, args.mime))
        return 0
    if args.command == "feedback":
        _emit(store.feedback(args.job_id, args.accepted, args.rule or ""))
        return 0
    if args.command == "validate-plan":
        from .edit_plan import EditPlan
        _emit(EditPlan.load_json(args.plan).model_dump(mode="json", exclude_none=True))
        return 0
    if args.command == "ingest":
        inbox = ensure_runtime() / "inbox"
        output = await SpilbergOrchestrator(str(inbox)).ingest_video(args.url)
        _emit({"video": str(output)})
        return 0
    raise ValueError(f"Comando desconhecido: {args.command}")


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Spilberg Agent: cortes locais auditaveis para Codex.")
    commands = result.add_subparsers(dest="command", required=True)
    commands.add_parser("doctor", help="Valida motor, brain e dependencias.")
    ingest = commands.add_parser("ingest", help="Baixa URL apenas quando autorizado.")
    ingest.add_argument("url")
    prepare = commands.add_parser("prepare", help="Cria job, transcreve localmente e gera EvidencePack.")
    prepare.add_argument("video")
    prepare.add_argument("--transcript")
    prepare.add_argument("--client", default="")
    prepare.add_argument("--platform", default="reels")
    prepare.add_argument("--count", type=int, default=1)
    prepare.add_argument("--model", default="small")
    status = commands.add_parser("status", help="Mostra estado retomavel do job.")
    status.add_argument("job_id")
    submit = commands.add_parser("submit-plan", help="Valida e recebe o plano criado pelo Codex.")
    submit.add_argument("job_id")
    submit.add_argument("plan")
    approve = commands.add_parser("approve", help="Registra uma aprovacao humana imutavel.")
    approve.add_argument("job_id")
    approve.add_argument("--approval-text", required=True)
    finish = commands.add_parser("finish", help="Renderiza e executa QA sem reanalise editorial.")
    finish.add_argument("job_id")
    deliver = commands.add_parser("deliver", help="Registra entrega local ou Drive confirmado.")
    deliver.add_argument("job_id")
    deliver.add_argument("--provider", default="local", choices=("local", "google-drive"))
    deliver.add_argument("--file-id", default="")
    deliver.add_argument("--url", default="")
    deliver.add_argument("--mime", default="video/mp4")
    feedback = commands.add_parser("feedback", help="Registra aceite e regra local explicita.")
    feedback.add_argument("job_id")
    feedback.add_argument("--accepted", action="store_true")
    feedback.add_argument("--rule")
    validate = commands.add_parser("validate-plan", help="Valida EditPlan sem renderizar.")
    validate.add_argument("plan")
    return result


def main() -> None:
    try:
        raise SystemExit(asyncio.run(_run(parser().parse_args())))
    except KeyboardInterrupt:
        raise SystemExit(130)
    except Exception as error:
        print(json.dumps({"error": str(error)}, ensure_ascii=False), file=sys.stderr)
        raise SystemExit(1)
