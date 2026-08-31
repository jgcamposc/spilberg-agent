import cv2
import numpy as np
from pathlib import Path


def _load_cascade(filename: str) -> cv2.CascadeClassifier:
    """Carrega apenas modelos locais e verificados; nunca baixa código em runtime."""
    bundled = Path(__file__).parent / "data" / filename
    candidates = [bundled]
    cv2_data = getattr(cv2, "data", None)
    if cv2_data and getattr(cv2_data, "haarcascades", None):
        candidates.append(Path(cv2_data.haarcascades) / filename)

    for candidate in candidates:
        if not candidate.is_file() or candidate.stat().st_size == 0:
            continue
        cascade = cv2.CascadeClassifier(str(candidate))
        if not cascade.empty():
            return cascade

    raise RuntimeError(
        f"Modelo facial local ausente ou inválido: {filename}. "
        "Execute 'python spilberg.py doctor' para diagnosticar."
    )


def _crop_geometry(frame_w: int, frame_h: int, target_ratio: float) -> tuple[int, int]:
    source_ratio = frame_w / frame_h
    if source_ratio >= target_ratio:
        return int(round(frame_h * target_ratio)), frame_h
    return frame_w, int(round(frame_w / target_ratio))


def _central_crop_filter(frame_w: int, frame_h: int, target_ratio: float, target_w: int = 1080, target_h: int = 1920) -> str:
    crop_w, crop_h = _crop_geometry(frame_w, frame_h, target_ratio)
    start_x = max(0, (frame_w - crop_w) // 2)
    start_y = max(0, (frame_h - crop_h) // 2)
    return f"crop={crop_w}:{crop_h}:{start_x}:{start_y},scale={target_w}:{target_h}"


def get_smart_crop_params(
    video_path: str,
    target_ratio: float = 9 / 16,
    max_samples: int = 300,
    target_w: int = 1080,
    target_h: int = 1920,
) -> str:
    """
    Analisa o vídeo usando The Anchor Method (Mediana Estática).
    Retorna a string de filtro do ffmpeg, ex: "crop=ih*(9/16):ih:200:0"
    """
    if target_ratio <= 0:
        raise ValueError("target_ratio precisa ser positivo")

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise RuntimeError(f"Não foi possível abrir o vídeo para reenquadramento: {video_path}")
        
    frame_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    frame_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = float(cap.get(cv2.CAP_PROP_FPS) or 30.0)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    if frame_w <= 0 or frame_h <= 0 or total_frames <= 0:
        cap.release()
        raise RuntimeError(f"Metadados de vídeo inválidos: {video_path}")

    cascade_frontal = _load_cascade("haarcascade_frontalface_default.xml")
    cascade_profile = _load_cascade("haarcascade_profileface.xml")

    # Uma leitura por segundo, limitada e distribuída pelo vídeo.
    seconds = max(1, int(np.ceil(total_frames / fps)))
    sample_count = min(max_samples, seconds)
    sample_frames = np.linspace(0, total_frames - 1, sample_count, dtype=int)

    # Não aumenta frames pequenos; 800 px preserva faces distantes sem custo excessivo.
    process_w = min(800, frame_w)
    process_h = int(frame_h * (process_w / frame_w))

    centers_x = []

    for frame_idx in sample_frames:
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(frame_idx))
        ok, frame = cap.read()
        if not ok:
            continue

        small_frame = cv2.resize(frame, (process_w, process_h))
        gray = cv2.cvtColor(small_frame, cv2.COLOR_BGR2GRAY)

        faces = cascade_frontal.detectMultiScale(
            gray, scaleFactor=1.1, minNeighbors=3, minSize=(24, 24)
        )
        if len(faces) == 0:
            faces = cascade_profile.detectMultiScale(
                gray, scaleFactor=1.1, minNeighbors=3, minSize=(24, 24)
            )
        if len(faces) == 0:
            flipped = cv2.flip(gray, 1)
            mirrored = cascade_profile.detectMultiScale(
                flipped, scaleFactor=1.1, minNeighbors=3, minSize=(24, 24)
            )
            if len(mirrored):
                faces = [
                    (process_w - x - w, y, w, h)
                    for x, y, w, h in mirrored
                ]

        if len(faces) > 0:
            x, _y, w, _h = max(faces, key=lambda face: face[2] * face[3])
            centers_x.append((x + w / 2.0) * (frame_w / process_w))

    cap.release()

    if not centers_x:
        print("⚠️ Nenhum rosto detectado na cena. Usando crop central.")
        return _central_crop_filter(frame_w, frame_h, target_ratio, target_w, target_h)

    # Decisão aprovada pelo usuário: uma âncora fixa pela mediana evita jitter.
    anchor_cx = float(np.median(centers_x))
    print(f"🎯 Âncora definida no eixo X: {anchor_cx:.1f} (baseado em {len(centers_x)} leituras)")

    crop_w, crop_h = _crop_geometry(frame_w, frame_h, target_ratio)
    start_x = int(anchor_cx - (crop_w / 2))
    start_x = max(0, min(start_x, frame_w - crop_w))
    start_y = max(0, (frame_h - crop_h) // 2)

    return f"crop={crop_w}:{crop_h}:{start_x}:{start_y},scale={target_w}:{target_h}"
