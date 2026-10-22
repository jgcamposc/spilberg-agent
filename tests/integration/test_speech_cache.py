from types import SimpleNamespace
import sys
import pytest


def test_final_asr_reuses_only_matching_content_and_model(tmp_path, master_factory, monkeypatch):
    from spilberg.quality import transcribe_final
    model_dir = tmp_path / "models"; model_dir.mkdir()
    model = model_dir / "fixture.pt"; model.write_bytes(b"model-one")
    monkeypatch.setenv("SPILBERG_WHISPER_CACHE", str(model_dir))
    # The model is an expensive external dependency. Extraction, hashing, cache I/O
    # and invalidation run for real; only inference is replaced with a fixed transcript.
    engine = SimpleNamespace(transcribe=lambda *a, **kw: {"segments": [{"start": 0, "end": .5, "text": "fixture"}]})
    monkeypatch.setitem(sys.modules, "whisper", SimpleNamespace(load_model=lambda *a, **kw: engine))
    video = master_factory(duration=2)
    first = transcribe_final(video, tmp_path / "cache", "fixture")
    assert first["available"] and first["cache_reused"] is False
    assert transcribe_final(video, tmp_path / "cache", "fixture")["cache_reused"] is True
    other = master_factory(name="other", duration=1)
    changed_audio = transcribe_final(other, tmp_path / "cache", "fixture")
    assert changed_audio["cache_reused"] is False and changed_audio["key"] != first["key"]
    model.write_bytes(b"model-two")
    changed_model = transcribe_final(video, tmp_path / "cache", "fixture")
    assert changed_model["cache_reused"] is False and changed_model["key"] != first["key"]


def test_prepare_does_not_reuse_transcript_from_different_model(tmp_path, master_factory, monkeypatch):
    from spilberg.jobs import JobStore
    import spilberg.jobs as jobs
    from spilberg.local_analysis import TranscriptSegment
    source = master_factory(); store = JobStore(tmp_path / "runtime")
    def infer(source, name, destination):
        value = {"segments": [{"start": 0, "end": 1, "text": name}]}
        store._write_json(destination, value)
        return [TranscriptSegment(start=0, end=1, text=name)]
    monkeypatch.setattr(jobs, "transcribe_local", infer)
    job = store.create(source)["job_id"]
    store.prepare(job, model_name="first")
    store.prepare(job, model_name="second")
    transcript = store._read_json(store.job_dir(job) / "transcript.json")
    assert transcript["segments"][0]["text"] == "second"


@pytest.mark.parametrize("explicit", [True, False])
def test_source_cache_and_inference_use_the_same_checkpoint(tmp_path, monkeypatch, explicit):
    from spilberg.local_analysis import transcribe_local
    xdg = tmp_path / "xdg"; configured = tmp_path / "configured"
    monkeypatch.setenv("XDG_CACHE_HOME", str(xdg))
    if explicit:
        monkeypatch.setenv("SPILBERG_WHISPER_CACHE", str(configured))
        weights = configured / "base.pt"
    else:
        monkeypatch.delenv("SPILBERG_WHISPER_CACHE", raising=False)
        weights = xdg / "whisper/base.pt"
    weights.parent.mkdir(parents=True); weights.write_bytes(b"local weights")
    engine = SimpleNamespace(transcribe=lambda *a, **kw: {"segments": [{"start": 0, "end": 1, "text": "fixture"}]})
    def load(name, **kwargs):
        assert name == str(weights.resolve())
        return engine
    monkeypatch.setitem(sys.modules, "whisper", SimpleNamespace(load_model=load))
    transcribe_local(tmp_path / "source.mp4", "base", tmp_path / "transcript.json")
