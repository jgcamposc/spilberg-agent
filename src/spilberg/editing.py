from __future__ import annotations

import asyncio
import json
import os
import platform as system_platform
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Iterable, Optional


class CommandExecutionError(RuntimeError):
    pass


class SpilbergOrchestrator:
    """Músculo local do Spilberg: executa planos já decididos e aprovados."""

    def __init__(self, workspace_dir: str):
        self.project_root = Path(__file__).resolve().parents[2]
        self.workspace_dir = Path(workspace_dir).resolve()
        self.inbox = self.workspace_dir / "inbox"
        self.outbox = self.workspace_dir / "outbox"
        self.plans = self.workspace_dir / "plans"
        self.temp = self.workspace_dir / "temp" / "jobs"

        for directory in (self.inbox, self.outbox, self.plans, self.temp):
            directory.mkdir(parents=True, exist_ok=True)

    def _resolve_executable(self, executable: str) -> str:
        requested = Path(executable).expanduser()
        if requested.parent != Path("."):
            if requested.is_file():
                return str(requested.resolve())
            raise FileNotFoundError(f"Executável não encontrado: {requested}")

        env_names = {
            "ffmpeg": "SPILBERG_FFMPEG",
            "ffprobe": "SPILBERG_FFPROBE",
            "whisper": "SPILBERG_WHISPER",
            "yt-dlp": "SPILBERG_YTDLP",
            "edge-tts": "SPILBERG_EDGE_TTS",
            "auto-editor": "SPILBERG_AUTO_EDITOR",
        }
        env_path = os.getenv(env_names.get(executable, ""))
        if env_path and Path(env_path).is_file():
            return str(Path(env_path).resolve())

        suffix = ".exe" if os.name == "nt" else ""
        active_venv_bin = Path(sys.executable).resolve().parent
        candidates = [
            active_venv_bin / f"{executable}{suffix}",
            self.project_root / ".venv" / "bin" / executable,
            self.project_root / ".venv" / "Scripts" / f"{executable}{suffix}",
            self.project_root / "lib" / "bin" / f"{executable}{suffix}",
        ]
        if (
            executable == "auto-editor"
            and system_platform.system() == "Darwin"
            and system_platform.machine() == "arm64"
        ):
            bundled_auto_editor = self.project_root / "lib" / "bin" / "auto-editor"
            candidates.remove(bundled_auto_editor)
            candidates.insert(0, bundled_auto_editor)
        for candidate in candidates:
            if candidate.is_file():
                return str(candidate.resolve())

        on_path = shutil.which(executable)
        if on_path:
            return on_path

        if executable == "ffmpeg":
            try:
                import imageio_ffmpeg

                bundled = Path(imageio_ffmpeg.get_ffmpeg_exe())
                if bundled.is_file():
                    return str(bundled.resolve())
            except (ImportError, RuntimeError):
                pass

        raise FileNotFoundError(
            f"Executável '{executable}' não encontrado. "
            "Rode 'python spilberg.py doctor' e depois o setup da plataforma."
        )

    async def _run_command(self, cmd: list[str], name: str) -> tuple[str, str]:
        if not cmd:
            raise ValueError("comando vazio")

        executable = self._resolve_executable(cmd[0])
        command = [executable, *cmd[1:]]
        env = os.environ.copy()
        try:
            import certifi

            env["SSL_CERT_FILE"] = certifi.where()
        except ImportError:
            pass

        print(f"🎬 Iniciando [{name}]...")
        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
        stdout_raw, stderr_raw = await process.communicate()
        stdout = stdout_raw.decode(errors="replace")
        stderr = stderr_raw.decode(errors="replace")
        if process.returncode != 0:
            detail = stderr[-5000:] or stdout[-5000:] or "sem detalhes"
            raise CommandExecutionError(
                f"{name} falhou com código {process.returncode}:\n{detail}"
            )
        print(f"✅ Concluído [{name}].")
        return stdout, stderr

    @staticmethod
    def _require_file(path: Path, label: str) -> Path:
        if not path.is_file() or path.stat().st_size <= 0:
            raise RuntimeError(f"{label} não foi gerado ou está vazio: {path}")
        return path

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = sha256()
        with path.open("rb") as file:
            for chunk in iter(lambda: file.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _video_duration(path: Path) -> float:
        import cv2

        capture = cv2.VideoCapture(str(path))
        if not capture.isOpened():
            raise RuntimeError(f"Não foi possível abrir o vídeo: {path}")
        fps = float(capture.get(cv2.CAP_PROP_FPS) or 0)
        frames = float(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        capture.release()
        if fps <= 0 or frames <= 0:
            raise RuntimeError(f"Metadados de duração inválidos: {path}")
        return frames / fps

    @staticmethod
    def _map_time(original_time: float, segments: Iterable) -> Optional[float]:
        current = 0.0
        for segment in segments:
            if segment.start_time <= original_time <= segment.end_time:
                return current + (original_time - segment.start_time)
            current += segment.end_time - segment.start_time
        return None

    def _output_path(self, plan_path: Path) -> Path:
        base = self.outbox / f"final_{plan_path.stem}.mp4"
        if not base.exists():
            return base
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        return self.outbox / f"final_{plan_path.stem}_{stamp}.mp4"

    async def ingest_video(self, video_url: str) -> Path:
        if not video_url.startswith(("http://", "https://")):
            raise ValueError("video_url precisa ser HTTP(S)")
        template = self.inbox / "download_%(id)s.%(ext)s"
        stdout, _ = await self._run_command(
            [
                "yt-dlp",
                "--no-overwrites",
                "--print",
                "after_move:filepath",
                "-o",
                str(template),
                "--format",
                "bestvideo[ext=mp4]+bestaudio[ext=m4a]/mp4",
                video_url,
            ],
            "Download com yt-dlp",
        )
        candidates = [Path(line.strip()) for line in stdout.splitlines() if line.strip()]
        if not candidates:
            raise RuntimeError("yt-dlp não informou o caminho do arquivo baixado")
        return self._require_file(candidates[-1], "Vídeo baixado")

    async def transcribe_video(self, input_path: str, model: str = "base") -> Path:
        source = self._require_file(Path(input_path).resolve(), "Vídeo de entrada")
        json_path = self.plans / f"{source.stem}.json"
        if json_path.exists():
            raise FileExistsError(
                f"Transcrição já existe e não será sobrescrita: {json_path}"
            )
        await self._run_command(
            [
                "whisper",
                str(source),
                "--model",
                model,
                "--output_dir",
                str(self.plans),
                "--word_timestamps",
                "True",
                "--output_format",
                "json",
            ],
            f"Transcrição Whisper ({model})",
        )
        return self._require_file(json_path, "Transcrição Whisper")

    def generate_ai_editing_prompt(self, transcript_json_path: str) -> str:
        raise RuntimeError(
            "Este atalho foi removido para evitar enviar uma transcrição inteira ao "
            "editor. Use `spilberg prepare <video> --transcript <arquivo.json>` e "
            "entregue o evidence.md ao skill $spilberg-editor."
        )

    def approve_plan(self, plan_path: str) -> Path:
        from .edit_plan import EditPlan, PlanStatus

        path = Path(plan_path).resolve()
        plan = EditPlan.load_json(str(path))
        plan.status = PlanStatus.APPROVED
        plan.export_json(str(path))
        return path

    async def execute_plan(
        self,
        plan_path: str,
        transcript_path: str | None = None,
    ) -> Path:
        from .edit_plan import EditPlan, EffectType, PlanStatus

        plan_file = Path(plan_path).resolve()
        plan = EditPlan.load_json(str(plan_file))
        if plan.status != PlanStatus.APPROVED:
            raise PermissionError(
                f"Render bloqueado: plano está {plan.status.value}. "
                "Aprovação humana explícita é obrigatória."
            )

        source_path = Path(plan.video_source).expanduser()
        if not source_path.is_absolute():
            source_path = self.project_root / source_path
        source = self._require_file(source_path.resolve(), "Vídeo original")
        source_duration = self._video_duration(source)
        segments = [segment for segment in plan.segments if segment.keep]
        for segment in segments:
            if segment.end_time > source_duration + 0.15:
                raise ValueError(
                    f"Segmento {segment.start_time}-{segment.end_time}s excede "
                    f"a duração da fonte ({source_duration:.3f}s)"
                )

        duration_delta = abs(plan.selected_duration - plan.target_duration)
        allowed_delta = max(2.0, plan.target_duration * 0.05)
        if duration_delta > allowed_delta:
            raise ValueError(
                f"Duração selecionada ({plan.selected_duration:.3f}s) diverge do alvo "
                f"({plan.target_duration:.3f}s) além da tolerância ({allowed_delta:.3f}s)"
            )

        transcript = Path(transcript_path).resolve() if transcript_path else None
        needs_transcript = any(
            effect.effect_type == EffectType.SUBTITLE_STYLE for effect in plan.effects
        )
        if needs_transcript and (not transcript or not transcript.is_file()):
            raise FileNotFoundError(
                "O plano pede legendas, mas transcript_path não existe."
            )

        job_dir = Path(
            tempfile.mkdtemp(prefix=f"{plan_file.stem}-", dir=str(self.temp))
        )
        chunk_files = []
        for index, segment in enumerate(segments):
            chunk = job_dir / f"chunk_{index:03d}.mp4"
            await self._run_command(
                [
                    "ffmpeg",
                    "-nostdin",
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-y",
                    "-ss",
                    f"{segment.start_time:.6f}",
                    "-i",
                    str(source),
                    "-t",
                    f"{segment.end_time - segment.start_time:.6f}",
                    "-c:v",
                    "libx264",
                    "-c:a",
                    "aac",
                    "-preset",
                    "fast",
                    "-pix_fmt",
                    "yuv420p",
                    str(chunk),
                ],
                f"Corte {index + 1}/{len(segments)}",
            )
            chunk_files.append(self._require_file(chunk, f"Trecho {index}"))

        concat_file = job_dir / "concat.txt"
        concat_file.write_text(
            "".join(f"file '{chunk.as_posix()}'\n" for chunk in chunk_files),
            encoding="utf-8",
        )
        raw_concat = job_dir / "raw_concat.mp4"
        await self._run_command(
            [
                "ffmpeg",
                "-nostdin",
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(concat_file),
                "-c",
                "copy",
                str(raw_concat),
            ],
            "Concatenação",
        )
        self._require_file(raw_concat, "Vídeo concatenado")

        platform = plan.target_platform.value
        final_output = self._output_path(plan_file)
        vertical = platform in {"tiktok", "instagram", "reels", "shorts"}
        target_w = 1080 if vertical else 1920
        target_h = 1920 if vertical else 1080
        target_ratio = 9 / 16 if vertical else 16 / 9

        from .reframer import get_smart_crop_params
        from .subtitles import generate_ass_subtitles

        brolls = [e for e in plan.effects if e.effect_type == EffectType.B_ROLL]
        split_screens = [e for e in plan.effects if e.effect_type == EffectType.SPLIT_SCREEN]
        ducking_effects = [e for e in plan.effects if e.effect_type == EffectType.AUDIO_DUCKING]
        if len(ducking_effects) > 1:
            raise ValueError("O plano aceita no máximo um AUDIO_DUCKING")
        valid_brolls = []

        for b in brolls:
            source_type = b.parameters.get("source")
            on_failure = b.parameters.get("on_failure", "fail")
            if source_type == "pexels_api":
                from .pexels import PexelsClient
                import hashlib

                query = b.parameters.get("search_query")
                if not query:
                    if on_failure == "skip":
                        print("Aviso: Pexels sem search_query; B-roll ignorado por política explícita.")
                        continue
                    raise ValueError("Pexels exige search_query para um B-roll obrigatório")

                orientation = b.parameters.get("orientation", "landscape") if not vertical else "portrait"
                try:
                    client = PexelsClient()
                    print(f"Buscando B-Roll no Pexels para: '{query}' ({orientation})...")
                    url = await asyncio.to_thread(client.search_video, query, orientation)
                    if url:
                        hash_q = hashlib.md5(f"{query}_{orientation}".encode()).hexdigest()
                        broll_dest = job_dir / f"pexels_{hash_q}.mp4"
                        print(f"Baixando B-Roll para {broll_dest}...")
                        await asyncio.to_thread(client.download_video, url, broll_dest)
                        b.parameters["media_path"] = str(broll_dest.absolute())
                        valid_brolls.append(b)
                    else:
                        if on_failure == "skip":
                            print(f"Aviso: Pexels sem resultado para '{query}'; B-roll ignorado por política explícita.")
                            continue
                        raise RuntimeError(f"Pexels não encontrou B-roll obrigatório para '{query}'")
                except Exception as error:
                    if on_failure != "skip":
                        raise RuntimeError(f"B-roll obrigatório falhou para '{query}'") from error
                    print(f"Aviso: Falha ao usar Pexels API: {error}. B-roll ignorado por política explícita.")
                    continue
            else:
                valid_brolls.append(b)

        brolls = valid_brolls

        ffmpeg_cmd = [
            "ffmpeg",
            "-nostdin",
            "-hide_banner",
            "-loglevel",
            "error",
            "-n",
            "-i",
            str(raw_concat),
        ]
        for b in brolls:
            media_path = b.parameters.get("media_path")
            if not media_path:
                raise ValueError("Efeito B_ROLL precisa do parâmetro 'media_path'")
            media_full_path = self.project_root / media_path if not Path(media_path).is_absolute() else Path(media_path)
            if not media_full_path.exists():
                raise FileNotFoundError(f"Arquivo de B-Roll não encontrado: {media_full_path}")
            local_start = self._map_time(b.start_time, segments)
            if local_start is None:
                local_start = 0.0
            ffmpeg_cmd.extend(["-stream_loop", "-1", "-itsoffset", f"{local_start:.4f}", "-i", str(media_full_path)])

        split_input_indices = []
        for split in split_screens:
            media_path = split.parameters["media_path"]
            media_full_path = self.project_root / media_path if not Path(media_path).is_absolute() else Path(media_path)
            if not media_full_path.is_file():
                raise FileNotFoundError(f"Arquivo de split-screen não encontrado: {media_full_path}")
            split_input_indices.append(1 + len(brolls) + len(split_input_indices))
            ffmpeg_cmd.extend(["-stream_loop", "-1", "-i", str(media_full_path)])

        music_input_index: int | None = None
        ducking_effect = ducking_effects[0] if ducking_effects else None
        if ducking_effect:
            music_path = ducking_effect.parameters["music_path"]
            music_full_path = self.project_root / music_path if not Path(music_path).is_absolute() else Path(music_path)
            if not music_full_path.is_file():
                raise FileNotFoundError(f"Trilha para ducking não encontrada: {music_full_path}")
            music_input_index = 1 + len(brolls) + len(split_screens)
            ffmpeg_cmd.extend(["-stream_loop", "-1", "-i", str(music_full_path)])

        filter_graph = []
        last_stream = "[0:v]"

        if vertical:
            crop_filter = get_smart_crop_params(
                str(raw_concat), target_ratio=target_ratio, target_w=target_w, target_h=target_h
            )
            filter_graph.append(f"{last_stream}{crop_filter}[v_cropped]")
        else:
            scale_pad = (
                f"scale={target_w}:{target_h}:force_original_aspect_ratio=decrease,"
                f"pad={target_w}:{target_h}:(ow-iw)/2:(oh-ih)/2:color=black"
            )
            filter_graph.append(f"{last_stream}{scale_pad}[v_cropped]")
        
        last_stream = "[v_cropped]"

        zoom_parts = ["1"]
        for effect in plan.effects:
            if effect.effect_type != EffectType.ZOOM_IN:
                continue
            local_start = self._map_time(effect.start_time, segments)
            local_end = self._map_time(effect.end_time, segments)
            if local_start is None or local_end is None or local_end <= local_start:
                raise ValueError(
                    f"Efeito zoom fora dos segmentos: "
                    f"{effect.start_time}-{effect.end_time}s"
                )
            amount = float(effect.parameters.get("amount", 0.2))
            if not 0 < amount <= 0.35:
                raise ValueError("zoom amount precisa estar entre 0 e 0.35")
            zoom_parts.append(
                f"{amount:.4f}*between(it,{local_start:.4f},{local_end:.4f})"
            )
        if len(zoom_parts) > 1:
            zoom_expr = "+".join(zoom_parts)
            zoom_filter = (
                "zoompan="
                f"z='{zoom_expr}':d=1:"
                "x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
                f"s={target_w}x{target_h}:fps=30"
            )
            filter_graph.append(f"{last_stream}{zoom_filter}[v_zoomed]")
            last_stream = "[v_zoomed]"

        for idx, b in enumerate(brolls):
            local_start = self._map_time(b.start_time, segments)
            local_end = self._map_time(b.end_time, segments)
            if local_start is None or local_end is None or local_end <= local_start:
                continue
            input_idx = idx + 1
            transition = b.parameters.get("transition", "cut")
            fade_duration = 0.3

            if transition == "fade" and (local_end - local_start > fade_duration * 2):
                alpha_fade = (
                    f",format=yuva420p,"
                    f"fade=t=in:st={local_start:.4f}:d={fade_duration}:alpha=1,"
                    f"fade=t=out:st={local_end-fade_duration:.4f}:d={fade_duration}:alpha=1"
                )
            else:
                alpha_fade = ""

            broll_scale = (
                f"[{input_idx}:v]scale={target_w}:{target_h}:force_original_aspect_ratio=decrease,"
                f"pad={target_w}:{target_h}:(ow-iw)/2:(oh-ih)/2:color=black"
                f"{alpha_fade}[broll{idx}]"
            )
            filter_graph.append(broll_scale)
            overlay_filter = (
                f"{last_stream}[broll{idx}]overlay=x=0:y=0:eof_action=pass:"
                f"enable='between(t,{local_start:.4f},{local_end:.4f})'[v_overlaid_{idx}]"
            )
            filter_graph.append(overlay_filter)
            last_stream = f"[v_overlaid_{idx}]"

        for split_index, (split, input_index) in enumerate(zip(split_screens, split_input_indices)):
            local_start = self._map_time(split.start_time, segments)
            local_end = self._map_time(split.end_time, segments)
            if local_start is None or local_end is None:
                raise ValueError("SPLIT_SCREEN precisa estar dentro dos segmentos selecionados")
            if local_start > 0.05 or abs(local_end - plan.selected_duration) > 0.05:
                raise ValueError("SPLIT_SCREEN v1 precisa cobrir a saída inteira")
            layout = split.parameters.get("layout", "top_bottom")
            if layout == "top_bottom":
                pane_w, pane_h, stack = target_w, target_h // 2, "vstack"
            else:
                pane_w, pane_h, stack = target_w // 2, target_h, "hstack"
            main_label = f"split_main_{split_index}"
            aux_label = f"split_aux_{split_index}"
            output_label = f"v_split_{split_index}"
            pane_filter = (
                f"scale={pane_w}:{pane_h}:force_original_aspect_ratio=decrease,"
                f"pad={pane_w}:{pane_h}:(ow-iw)/2:(oh-ih)/2:color=black"
            )
            filter_graph.append(f"{last_stream}{pane_filter}[{main_label}]")
            filter_graph.append(
                f"[{input_index}:v]setpts=PTS-STARTPTS,trim=duration={plan.selected_duration:.6f},"
                f"{pane_filter}[{aux_label}]"
            )
            filter_graph.append(f"[{main_label}][{aux_label}]{stack}=inputs=2[{output_label}]")
            last_stream = f"[{output_label}]"

        text_effects = [
            effect
            for effect in plan.effects
            if effect.effect_type
            in {EffectType.HEADLINE, EffectType.CTA, EffectType.SUBTITLE_STYLE}
        ]
        if text_effects:
            if transcript and transcript.is_file():
                subtitle_source = transcript
            else:
                subtitle_source = job_dir / "empty_transcript.json"
                subtitle_source.write_text('{"segments":[]}', encoding="utf-8")

            style_effect = next(
                (
                    effect
                    for effect in plan.effects
                    if effect.effect_type == EffectType.SUBTITLE_STYLE
                ),
                None,
            )
            style_name = (
                str(style_effect.parameters.get("style", "hormozi"))
                if style_effect
                else "hormozi"
            )
            custom_color = (
                style_effect.parameters.get("color") if style_effect else None
            )
            ass_path = job_dir / "overlays.ass"
            generate_ass_subtitles(
                segments,
                str(subtitle_source),
                str(ass_path),
                style_name=style_name,
                custom_color=custom_color,
                effects=plan.effects,
                map_time=lambda value: self._map_time(value, segments),
                target_w=target_w,
                target_h=target_h,
            )
            escaped_ass = ass_path.as_posix().replace(":", r"\:")
            sub_filter = f"{last_stream}subtitles='{escaped_ass}'[v_subbed]"
            filter_graph.append(sub_filter)
            last_stream = "[v_subbed]"

        audio_map = ["-map", "0:a?"]
        if ducking_effect and music_input_index is not None:
            volume = float(ducking_effect.parameters.get("music_volume", 0.18))
            threshold = float(ducking_effect.parameters.get("threshold", 0.03))
            if not 0.001 <= threshold <= 0.2:
                raise ValueError("AUDIO_DUCKING threshold deve estar entre 0.001 e 0.2")
            filter_graph.append(
                f"[{music_input_index}:a]atrim=duration={plan.selected_duration:.6f},"
                f"volume={volume:.4f}[music_bed];"
                f"[music_bed][0:a]sidechaincompress=threshold={threshold:.4f}:ratio=12:attack=20:release=300[music_ducked];"
                f"[0:a][music_ducked]amix=inputs=2:duration=first:normalize=0[a_mixed]"
            )
            audio_map = ["-map", "[a_mixed]"]

        ffmpeg_cmd.extend([
            "-filter_complex",
            ";".join(filter_graph),
            "-map",
            last_stream,
            *audio_map,
            "-c:v",
            "libx264",
            "-crf",
            "20",
            "-preset",
            "fast",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-movflags",
            "+faststart",
            str(final_output),
        ])

        await self._run_command(ffmpeg_cmd, f"Render {platform}")

        self._require_file(final_output, "Vídeo final")
        rendered_duration = self._video_duration(final_output)
        if abs(rendered_duration - plan.selected_duration) > 1.0:
            raise RuntimeError(
                f"Duração final inesperada: {rendered_duration:.3f}s; "
                f"esperado {plan.selected_duration:.3f}s"
            )

        manifest = {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "plan": str(plan_file),
            "plan_sha256": self._sha256(plan_file),
            "source": str(source),
            "source_sha256": self._sha256(source),
            "output": str(final_output),
            "output_sha256": self._sha256(final_output),
            "platform": platform,
            "expected_duration": plan.selected_duration,
            "rendered_duration": rendered_duration,
            "anchor_method": "fixed_median",
        }
        (job_dir / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"✅ Vídeo final validado: {final_output}")
        return final_output

    async def validate_output(self, output_path: str, full_decode: bool = True) -> None:
        output = self._require_file(Path(output_path).resolve(), "Vídeo para validar")
        command = [
            "ffmpeg",
            "-nostdin",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(output),
        ]
        if not full_decode:
            command.extend(["-t", "1"])
        command.extend(["-f", "null", "-"])
        await self._run_command(command, "Validação de decodificação")

    async def analyze_video(self, video_path: str, transcript_path: str):
        raise RuntimeError(
            "Não há um SpilbergAnalyzer autônomo instalado. A decisão editorial é "
            "feita pelo Codex usando o EvidencePack produzido por `spilberg prepare`."
        )

    def register_feedback(self, feedback: str) -> None:
        raise RuntimeError(
            "Feedback é associado a um job: use `spilberg feedback <job-id> "
            "--accepted --rule <regra>`."
        )

    def register_approval(
        self,
        plan_path: str,
        output_path: str,
        feedback: str = "",
    ) -> Path:
        raise RuntimeError(
            "Aprovação é imutável e associada a um job: use `spilberg approve "
            "<job-id> --approval-text <texto>`."
        )

    async def render_visuals(self, video_path: str, transcript_json_path: str):
        raise NotImplementedError(
            "HyperFrames não está integrado. O diretório lib/hyperframes é apenas "
            "um esqueleto e não deve ser anunciado como renderer funcional."
        )

    async def generate_edge_tts_audio(
        self,
        text: str,
        voice: str = "pt-BR-AntonioNeural",
    ) -> Path:
        if not text.strip():
            raise ValueError("texto de locução vazio")
        output = self.plans / "voiceover_edge_tts.mp3"
        if output.exists():
            raise FileExistsError(output)
        await self._run_command(
            [
                "edge-tts",
                "--voice",
                voice,
                "--text",
                text,
                "--write-media",
                str(output),
            ],
            "Locução Edge TTS",
        )
        return self._require_file(output, "Locução Edge TTS")

    async def generate_synthetic_audio(
        self,
        text: str,
        voice: str = "pt-BR-AntonioNeural",
    ) -> Path:
        return await self.generate_edge_tts_audio(text, voice)

    async def generate_synthetic_video(self, script_text: str):
        raise NotImplementedError(
            "Geração sintética com MoneyPrinterTurbo, Chatterbox ou Manim não está "
            "integrada. B-roll existe somente como efeito dentro de um EditPlan para "
            "uma fonte de vídeo já existente."
        )

    async def auto_edit_video(
        self,
        input_path: str,
        output_name: str = "final_cut.mp4",
    ) -> Path:
        source = self._require_file(Path(input_path).resolve(), "Vídeo de entrada")
        output = self.outbox / Path(output_name).name
        if output.exists():
            raise FileExistsError(
                f"Saída existente não será sobrescrita: {output}"
            )
        await self._run_command(
            [
                "auto-editor",
                str(source),
                "--margin",
                "0.2sec",
                "-o",
                str(output),
            ],
            "Auto-Editor",
        )
        return self._require_file(output, "Saída Auto-Editor")


if __name__ == "__main__":
    print("Use: python spilberg.py --help")
