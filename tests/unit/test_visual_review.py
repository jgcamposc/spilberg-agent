from pathlib import Path

import cv2
import numpy as np
import pytest


def movie(path, colors, fps=24):
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (160, 90))
    assert writer.isOpened()
    for color in colors:
        writer.write(np.full((90, 160, 3), color, dtype=np.uint8))
    writer.release()
    return path


@pytest.mark.parametrize("length", [1, 2, 3, 4])
def test_micro_insert_reports_exact_frames_and_contact_sheet(tmp_path, length):
    from spilberg.visual_review import scan_video
    video = movie(tmp_path / "flash.mp4", [40] * 24 + [230] * length + [40] * 36)
    result = scan_video(video, tmp_path / "qa")
    event = next(e for e in result["events"] if e["type"] == "micro_insert")
    assert event["start_frame"] == 24
    assert event["frame_count"] == length
    assert event["time"] == pytest.approx(1)
    assert Path(result["contact_sheet"]).is_file()
    assert result["status"] == "REVIEW_REQUIRED"


def test_clean_camera_cut_is_not_a_flash(tmp_path):
    from spilberg.visual_review import scan_video
    video = movie(tmp_path / "cut.mp4", [40] * 36 + [210] * 36)
    assert scan_video(video, tmp_path / "qa")["events"] == []


def test_short_camera_shot_is_listed_for_review(tmp_path):
    from spilberg.visual_review import scan_video
    video = movie(tmp_path / "short.mp4", [40] * 24 + [210] * 12 + [100] * 36)
    events = scan_video(video, tmp_path / "qa")["events"]
    assert any(e["type"] == "short_shot" and e["duration"] == pytest.approx(.5) for e in events)


def test_missing_video_cannot_be_an_automated_pass(tmp_path):
    from spilberg.visual_review import scan_video
    assert scan_video(tmp_path / "missing.mp4", tmp_path / "qa")["status"] == "FAIL"
