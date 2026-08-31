from pathlib import Path

import pytest

from spilberg.editing import SpilbergOrchestrator

def test_orchestrator_initialization(tmp_path):
    orchestrator = SpilbergOrchestrator(str(tmp_path))
    assert orchestrator.workspace_dir == tmp_path
    assert (tmp_path / "inbox").exists()
    assert (tmp_path / "outbox").exists()
    assert (tmp_path / "plans").exists()
    assert (tmp_path / "temp" / "jobs").exists()


def test_orchestrator_finds_tools_from_active_environment_outside_repo(tmp_path, monkeypatch):
    """Installed console tools must not depend on a checkout-local .venv."""
    monkeypatch.chdir(tmp_path)
    orchestrator = SpilbergOrchestrator(str(tmp_path / "workspace"))
    for executable in ("whisper", "auto-editor"):
        resolved = Path(orchestrator._resolve_executable(executable))
        assert resolved.is_file()
