"""Content-bound quality reports. Heuristic alerts always retain editorial review.

Inspired by CIBO's quality workflow; implemented against Spilberg's job contract.
No client data, external services, model download or vendor scripts are required.
"""
from __future__ import annotations

import difflib
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import re
import subprocess
import tempfile
from typing import Any

from .local_analysis import file_sha256
from .media_clock import tool


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # Distinct temporary file per writer. Atomic replacement never publishes half a report.
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2, allow_nan=False)
        handle.write("\n")
        temporary = Path(handle.name)
    temporary.replace(path)


def check(name: str, status: str, *, blocking: bool = False, **detail: Any) -> dict:
    if status not in {"PASS", "FAIL", "REVIEW_REQUIRED"}:
        raise ValueError("Status de verificação inválido")
    return {"name": name, "status": status, "blocking": blocking, **detail}


def write_captions(video: Path, clip_id: str, segments: list[dict]) -> Path:
    path = video.with_suffix(".captions.json")
    write_json(path, {"schema_version": "1.0", "clip_id": clip_id,
                      "video_sha256": file_sha256(video), "segments": segments})
    return path


def check_captions(path: Path, video: Path, clip_id: str, duration: float) -> dict:
    issues = []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("clip_id") != clip_id or data.get("video_sha256") != file_sha256(video):
            issues.append("Legenda não pertence a este ID/MP4")
        segments = data.get("segments")
        if not isinstance(segments, list) or not segments:
            issues.append("Legenda solicitada está vazia")
        previous = 0.0
        for item in segments or []:
            start, end = float(item["start"]), float(item["end"])
            if not all(math.isfinite(t) for t in (start, end)) or not 0 <= start < end <= duration + .1:
                issues.append("Intervalo inválido de legenda")
            if start < previous - .01:
                issues.append("Blocos de legenda sobrepostos")
            if not str(item["text"]).strip():
                issues.append("Texto de legenda vazio")
            previous = end
    except (OSError, ValueError, KeyError, TypeError) as error:
        issues.append(f"Legenda inacessível/inválida: {error}")
    return check("caption_structure", "FAIL" if issues else "PASS", blocking=True, issues=issues)


def _tokens(text: str) -> list[str]:
    return re.findall(r"[^\W_]+", text.casefold(), flags=re.UNICODE)


def compare_speech(expected: list[dict], observed: list[dict]) -> dict:
    """Compare by temporal block, not a bag of all words in the movie.

    ASR discrepancies are editorial evidence, never automatic text corrections.
    A PASS here still does not inspect burned pixels or certify proper names.
    """
    issues, critical = [], []
    if not expected or not observed:
        return check("final_speech", "REVIEW_REQUIRED", issues=["Fala/legenda sem evidência suficiente"], critical_tokens=[])
    for block in expected:
        text = str(block["text"])
        critical.extend(re.findall(r"\b\d[\w.,]*|\b[A-ZÀ-ÖØ-Þ][a-zà-öø-ÿ]+", text))
        a, b = float(block["start"]), float(block["end"])
        nearby = [s for s in observed if min(b, float(s["end"])) > max(a, float(s["start"]))]
        actual = " ".join(str(s["text"]) for s in nearby)
        want, got = _tokens(text), _tokens(actual)
        similarity = difflib.SequenceMatcher(None, want, got, autojunk=False).ratio()
        # Per-word timestamps, when present, reduce unrelated context in an ASR phrase.
        words = [w for s in nearby for w in s.get("words", []) if a - .15 <= float(w["start"]) < b + .15]
        if words:
            actual = " ".join(str(w.get("word", w.get("text", ""))) for w in words)
            got = _tokens(actual)
            similarity = difflib.SequenceMatcher(None, want, got, autojunk=False).ratio()
        if want != got:
            issues.append({"start": a, "end": b, "expected": text, "observed": actual,
                           "similarity": round(similarity, 3)})
    return check("final_speech", "REVIEW_REQUIRED" if issues or critical else "PASS",
                 issues=issues, critical_tokens=sorted(set(critical)),
                 limitation="ASR não confirma grafia, identidade do locutor nem pixels da legenda")


def cut_boundaries(transcript: dict, segments: list) -> dict:
    words = [w for s in transcript.get("segments", []) for w in s.get("words", [])]
    issues = []
    offset = 0.0
    for segment in segments:
        for kind, time in (("start", segment.start_time), ("end", segment.end_time)):
            for word in words:
                if float(word["start"]) + .02 < time < float(word["end"]) - .02:
                    issues.append({"boundary": kind, "source_time": time,
                                   "output_time": offset if kind == "start" else offset + segment.end_time - segment.start_time,
                                   "word": word.get("word", word.get("text", ""))})
        offset += segment.end_time - segment.start_time
    return check("speech_boundaries", "REVIEW_REQUIRED" if issues or not words else "PASS",
                 issues=issues, word_timestamps_available=bool(words))


