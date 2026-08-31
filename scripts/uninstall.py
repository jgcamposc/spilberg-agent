#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import shutil
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Remove o runtime sem apagar jobs ou brain local por padrão.")
    parser.add_argument("--remove-runtime", action="store_true")
    args = parser.parse_args()
    if os.name == "nt":
        runtime = Path(os.getenv("LOCALAPPDATA", str(Path.home() / "AppData" / "Local"))) / "Spilberg"
    else:
        runtime = Path.home() / "Library" / "Application Support" / "Spilberg"
    if args.remove_runtime:
        if runtime.exists():
            shutil.rmtree(runtime)
            print(f"Runtime removido: {runtime}")
    else:
        print("Nenhum job, cache ou regra local foi removido.")
        print("Remova o plugin pela interface de Plugins do Codex, se ele tiver sido instalado.")


if __name__ == "__main__":
    main()
