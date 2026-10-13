import asyncio
from pathlib import Path

import pytest
from spilberg.edit_plan import CutSegment, EditPlan, EffectType, Platform, PlanStatus, SeoMetadata, VisualEffect
from spilberg.editing import SpilbergOrchestrator
from spilberg.spilberg2_engine import captions_from_transcript, compute_median_face_crop


def test_word_mapping_cannot_borrow_text_outside_the_master_cut():
    transcript={'segments':[{'start':1,'end':4,'text':'ANTES MEIO DEPOIS','words':[{'start':1,'end':1.5,'word':'ANTES'},{'start':2,'end':2.5,'word':'MEIO'},{'start':3,'end':3.5,'word':'DEPOIS'}]}]}
    caps=captions_from_transcript(transcript,1.8,2.8)
    assert caps[0]['words']==['MEIO']
    assert caps[0]['s']==pytest.approx(0.2)
    assert caps[0]['word_starts']==pytest.approx([0.2])
    with pytest.raises(ValueError,match='timestamps'):
        captions_from_transcript({'segments':[{'start':1,'end':4,'text':'ANTES MEIO DEPOIS'}]},1.8,2.8)


def test_cibo_cannot_silently_drop_an_approved_effect(tmp_path, master_factory):
    source=master_factory()
    plan=EditPlan(video_source=str(source),target_duration=1,status=PlanStatus.APPROVED,render_profile='cibo',segments=[CutSegment(start_time=0,end_time=1,reason='fixture')],effects=[VisualEffect(effect_type=EffectType.ZOOM_IN,start_time=0,end_time=1)],seo=[SeoMetadata(platform=Platform.REELS)])
    file=tmp_path/'plan.json';plan.export_json(str(file));engine=SpilbergOrchestrator(str(tmp_path/'work'))
    with pytest.raises(ValueError,match='não suportado'):
        asyncio.run(engine.execute_plan(str(file)))
    assert list(engine.outbox.iterdir())==[]


def test_anchor_uses_the_selected_interval_and_handles_portrait_source(monkeypatch):
    import spilberg.spilberg2_engine as engine
    observed={}
    def crop(path,**options):
        observed.update(options)
        return 'crop=720:1280:0:0,scale=1080:1920'
    monkeypatch.setattr(engine,'get_smart_crop_params',crop)
    assert compute_median_face_crop('master.mp4',20,30)==(720,1280,0,0)
    assert observed['start_time']==20 and observed['end_time']==30


def test_cibo_rejects_conflicting_caption_preset_in_an_approved_plan(tmp_path, master_factory):
    source=master_factory()
    plan=EditPlan(video_source=str(source),target_duration=1,status=PlanStatus.APPROVED,render_profile='cibo',segments=[CutSegment(start_time=0,end_time=1,reason='fixture')],effects=[VisualEffect(effect_type=EffectType.SUBTITLE_STYLE,start_time=0,end_time=1,parameters={'style':'cinematic','color':'#ff0000'})],seo=[SeoMetadata(platform=Platform.REELS)])
    file=tmp_path/'plan.json';plan.export_json(str(file));text=tmp_path/'text.json';text.write_text('{"segments":[{"start":0,"end":0.8,"text":"uma ideia"}]}')
    with pytest.raises(ValueError,match='preset CIBO'):
        asyncio.run(SpilbergOrchestrator(str(tmp_path/'work')).execute_plan(str(file),str(text)))


def test_cibo_and_core_use_the_same_private_tool_resolution(monkeypatch, tmp_path):
    from spilberg.media_clock import tool
    monkeypatch.setenv('PATH','')
    monkeypatch.delenv('SPILBERG_FFMPEG',raising=False)
    expected=SpilbergOrchestrator(str(tmp_path/'workspace'))._resolve_executable('ffmpeg')
    assert tool('ffmpeg') == expected


def test_standard_profile_does_not_silently_accept_an_unused_hardware_encoder():
    with pytest.raises(ValueError,match='render_encoder'):
        EditPlan(video_source='master.mp4',target_duration=1,render_encoder='videotoolbox',segments=[CutSegment(start_time=0,end_time=1,reason='source')])