def asr_cache_key(audio: Path, model: Path, parameters: dict) -> str:
    data = {"audio": file_sha256(audio), "model": file_sha256(model), "parameters": parameters}
    return hashlib.sha256(json.dumps(data, sort_keys=True, allow_nan=False).encode()).hexdigest()


def transcribe_final(video: Path, cache: Path, model_name: str | None = None) -> dict:
    """Only load explicitly cached local Whisper weights. Never download a model."""
    name = model_name or os.getenv("SPILBERG_QA_MODEL", "large-v3")
    model = Path(os.getenv("SPILBERG_WHISPER_CACHE", Path.home() / ".cache/whisper")) / f"{name}.pt"
    if not re.fullmatch(r"[\w.-]+", name) or not model.is_file():
        return {"available": False, "reason": f"Modelo local {name} indisponível; conferir áudio manualmente"}
    try:
        import whisper
        version = importlib.metadata.version("openai-whisper")
    except (ImportError, importlib.metadata.PackageNotFoundError) as error:
        return {"available": False, "reason": str(error)}
    parameters = {"backend": "openai-whisper", "version": version, "model": name,
                  "language": "pt", "word_timestamps": True, "temperature": 0, "fp16": False, "device": "cpu"}
    cache.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="speech-", dir=cache) as work:
        audio = Path(work) / "audio.wav"
        subprocess.run([tool("ffmpeg"), "-nostdin", "-v", "error", "-i", str(video), "-vn",
                        "-ac", "1", "-ar", "16000", str(audio)], capture_output=True, check=True, timeout=300)
        key = asr_cache_key(audio, model, parameters)
        destination = cache / f"{key}.json"
        if destination.is_file():
            try:
                cached = json.loads(destination.read_text(encoding="utf-8"))
                if cached["key"] == key and isinstance(cached["segments"], list):
                    return {**cached, "available": True, "cache_reused": True}
            except (OSError, ValueError, KeyError, TypeError):
                pass
        engine = whisper.load_model(str(model), device="cpu")
        result = engine.transcribe(str(audio), language="pt", word_timestamps=True,
                                   temperature=0, fp16=False, verbose=False)
        value = {"key": key, "parameters": parameters, "audio_sha256": file_sha256(audio),
                 "model_sha256": file_sha256(model), "segments": result.get("segments", [])}
        write_json(destination, value)
        return {**value, "available": True, "cache_reused": False}


def mapped_reference(transcript: dict, segments: list) -> list[dict]:
    """Map selected source phrases to output time, retaining uncertainty at boundaries."""
    reference, offset = [], 0.0
    for cut in segments:
        for phrase in transcript.get("segments", []):
            words = [w for w in phrase.get("words", [])
                     if cut.start_time <= float(w["start"]) < float(w["end"]) <= cut.end_time]
            if words:
                reference.append({"start": offset + float(words[0]["start"]) - cut.start_time,
                                  "end": offset + float(words[-1]["end"]) - cut.start_time,
                                  "text": " ".join(str(w.get("word", w.get("text", ""))).strip() for w in words)})
            elif not phrase.get("words") and cut.start_time <= float(phrase["start"]) < float(phrase["end"]) <= cut.end_time:
                reference.append({"start": offset + float(phrase["start"]) - cut.start_time,
                                  "end": offset + float(phrase["end"]) - cut.start_time, "text": phrase["text"]})
        offset += cut.end_time - cut.start_time
    return reference


def fingerprints(paths: list[Path]) -> dict[str, str]:
    return {str(p.resolve()): file_sha256(p) for p in paths}


def verify_fingerprints(expected: dict[str, str]) -> None:
    for name, digest in expected.items():
        path = Path(name)
        if not path.is_file() or file_sha256(path) != digest:
            raise RuntimeError(f"Evidência mudou ou está ausente: {path.name}")


def report_status(checks: list[dict]) -> str:
    if not checks or any(c["blocking"] and c["status"] != "PASS" for c in checks):
        return "FAIL"
    # Human perception/context is never certified just because automation succeeded.
    return "REVIEW_REQUIRED"


