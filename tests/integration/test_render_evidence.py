import asyncio
import json
from pathlib import Path

from spilberg.edit_plan import CutSegment, EditPlan, EffectType, Platform, PlanStatus, VisualEffect
from spilberg.editing import SpilbergOrchestrator
from spilberg.local_analysis import file_sha256


def test_standard_render_records_actual_captions_and_input_hashes(tmp_path, master_factory):
    source = master_factory(duration=2)
    transcript = tmp_path / "text.json"
    transcript.write_text(json.dumps({"segments": [{"start": .1, "end": 1.2, "text": "UMA IDEIA", "words": [
        {"start": .1, "end": .5, "word": "UMA"}, {"start": .7, "end": 1.2, "word": "IDEIA"}]}]}))
    plan = EditPlan(video_source=str(source), target_duration=1.5, status=PlanStatus.APPROVED,
        platform=Platform.YOUTUBE, segments=[CutSegment(start_time=0, end_time=1.5, reason="fixture")],
        effects=[VisualEffect(effect_type=EffectType.SUBTITLE_STYLE, start_time=0, end_time=1.5, parameters={"style": "cinematic"})])
    file = tmp_path / "clip-01.json"; plan.export_json(str(file))
    output = asyncio.run(SpilbergOrchestrator(str(tmp_path / "engine")).execute_plan(str(file), str(transcript)))
    receipt = json.loads(output.with_suffix(".render.json").read_text())
    captions = json.loads(output.with_suffix(".captions.json").read_text())
    assert captions["clip_id"] == "clip-01"
    assert captions["segments"][0]["text"] == "UMA IDEIA"
    assert captions["video_sha256"] == file_sha256(output)
    assert receipt["transcript_sha256"] == file_sha256(transcript)
    assert receipt["captions_sha256"] == file_sha256(output.with_suffix(".captions.json"))
    assert receipt["source_sha256"] == file_sha256(source)


def test_direct_cibo_render_has_reproducible_receipt_without_assets(tmp_path, master_factory):
    from spilberg.spilberg2_engine import render_spilberg2_cut
    source = master_factory(rate="24000/1001")
    output = Path(render_spilberg2_cut(source, .2, 1.4, "", [], tmp_path / "out.mp4", tmp_path / "work",
        encoder="cpu", intro=False, filmburn=False, clicks=False))
    report = json.loads(output.with_suffix(".render.json").read_text())
    assert report["source_sha256"] == file_sha256(source)
    assert report["output_sha256"] == file_sha256(output)
    assert report["captions_sha256"] == file_sha256(output.with_suffix(".captions.json"))
    assert report["assets"] == {}
