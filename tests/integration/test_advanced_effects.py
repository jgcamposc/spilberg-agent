import asyncio
import subprocess
from pathlib import Path

import cv2
import imageio_ffmpeg

from spilberg.edit_plan import CutSegment, EditPlan, EffectType, Platform, PlanStatus, SeoMetadata, VisualEffect
from spilberg.editing import SpilbergOrchestrator


def test_split_screen_and_ducking_render_locally(tmp_path):
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    source = tmp_path / "source.mp4"
    subprocess.run(
        [
            ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
            "-f", "lavfi", "-i", "testsrc2=size=640x360:rate=24",
            "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=44100",
            "-t", "2", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(source),
        ],
        check=True,
    )
    plan = EditPlan(
        video_source=str(source),
        target_duration=2,
        status=PlanStatus.APPROVED,
        segments=[CutSegment(start_time=0, end_time=2, reason="synthetic")],
        effects=[
            VisualEffect(
                effect_type=EffectType.B_ROLL,
                start_time=0.4,
                end_time=1.6,
                parameters={"source": "local", "media_path": str(source), "transition": "fade"},
            ),
            VisualEffect(
                effect_type=EffectType.SPLIT_SCREEN,
                start_time=0,
                end_time=2,
                parameters={"media_path": str(source), "layout": "top_bottom"},
            ),
            VisualEffect(
                effect_type=EffectType.AUDIO_DUCKING,
                start_time=0,
                end_time=2,
                parameters={"music_path": str(source), "music_volume": 0.12},
            ),
        ],
        seo=[SeoMetadata(platform=Platform.REELS)],
    )
    workspace = tmp_path / "workspace"
    plan_path = workspace / "plans" / "advanced.json"
    plan.export_json(str(plan_path))
    engine = SpilbergOrchestrator(str(workspace))
    output = asyncio.run(engine.execute_plan(str(plan_path)))
    asyncio.run(engine.validate_output(str(output)))
    capture = cv2.VideoCapture(str(output))
    assert capture.isOpened()
    assert (int(capture.get(cv2.CAP_PROP_FRAME_WIDTH)), int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))) == (1080, 1920)
    capture.release()
