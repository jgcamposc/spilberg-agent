#!/usr/bin/env python3
import argparse
import platform
import subprocess
import sys
from pathlib import Path

def run(cmd: list[str]) -> None:
    print(f"Executando: {' '.join(cmd)}")
    subprocess.check_call(cmd)

def executable_in(venv_dir: Path, name: str) -> Path:
    return venv_dir / ("Scripts" if platform.system() == "Windows" else "bin") / name


def main() -> None:
    parser = argparse.ArgumentParser(description="Bootstrap Spilberg Environment")
    parser.add_argument(
        "--runtime-dir",
        type=Path,
        help="Diretório privado para ambiente, jobs, cache e preferências.",
    )
    args = parser.parse_args()
    repository = Path(__file__).resolve().parents[1]
    if args.runtime_dir:
        runtime_dir = args.runtime_dir.expanduser().resolve()
    elif platform.system() == "Windows":
        runtime_dir = Path.home() / "AppData" / "Local" / "Spilberg"
    else:
        runtime_dir = Path.home() / "Library" / "Application Support" / "Spilberg"
    runtime_dir.mkdir(parents=True, exist_ok=True)

    venv_dir = runtime_dir / "venv"
    if not venv_dir.exists():
        run([sys.executable, "-m", "venv", str(venv_dir)])

    pip_name = "pip.exe" if platform.system() == "Windows" else "pip"
    python_name = "python.exe" if platform.system() == "Windows" else "python"
    pip_exe = executable_in(venv_dir, pip_name)
    python_exe = executable_in(venv_dir, python_name)
    run([str(pip_exe), "install", "--upgrade", "pip"])
    run([str(pip_exe), "install", "-e", str(repository)])
    run([str(python_exe), "-m", "spilberg.cli", "doctor"])

    print(f"Instalação concluída. Runtime privado: {runtime_dir}")
    print("Para usar o CLI, ative o ambiente mostrado em docs/installation.md.")

if __name__ == "__main__":
    main()
