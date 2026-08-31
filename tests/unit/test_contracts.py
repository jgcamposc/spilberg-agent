import pytest
from spilberg.edit_plan import CutSegment, EditPlan, Platform, SeoMetadata, ViralScore, VisualEffect, EffectType

def test_viral_score_validation():
    with pytest.raises(ValueError, match="soma dos critérios"):
        ViralScore(hook=1, curiosity=1, clarity=1, relevance=1, emotion=1, originality=1, sharing=1, comments=1, retention=1, payoff=1, total=20)
    
    score = ViralScore(hook=10, curiosity=10, clarity=10, relevance=10, emotion=10, originality=10, sharing=10, comments=10, retention=10, payoff=10, total=100)
    assert score.total == 100

def test_cut_segment_validation():
    with pytest.raises(ValueError, match="end_time precisa ser maior que start_time"):
        CutSegment(start_time=10.0, end_time=5.0, reason="test")

def test_edit_plan_validation():
    segment = CutSegment(start_time=0.0, end_time=10.0, reason="test", keep=True)
    plan = EditPlan(
        video_source="test.mp4",
        target_duration=10.0,
        segments=[segment],
        seo=[SeoMetadata(platform=Platform.REELS)]
    )
    assert plan.selected_duration == 10.0
    assert plan.target_platform == Platform.REELS
