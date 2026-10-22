from pathlib import Path
import tomllib
import yaml


ROOT = Path(__file__).resolve().parents[2]


def test_release_dependencies_are_aligned_and_include_security_fixes():
    declared = set(tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["dependencies"])
    locked = {line for line in (ROOT / "requirements/base.txt").read_text().splitlines()
              if line and not line.startswith("#")}
    assert declared == locked
    assert {"Pillow==13.0.0", "certifi==2026.10.19"} <= declared


def test_macos_ci_installs_and_selects_subtitle_capable_ffmpeg():
    workflow = yaml.safe_load((ROOT / ".github/workflows/ci.yml").read_text())
    mac = next(s for s in workflow["jobs"]["test"]["steps"]
               if s.get("name") == "Install FFmpeg and FFprobe on macOS")
    assert "brew install ffmpeg-full" in mac["run"]
    assert "brew --prefix ffmpeg-full" in mac["run"] and "GITHUB_PATH" in mac["run"]
    # Current Homebrew bottles support Sequoia (15), not the old Sonoma runner.
    matrix = workflow["jobs"]["test"]["strategy"]["matrix"]["include"]
    assert all(entry["os"] == "macos-15" for entry in matrix if entry["os"].startswith("macos-"))
