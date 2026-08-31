from __future__ import annotations

import json
import math
import re
from collections import Counter
from dataclasses import asdict, dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any, Iterable


WORD_RE = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿ0-9']+")
OPENING_CONNECTORS = {"e", "mas", "então", "entao", "porque", "isso", "ele", "ela", "eles", "elas", "também", "tambem"}
ENDING_CONNECTORS = {"porque", "que", "então", "entao", "mas", "e", "ou"}
HOOK_WORDS = {"erro", "verdade", "segredo", "nunca", "sempre", "problema", "mudar", "mudou", "medo", "resultado", "vender", "cliente", "dinheiro", "como", "porquê", "porque"}
PAYOFF_WORDS = {"então", "entao", "resultado", "por isso", "aprendi", "conclusão", "conclusao", "solução", "solucao", "funciona"}


@dataclass(frozen=True)
class TranscriptSegment:
    start: float
    end: float
    text: str


def file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _words(text: str) -> list[str]:
    return [item.lower() for item in WORD_RE.findall(text)]


def normalize_transcript(data: Any) -> list[TranscriptSegment]:
    raw_segments = data.get("segments", []) if isinstance(data, dict) else data
    if not isinstance(raw_segments, list):
        raise ValueError("Transcricao precisa conter uma lista 'segments'.")
    result: list[TranscriptSegment] = []
    for raw in raw_segments:
        if not isinstance(raw, dict):
            continue
        text = str(raw.get("text", "")).strip()
        start = float(raw.get("start", 0))
        end = float(raw.get("end", start))
        if text and end > start:
            result.append(TranscriptSegment(start=start, end=end, text=text))
    if not result:
        raise ValueError("Transcricao sem segmentos utilizaveis.")
    return result


def load_transcript(path: Path) -> list[TranscriptSegment]:
    return normalize_transcript(json.loads(path.read_text(encoding="utf-8")))


def transcribe_local(video: Path, model_name: str, destination: Path) -> list[TranscriptSegment]:
    try:
        import whisper
    except ImportError as error:
        raise RuntimeError("Whisper local indisponivel. Rode o instalador do Spilberg.") from error
    model = whisper.load_model(model_name)
    result = model.transcribe(str(video), word_timestamps=True, verbose=False)
    destination.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return normalize_transcript(result)


def _topic_key(text: str) -> str:
    tokens = [word for word in _words(text) if len(word) > 3]
    if not tokens:
        return "geral"
    return Counter(tokens).most_common(1)[0][0]


def _jaccard(left: str, right: str) -> float:
    a, b = set(_words(left)), set(_words(right))
    return len(a & b) / max(1, len(a | b))


def _score(text: str, duration: float, starts_after_pause: bool) -> tuple[int, list[str], list[str]]:
    tokens = _words(text)
    token_set = set(tokens)
    score = 35
    notes: list[str] = []
    risks: list[str] = []
    if 30 <= duration <= 179:
        score += 18
        notes.append("duracao dentro da faixa preferencial")
    elif 15 <= duration < 30:
        score += 8
        notes.append("ideia curta potencialmente completa")
    if starts_after_pause:
        score += 8
        notes.append("inicio apos pausa natural")
    hook_hits = len(token_set & HOOK_WORDS)
    payoff_hits = len(token_set & PAYOFF_WORDS)
    score += min(18, hook_hits * 5)
    score += min(14, payoff_hits * 5)
    if hook_hits:
        notes.append("contem sinal lexical de hook")
    if payoff_hits:
        notes.append("contem sinal lexical de payoff")
    if len(tokens) / max(duration, 1) >= 1.4:
        score += 5
        notes.append("densidade de fala adequada")
    if tokens and tokens[0] in OPENING_CONNECTORS:
        score -= 16
        risks.append("pode depender de contexto anterior")
    if tokens and tokens[-1] in ENDING_CONNECTORS:
        score -= 12
        risks.append("pode terminar sem conclusao")
    return max(0, min(100, score)), notes, risks


