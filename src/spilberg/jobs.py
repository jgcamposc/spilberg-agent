from __future__ import annotations

import asyncio
import json
import re
import shutil
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .edit_plan import EditPlan, PlanStatus
from .local_analysis import (
    build_evidence,
    evidence_markdown,
    file_sha256,
    load_transcript,
    transcript_to_json,
    transcribe_local,
    source_cache_path,
)
from .runtime import ensure_runtime


class JobStatus(str, Enum):
    PREPARED = "PREPARED"
    READY_FOR_EDITORIAL = "READY_FOR_EDITORIAL"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    APPROVED = "APPROVED"
    RENDERING = "RENDERING"
    QA_PASSED = "QA_PASSED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    LOCAL_READY = "LOCAL_READY"
    UPLOADING = "UPLOADING"
    DELIVERED = "DELIVERED"
    STALE_SOURCE = "STALE_SOURCE"
    INVALID_PLAN = "INVALID_PLAN"
    BLOCKED_DEPENDENCY = "BLOCKED_DEPENDENCY"
    QA_FAILED = "QA_FAILED"
    DRIVE_BLOCKED = "DRIVE_BLOCKED"
    FAILED = "FAILED"


class AgentCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate_id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{1,62}$")
    rank: int = Field(ge=1, le=5)
    title: str = Field(min_length=3, max_length=120)
    editorial_rationale: str = Field(min_length=10, max_length=3000)
    style_rationale: str = Field(min_length=3, max_length=1000)
    cleanup_summary: str = "Nenhuma limpeza adicional proposta."
    edit_plan: dict[str, Any]

    @model_validator(mode="after")
    def edit_plan_must_be_pending(self) -> "AgentCandidate":
        plan = EditPlan.model_validate(self.edit_plan)
        if plan.status not in {PlanStatus.PENDING_APPROVAL, PlanStatus.APPROVED}:
            raise ValueError("Plano precisa estar PENDING_APPROVAL ou APPROVED")
        return self


class AgentPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0"
    job_id: str
    source_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    candidates: list[AgentCandidate] = Field(min_length=1, max_length=5)
    drive_destination: str = "Spilberg — Entregas"
    editorial_notes: str = ""

    @model_validator(mode="after")
    def candidate_ranks_are_unique(self) -> "AgentPlan":
        ranks = [item.rank for item in self.candidates]
        if len(set(ranks)) != len(ranks):
            raise ValueError("Ranks de candidatos precisam ser unicos")
        ids = [item.candidate_id for item in self.candidates]
        if len(set(ids)) != len(ids):
            raise ValueError("candidate_id precisa ser unico")
        return self


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _slug(value: str) -> str:
    clean = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return clean[:40] or "video"


