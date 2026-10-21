"""Streaming visual triage. Short shots/crop flashes are evidence, not verdicts."""
from pathlib import Path

from .quality import check


def scan_video(video: Path, qa_dir: Path, min_shot: float = 1.2, threshold: float = 35) -> dict:
    import cv2
    import numpy as np

    capture = cv2.VideoCapture(str(video))
    if not capture.isOpened():
        capture.release()
        return check("visual_events", "FAIL", blocking=True, events=[], reason="Vídeo inacessível")
    fps = float(capture.get(cv2.CAP_PROP_FPS))
    if fps <= 0:
        capture.release()
        return check("visual_events", "FAIL", blocking=True, events=[], reason="FPS inválido")
    peaks, previous, index = [], None, 0
    try:
        while True:
            ok, frame = capture.read()
            if not ok:
                break
            small = cv2.resize(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY), (160, 90))
            if previous is not None and float(cv2.absdiff(previous, small).mean()) > threshold:
                peaks.append(index)
            previous = small
            index += 1
    finally:
        capture.release()
    if not index:
        return check("visual_events", "FAIL", blocking=True, events=[], reason="Sem frames decodificados")

    # Read just the few event boundaries; memory does not grow with video duration.
    event_capture = cv2.VideoCapture(str(video))
    def frame_at(n):
        event_capture.set(cv2.CAP_PROP_POS_FRAMES, max(0, min(index - 1, n)))
        ok, image = event_capture.read()
        if not ok:
            raise RuntimeError("Frame de evidência indisponível")
        return image

    events, micro = [], set()
    try:
        for a, b in zip(peaks, peaks[1:]):
            if 1 <= b - a <= 4:
                before = cv2.resize(frame_at(a - 1), (160, 90))
                after = cv2.resize(frame_at(b), (160, 90))
                if float(cv2.absdiff(before, after).mean()) < threshold / 2:
                    events.append({"type": "micro_insert", "start_frame": a, "frame_count": b - a,
                                   "time": a / fps, "end_time": b / fps})
                    micro.update((a, b))
        grouped = []
        for p in peaks:
            if not grouped or p - grouped[-1] > 3:
                grouped.append(p)
        for a, b in zip(grouped, grouped[1:]):
            if a not in micro and b not in micro and (b - a) / fps < min_shot:
                events.append({"type": "short_shot", "start_frame": a, "time": a / fps,
                               "end_time": b / fps, "duration": (b - a) / fps})
        evidence = []
        # Every event retains timestamps. Pages keep thumbnails readable and bounded.
        for page_start in range(0, len(events), 8):
            rows = []
            for event in events[page_start:page_start + 8]:
                n = event["start_frame"]
                pictures = []
                for number in (n - 1, n, round(event["end_time"] * fps)):
                    image = cv2.resize(frame_at(number), (240, 135))
                    cv2.putText(image, f"frame {number} / {number / fps:.3f}s", (4, 16), cv2.FONT_HERSHEY_SIMPLEX, .4, (0, 255, 255), 1)
                    pictures.append(image)
                rows.append(np.hstack(pictures))
            qa_dir.mkdir(parents=True, exist_ok=True)
            path = qa_dir / f"{video.stem}-events-{page_start // 8 + 1}.jpg"
            if not cv2.imwrite(str(path), np.vstack(rows)):
                raise RuntimeError("Falha ao gravar evidências visuais")
            evidence.append(str(path))
    finally:
        event_capture.release()
    return check("visual_events", "REVIEW_REQUIRED" if events else "PASS", events=events,
                 scanned_frames=index, fps=fps, contact_sheet=evidence[0] if evidence else None,
                 contact_sheets=evidence, threshold=threshold, min_shot=min_shot,
                 limitation="Movimento/flash criativo pode gerar alerta; inspeção humana confirma")
