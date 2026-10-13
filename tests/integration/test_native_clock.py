import asyncio
import json
import subprocess
from fractions import Fraction

import pytest

from spilberg.editing import SpilbergOrchestrator
from spilberg.edit_plan import CutSegment, EditPlan, VisualEffect, EffectType, Platform, PlanStatus, SeoMetadata

@pytest.mark.parametrize('rate', ['24', '24000/1001', '30'])
def test_zoom_keeps_master_frame_rate_and_audio_clock(tmp_path, rate):
    engine = SpilbergOrchestrator(str(tmp_path/'workspace'))
    source = tmp_path/'master.mp4'
    subprocess.run([engine._resolve_executable('ffmpeg'), '-v','error','-y','-f','lavfi','-i',f'testsrc2=size=320x180:rate={rate}', '-f','lavfi','-i','sine=frequency=440:sample_rate=48000', '-t','2', '-c:v','libx264','-c:a','aac',str(source)],check=True)
    plan = EditPlan(video_source=str(source), target_duration=1.8, status=PlanStatus.APPROVED, segments=[CutSegment(start_time=0.1,end_time=1.9,reason='clock fixture')], effects=[VisualEffect(effect_type=EffectType.ZOOM_IN,start_time=0.1,end_time=1.9,parameters={'amount':0.1})],seo=[SeoMetadata(platform=Platform.YOUTUBE)])
    path=tmp_path/'plan.json';plan.export_json(str(path))
    output=asyncio.run(engine.execute_plan(str(path)))
    streams=json.loads(subprocess.check_output([engine._resolve_executable('ffprobe'),'-v','error','-show_streams','-of','json',str(output)]))['streams']
    v=next(s for s in streams if s['codec_type']=='video');a=next(s for s in streams if s['codec_type']=='audio')
    assert Fraction(v['avg_frame_rate']) == Fraction(rate)
    assert abs(float(v['duration'])-float(a['duration'])) < 1/float(Fraction(rate))+0.025
    asyncio.run(engine.validate_output(str(output), full_decode=True))


@pytest.mark.parametrize('rate', ['24','24000/1001'])
def test_master_flash_and_audio_pulse_stay_aligned_after_cut(tmp_path, rate):
    import cv2
    import numpy as np
    from spilberg.spilberg2_engine import render_spilberg2_cut
    engine=SpilbergOrchestrator(str(tmp_path/'workspace'));source=tmp_path/'pulse-master.mp4'
    subprocess.run([engine._resolve_executable('ffmpeg'),'-v','error','-y','-f','lavfi','-i',f"color=c=black:s=320x180:r={rate}:d=2,drawbox=color=white:t=fill:enable='between(t,1,1.1)'",'-f','lavfi','-i',"aevalsrc='if(between(t,1,1.1),sin(2*PI*880*t),0)':s=48000:d=2",'-c:v','libx264','-c:a','aac',str(source)],check=True)
    output=tmp_path/'pulse-cut.mp4'
    render_spilberg2_cut(source,0.25,1.75,'',[],output,tmp_path/'work',encoder='cpu',intro=False,filmburn=False,clicks=False)
    cap=cv2.VideoCapture(str(output));fps=cap.get(cv2.CAP_PROP_FPS);index=0;video_pulse=None
    while True:
        ok,frame=cap.read()
        if not ok:break
        if frame.mean()>180 and video_pulse is None:video_pulse=index/fps
        index+=1
    cap.release()
    raw=subprocess.check_output([engine._resolve_executable('ffmpeg'),'-v','error','-i',str(output),'-vn','-f','f32le','-ar','48000','-ac','1','-'])
    samples=np.frombuffer(raw,dtype='<f4');audio_pulse=np.flatnonzero(np.abs(samples)>0.2)[0]/48000
    assert video_pulse is not None
    assert abs(video_pulse-audio_pulse) < 1/fps+0.022
