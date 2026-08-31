from __future__ import annotations

import os
from pathlib import Path


def repository_root() -> Path:
    return Path(__file__).resolve().parents[2]


def runtime_root() -> Path:
    override = os.getenv("SPILBERG_RUNTIME_DIR")
    if override:
        return Path(override).expanduser().resolve()
    if os.name == "nt":
        base = Path(os.getenv("LOCALAPPDATA", str(Path.home() / "AppData" / "Local")))
        return base / "Spilberg"
    return Path.home() / "Library" / "Application Support" / "Spilberg"


def ensure_runtime() -> Path:
    root = runtime_root()
    for name in ("config", "models", "brain-local", "jobs", "cache", "outputs", "inbox"):
        (root / name).mkdir(parents=True, exist_ok=True)
    local_rules = root / "brain-local" / "learned_rules.md"
    if not local_rules.exists():
        local_rules.write_text(
            "# Regras locais confirmadas\n\n"
            "Este arquivo e pessoal. Somente feedback humano explicitamente reutilizavel entra aqui.\n",
            encoding="utf-8",
        )
    return root


def base_brain_root() -> Path:
    return repository_root() / "brain" / "base"
