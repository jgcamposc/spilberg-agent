#!/usr/bin/env python3
import argparse
import platform
import subprocess
import sys
from pathlib import Path

def run(cmd):
    print(f"Running: {' '.join(cmd)}")
    subprocess.check_call(cmd)

def main():
    parser = argparse.ArgumentParser(description="Bootstrap Spilberg Environment")
    parser.parse_args()

    # Create venv
    venv_dir = Path(".venv")
    if not venv_dir.exists():
        run([sys.executable, "-m", "venv", ".venv"])
    
    # Pip install
    pip_exe = venv_dir / "bin" / "pip" if platform.system() != "Windows" else venv_dir / "Scripts" / "pip.exe"
    run([str(pip_exe), "install", "--upgrade", "pip"])
    run([str(pip_exe), "install", "-e", "."])

    print("Bootstrap complete. Run 'spilberg doctor' to check dependencies.")

if __name__ == "__main__":
    main()
