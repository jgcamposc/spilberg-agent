import json
from pathlib import Path
from typing import Callable, Iterable, Optional


ASS_COLORS = {
    "white": "&H00FFFFFF",
    "yellow": "&H0000FFFF",
    "black": "&H00000000",
    "red": "&H000000FF",
    "blue": "&H00FF0000",
}


def format_ass_timestamp(seconds: float) -> str:
    total_centiseconds = max(0, int(round(seconds * 100)))
    total_seconds, centiseconds = divmod(total_centiseconds, 100)
    hours, remainder = divmod(total_seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}.{centiseconds:02d}"


def escape_ass_text(text: str) -> str:
    return (
        str(text)
        .replace("\\", r"\\")
        .replace("{", r"\{")
        .replace("}", r"\}")
        .replace("\r\n", r"\N")
        .replace("\n", r"\N")
        .strip()
    )


def ass_color(value: Optional[str], default: str = "white") -> str:
    if not value:
        return ASS_COLORS[default]
    normalized = value.strip().lower()
    if normalized in ASS_COLORS:
        return ASS_COLORS[normalized]
    if normalized.startswith("#") and len(normalized) == 7:
        red, green, blue = normalized[1:3], normalized[3:5], normalized[5:7]
        return f"&H00{blue}{green}{red}".upper()
    return ASS_COLORS[default]


def _effect_type(effect) -> str:
    effect_type = getattr(effect, "effect_type", "")
    return getattr(effect_type, "value", str(effect_type))


def generate_ass_subtitles(
    plan_segments,
    transcript_path: str,
    output_path: str,
    style_name: str = "hormozi",
    custom_color: str = None,
    effects: Optional[Iterable] = None,
    map_time: Optional[Callable[[float], Optional[float]]] = None,
    target_w: int = 1080,
    target_h: int = 1920,
) -> Path:
    """Gera legendas e textos estáticos depois do crop/zoom, dentro da safe area."""
    data = json.loads(Path(transcript_path).read_text(encoding="utf-8"))

    all_words = [
        word
        for segment in data.get("segments", [])
        for word in segment.get("words", [])
        if {"start", "end", "word"}.issubset(word)
    ]

    primary_color = ass_color(custom_color, default="white")
    style_name = style_name.lower()
    subtitle_style = "SubtitleCinematic" if style_name == "cinematic" else "SubtitleHormozi"
    chunk_size = 6 if style_name == "cinematic" else 3

    # Margens proporcionais
    margin_v_sub_hormozi = int(target_h * 0.10) # 10% bottom
    margin_v_sub_cine = int(target_h * 0.22)    # 22% bottom
    margin_v_headline = int(target_h * 0.15)    # 15% top (safe zone trends)
    margin_v_cta = int(target_h * 0.20)         # 20% top

    ass_header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {target_w}
PlayResY: {target_h}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: SubtitleHormozi,Arial,72,{primary_color},&H0000FFFF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,4,3,2,110,110,{margin_v_sub_hormozi},1
Style: SubtitleCinematic,Arial,48,{primary_color},&H000000FF,&H00000000,&H80000000,0,0,0,0,100,100,0,0,1,2,0,2,110,110,{margin_v_sub_cine},1
Style: Headline,Arial,65,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,-1,0,0,0,100,100,0,0,3,15,0,8,120,120,{margin_v_headline},1
Style: CTA,Arial,55,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,-1,0,0,0,100,100,0,0,3,15,0,8,120,120,{margin_v_cta},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    events = []
    current_video_time = 0.0

    for segment in plan_segments:
        seg_duration = segment.end_time - segment.start_time
        seg_words = [
            word
            for word in all_words
            if segment.start_time
            <= (float(word["start"]) + float(word["end"])) / 2
            < segment.end_time
        ]

        for i in range(0, len(seg_words), chunk_size):
            chunk = seg_words[i : i + chunk_size]
            if not chunk:
                continue

            # Start/End absolutos do chunk no vídeo final
            orig_start = float(chunk[0]["start"])
            orig_end = float(chunk[-1]["end"])
            chunk_start = (orig_start - segment.start_time) + current_video_time
            chunk_end = (orig_end - segment.start_time) + current_video_time
            chunk_start = max(current_video_time, chunk_start)
            chunk_end = min(current_video_time + seg_duration, chunk_end)
            if chunk_end <= chunk_start:
                continue

            if style_name == "hormozi":
                # Para cada palavra no chunk, gera um evento onde só ela está destacada (amarela)
                for w_idx, active_word in enumerate(chunk):
                    w_start = (float(active_word["start"]) - segment.start_time) + current_video_time
                    w_end = (float(active_word["end"]) - segment.start_time) + current_video_time
                    
                    # Garantir que os tempos da palavra estejam dentro do chunk e do segmento
                    w_start = max(chunk_start, w_start)
                    w_end = min(chunk_end, w_end)
                    if w_end <= w_start:
                        continue
                    
                    # Construir o texto do chunk com o destaque na palavra atual
                    formatted_words = []
                    for j, w in enumerate(chunk):
                        word_text = escape_ass_text(w["word"])
                        if j == w_idx:
                            # Destaque com amarelo
                            formatted_words.append(rf"{{\c&H0000FFFF}}{word_text}{{\c&HFFFFFF}}")
                        else:
                            formatted_words.append(word_text)
                    
                    text = " ".join(formatted_words)
                    t_start = format_ass_timestamp(w_start)
                    t_end = format_ass_timestamp(w_end)
                    events.append(
                        f"Dialogue: 0,{t_start},{t_end},{subtitle_style},,0,0,0,,{text}"
                    )
            else:
                # Estilo cinematic clássico (estático)
                text = escape_ass_text(" ".join(word["word"].strip() for word in chunk))
                t_start = format_ass_timestamp(chunk_start)
                t_end = format_ass_timestamp(chunk_end)
                events.append(
                    f"Dialogue: 0,{t_start},{t_end},{subtitle_style},,0,0,0,,{text}"
                )

        current_video_time += seg_duration

    if effects and map_time:
        for effect in effects:
            kind = _effect_type(effect)
            if kind not in {"headline", "cta"}:
                continue
            local_start = map_time(float(effect.start_time))
            local_end = map_time(float(effect.end_time))
            if local_start is None or local_end is None or local_end <= local_start:
                continue

            params = effect.parameters
            text = escape_ass_text(params.get("text", ""))
            if not text:
                continue
            color = ass_color(
                params.get("color"),
                "yellow" if kind == "cta" else "white",
            )
            override = rf"{{\c{color}}}"
            style = "Headline" if kind == "headline" else "CTA"
            events.append(
                "Dialogue: 1,"
                f"{format_ass_timestamp(local_start)},"
                f"{format_ass_timestamp(local_end)},"
                f"{style},,0,0,0,,{override}{text}"
            )

    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(ass_header + "\n".join(events) + "\n", encoding="utf-8")
    return destination
