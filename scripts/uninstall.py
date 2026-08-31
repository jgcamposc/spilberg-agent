#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Remove plugin sem apagar jobs ou brain local por padrão.")
    parser.add_argument("--remove-runtime", action="store_true")
    args = parser.parse_args()
    plugin = Path.home() / "plugins" / "spilberg-agent"
    if plugin.exists():
        shutil.rmtree(plugin)
    marketplace = Path.home() / ".agents" / "plugins" / "marketplace.json"
    if marketplace.exists():
        data = json.loads(marketplace.read_text(encoding="utf-8"))
        data["plugins"] = [item for item in data.get("plugins", []) if item.get("name") != "spilberg-agent"]
        marketplace.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.remove_runtime:
        runtime = Path.home() / "Library" / "Application Support" / "Spilberg"
        if runtime.exists():
            shutil.rmtree(runtime)


if __name__ == "__main__":
    main()
