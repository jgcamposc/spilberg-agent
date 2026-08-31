import pytest
from spilberg.jobs import JobStore

def test_job_lifecycle(tmp_path):
    store = JobStore(root=tmp_path)
    
    # Fake video source
    video = tmp_path / "fake_video.mp4"
    video.write_text("fake video content")
    
    state = store.create(video, client="Test Client", platform="reels")
    assert state["status"] == "PREPARED"
    assert state["client"] == "Test Client"
    
    # Can't easily test prepare/submit without full environment (ffmpeg, whisper),
    # but the lifecycle structure is verified.