def approval_inputs(plan: Any, transcript: Path) -> dict[str, str]:
    """Freeze local inputs used by approved-plan execution, not only the master."""
    paths = [transcript]
    root = Path(__file__).resolve().parents[2]
    for candidate in plan.candidates:
        edit = candidate.edit_plan
        for effect in edit.get("effects", []):
            params = effect.get("parameters", {})
            for key in ("media_path", "music_path"):
                if params.get(key):
                    p = Path(params[key]).expanduser()
                    paths.append(p if p.is_absolute() else root / p)
        if edit.get("render_profile") == "cibo":
            from .spilberg2_engine import FONT_PATH, FILMBURN_PATH, CLICK_SFX_PATH
            paths.append(Path(FILMBURN_PATH))
            has_captions = any(e["effect_type"] == "subtitle_style" for e in edit.get("effects", []))
            has_cover = bool(edit.get("seo", [{}])[0].get("title")) if edit.get("seo") else False
            has_cover = has_cover or any(e["effect_type"] == "headline" for e in edit.get("effects", []))
            if has_captions or has_cover:
                paths.append(Path(FONT_PATH))
            if has_captions:
                paths.append(Path(CLICK_SFX_PATH))
    return fingerprints(paths)


def review_output(video: Path, clip_id: str, plan: Any, transcript: Path,
                  qa_dir: Path, technical: dict, approved_path: Path) -> Path:
    from fractions import Fraction
    from .media_clock import probe_video
    from .visual_review import scan_video

    qa_dir.mkdir(parents=True, exist_ok=True)
    checks = [check("technical", "PASS" if technical.get("passed") else "FAIL", blocking=True, result=technical)]
    paths = [video, transcript, approved_path]
    receipt_path, captions_path = video.with_suffix(".render.json"), video.with_suffix(".captions.json")
    segments = [s for s in plan.segments if s.keep]
    try:
        native, final = probe_video(Path(plan.video_source)), probe_video(video)
        tolerance = 2 / native["fps"] + .025
        audio = next((s for s in final["streams"] if s.get("codec_type") == "audio"), None)
        stream = next(s for s in final["streams"] if s.get("codec_type") == "video")
        av_delta = abs(float(audio.get("duration", final["duration"])) - float(stream.get("duration", final["duration"]))) if audio else None
        clock_ok = (Fraction(native["rate"]) == Fraction(final["rate"]) and
                    abs(final["duration"] - plan.selected_duration) <= tolerance and
                    (not native["audio"] or audio is not None) and (av_delta is None or av_delta <= tolerance))
        checks.append(check("source_clock", "PASS" if clock_ok else "FAIL", blocking=True,
                            source_rate=native["rate"], output_rate=final["rate"], av_delta=av_delta, tolerance=tolerance))
        paths.append(Path(plan.video_source))
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        if receipt.get("output_sha256") != file_sha256(video) or receipt.get("source_sha256") != file_sha256(Path(plan.video_source)):
            raise RuntimeError("Recibo não corresponde à fonte/MP4")
        verify_fingerprints(receipt.get("assets", {}))
        paths += [receipt_path] + [Path(p) for p in receipt.get("assets", {})]
        needs_captions = any(e.effect_type.value == "subtitle_style" for e in plan.effects)
        if captions_path.is_file():
            if receipt.get("captions_sha256") != file_sha256(captions_path):
                raise RuntimeError("Legenda usada no render mudou")
            paths.append(captions_path)
        if needs_captions:
            checks.append(check_captions(captions_path, video, clip_id, final["duration"]))
        data = json.loads(transcript.read_text(encoding="utf-8"))
        checks.append(cut_boundaries(data, segments))
        reference = (json.loads(captions_path.read_text(encoding="utf-8"))["segments"] if needs_captions and captions_path.is_file()
                     else mapped_reference(data, segments))
        asr = transcribe_final(video, qa_dir / "asr-cache")
        speech = compare_speech(reference, asr["segments"]) if asr.get("available") else check("final_speech", "REVIEW_REQUIRED", reason=asr["reason"])
        speech["asr"] = {k: v for k, v in asr.items() if k != "segments"}
        checks.append(speech)
        checks.append(scan_video(video, qa_dir))
    except Exception as error:
        checks.append(check("quality_execution", "FAIL", blocking=True, reason=str(error)))
    report = {"schema_version": "1.0", "clip_id": clip_id, "video": str(video),
              "video_sha256": file_sha256(video), "inputs": fingerprints(paths),
              "status": report_status(checks), "technical_status": "FAIL" if report_status(checks) == "FAIL" else "PASS",
              "editorial_status": "REVIEW_REQUIRED", "checks": checks,
              "review_instructions": "Assista/escute o MP4 completo, confira legendas, nomes/números, limites de fala e todos os alertas. Registre a decisão para este hash de relatório."}
    path = qa_dir / f"{clip_id}-quality.json"
    write_json(path, report)
    return path
