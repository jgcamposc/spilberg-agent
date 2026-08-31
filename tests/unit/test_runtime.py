from pathlib import Path

from spilberg.runtime import base_brain_root


def test_packaged_brain_is_available_without_a_repository_checkout():
    brain = base_brain_root()
    assert brain.is_dir()
    assert {"editorial-rules.md", "editing-university.md", "presets.yaml"} <= {
        path.name for path in brain.iterdir()
    }


def test_packaged_brain_matches_the_public_brain_source():
    root = Path(__file__).resolve().parents[2]
    for name in ("editorial-rules.md", "editing-university.md", "presets.yaml"):
        public_words = " ".join((root / "brain" / "base" / name).read_text(encoding="utf-8").split())
        packaged_words = " ".join((base_brain_root() / name).read_text(encoding="utf-8").split())
        assert packaged_words == public_words
