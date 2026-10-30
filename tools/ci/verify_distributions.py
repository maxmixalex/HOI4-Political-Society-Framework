"""Reproduce both downloadable installers from the current compiler version.

The primary build is supplied by CI's compile step. The optional workshop is
built and validated independently; it never shares a content registry with the
primary example. Archive selection uses explicit versioned names, not a glob.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import zipfile


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from psf import __version__
from psf.compiler import pack


def verify(build: Path, name: str, reports: Path) -> dict:
    expected = ROOT / "distributions" / name
    if not expected.is_file():
        raise SystemExit(f"Missing current-version distribution: {expected}")
    archive = pack(build, reports / name)
    with zipfile.ZipFile(archive) as installed:
        damaged = installed.testzip()
        if damaged is not None:
            raise SystemExit(f"Archive CRC failed: {name}: {damaged}")
        entries = len(installed.infolist())
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    if archive.read_bytes() != expected.read_bytes():
        raise SystemExit(f"Distribution differs from its source build: {name}")
    result = {"name": name, "bytes": archive.stat().st_size, "entries": entries,
              "crc": "pass", "source_identical": True, "sha256": digest}
    print(f"{name}: {entries} entries, CRC passed, source-identical, SHA256 {digest}", flush=True)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT / "dist", help="Already compiled vanilla build")
    parser.add_argument("--reports", type=Path, default=ROOT / "build/distribution-validation")
    args = parser.parse_args()
    reports = args.reports.resolve()
    reports.mkdir(parents=True, exist_ok=True)
    results = [verify(args.root.resolve(), f"psf-{__version__}.zip", reports)]
    workshop = reports / "coalitions"
    subprocess.run([sys.executable, str(ROOT / "examples/coalitions/build.py"),
                    "--output", str(workshop)], cwd=ROOT, check=True)
    subprocess.run([sys.executable, str(ROOT / "tools/ci/validate.py"),
                    "--root", str(workshop), "--reports", str(reports / "coalitions-validation")],
                   cwd=ROOT, check=True)
    results.append(verify(workshop, f"psf-coalition-workshop-{__version__}.zip", reports))
    (reports / "summary.json").write_text(json.dumps({"version": __version__, "artifacts": results}, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
