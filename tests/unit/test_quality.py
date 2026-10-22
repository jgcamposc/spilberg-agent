import json
from pathlib import Path

import pytest


def quality():
    from spilberg import quality
    return quality


def test_final_caption_manifest_is_bound_to_clip_and_video(tmp_path):
    q = quality()
    video = tmp_path / "video.mp4"; video.write_bytes(b"original")
    path = q.write_captions(video, "clip-01", [{"start": 0, "end": 1, "text": "Uma ideia"}])
    assert q.check_captions(path, video, "clip-01", 2)["status"] == "PASS"
    assert q.check_captions(path, video, "clip-02", 2)["status"] == "FAIL"
    video.write_bytes(b"changed")
    assert q.check_captions(path, video, "clip-01", 2)["status"] == "FAIL"


@pytest.mark.parametrize("segments", [[], [{"start": 0, "end": 0, "text": "a"}],
    [{"start": 0, "end": 1, "text": "a"}, {"start": .5, "end": 1.5, "text": "b"}]])
def test_empty_invalid_or_overlapping_captions_fail(tmp_path, segments):
    q = quality(); video = tmp_path / "video.mp4"; video.write_bytes(b"video")
    path = q.write_captions(video, "clip-01", segments)
    assert q.check_captions(path, video, "clip-01", 2)["status"] == "FAIL"


def test_cross_check_does_not_hide_wrong_number_behind_global_similarity():
    q = quality()
    expected = [{"start": 0, "end": 5, "text": "O resultado de Maria foi 150 vendas neste primeiro projeto"}]
    changed = [{"start": 0, "end": 5, "text": "O resultado de Maria foi 250 vendas neste primeiro projeto"}]
    result = q.compare_speech(expected, changed)
    assert result["status"] != "PASS"
    assert result["issues"] and result["critical_tokens"]


def test_cross_check_finds_temporal_swap_even_with_identical_global_text():
    q = quality()
    expected = [{"start": 0, "end": 1, "text": "primeira frase"}, {"start": 3, "end": 4, "text": "segunda frase"}]
    shifted = [{"start": 3, "end": 4, "text": "primeira frase"}, {"start": 0, "end": 1, "text": "segunda frase"}]
    assert q.compare_speech(expected, shifted)["status"] != "PASS"


def test_empty_asr_cannot_pass():
    assert quality().compare_speech([{"start": 0, "end": 1, "text": "fala"}], [])["status"] == "REVIEW_REQUIRED"


def test_asr_cache_is_keyed_by_audio_model_and_parameters(tmp_path):
    q = quality(); audio = tmp_path / "audio.wav"; audio.write_bytes(b"voice one")
    model = tmp_path / "model.pt"; model.write_bytes(b"weights")
    key = q.asr_cache_key(audio, model, {"language": "pt"})
    audio.write_bytes(b"voice two")
    assert q.asr_cache_key(audio, model, {"language": "pt"}) != key
    audio.write_bytes(b"voice one"); model.write_bytes(b"new weights")
    assert q.asr_cache_key(audio, model, {"language": "pt"}) != key
    model.write_bytes(b"weights")
    assert q.asr_cache_key(audio, model, {"language": "en"}) != key


def test_word_crossing_last_cut_is_not_silently_approved():
    from spilberg.edit_plan import CutSegment
    q = quality()
    transcript = {"segments": [{"start": 0, "end": 2, "text": "palavra", "words": [
        {"start": .8, "end": 1.2, "word": "palavra"}]}]}
    result = q.cut_boundaries(transcript, [CutSegment(start_time=0, end_time=1, reason="fixture")])
    assert result["status"] == "REVIEW_REQUIRED"
    assert result["issues"][0]["boundary"] == "end"


def test_prepare_keeps_word_timestamps_needed_by_renderer(tmp_path):
    from spilberg.local_analysis import normalize_transcript, transcript_to_json
    word = {"start": .1, "end": .3, "word": "Olá"}
    value = transcript_to_json(normalize_transcript({"segments": [{"start": 0, "end": 1, "text": "Olá", "words": [word]}]}))
    assert value["segments"][0].get("words") == [word]