def _windows(segments: list[TranscriptSegment]) -> Iterable[tuple[int, int, bool]]:
    for start_index, segment in enumerate(segments):
        for end_index in range(start_index, len(segments)):
            duration = segments[end_index].end - segment.start
            if duration > 179:
                break
            if duration < 15:
                continue
            if end_index + 1 < len(segments) and duration < 30:
                continue
            prior_gap = segment.start - segments[start_index - 1].end if start_index else 99.0
            yield start_index, end_index, prior_gap >= 0.65
            if duration >= 105:
                break


def build_evidence(segments: list[TranscriptSegment], source_sha: str, candidate_limit: int = 20) -> dict[str, Any]:
    candidate_limit = max(1, min(candidate_limit, 20))
    raw: list[dict[str, Any]] = []
    for start_index, end_index, starts_after_pause in _windows(segments):
        group = segments[start_index : end_index + 1]
        text = " ".join(item.text.strip() for item in group)
        duration = group[-1].end - group[0].start
        score, notes, risks = _score(text, duration, starts_after_pause)
        raw.append(
            {
                "start": round(group[0].start, 3),
                "end": round(group[-1].end, 3),
                "duration": round(duration, 3),
                "text": text,
                "local_score": score,
                "selection_notes": notes,
                "risks": risks,
                "topic": _topic_key(text),
            }
        )
    raw.sort(key=lambda item: (item["local_score"], item["duration"]), reverse=True)
    selected: list[dict[str, Any]] = []
    topic_counts: Counter[str] = Counter()
    for candidate in raw:
        if any(_jaccard(candidate["text"], chosen["text"]) >= 0.72 for chosen in selected):
            continue
        if topic_counts[candidate["topic"]] >= 2 and len(selected) < 12:
            continue
        selected.append(candidate)
        topic_counts[candidate["topic"]] += 1
        if len(selected) >= candidate_limit:
            break
    for index, candidate in enumerate(selected, start=1):
        candidate["candidate_id"] = f"candidate-{index:02d}"
        candidate["full_transcript"] = index <= 12
        candidate["summary"] = candidate["text"] if index <= 12 else candidate["text"][:480].rstrip() + "…"
    full_text = "\n".join(f"[{item.start:.2f}-{item.end:.2f}] {item.text}" for item in segments)
    sent_chars = sum(len(item["text"]) if item["full_transcript"] else len(item["summary"]) for item in selected)
    reduction = 0 if not full_text else max(0, round((1 - sent_chars / len(full_text)) * 100, 2))
    index = [
        {"start": round(item.start, 3), "end": round(item.end, 3), "preview": item.text[:180].strip()}
        for item in segments
    ]
    return {
        "schema_version": "1.0",
        "source_sha256": source_sha,
        "transcript_chars": len(full_text),
        "sent_to_editor_chars": sent_chars,
        "context_reduction_percent": reduction,
        "candidate_limit": candidate_limit,
        "full_transcript_candidate_limit": 12,
        "candidates": selected,
        "omitted_region_index": index,
        "topic_map": dict(topic_counts),
    }


def evidence_markdown(evidence: dict[str, Any]) -> str:
    lines = [
        "# Pacote editorial local",
        "",
        f"Fonte SHA-256: `{evidence['source_sha256']}`",
        f"Reducao de contexto: `{evidence['context_reduction_percent']}%`",
        "",
        "## Candidatos",
        "",
    ]
    for item in evidence["candidates"]:
        lines.extend(
            [
                f"### {item['candidate_id']} — score local {item['local_score']}/100",
                f"`{item['start']:.2f}s` a `{item['end']:.2f}s` · {item['duration']:.2f}s · tópico `{item['topic']}`",
                item["text"] if item["full_transcript"] else item["summary"],
                f"Evidencias locais: {', '.join(item['selection_notes']) or 'sem sinal forte'}.",
                f"Riscos: {', '.join(item['risks']) or 'nenhum mecanico detectado'}.",
                "",
            ]
        )
    lines.extend(["## Instrução ao editor", "", "Escolha somente ideias completas. Não invente falas, timestamps ou capacidades técnicas."])
    return "\n".join(lines) + "\n"


def transcript_to_json(segments: list[TranscriptSegment]) -> dict[str, Any]:
    return {"segments": [asdict(item) for item in segments]}
