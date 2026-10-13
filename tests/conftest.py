import subprocess
import pytest
from spilberg.editing import SpilbergOrchestrator

@pytest.fixture
def master_factory(tmp_path):
    engine = SpilbergOrchestrator(str(tmp_path / "fixture-tools"))
    def create(name="master", rate="30", duration=2):
        path = tmp_path / (name + ".mp4")
        subprocess.run([engine._resolve_executable("ffmpeg"), "-v", "error", "-y", "-f", "lavfi", "-i", f"testsrc2=size=320x180:rate={rate}", "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000", "-t", str(duration), "-c:v", "libx264", "-c:a", "aac", str(path)], check=True)
        return path
    return create
