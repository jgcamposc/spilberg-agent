import json
from pathlib import Path


def test_plugin_manifest_and_editor_metadata_are_present():
    root = Path(__file__).resolve().parents[2]
    manifest = json.loads((root / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))
    assert manifest["name"] == "spilberg-agent"
    assert manifest["license"] == "Apache-2.0"
    assert (root / "skills" / "spilberg-editor" / "agents" / "openai.yaml").is_file()
