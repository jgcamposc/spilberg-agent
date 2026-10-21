import asyncio
import json
from pathlib import Path

import pytest

from spilberg.jobs import JobStore
from spilberg.local_analysis import file_sha256


def approved_job(tmp_path, master_factory):
    source = master_factory(duration=2)
    store = JobStore(tmp_path / "runtime")
    state = store.create(source, "Synthetic", "youtube", 1); job = state["job_id"]
    transcript = tmp_path / "words.json"
    transcript.write_text(json.dumps({"segments": [{"start": .1, "end": 1.1, "text": "uma ideia", "words": [
        {"start": .1, "end": .4, "word": "uma"}, {"start": .7, "end": 1.1, "word": "ideia"}]}]}))
    store.prepare(job, transcript)
    plan = {"job_id": job, "source_sha256": state["source_sha256"], "candidates": [{
        "candidate_id": "clip-01", "rank": 1, "title": "Uma ideia", "editorial_rationale": "Synthetic source for the quality gate",
        "style_rationale": "Plain source", "edit_plan": {"video_source": str(source), "target_duration": 1.5,
        "segments": [{"start_time": 0, "end_time": 1.5, "reason": "fixture"}],
        "seo": [{"platform": "youtube"}], "effects": [{"effect_type": "subtitle_style", "start_time": 0, "end_time": 1.5,
            "parameters": {"style": "cinematic"}}]}}]}
    pending = tmp_path / "plan.json"; pending.write_text(json.dumps(plan))
    store.submit_plan(job, pending); store.approve(job, "Synthetic fixture only")
    return store, job


def review(store, job):
    manifest = store._read_json(store.job_dir(job) / "render-manifest.json")
    report = Path(manifest["outputs"][0]["quality_report"])
    return store.review(job, "clip-01", "approve", "fixture-reviewer", "Synthetic test review, not editorial acceptance of client media", file_sha256(report))


def test_finish_waits_for_content_bound_editorial_review_without_rerender(tmp_path, master_factory, monkeypatch):
    monkeypatch.setenv("SPILBERG_QA_MODEL", "unavailable-test-model")
    store, job = approved_job(tmp_path, master_factory)
    state = asyncio.run(store.finish(job))
    assert state["status"] == "REVIEW_REQUIRED"
    with pytest.raises(RuntimeError):
        store.record_delivery(job, "local")
    manifest = store._read_json(store.job_dir(job) / "render-manifest.json")
    assert manifest["outputs"][0]["quality_status"] == "REVIEW_REQUIRED"
    state = review(store, job)
    assert state["status"] == "LOCAL_READY"
    assert state["render_attempts"] == 1
    assert store.record_delivery(job, "local")["status"] == "LOCAL_READY"


def test_approval_is_invalidated_when_transcript_changes(tmp_path, master_factory):
    store, job = approved_job(tmp_path, master_factory)
    (store.job_dir(job) / "transcript.json").write_text('{"segments":[]}')
    with pytest.raises(RuntimeError, match="Evidência|dependência"):
        asyncio.run(store.finish(job))
    assert store.load_state(job)["status"] != "LOCAL_READY"


def test_delivery_rejects_video_modified_after_review(tmp_path, master_factory, monkeypatch):
    monkeypatch.setenv("SPILBERG_QA_MODEL", "unavailable-test-model")
    store, job = approved_job(tmp_path, master_factory)
    asyncio.run(store.finish(job)); review(store, job)
    manifest = store._read_json(store.job_dir(job) / "render-manifest.json")
    Path(manifest["outputs"][0]["local_output"]).write_bytes(b"changed final")
    with pytest.raises(RuntimeError, match="mudou|alterado"):
        store.record_delivery(job, "local")
    assert store.load_state(job)["status"] != "LOCAL_READY"


def test_module_failure_cannot_be_approved(tmp_path, master_factory, monkeypatch):
    from spilberg import visual_review
    monkeypatch.setattr(visual_review, "scan_video", lambda *args, **kw: {
        "name": "visual_events", "status": "FAIL", "blocking": True, "reason": "injected decoder failure"})
    store, job = approved_job(tmp_path, master_factory)
    with pytest.raises(RuntimeError, match="QA"):
        asyncio.run(store.finish(job))
    assert store.load_state(job)["status"] == "QA_FAILED"
    with pytest.raises(RuntimeError):
        review(store, job)


def test_review_rejects_report_changed_since_it_was_seen(tmp_path, master_factory, monkeypatch):
    monkeypatch.setenv("SPILBERG_QA_MODEL", "unavailable-test-model")
    store, job = approved_job(tmp_path, master_factory); asyncio.run(store.finish(job))
    with pytest.raises(RuntimeError, match="relatório|Relatório"):
        store.review(job, "clip-01", "approve", "editor", "reviewed", "0" * 64)


def test_resume_rejects_caption_changed_after_report(tmp_path, master_factory, monkeypatch):
    monkeypatch.setenv("SPILBERG_QA_MODEL", "unavailable-test-model")
    store, job = approved_job(tmp_path, master_factory); asyncio.run(store.finish(job))
    manifest = store._read_json(store.job_dir(job) / "render-manifest.json")
    Path(manifest["outputs"][0]["captions"]).write_text('{"segments":[]}')
    with pytest.raises(RuntimeError, match="mudou|ausente"):
        asyncio.run(store.finish(job))
    assert store.load_state(job)["status"] == "QA_FAILED"


def test_approval_tracks_local_assets(tmp_path, master_factory):
    from spilberg.jobs import AgentPlan
    from spilberg.quality import approval_inputs, verify_fingerprints
    source = master_factory(); transcript = tmp_path / "text.json"; transcript.write_text('{}')
    music = tmp_path / "music.wav"; music.write_bytes(b"music")
    plan = AgentPlan(job_id="job", source_sha256="a" * 64, candidates=[{
        "candidate_id": "clip-01", "rank": 1, "title": "Fixture", "editorial_rationale": "Source based fixture",
        "style_rationale": "Plain", "edit_plan": {"video_source": str(source), "target_duration": 1,
        "segments": [{"start_time": 0, "end_time": 1, "reason": "fixture"}],
        "effects": [{"effect_type": "audio_ducking", "start_time": 0, "end_time": 1,
                     "parameters": {"music_path": str(music)}}]}}])
    recorded = approval_inputs(plan, transcript)
    music.write_bytes(b"other music")
    with pytest.raises(RuntimeError):
        verify_fingerprints(recorded)
