#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Spilberg 2.0 - Unified Video Engine
Combines the precision cutting and median-anchor face reframing of Spilberg
with the viral editorial curation, Cal Sans typography, filmburn transitions,
click SFX, and cover generation of CIBO.
"""

import os
import sys
import math
import json
import wave
import subprocess
import numpy as np
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter

# Assets stay local; callers can supply a portable CIBO asset directory.
CIBO_DIR = Path(os.environ.get("SPILBERG_CIBO_DIR", Path(__file__).resolve().parents[3] / "cibo"))
CIBO_ASSETS_DIR = Path(os.environ.get("SPILBERG_CIBO_ASSETS", CIBO_DIR / "skills/podcast-reels/assets"))
FONT_PATH = str(CIBO_ASSETS_DIR / "CalSans-Regular.ttf")
FILMBURN_PATH = str(CIBO_ASSETS_DIR / "filmburn_blue.mp4")
CLICK_SFX_PATH = str(CIBO_ASSETS_DIR / "click.wav")
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from spilberg.media_clock import probe_video, tool, run
from spilberg.reframer import get_smart_crop_params

W, H = 1080, 1920
BAND_H = 420
BAND_Y = 820
CY = BAND_Y + 210 - BAND_Y  # 210 inside band
BASE_FONT_SZ = 72
EMPH_FONT_SZ = 98
MAXW = W - 140
SR = 48000
INTRO_DUR = 0.90

def get_video_info(video_path):
    info = probe_video(video_path)
    return info["width"], info["height"], info["fps"]


def compute_median_face_crop(video_path, t_start, t_end, default_cx=None):
    # Analyze only the selected original interval, without encoding a proxy.
    import re
    filt = get_smart_crop_params(str(video_path), start_time=t_start, end_time=t_end, max_samples=30)
    crop_w, crop_h, x, y = map(int, re.match(r"crop=(\d+):(\d+):(\d+):(\d+)", filt).groups())
    return crop_w, crop_h, x, y


def generate_cover_card(master_path, cover_time, headline, crop_w, crop_h, start_x, out_path, start_y=0, font_path=FONT_PATH):
    """
    CIBO Cover Card Generator:
    Extracts frame, applies 9:16 crop, dark bottom gradient scrim,
    and bold multi-line headline in safe zone.
    """
    raw = run([tool("ffmpeg"), "-v", "error", "-ss", str(cover_time), "-i", str(master_path), "-vf", f"crop={crop_w}:{crop_h}:{start_x}:{start_y},scale={W}:{H}:flags=lanczos", "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"])
    im = Image.frombytes('RGB', (W, H), raw[:W*H*3])

    # Scrim gradient on lower half
    sc = Image.new('L', (1, H))
    for y in range(H):
        v = 0
        if y > H * 0.42:
            v = int(235 * min(1.0, ((y - H * 0.42) / (H * 0.42)) ** 1.25))
        sc.putpixel((0, y), v)
    scrim = sc.resize((W, H))
    dark = Image.new('RGB', (W, H), (6, 10, 20))
    im = Image.composite(dark, im, scrim)

    # Render typography
    draw = ImageDraw.Draw(im)
    lines = headline.strip().split('\n')

    # Find fitting font size
    sz = 100
    while sz > 48:
        ft = ImageFont.truetype(font_path, sz)
        max_line_w = max(ft.getbbox(l)[2] - ft.getbbox(l)[0] for l in lines)
        if max_line_w <= W - 140:
            break
        sz -= 4
    ft = ImageFont.truetype(font_path, sz)
    if max(ft.getlength(line) for line in lines) > MAXW or len(lines) * sz * 1.18 > H * 0.4:
        raise ValueError("Headline não cabe na capa; revise a quebra de linhas")

    line_h = int(sz * 1.18)
    total_h = line_h * len(lines)
    start_y = int(H * 0.735) - total_h // 2

    for i, l in enumerate(lines):
        bb = ft.getbbox(l)
        w = bb[2] - bb[0]
        x = (W - w) // 2 - bb[0]
        y = start_y + i * line_h
        # Drop shadow
        draw.text((x + 4, y + 4), l, font=ft, fill=(0, 0, 0, 220))
        draw.text((x, y), l, font=ft, fill=(255, 255, 255, 255))

    im.save(out_path, quality=95)
    print(f"🖼️ [CIBO Cover] Created: {out_path}")

# Caption Layout & Rendering
def fit_caption_lines(words, flags, base_sz=BASE_FONT_SZ, emp_sz=EMPH_FONT_SZ, font_path=FONT_PATH):
    sc = 1.0
    for _ in range(16):
        b = int(base_sz * sc)
        e = int(emp_sz * sc)
        ft_b = ImageFont.truetype(font_path, b)
        ft_e = ImageFont.truetype(font_path, e)

        sizes = [e if fl else b for fl in flags]
        fonts = [ft_e if fl else ft_b for fl in flags]
        sp = b * 0.28

        advs = [fonts[i].getlength(words[i]) for i in range(len(words))]
        tot = sum(advs) + sp * (len(words) - 1)
        if tot <= MAXW:
            return [list(zip(words, sizes, flags))], sc

        best = None
        for k in range(1, len(words)):
            wa = sum(advs[:k]) + sp * (k - 1)
            wb = sum(advs[k:]) + sp * (len(words) - k - 1)
            m = max(wa, wb)
            if best is None or m < best[0]:
                best = (m, k)
        if best and best[0] <= MAXW:
            k = best[1]
            return [list(zip(words[:k], sizes[:k], flags[:k])),
                    list(zip(words[k:], sizes[k:], flags[k:]))], sc
        sc *= 0.94
    raise ValueError("Legenda não cabe nas margens seguras; divida o trecho antes de renderizar")

def draw_word_tile(word, sz, font_path=FONT_PATH):
    ft = ImageFont.truetype(font_path, sz)
    asc, desc = ft.getmetrics()
    pad = int(sz * 0.5)
    tw = int(ft.getlength(word)) + pad * 2
    th = asc + desc + pad * 2

    sh = Image.new('RGBA', (tw, th), (0, 0, 0, 0))
    ImageDraw.Draw(sh).text((pad, pad + int(sz * 0.05)), word, font=ft, fill=(0, 0, 0, 200))
    sh = sh.filter(ImageFilter.GaussianBlur(sz * 0.12))

    tl = Image.new('RGBA', (tw, th), (0, 0, 0, 0))
    ImageDraw.Draw(tl).text((pad, pad), word, font=ft, fill=(255, 255, 255, 255))
    out = Image.alpha_composite(sh, tl)
    return out, pad, pad + asc, ft.getlength(word), asc, desc

def build_caption_items(words, flags, font_path=FONT_PATH):
    lines, sc = fit_caption_lines(words, flags, font_path=font_path)
    base_sp = BASE_FONT_SZ * sc * 0.28
    L = []
    for ln in lines:
        ws = [(w, s, fl) + draw_word_tile(w, s, font_path) for w, s, fl in ln]
        L.append(ws)

    asc = [max(x[7] for x in ws) for ws in L]
    des = [max(x[8] for x in ws) for ws in L]
    gap = int(max(max(s for _, s, _, _, _, _, _, _, _ in ws) for ws in L) * 0.16)
    total = sum(a + d for a, d in zip(asc, des)) + gap * (len(L) - 1)
    top = CY - total / 2.0

    items = []
    y = top
    for i, ws in enumerate(L):
        bl = y + asc[i]
        width = sum(x[6] for x in ws) + base_sp * (len(ws) - 1)
        x = (W - width) / 2.0
        for (w, s, fl, tile, ox, oy, aw, a2, d2) in ws:
            capH = s * 0.70
            items.append({
                'word': w, 'sz': s, 'fl': fl, 'tile': tile,
                'px': x, 'bl': bl,
                'ax': ox + aw / 2.0, 'ay': oy - capH / 2.0,
                'cx': x + aw / 2.0,  'cy': bl - capH / 2.0
            })
            x += aw + base_sp
        y = bl + des[i] + gap
    return items

def render_dual_captions(caps, duration, fps, out_base, font_path=FONT_PATH, encoder="cpu"):
    rate = str(fps)
    fps = float(__import__("fractions").Fraction(rate))
    """
    Renders Cal Sans motion captions to dual alpha streams:
    - {out_base}_rgb.mp4 (RGB color stream)
    - {out_base}_a.mp4 (Grayscale alpha matte stream)
    """
    import copy
    caps = copy.deepcopy(caps)
    for c in caps:
        c['items'] = build_caption_items(c['words'], c['flags'], font_path)

    rgb_out = f"{out_base}_rgb.mp4"
    a_out = f"{out_base}_a.mp4"
    nframes = int(math.ceil(duration * fps))

    enc = subprocess.Popen([
        tool('ffmpeg'), '-y', '-v', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgba',
        '-s', f'{W}x{BAND_H}', '-r', rate, '-i', '-',
        '-filter_complex', '[0:v]split[c][a];[c]format=yuv420p[cv];[a]alphaextract,format=gray[av]',
        '-map', '[cv]', *encoder_args(encoder, '6M'), rgb_out,
        '-map', '[av]', *encoder_args(encoder, '4M'), a_out
    ], stdin=subprocess.PIPE)

    blank = Image.new('RGBA', (W, BAND_H), (0, 0, 0, 0))

    for i in range(nframes):
        t = i / fps
        act = [c for c in caps if c['s'] - 0.02 <= t < c['e']]
        if not act:
            enc.stdin.write(blank.tobytes())
            continue

        cv = Image.new('RGBA', (W, BAND_H), (0, 0, 0, 0))
        for c in act:
            dt = t - c['s']

            for word_index, it in enumerate(c['items']):
                word_dt = t - c['word_starts'][word_index] if c.get('word_starts') else dt
                if word_dt < 0:
                    continue
                pe_word = min(1.0, word_dt / 0.14)
                dy = 28.0 * (1.0 - pe_word)**3
                tile = it['tile']
                scale = 1.0
                alpha = max(0.0, min(1.0, word_dt / 0.08))
                if it['fl']:
                    pw = min(1.0, max(0.0, (word_dt - 0.02) / 0.22))
                    # bounce overshoot
                    scale = 1.0 + 0.18 * math.sin(pw * math.pi)

                # composite
                tw = max(1, int(round(tile.width * scale)))
                th = max(1, int(round(tile.height * scale)))
                t_img = tile.resize((tw, th), Image.LANCZOS) if abs(scale - 1.0) > 0.01 else tile.copy()
                if alpha < 0.99:
                    a_ch = t_img.getchannel('A').point(lambda v: int(v * alpha))
                    t_img.putalpha(a_ch)
                pos_x = int(round(it['cx'] - it['ax'] * scale))
                pos_y = int(round(it['cy'] - it['ay'] * scale + dy))
                cv.alpha_composite(t_img, (pos_x, pos_y))

        enc.stdin.write(cv.tobytes())

    enc.stdin.close()
    if enc.wait() != 0:
        raise RuntimeError("Falha na renderização das legendas CIBO")
    print(f"💬 [CIBO Captions] Rendered {nframes} frames @ {fps:.2f}fps -> {rgb_out}, {a_out}")
    return rgb_out, a_out


def captions_from_transcript(transcript, start, end):
    """Map source word times to the cut, never borrow text outside its range."""
    caps = []
    for segment in transcript.get("segments", []):
        words = segment.get("words") or []
        if words:
            kept = [w for w in words if start <= float(w["start"]) < float(w["end"]) <= end and str(w.get("word", w.get("text", ""))).strip()]
            for at in range(0, len(kept), 6):
                group = kept[at:at+6]
                caps.append({"s":float(group[0]["start"])-start,"e":float(group[-1]["end"])-start,"words":[str(w.get("word",w.get("text",""))).strip() for w in group],"flags":[False]*len(group),"word_starts":[float(w["start"])-start for w in group]})
        elif float(segment.get("end", 0)) > start and float(segment.get("start", 0)) < end:
            if segment["start"] < start or segment["end"] > end:
                raise ValueError("Legenda cruza o corte sem timestamps de palavras; revise o limite ou a transcrição")
            text = str(segment.get("text", "")).strip().split()
            if text:
                caps.append({"s":segment["start"]-start,"e":segment["end"]-start,"words":text,"flags":[False]*len(text)})
    return sorted(caps, key=lambda c:c["s"])


def encoder_args(encoder, bitrate="14M"):
    if encoder not in {"auto", "cpu", "videotoolbox"}:
        raise ValueError("Encoder inválido")
    if encoder == "auto":
        import platform
        encoder = "videotoolbox" if platform.system() == "Darwin" else "cpu"
    if encoder == "videotoolbox":
        return ["-c:v", "h264_videotoolbox", "-b:v", bitrate, "-pix_fmt", "yuv420p"]
    return ["-c:v", "libx264", "-crf", "20", "-preset", "fast", "-pix_fmt", "yuv420p"]


def normalize_captions(caps, duration):
    import copy
    result = copy.deepcopy(caps)
    previous = 0.0
    for c in result:
        if not (math.isfinite(c["s"]) and math.isfinite(c["e"]) and 0 <= c["s"] < c["e"] <= duration + 0.001 and c["s"] >= previous):
            raise ValueError("Tempos de legenda inválidos; use o relógio relativo ao corte")
        words = c.get("words", [])
        if not words or any(not isinstance(w, str) or not w.strip() for w in words):
            raise ValueError("Legenda sem palavras válidas")
        c["flags"] = c.get("flags", [False] * len(words))
        if len(c["flags"]) != len(words):
            raise ValueError("Destaques não correspondem às palavras")
        if c.get("word_starts") is not None:
            times = c["word_starts"]
            if len(times) != len(words) or any(not math.isfinite(t) or not c["s"] <= t < c["e"] for t in times) or times != sorted(times):
                raise ValueError("Relógio das palavras inválido")
        previous = c["s"]
    return result


def generate_clicks_wav(caps, duration, out_wav, click_path=CLICK_SFX_PATH):
    raw = run([tool("ffmpeg"), "-v", "error", "-i", str(click_path), "-f", "s16le", "-ar", str(SR), "-ac", "1", "-"])
    sample = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
    if not len(sample):
        raise ValueError("SFX de clique vazio")
    sample *= 0.24 / max(float(np.abs(sample).max()), 1e-9)
    audio = np.zeros(int(math.ceil(duration * SR)), dtype=np.float32)
    for c in caps:
        # Without word timestamps there is one phrase-level trigger, never
        # a fabricated claim of word-level synchronization.
        times = {c["s"]}
        if c.get("word_starts"):
            times.update(t for t, emphasis in zip(c["word_starts"], c["flags"]) if emphasis)
        for t in times:
            index = int(t * SR)
            count = min(len(sample), len(audio) - index)
            if count > 0:
                audio[index:index + count] += sample[:count]
    with wave.open(str(out_wav), "w") as wf:
        wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(SR)
        wf.writeframes((np.clip(audio, -1, 1) * 32767).astype("<i2").tobytes())


def make_intro_blur_zoom(passA_path, rate, out_intro, encoder="cpu", duration=INTRO_DUR):
    from fractions import Fraction
    fps = float(Fraction(str(rate)))
    count = max(1, int(math.ceil(duration * fps)))
    raw = run([tool("ffmpeg"), "-v", "error", "-i", str(passA_path), "-frames:v", str(count), "-f", "rawvideo", "-pix_fmt", "rgb24", "-"])
    size = W * H * 3
    count = min(count, len(raw) // size)
    if count < 1:
        raise ValueError("Não foi possível preparar a abertura")
    process = subprocess.Popen([tool("ffmpeg"), "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(rate), "-i", "-", "-an", *encoder_args(encoder, "20M"), str(out_intro)], stdin=subprocess.PIPE)
    try:
        for i in range(count):
            im = Image.frombytes("RGB", (W, H), raw[i*size:(i+1)*size])
            t = i / max(1, count - 1)
            ease = 4*t**3 if t < 0.5 else 1 - (-2*t+2)**3/2
            zoom = 1.25 - 0.25*ease
            cw, ch = int(W/zoom), int(H/zoom)
            im = im.crop(((W-cw)//2, (H-ch)//2, (W+cw)//2, (H+ch)//2)).resize((W,H), Image.Resampling.LANCZOS)
            blur = 16 * (1-ease)**1.4
            if blur > 0.4: im = im.filter(ImageFilter.GaussianBlur(blur))
            process.stdin.write(im.tobytes())
    finally:
        process.stdin.close()
        status = process.wait()
    if status:
        raise RuntimeError("Falha ao renderizar abertura CIBO")
    return count/fps


def render_spilberg2_cut(master_path, t_start, t_end, headline, caps_data,
                         out_final_mp4, work_dir, cover_t_offset=4.0, *,
                         assets_dir=None, encoder="auto", intro=True,
                         filmburn=True, clicks=True, embed_cover=False):
    """Direct master cut, native rational clock, median crop and optional CIBO.

    Headline is a separate cover by default. Embed is an explicit legacy mode.
    Never edits caller captions, changes speed, or overwrites an existing final.
    """
    from fractions import Fraction
    import tempfile
    master = Path(master_path).expanduser().resolve(strict=True)
    output = Path(out_final_mp4).expanduser().resolve()
    cover = output.with_suffix(".cover.jpg")
    report = output.with_suffix(".render.json")
    if master == output or output.exists() or report.exists() or (headline and cover.exists()):
        raise FileExistsError("Preserve o original e versões existentes; escolha outra saída")
    info = probe_video(master)
    if not all(math.isfinite(t) for t in (t_start, t_end, cover_t_offset)) or not 0 <= t_start < t_end <= info["duration"] + 0.001 or cover_t_offset < 0:
        raise ValueError("Intervalo de corte inválido")
    duration = t_end - t_start
    caps = normalize_captions(caps_data or [], duration)
    assets = Path(assets_dir) if assets_dir else None
    font = str(assets/"CalSans-Regular.ttf") if assets else FONT_PATH
    burn = str(assets/"filmburn_blue.mp4") if assets else FILMBURN_PATH
    click = str(assets/"click.wav") if assets else CLICK_SFX_PATH
    required = ([font] if caps or headline else []) + ([burn] if filmburn else []) + ([click] if clicks and caps else [])
    for asset in required:
        if not Path(asset).is_file():
            raise FileNotFoundError(f"Recurso CIBO ausente: {asset}; configure assets_dir ou SPILBERG_CIBO_DIR")
    output.parent.mkdir(parents=True, exist_ok=True)
    Path(work_dir).mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="render-", dir=str(work_dir)))
    cw, ch, x, y = compute_median_face_crop(master, t_start, t_end)
    passA = work/"master-cut.mp4"
    args = [tool("ffmpeg"), "-nostdin", "-v", "error", "-y", "-ss", str(t_start), "-i", str(master), "-t", str(duration), "-map", "0:v:0", "-map", "0:a:0?", "-vf", f"crop={cw}:{ch}:{x}:{y},scale={W}:{H}:flags=lanczos,setsar=1,setpts=PTS-STARTPTS", "-fps_mode", "passthrough", *encoder_args(encoder), "-c:a", "aac", "-b:a", "192k", "-ar", str(SR)]
    if info["audio"]: args += ["-af", "asetpts=PTS-STARTPTS"]
    run(args + [str(passA)])
    if headline:
        generate_cover_card(master, t_start + min(cover_t_offset, duration/2), headline, cw, ch, x, work/"cover.jpg", y, font)
    command = [tool("ffmpeg"), "-nostdin", "-v", "error", "-y", "-i", str(passA)]
    filters = ["[0:v]setpts=PTS-STARTPTS[base]"]
    current = "base"
    index = 1
    if intro:
        intro_path = work/"intro.mp4"
        intro_duration = make_intro_blur_zoom(passA, info["rate"], intro_path, encoder, min(duration,INTRO_DUR))
        command += ["-i", str(intro_path)]
        # Composite only the opening frames onto the original clock: no
        # concat/trim replacement that can shift the entire speech timeline.
        filters += [f"[{current}][{index}:v]overlay=0:0:eof_action=pass:repeatlast=0:enable='lt(t,{intro_duration:.9f})'[opened]"]
        current = "opened"; index += 1
    if filmburn:
        command += ["-i", burn]
        filters += [f"[{index}:v]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={info['rate']},setpts=PTS-STARTPTS,format=gbrp,tpad=stop_mode=add:stop_duration={duration+1}:color=black[burn]", f"[{current}]format=gbrp[bodyrgb]", "[bodyrgb][burn]blend=all_mode=screen:shortest=1[burned]"]
        current = "burned"; index += 1
    if caps:
        rgb, alpha = render_dual_captions(caps, duration, info["rate"], str(work/"captions"), font, encoder)
        command += ["-i", rgb, "-i", alpha]
        filters += [f"[{index}:v][{index+1}:v]alphamerge[caption]",f"[{current}][caption]overlay=0:{BAND_Y}:eof_action=pass:repeatlast=0[captioned]"]
        current = "captioned"; index += 2
    audio = "0:a:0" if info["audio"] else None
    if clicks and caps:
        sfx = work/"clicks.wav";generate_clicks_wav(caps,duration,sfx,click)
        command += ["-i",str(sfx)]
        if audio:
            filters += [f"[0:a:0][{index}:a]amix=inputs=2:duration=first:normalize=0[voice]"]
            audio = "[voice]"
        else: audio = f"{index}:a:0"
        index += 1
    expected = duration
    if embed_cover:
        if not headline: raise ValueError("Inserir capa no vídeo exige headline")
        frame = float(1/Fraction(info["rate"]))
        command += ["-loop","1","-framerate",info["rate"],"-t",str(frame),"-i",str(work/"cover.jpg")]
        filters += [f"[{index}:v]setsar=1,format=yuv420p[cover]",f"[cover][{current}]concat=n=2:v=1:a=0[withcover]"]
        current = "withcover"; expected += frame
        if audio:
            label = audio if audio.startswith('[') else f"[{audio}]"
            filters += [f"anullsrc=r={SR}:cl=stereo,atrim=duration={frame},asetpts=PTS-STARTPTS[silence]",f"[silence]{label}concat=n=2:v=0:a=1[covered_audio]"]
            audio = "[covered_audio]"
    temporary = work/"final.mp4"
    command += ["-filter_complex", ";".join(filters), "-map", f"[{current}]"]
    if audio: command += ["-map",audio]
    command += ["-fps_mode","passthrough",*encoder_args(encoder,"8M"),"-c:a","aac","-b:a","192k","-t",str(expected),"-movflags","+faststart",str(temporary)]
    run(command)
    run([tool("ffmpeg"),"-v","error","-xerror","-i",str(temporary),"-f","null","-"])
    result = probe_video(temporary)
    video = next(s for s in result["streams"] if s["codec_type"] == "video")
    audio_stream = next((s for s in result["streams"] if s["codec_type"] == "audio"), None)
    delta = abs(float(video.get("duration",expected))-float(audio_stream.get("duration",expected))) if audio_stream else None
    tolerance = 2/info["fps"] + 0.025
    if abs(result["duration"]-expected) > tolerance or (delta is not None and delta > tolerance):
        raise RuntimeError("QA de relógio rejeitou a saída; original e render temporário preservados")
    if output.exists(): raise FileExistsError("Saída criada durante render; versão preservada")
    # Exclusive final publication, without replacing another worker's result.
    import shutil
    with temporary.open('rb') as src, output.open('xb') as dst: shutil.copyfileobj(src,dst)
    if headline:
        with (work/'cover.jpg').open('rb') as src, cover.open('xb') as dst: shutil.copyfileobj(src,dst)
    report.write_text(json.dumps({"engine":"spilberg2", "source":str(master), "start":t_start,"end":t_end,"source_frame_rate":info["rate"],"output_frame_rate":result["rate"],"expected_duration":expected,"output_duration":result["duration"],"av_duration_delta":delta,"full_decode":True,"speed":1,"headline_in_video":embed_cover,"cover":str(cover) if headline else None,"encoder":encoder,"work_dir":str(work)},indent=2)+"\n")
    return str(output)


def main(argv=None):
    import argparse
    parser = argparse.ArgumentParser(description="Spilberg 2.0 master renderer")
    parser.add_argument("--master",required=True);parser.add_argument("--start",type=float,required=True);parser.add_argument("--end",type=float,required=True)
    parser.add_argument("--output",required=True);parser.add_argument("--headline",default="");parser.add_argument("--caps-json")
    parser.add_argument("--work-dir",default="/tmp/spilberg2_work");parser.add_argument("--cover-offset",type=float,default=4.0)
    parser.add_argument("--assets-dir");parser.add_argument("--encoder",choices=["auto","cpu","videotoolbox"],default="auto")
    parser.add_argument("--embed-cover",action="store_true")
    for effect in ["intro","filmburn","clicks"]: parser.add_argument("--no-"+effect,action="store_true")
    args = parser.parse_args(argv)
    caps = json.loads(Path(args.caps_json).read_text()) if args.caps_json else []
    output = render_spilberg2_cut(args.master,args.start,args.end,args.headline.replace("\\n","\n"),caps,args.output,args.work_dir,args.cover_offset,assets_dir=args.assets_dir,encoder=args.encoder,intro=not args.no_intro,filmburn=not args.no_filmburn,clicks=not args.no_clicks,embed_cover=args.embed_cover)
    print(json.dumps({"output":output,"report":str(Path(output).with_suffix('.render.json'))}))

if __name__ == "__main__":
    main()
