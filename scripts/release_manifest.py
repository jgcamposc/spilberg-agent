#!/usr/bin/env python3
"""Write checksums and a compact manifest for the current release artifacts."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    artifacts_dir = Path("dist")
    files = sorted(path for path in artifacts_dir.iterdir() if path.is_file())
    records = [
        {"name": path.name, "sha256": sha256(path), "size_bytes": path.stat().st_size}
        for path in files
        if path.name not in {"SHA256SUMS", "release-manifest.json"}
    ]
    (artifacts_dir / "SHA256SUMS").write_text(
        "".join(f"{item['sha256']}  {item['name']}\n" for item in records),
        encoding="utf-8",
    )
    (artifacts_dir / "release-manifest.json").write_text(
        json.dumps({"schema_version": "1.0", "artifacts": records}, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
