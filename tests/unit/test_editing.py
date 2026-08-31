import pytest
from spilberg.editing import SpilbergOrchestrator

def test_orchestrator_initialization(tmp_path):
    orchestrator = SpilbergOrchestrator(str(tmp_path))
    assert orchestrator.workspace_dir == tmp_path
    assert (tmp_path / "inbox").exists()
    assert (tmp_path / "outbox").exists()
    assert (tmp_path / "plans").exists()
    assert (tmp_path / "temp" / "jobs").exists()
