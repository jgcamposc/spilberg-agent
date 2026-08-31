from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any


def _contact_sheet(video: Path, destination: Path) -> dict[str, Any]:
    import cv2
    import numpy as np

    capture = cv2.VideoCapture(str(video))
    if not capture.isOpened():
        raise RuntimeError(f"Nao foi possivel abrir video para QA: {video}")
    count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    indexes = [max(0, min(count - 1, int((count - 1) * fraction))) for fraction in (0.0, 0.25, 0.5, 0.75, 0.99)]
    frames = []
    black = 0
    for index in indexes:
        capture.set(cv2.CAP_PROP_POS_FRAMES, index)
        ok, frame = capture.read()
        if not ok:
            continue
        if float(frame.mean()) < 4.0:
            black += 1
        frame = cv2.resize(frame, (216, 384))
        frames.append(frame)
    capture.release()
    if not frames:
        raise RuntimeError("QA nao conseguiu extrair frames")
    sheet = np.hstack(frames)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(destination), sheet):
        raise RuntimeError("Nao foi possivel gravar contact sheet")
    return {"contact_sheet": str(destination), "sampled_frames": len(frames), "black_samples": black, "resolution": [width, height]}


async def run_qa(video: Path, qa_dir: Path, platform: str, expected_duration: float, orchestrator: Any) -> dict[str, Any]:
    qa_dir.mkdir(parents=True, exist_ok=True)
    await orchestrator.validate_output(str(video), full_decode=True)
    duration = orchestrator._video_duration(video)
    sheet = await asyncio.to_thread(_contact_sheet, video, qa_dir / f"{video.stem}-contact-sheet.jpg")
    vertical_required = platform in {"reels", "tiktok", "instagram", "shorts"}
    dimensions_ok = not vertical_required or sheet["resolution"] == [1080, 1920]
    duration_ok = abs(duration - expected_duration) <= 1.0
    black_ok = sheet["black_samples"] < max(2, sheet["sampled_frames"])
    result = {
        "full_decode": True,
        "anchor_method": "fixed_median",
        "expected_duration": expected_duration,
        "rendered_duration": duration,
        "duration_ok": duration_ok,
        "dimensions_ok": dimensions_ok,
        "black_samples_ok": black_ok,
        **sheet,
    }
    result["passed"] = bool(duration_ok and dimensions_ok and black_ok)
    (qa_dir / f"{video.stem}-qa.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result
