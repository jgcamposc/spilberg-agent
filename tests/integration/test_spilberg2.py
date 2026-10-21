import asyncio
import copy
import json
import subprocess
from fractions import Fraction
from pathlib import Path

import pytest

from spilberg.editing import SpilbergOrchestrator
from spilberg.edit_plan import CutSegment, EditPlan, EffectType, Platform, PlanStatus, SeoMetadata, VisualEffect
from spilberg.spilberg2_engine import render_spilberg2_cut, normalize_captions

import os
ASSETS=Path(os.environ.get('SPILBERG_CIBO_ASSETS',Path(__file__).parents[3]/'cibo/skills/podcast-reels/assets'))
pytestmark=pytest.mark.skipif(not all((ASSETS / name).is_file() for name in ['CalSans-Regular.ttf','filmburn_blue.mp4','click.wav']), reason='Configure local CIBO assets before running compositor integration tests')

@pytest.mark.parametrize('rate', ['24','24000/1001','30'])
def test_cibo_finish_from_master_preserves_clock_captions_and_separate_cover(tmp_path,rate):
    engine=SpilbergOrchestrator(str(tmp_path/'workspace'));source=tmp_path/'master.mp4'
    subprocess.run([engine._resolve_executable('ffmpeg'),'-v','error','-y','-f','lavfi','-i',f'testsrc2=size=320x180:rate={rate}','-f','lavfi','-i','sine=frequency=440:sample_rate=48000','-t','2','-c:v','libx264','-c:a','aac',str(source)],check=True)
    caps=[{'s':0.2,'e':0.9,'words':['UMA','IDEIA'],'flags':[False,True],'word_starts':[0.2,0.5]}];before=copy.deepcopy(caps);out=tmp_path/'finished.mp4'
    render_spilberg2_cut(source,0.25,1.25,'UMA IDEIA',caps,out,tmp_path/'work',assets_dir=ASSETS,encoder='cpu')
    report=json.loads(out.with_suffix('.render.json').read_text())
    assert Fraction(report['source_frame_rate']) == Fraction(rate)
    assert Fraction(report['output_frame_rate']) == Fraction(rate)
    assert report['av_duration_delta'] < 1/float(Fraction(rate))+0.025
    assert abs(report['output_duration']-1) < 1/float(Fraction(rate))+0.025
    assert report['headline_in_video'] is False
    assert out.with_suffix('.cover.jpg').is_file()
    assert report['full_decode'] is True
    assert caps==before
    with pytest.raises(FileExistsError):
        render_spilberg2_cut(source,0,1,'',[],out,tmp_path/'work',encoder='cpu',intro=False,filmburn=False,clicks=False)


def test_approved_plan_selects_cibo_core_and_pending_plan_stays_blocked(tmp_path, master_factory):
    source=master_factory()
    values=dict(video_source=str(source), target_duration=1.2, segments=[CutSegment(start_time=0.2,end_time=1.4,reason='fixture')], render_profile='cibo', effects=[VisualEffect(effect_type=EffectType.SUBTITLE_STYLE,start_time=0.2,end_time=1.4,parameters={'style':'cibo'})],seo=[SeoMetadata(platform=Platform.REELS,title='IDEIA')])
    plan=EditPlan(**values);path=tmp_path/'plan.json';plan.export_json(str(path));engine=SpilbergOrchestrator(str(tmp_path/'workspace'))
    transcript=tmp_path/'transcript.json';transcript.write_text(json.dumps({'segments':[{'start':0.2,'end':1.1,'text':'UMA IDEIA'}]}))
    with pytest.raises(PermissionError):asyncio.run(engine.execute_plan(str(path),str(transcript)))
    plan.status=PlanStatus.APPROVED;plan.export_json(str(path));out=asyncio.run(engine.execute_plan(str(path),str(transcript)))
    assert out.is_file()
    assert json.loads(out.with_suffix('.render.json').read_text())['engine']=='spilberg2'


def test_caps_validate_timing_and_keep_callers_data():
    caps=[{'s':0,'e':1,'words':['uma']}]; result=normalize_captions(caps,1)
    assert result[0]['flags']==[False] and 'flags' not in caps[0]
    for bad in [[{'s':-0.1,'e':1,'words':['uma']}],[{'s':0,'e':1,'words':['uma'],'flags':[]}],[{'s':0,'e':1,'words':['uma'],'word_starts':[2]}]]:
        with pytest.raises(ValueError):normalize_captions(bad,1)


