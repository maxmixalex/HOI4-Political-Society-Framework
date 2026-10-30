"""Command-line tools for authors; all outputs are explicit local paths."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from . import __version__
from .compiler import compile_manifest, pack
from .model import ManifestError, load, profiles


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="psf", description="Compile political societies into native HOI4 mods")
    parser.add_argument("--version", action="version", version=__version__)
    commands = parser.add_subparsers(dest="command", required=True)
    validate = commands.add_parser("validate", help="JSON Schema and cross-reference validation")
    validate.add_argument("manifest", type=Path)
    compile_cmd = commands.add_parser("compile", help="Build the reusable framework and dependent content mod")
    compile_cmd.add_argument("manifest", type=Path)
    compile_cmd.add_argument("--output", type=Path, default=Path("dist"))
    compile_cmd.add_argument("--vanilla", type=Path, help="Original game's interface directory; strict mode also reads sibling history/countries and common/ideologies")
    compile_cmd.add_argument("--supported-version", help="Optional verified target version, e.g. 1.19.*; omitted when unknown")
    inspect = commands.add_parser("inspect", help="Inspect stable IDs and authored group positions")
    inspect.add_argument("manifest", type=Path)
    inspect.add_argument("--group")
    package = commands.add_parser("pack", help="Create deterministic launcher-ready mod ZIP")
    package.add_argument("--root", type=Path, default=Path("dist"))
    package.add_argument("--output", type=Path, default=Path("artifacts/psf-vanilla-example.zip"))
    args = parser.parse_args(argv)
    try:
        if args.command == "validate":
            manifest = load(args.manifest)
            print(f"Valid PSF manifest: {manifest['id']} ({len(profiles(manifest))} profiles, {sum(len(p['groups']) for p in profiles(manifest))} groups)")
        elif args.command == "compile":
            report = compile_manifest(args.manifest, args.output, vanilla=args.vanilla, supported_version=args.supported_version)
            print(json.dumps({"output": str(args.output), **report["counts"]}, ensure_ascii=False, indent=2))
        elif args.command == "inspect":
            manifest = load(args.manifest)
            if args.group:
                groups = [g for p in profiles(manifest) for g in p["groups"] if g["id"] == args.group]
                if not groups:
                    raise ManifestError(f"No organization named {args.group}")
                print(json.dumps(groups[0], ensure_ascii=False, indent=2))
            else:
                print(json.dumps({p["id"]: {"groups": {g["id"]: g["_index"] for g in p["groups"]}, "alliances": {a["id"]: a["_index"] for a in p["alliances"]}} for p in profiles(manifest)}, ensure_ascii=False, indent=2))
        elif args.command == "pack":
            print(pack(args.root, args.output))
    except (ManifestError, ValueError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0
