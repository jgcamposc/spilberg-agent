import pytest

from spilberg.edit_plan import EffectType, VisualEffect


def test_broll_requires_a_resolvable_source():
    with pytest.raises(ValueError, match="media_path"):
        VisualEffect(effect_type=EffectType.B_ROLL, start_time=0, end_time=1, parameters={})

    effect = VisualEffect(
        effect_type=EffectType.B_ROLL,
        start_time=0,
        end_time=1,
        parameters={"source": "pexels_api", "search_query": "office", "on_failure": "fail"},
    )
    assert effect.parameters["on_failure"] == "fail"


def test_split_screen_and_ducking_require_local_media():
    with pytest.raises(ValueError, match="SPLIT_SCREEN exige media_path"):
        VisualEffect(effect_type=EffectType.SPLIT_SCREEN, start_time=0, end_time=1)
    with pytest.raises(ValueError, match="AUDIO_DUCKING exige music_path"):
        VisualEffect(effect_type=EffectType.AUDIO_DUCKING, start_time=0, end_time=1)

    split = VisualEffect(
        effect_type=EffectType.SPLIT_SCREEN,
        start_time=0,
        end_time=1,
        parameters={"media_path": "secondary.mp4", "layout": "top_bottom"},
    )
    ducking = VisualEffect(
        effect_type=EffectType.AUDIO_DUCKING,
        start_time=0,
        end_time=1,
        parameters={"music_path": "bed.mp3", "music_volume": 0.18},
    )
    assert split.effect_type == EffectType.SPLIT_SCREEN
    assert ducking.effect_type == EffectType.AUDIO_DUCKING
