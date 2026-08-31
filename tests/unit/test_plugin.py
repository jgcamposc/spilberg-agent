import json
from pathlib import Path


def test_plugin_manifest_and_editor_metadata_are_present():
    root = Path(__file__).resolve().parents[2]
    manifest = json.loads((root / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))
    assert manifest["name"] == "spilberg-agent"
    assert manifest["license"] == "Apache-2.0"
    assert (root / "skills" / "spilberg-editor" / "agents" / "openai.yaml").is_file()


def test_marketplace_points_to_a_packaged_plugin_without_drift():
    root = Path(__file__).resolve().parents[2]
    marketplace = json.loads(
        (root / ".agents" / "plugins" / "marketplace.json").read_text(encoding="utf-8")
    )
    plugin = next(item for item in marketplace["plugins"] if item["name"] == "spilberg-agent")
    assert plugin["source"] == {"source": "local", "path": "./plugins/spilberg-agent"}

    package_root = root / "plugins" / "spilberg-agent"
    assert (package_root / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8") == (
        root / ".codex-plugin" / "plugin.json"
    ).read_text(encoding="utf-8")
    assert (package_root / "skills" / "spilberg-editor" / "SKILL.md").read_text(encoding="utf-8") == (
        root / "skills" / "spilberg-editor" / "SKILL.md"
    ).read_text(encoding="utf-8")
    assert (package_root / "skills" / "spilberg-editor" / "agents" / "openai.yaml").read_text(
        encoding="utf-8"
    ) == (root / "skills" / "spilberg-editor" / "agents" / "openai.yaml").read_text(encoding="utf-8")