def test_word_timestamps_control_caption_reveal(tmp_path):
    import cv2
    from spilberg.spilberg2_engine import render_dual_captions
    caps=[{'s':0.1,'e':1.0,'words':['FIRST','SECOND'],'flags':[False,False],'word_starts':[0.1,0.7]}]
    _, matte=render_dual_captions(caps,1,'24',str(tmp_path/'caps'),str(ASSETS/'CalSans-Regular.ttf'),encoder='cpu')
    cap=cv2.VideoCapture(matte);counts=[]
    for t in [0.35,0.9]:
        cap.set(cv2.CAP_PROP_POS_MSEC,t*1000);ok,frame=cap.read();assert ok
        counts.append(int((frame[:,:,0]>60).sum()))
    cap.release()
    assert counts[1] > counts[0]*1.4


def test_contenthub_request_bridge_produces_preview_without_headline(tmp_path, master_factory):
    from spilberg.contenthub_adapter import render_request
    source=master_factory()
    req={'source':str(source),'asset':{'type':'video'},'clip':{'start':0.2,'end':1.4,'title':'HEADLINE ONLY ON COVER'},'cues':[{'start':0.2,'end':1.1,'text':'UMA IDEIA'}],'options':{'aspect':'vertical','subtitles':True,'cibo':{'encoder':'cpu','intro':False,'filmburn':False,'clicks':False}},'output':str(tmp_path/'preview.mp4'),'report':str(tmp_path/'native-report.json')}
    result=render_request(req)
    assert result['engine']=='spilberg2-cibo' and result['captionsBurned']
    assert result['qa']['headline_in_video'] is False
    assert result['qa']['cover'] is None
    assert json.loads(Path(req['report']).read_text())==result
    with pytest.raises(FileExistsError):render_request(req)


def test_jobstore_cibo_approved_flow_reaches_local_ready(tmp_path, master_factory):
    from spilberg.jobs import JobStore
    source=master_factory();store=JobStore(tmp_path/'jobs-root')
    state=store.create(source,'Fixture','reels',1);job=state['job_id']
    transcript=tmp_path/'transcript.json';transcript.write_text(json.dumps({'segments':[{'start':0.2,'end':1.1,'text':'UMA IDEIA'}]}))
    state=store.prepare(job,transcript)
    plan={'job_id':job,'source_sha256':state['source_sha256'],'candidates':[{'candidate_id':'clip-01','rank':1,'title':'UMA IDEIA','editorial_rationale':'Source-based fixture for local renderer','style_rationale':'CIBO preset','edit_plan':{'video_source':str(source),'target_duration':1.2,'render_profile':'cibo','render_encoder':'cpu','segments':[{'start_time':0.2,'end_time':1.4,'reason':'fixture'}],'effects':[{'effect_type':'subtitle_style','start_time':0.2,'end_time':1.4,'parameters':{'style':'cibo'}}],'seo':[{'platform':'reels','title':'UMA IDEIA'}]}}]}
    pending=tmp_path/'agent-plan.json';pending.write_text(json.dumps(plan));store.submit_plan(job,pending)
    with pytest.raises(RuntimeError):asyncio.run(store.finish(job))
    store.approve(job,'Approved local fixture, no publication')
    final=asyncio.run(store.finish(job))
    assert final['status']=='REVIEW_REQUIRED'
    pending_report=store._read_json(store.job_dir(job)/'render-manifest.json')['outputs'][0]
    final=store.review(job,'clip-01','approve','synthetic-test-reviewer','Synthetic compositor fixture reviewed, not client editorial acceptance',pending_report['quality_report_sha256'])
    assert final['status']=='LOCAL_READY'
    manifest=json.loads((store.job_dir(job)/'render-manifest.json').read_text());assert manifest['qa_passed']
    for item in manifest['outputs']:
        assert Path(item['local_output']).is_file()
        assert Path(item['local_cover']).is_file()


def test_contenthub_shared_caption_style_remains_owned_by_its_finalizer(tmp_path, master_factory):
    from spilberg.contenthub_adapter import render_request
    source=master_factory()
    req={'source':str(source),'asset':{'type':'video'},'clip':{'start':0.2,'end':1.4},'cues':[{'start':0.2,'end':1.1,'text':'UMA IDEIA'}],'options':{'aspect':'vertical','subtitles':True,'captionStyle':{'preset':'clean'},'cibo':{'encoder':'cpu','intro':False,'filmburn':False,'clicks':False}},'output':str(tmp_path/'preview.mp4'),'report':str(tmp_path/'report.json')}
    result=render_request(req)
    assert result['captionsBurned'] is False
    assert not list((tmp_path/'spilberg2-work').glob('render-*/captions_rgb.mp4'))