class JobStore:
    def __init__(self, root: Path | None = None):
        self.root = root or ensure_runtime()
        self.jobs = self.root / "jobs"
        self.cache = self.root / "cache"
        self.jobs.mkdir(parents=True, exist_ok=True)
        self.cache.mkdir(parents=True, exist_ok=True)

    def job_dir(self, job_id: str) -> Path:
        path = (self.jobs / job_id).resolve()
        if path.parent != self.jobs.resolve():
            raise ValueError("job_id invalido")
        return path

    @staticmethod
    def _write_json(path: Path, payload: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temporary.replace(path)

    @staticmethod
    def _read_json(path: Path) -> dict[str, Any]:
        return json.loads(path.read_text(encoding="utf-8"))

    def _state_path(self, job_id: str) -> Path:
        return self.job_dir(job_id) / "state.json"

    def load_state(self, job_id: str) -> dict[str, Any]:
        path = self._state_path(job_id)
        if not path.is_file():
            raise FileNotFoundError(f"Job inexistente: {job_id}")
        return self._read_json(path)

    def _save_state(self, job_id: str, state: dict[str, Any]) -> None:
        state["updated_at"] = _utc_now()
        self._write_json(self._state_path(job_id), state)

    def _set_status(self, job_id: str, status: JobStatus, **extra: Any) -> dict[str, Any]:
        state = self.load_state(job_id)
        state["status"] = status.value
        state.update(extra)
        self._save_state(job_id, state)
        return state

    def create(self, video: Path, client: str = "", platform: str = "reels", count: int = 1) -> dict[str, Any]:
        video = video.expanduser().resolve()
        if not video.is_file() or video.stat().st_size <= 0:
            raise FileNotFoundError(f"Video ausente ou vazio: {video}")
        if not 1 <= count <= 5:
            raise ValueError("count precisa estar entre 1 e 5")
        source_sha = file_sha256(video)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        job_id = f"{stamp}-{_slug(video.stem)}-{source_sha[:8]}"
        directory = self.job_dir(job_id)
        directory.mkdir(parents=True, exist_ok=False)
        source = {
            "path": str(video),
            "name": video.name,
            "size_bytes": video.stat().st_size,
            "sha256": source_sha,
        }
        self._write_json(directory / "source.json", source)
        state = {
            "schema_version": "1.0",
            "job_id": job_id,
            "created_at": _utc_now(),
            "updated_at": _utc_now(),
            "status": JobStatus.PREPARED.value,
            "client": client.strip() or None,
            "platform": platform.lower(),
            "requested_count": count,
            "source_sha256": source_sha,
            "render_attempts": 0,
            "next_step": "prepare",
        }
        self._write_json(directory / "state.json", state)
        return state

    def _check_source(self, job_id: str) -> Path:
        source = self._read_json(self.job_dir(job_id) / "source.json")
        path = Path(source["path"])
        if not path.is_file() or file_sha256(path) != source["sha256"]:
            self._set_status(job_id, JobStatus.STALE_SOURCE, next_step="recreate_job_from_current_source")
            raise RuntimeError("Fonte mudou ou nao esta mais acessivel; aprovacao invalidada.")
        return path

    def prepare(self, job_id: str, transcript_path: Path | None = None, model_name: str = "small") -> dict[str, Any]:
        state = self.load_state(job_id)
        if state["status"] not in {JobStatus.PREPARED.value, JobStatus.READY_FOR_EDITORIAL.value}:
            raise RuntimeError(f"Job em estado incompatível para prepare: {state['status']}")
        source = self._check_source(job_id)
        job_dir = self.job_dir(job_id)
        cache_dir = self.cache / state["source_sha256"]
        cache_dir.mkdir(parents=True, exist_ok=True)
        cached_transcript = source_cache_path(cache_dir, model_name)
        local_transcript = job_dir / "transcript.json"
        reused = False
        if transcript_path:
            segments = load_transcript(transcript_path.expanduser().resolve())
            self._write_json(local_transcript, transcript_to_json(segments))
            # A supplied transcript must not become an automatic ASR cache entry.
        elif cached_transcript.is_file():
            shutil.copy2(cached_transcript, local_transcript)
            segments = load_transcript(local_transcript)
            reused = True
        else:
            segments = transcribe_local(source, model_name, local_transcript)
            # Recompute after inference: a newly provisioned model now has a weight hash.
            shutil.copy2(local_transcript, source_cache_path(cache_dir, model_name))
        evidence = build_evidence(segments, state["source_sha256"])
        self._write_json(job_dir / "evidence.json", evidence)
        (job_dir / "evidence.md").write_text(evidence_markdown(evidence), encoding="utf-8")
        usage = {
            "schema_version": "1.0",
            "editorial_analysis_count": 0,
            "repair_analysis_count": 0,
            "transcript_chars": evidence["transcript_chars"],
            "sent_to_editor_chars": evidence["sent_to_editor_chars"],
            "context_reduction_percent": evidence["context_reduction_percent"],
            "candidate_count": len(evidence["candidates"]),
            "transcript_cache_reused": reused,
            "expansions_used": 0,
        }
        self._write_json(job_dir / "ai-usage.json", usage)
        return self._set_status(job_id, JobStatus.READY_FOR_EDITORIAL, next_step="submit_plan")

    def submit_plan(self, job_id: str, plan_path: Path) -> dict[str, Any]:
        state = self.load_state(job_id)
        if state["status"] != JobStatus.READY_FOR_EDITORIAL.value:
            raise RuntimeError("O job precisa estar READY_FOR_EDITORIAL para receber plano")
        self._check_source(job_id)
        plan = AgentPlan.model_validate_json(plan_path.read_text(encoding="utf-8"))
        if plan.job_id != job_id or plan.source_sha256 != state["source_sha256"]:
            raise ValueError("Plano nao pertence a este job ou a esta fonte")
        if len(plan.candidates) > state["requested_count"]:
            raise ValueError("Plano excede a quantidade solicitada para o job")
        for candidate in plan.candidates:
            candidate.edit_plan["video_source"] = str(self._check_source(job_id))
        destination = self.job_dir(job_id) / "agent-plan.pending.json"
        destination.write_text(plan.model_dump_json(indent=2, exclude_none=True) + "\n", encoding="utf-8")
        usage = self._read_json(self.job_dir(job_id) / "ai-usage.json")
        usage["editorial_analysis_count"] += 1
        self._write_json(self.job_dir(job_id) / "ai-usage.json", usage)
        return self._set_status(job_id, JobStatus.PENDING_APPROVAL, next_step="approve")

    def approve(self, job_id: str, approval_text: str) -> dict[str, Any]:
        if not approval_text.strip():
            raise ValueError("Aprovacao humana explicita e obrigatoria")
        state = self.load_state(job_id)
        if state["status"] != JobStatus.PENDING_APPROVAL.value:
            raise RuntimeError("Somente plano pendente pode ser aprovado")
        self._check_source(job_id)
        pending = self.job_dir(job_id) / "agent-plan.pending.json"
        plan = AgentPlan.model_validate_json(pending.read_text(encoding="utf-8"))
        raw = plan.model_dump(mode="json")
        for candidate in raw["candidates"]:
            candidate["edit_plan"]["status"] = PlanStatus.APPROVED.value
        approved = self.job_dir(job_id) / "agent-plan.approved.json"
        self._write_json(approved, raw)
        record = {
            "approved_at": _utc_now(),
            "approval_text": approval_text.strip(),
            "source_sha256": state["source_sha256"],
            "approved_plan_sha256": file_sha256(approved),
            "drive_destination": plan.drive_destination,
        }
        from .quality import approval_inputs
        record["dependencies"] = approval_inputs(plan, self.job_dir(job_id) / "transcript.json")
        self._write_json(self.job_dir(job_id) / "approval.json", record)
        return self._set_status(job_id, JobStatus.APPROVED, next_step="finish")

    async def finish(self, job_id: str) -> dict[str, Any]:
        from .editing import SpilbergOrchestrator
        from .qa import run_qa

        state = self.load_state(job_id)
        if state["status"] not in {JobStatus.APPROVED.value, JobStatus.RENDERING.value, JobStatus.QA_FAILED.value, JobStatus.REVIEW_REQUIRED.value}:
            raise RuntimeError(f"Job em estado incompatível para finish: {state['status']}")
        source = self._check_source(job_id)
        job_dir = self.job_dir(job_id)
        approval = self._read_json(job_dir / "approval.json")
        approved_path = job_dir / "agent-plan.approved.json"
        if file_sha256(approved_path) != approval["approved_plan_sha256"]:
            self._set_status(job_id, JobStatus.INVALID_PLAN, next_step="submit_plan")
            raise RuntimeError("Plano aprovado mudou; nova aprovacao e obrigatoria.")
        from .quality import verify_fingerprints, review_output
        verify_fingerprints(approval.get("dependencies", {}))
        existing = job_dir / "render-manifest.json"
        if existing.is_file():
            manifest = self._read_json(existing)
            if manifest.get("schema_version") == "2.0":
                # Recovery must revalidate content, not trust a historical qa_passed flag.
                return self._complete_quality(job_id, manifest)
        attempts = int(state.get("render_attempts", 0))
        if attempts >= 2:
            self._set_status(job_id, JobStatus.QA_FAILED, next_step="inspect_qa")
            raise RuntimeError("Limite de duas renderizacoes atingido")
        self._set_status(job_id, JobStatus.RENDERING, render_attempts=attempts + 1, next_step="rendering")
        plan = AgentPlan.model_validate_json(approved_path.read_text(encoding="utf-8"))
        engine_workspace = job_dir / "engine"
        orchestrator = SpilbergOrchestrator(str(engine_workspace))
        outputs: list[dict[str, Any]] = []
        transcript = job_dir / "transcript.json"
        for candidate in sorted(plan.candidates, key=lambda item: item.rank):
            plan_file = engine_workspace / "plans" / f"{candidate.candidate_id}.json"
            candidate_plan = EditPlan.model_validate(candidate.edit_plan)
            candidate_plan.video_source = str(source)
            candidate_plan.status = PlanStatus.APPROVED
            candidate_plan.export_json(str(plan_file))
            output = await orchestrator.execute_plan(str(plan_file), str(transcript))
            try:
                qa = await run_qa(output, engine_workspace / "qa", candidate_plan.target_platform.value, candidate_plan.selected_duration, orchestrator)
            except Exception as error:
                qa = {"passed": False, "error": str(error)}
            item = {"candidate_id": candidate.candidate_id, "title": candidate.title, "output": str(output), "qa": qa}
            receipt = output.with_suffix(".render.json")
            if receipt.is_file():
                render = self._read_json(receipt)
                item["render_receipt"] = str(receipt)
                if render.get("cover"):
                    item["cover"] = render["cover"]
            quality_report = await asyncio.to_thread(review_output, output, candidate.candidate_id, candidate_plan, transcript,
                                                    engine_workspace / "qa" / candidate.candidate_id, qa, approved_path)
            quality = self._read_json(quality_report)
            item.update(quality_report=str(quality_report), quality_report_sha256=file_sha256(quality_report),
                        quality_status=quality["status"], output_sha256=file_sha256(output))
            captions = output.with_suffix(".captions.json")
            if captions.is_file():
                item["captions"] = str(captions)
            outputs.append(item)
        passed = bool(outputs) and all(item["quality_status"] != "FAIL" for item in outputs)
        manifest = {
            "schema_version": "2.0",
            "created_at": _utc_now(),
            "source_sha256": state["source_sha256"],
            "approved_plan_sha256": approval["approved_plan_sha256"],
            "outputs": outputs,
            "qa_passed": passed,
        }
        self._write_json(job_dir / "render-manifest.json", manifest)
        return self._complete_quality(job_id, manifest)

    def _quality_ready(self, job_id, manifest):
        try:
            return self._validate_quality(job_id, manifest)
        except (OSError, ValueError, KeyError, RuntimeError) as error:
            self._set_status(job_id, JobStatus.QA_FAILED, next_step="inspect_quality_report", quality_error=str(error))
            raise RuntimeError(f"Evidência de revisão mudou ou está ausente: {error}") from error

    def _validate_quality(self, job_id, manifest):
        from .quality import verify_fingerprints
        if manifest.get("schema_version") != "2.0" or not manifest.get("outputs"):
            raise RuntimeError("Manifesto sem revisão de qualidade; execute finish para gerar revisão")
        approval = self._read_json(self.job_dir(job_id) / "approval.json")
        verify_fingerprints(approval.get("dependencies", {}))
        if file_sha256(self.job_dir(job_id) / "agent-plan.approved.json") != approval["approved_plan_sha256"]:
            raise RuntimeError("Plano aprovado mudou")
        ready, failed = True, False
        for item in manifest["outputs"]:
            path = Path(item["quality_report"])
            if file_sha256(path) != item["quality_report_sha256"]:
                raise RuntimeError("Relatório de qualidade mudou")
            report = self._read_json(path)
            if report["clip_id"] != item["candidate_id"] or report["video_sha256"] != item["output_sha256"]:
                raise RuntimeError("Relatório associado ao corte errado")
            verify_fingerprints(report["inputs"])
            if report["status"] == "FAIL":
                failed, ready = True, False
            record = item.get("editorial_review", {})
            if (record.get("decision") != "approve" or record.get("report_sha256") != item["quality_report_sha256"]
                    or record.get("video_sha256") != report["video_sha256"]):
                ready = False
        return ready, failed

    def _complete_quality(self, job_id, manifest):
        ready, failed = self._quality_ready(job_id, manifest)
        if failed:
            self._set_status(job_id, JobStatus.QA_FAILED, next_step="inspect_quality_report")
            raise RuntimeError("QA falhou; corrija o problema antes da entrega")
        if not ready:
            return self._set_status(job_id, JobStatus.REVIEW_REQUIRED, next_step="review",
                                    quality_reports=[i["quality_report"] for i in manifest["outputs"]])
        return self._promote_local_outputs(job_id, manifest)

    def review(self, job_id: str, candidate_id: str, decision: str, reviewer: str, notes: str, report_sha256: str):
        self._check_source(job_id)
        if decision not in {"approve", "reject"} or not reviewer.strip() or not notes.strip():
            raise ValueError("Revisão exige decisão, revisor e justificativa")
        if self.load_state(job_id)["status"] not in {JobStatus.REVIEW_REQUIRED.value, JobStatus.QA_FAILED.value}:
            raise RuntimeError("Job não está aguardando revisão")
        manifest = self._read_json(self.job_dir(job_id) / "render-manifest.json")
        _, failed = self._quality_ready(job_id, manifest)
        item = next((i for i in manifest["outputs"] if i["candidate_id"] == candidate_id), None)
        if not item or report_sha256 != item["quality_report_sha256"]:
            raise RuntimeError("ID ou hash do relatório não corresponde ao material revisado")
        if failed and decision == "approve":
            raise RuntimeError("QA determinístico falhou; a revisão não pode dispensar a falha")
        item["editorial_review"] = {"reviewed_at": _utc_now(), "decision": decision, "reviewer": reviewer.strip(),
                                    "notes": notes.strip(), "report_sha256": report_sha256,
                                    "video_sha256": item["output_sha256"]}
        self._write_json(self.job_dir(job_id) / "render-manifest.json", manifest)
        return self._complete_quality(job_id, manifest)

    def _promote_local_outputs(self, job_id, manifest):
        """Recovery completes promotion too; never declare a missing cover ready."""
        ready, failed = self._quality_ready(job_id, manifest)
        if failed or not ready:
            raise RuntimeError("Entrega requer QA e revisão editorial da versão atual")
        final_dir = self.root / "outputs" / job_id
        final_dir.mkdir(parents=True, exist_ok=True)
        for item in manifest["outputs"]:
            for source_key, local_key, hash_key in [
                ("output", "local_output", "output_sha256"),
                ("cover", "local_cover", "cover_sha256"),
                ("render_receipt", "local_render_receipt", "render_receipt_sha256"),
                ("captions", "local_captions", "captions_sha256"),
                ("quality_report", "local_quality_report", "quality_report_sha256"),
            ]:
                if not item.get(source_key):
                    continue
                original = Path(item[source_key])
                if not original.is_file():
                    raise FileNotFoundError(f"Artefato de render ausente: {original}")
                final = final_dir / original.name
                digest = file_sha256(original)
                if final.exists() and file_sha256(final) != digest:
                    raise RuntimeError("Artefato final mudou; preserve as duas versões antes de retomar")
                if not final.exists():
                    shutil.copy2(original, final)
                item[local_key] = str(final)
                item[hash_key] = digest
        self._write_json(self.job_dir(job_id) / "render-manifest.json", manifest)
        return self._set_status(job_id, JobStatus.LOCAL_READY, next_step="deliver")

    def record_delivery(self, job_id: str, provider: str, file_id: str = "", url: str = "", mime: str = "video/mp4") -> dict[str, Any]:
        state = self.load_state(job_id)
        if state["status"] not in {JobStatus.LOCAL_READY.value, JobStatus.DRIVE_BLOCKED.value, JobStatus.UPLOADING.value}:
            raise RuntimeError("Entrega exige um job localmente pronto")
        manifest = self._read_json(self.job_dir(job_id) / "render-manifest.json")
        self._check_source(job_id)
        ready, failed = self._quality_ready(job_id, manifest)
        if not ready or failed:
            raise RuntimeError("Entrega exige revisão atual")
        from .quality import verify_fingerprints
        try:
            for item in manifest["outputs"]:
                verify_fingerprints({item[key]: item[digest] for key, digest in (
                    ("local_output", "output_sha256"), ("local_cover", "cover_sha256"),
                    ("local_render_receipt", "render_receipt_sha256"), ("local_captions", "captions_sha256"),
                    ("local_quality_report", "quality_report_sha256")) if item.get(key)})
        except RuntimeError:
            self._set_status(job_id, JobStatus.QA_FAILED, next_step="inspect_local_outputs")
            raise
        delivery = {
            "delivered_at": _utc_now(),
            "provider": provider,
            "file_id": file_id or None,
            "url": url or None,
            "mime": mime,
            "outputs": [{"path": item["local_output"], "sha256": item["output_sha256"]} for item in manifest["outputs"]],
        }
        self._write_json(self.job_dir(job_id) / "delivery-manifest.json", delivery)
        if provider == "local":
            return self._set_status(job_id, JobStatus.LOCAL_READY, next_step="deliver")
        if not file_id or not url:
            return self._set_status(job_id, JobStatus.DRIVE_BLOCKED, next_step="record_delivery")
        return self._set_status(job_id, JobStatus.DELIVERED, next_step="done")

    def feedback(self, job_id: str, accepted: bool, rule: str = "") -> dict[str, Any]:
        state = self.load_state(job_id)
        if not accepted:
            raise ValueError("Feedback sem aprovacao nao pode virar aprendizado")
        record = {"accepted_at": _utc_now(), "job_id": job_id, "accepted": True, "rule": rule.strip() or None}
        self._write_json(self.job_dir(job_id) / "feedback.json", record)
        if rule.strip():
            local_rules = self.root / "brain-local" / "learned_rules.md"
            with local_rules.open("a", encoding="utf-8") as handle:
                handle.write(f"\n- [{record['accepted_at']}] {rule.strip()}\n")
        return state
