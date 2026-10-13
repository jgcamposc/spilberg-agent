"""Native source clock shared by the approved-plan and CIBO renderers."""
from fractions import Fraction
import json
import os
from pathlib import Path
import shutil
import sys
import platform as system_platform
import subprocess


def resolve_executable(executable, project_root):
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
    # Do not resolve the interpreter symlink here. On macOS, a virtualenv
    # commonly points at the system Python; resolving it would discard the
    # virtualenv's bin directory and hide console tools such as whisper.
    active_venv_bin = Path(sys.executable).parent
    active_prefix = Path(sys.prefix)
    candidates = [
        active_venv_bin / f"{executable}{suffix}",
        active_prefix / "bin" / executable,
        active_prefix / "Scripts" / f"{executable}{suffix}",
        project_root / ".venv" / "bin" / executable,
        project_root / ".venv" / "Scripts" / f"{executable}{suffix}",
        project_root / "lib" / "bin" / f"{executable}{suffix}",
    ]
    if (
        executable == "auto-editor"
        and system_platform.system() == "Darwin"
        and system_platform.machine() == "arm64"
    ):
        bundled_auto_editor = project_root / "lib" / "bin" / "auto-editor"
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
        "Rode 'spilberg doctor' e depois o setup da plataforma."
    )

def tool(name):
    return resolve_executable(name, Path(__file__).resolve().parents[2])


def run(args, **kwargs):
    result = subprocess.run(args, capture_output=True, check=False, **kwargs)
    if result.returncode:
        stderr = result.stderr.decode(errors="replace") if isinstance(result.stderr, bytes) else result.stderr
        raise RuntimeError(f"{Path(args[0]).name} falhou ({result.returncode}): {stderr[-2000:]}")
    return result.stdout


def probe_video(path, ffprobe=None):
    data = json.loads(run([ffprobe or tool("ffprobe"), "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)], text=True))
    video = next((s for s in data["streams"] if s.get("codec_type") == "video"), None)
    if not video:
        raise ValueError("O master precisa ter uma faixa de vídeo")
    rate = Fraction(video.get("r_frame_rate") or video.get("avg_frame_rate") or "0")
    if rate <= 0:
        raise ValueError("FPS nativo inválido no master")
    duration = float(data.get("format", {}).get("duration") or video.get("duration") or 0)
    if duration <= 0:
        raise ValueError("Duração inválida no master")
    return {"width": int(video["width"]), "height": int(video["height"]), "rate": str(rate), "fps": float(rate), "duration": duration, "audio": any(s.get("codec_type") == "audio" for s in data["streams"]), "streams": data["streams"]}
