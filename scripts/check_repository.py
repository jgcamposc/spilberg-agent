#!/usr/bin/env python3
"""Fail release checks when tracked files violate the public-repository boundary."""

from __future__ import annotations

import subprocess
from pathlib import Path


MAX_FILE_BYTES = 20 * 1024 * 1024
BLOCKED_SUFFIXES = {".mp4", ".mov", ".mkv", ".aiff", ".wav", ".mp3", ".srt", ".pem", ".key"}
BLOCKED_NAMES = {".env", ".env.local", ".env.production"}
SENSITIVE_MARKERS = ("/Users/joaoguilhermecampos/", "PEXELS_API_KEY=")


def tracked_files(root: Path) -> list[Path]:
    raw = subprocess.check_output(["git", "ls-files", "-z"], cwd=root)
    return [root / item for item in raw.decode("utf-8").split("\0") if item]


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    violations: list[str] = []
    for path in tracked_files(root):
        relative = path.relative_to(root)
        if path.name in BLOCKED_NAMES or path.suffix.lower() in BLOCKED_SUFFIXES:
            violations.append(f"arquivo bloqueado no repositório: {relative}")
            continue
        if path.stat().st_size > MAX_FILE_BYTES:
            violations.append(f"arquivo acima de 20 MB: {relative}")
            continue
        if path.suffix.lower() not in {".py", ".md", ".yaml", ".yml", ".json", ".toml", ".sh", ".ps1", ".txt"}:
            continue
        content = path.read_text(encoding="utf-8", errors="ignore")
        if any(marker in content for marker in SENSITIVE_MARKERS):
            violations.append(f"caminho pessoal ou credencial literal: {relative}")
    if violations:
        raise SystemExit("\n".join(violations))
    print("Escopo público validado: sem mídia, credenciais ou caminhos pessoais rastreados.")


if __name__ == "__main__":
    main()
