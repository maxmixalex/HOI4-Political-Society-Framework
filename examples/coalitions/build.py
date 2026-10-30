"""Build a fictional, playable workshop for independent governments and pacts.

The existing minimal example is consumed by the normal loader; authoring data
is not printed. Run from the repository root with --output build/coalitions.
"""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from psf.compiler import compile_manifest
from psf.model import load, validate


def labels(english: str, chinese: str) -> dict[str, str]:
    return {"english": english, "simp_chinese": chinese}


def authored(value):
    """Remove private normalized registry fields before another compilation."""
    if isinstance(value, dict):
        return {key: authored(item) for key, item in value.items() if not key.startswith("_")}
    if isinstance(value, list):
        return [authored(item) for item in value]
    return value


def workshop_manifest(country: str = "GER") -> dict:
    data = authored(load(ROOT / "examples/minimal/manifest.json"))
    data["id"] = "psf_coalition_workshop"
    data["name"] = labels("PSF Coalition Workshop", "PSF 联盟实践")
    data["settings"].update(mechanics_mode="strict", bridge_mode="export", scenarios_enabled=True)
    prototype = data["fallback_profiles"][0]
    profile = copy.deepcopy(prototype)
    profile.pop("engine_ideology", None)
    profile.update(id="workshop", tag=country,
                   regime=next(regime["id"] for regime in data["regimes"] if regime["elections"]))
    groups = []
    for gid, name, short_name, votes, influence, color, electoral, description in (
            ("ws_civic", ("Civic Assembly", "公民议会"), ("Civic", "公民"), 35, 45, [70, 133, 188], True,
             ("Parliamentary accountability and open government.", "主张议会问责与公开施政。")),
            ("ws_labor", ("Labour League", "劳动联盟"), ("Labour", "劳动"), 30, 30, [183, 76, 66], True,
             ("Secure employment, collective bargaining and social insurance.", "主张稳定就业、集体协商与社会保障。")),
            ("ws_local", ("Local Reform Party", "地方改革党"), ("Reform", "改革"), 20, 20, [196, 165, 65], True,
             ("Local autonomy and elected regional administration.", "主张地方自治与民选地方政府。")),
            ("ws_industry", ("Industrial Council", "工业理事会"), ("Industry", "工业"), 15, 25, [98, 146, 119], False,
             ("Investment, infrastructure and consultation with industrial employers.", "主张扩大投资、发展基础设施与企业协商。"))):
        group = copy.deepcopy(prototype["groups"][0])
        group.update(id=gid, name=labels(*name), short_name=labels(*short_name),
                     description=labels(*description), kind="party" if electoral else "industrial_association",
                     support=votes, influence=influence, satisfaction=60, color=color,
                     electoral=electoral, status="legal")
        group.pop("icon", None)
        group["positions"] = {axis["id"]: 0 for axis in data["axes"]}
        groups.append(group)
    profile["groups"] = groups
    profile["government"] = {"group": "ws_civic"}
    profile["alliances"] = [
        {"id": "ws_reform", "name": labels("Reform Agreement", "改革协定"),
         "description": labels("An agreement for constitutional reform.", "推动制度改革的协定。"),
         "kind": "opposition", "members": ["ws_civic", "ws_local"], "cohesion": 70},
        {"id": "ws_labor_front", "name": labels("Labour and Industry Forum", "劳工与工业论坛"),
         "description": labels("An independent forum for workplace negotiation.", "独立开展劳资协商的论坛。"),
         "kind": "opposition", "members": ["ws_labor", "ws_industry"], "cohesion": 65},
        {"id": "ws_electoral_pact", "name": labels("Joint Electoral List", "联合选举名单"),
         "description": labels("Two parties pool their electoral support.", "两个政党合计选举支持的协约。"),
         "kind": "electoral", "members": ["ws_labor", "ws_local"], "cohesion": 75},
    ]
    profile["identities"] = [
        {"id": "ws_civic_identity", "name": labels("Civic Administration", "公民政府"),
         "when": {"group": "ws_civic"}},
        {"id": "ws_coalition_identity", "name": labels("Reform Administration", "改革联合政府"),
         "when": {"alliance": "ws_reform"}},
        {"id": "ws_default_identity", "name": labels("Parliamentary Administration", "议会政府")},
    ]
    profile["start_overrides"] = []
    data["profiles"] = [profile]
    data["scenarios"] = [{
        "id": "ws_cabinet_negotiations", "profile": "workshop", "date": "1936.1.15",
        "title": labels("Parliamentary negotiations", "议会协商"),
        "description": labels("The parties can preserve an independent cabinet, invite their reform partners into government, or leave office pending a new agreement.",
                              "各党可以维持独立内阁，邀请改革伙伴共同执政，或暂时卸任、等待新的协议。"),
        "options": [
            {"id": "independent", "label": labels("Keep the independent cabinet", "维持独立内阁"),
             "effects": [{"op": "govern_group", "group": "ws_civic"}]},
            {"id": "coalition", "label": labels("Form a coalition", "组成联合政府"),
             "effects": [{"op": "govern", "alliance": "ws_reform"}]},
            {"id": "resign", "label": labels("Resign from government", "政府辞职"),
             "effects": [{"op": "clear_government"}]},
        ],
    }]
    validate(data)
    return data


def build(output: Path, country: str = "GER") -> None:
    data = workshop_manifest(country)
    with tempfile.TemporaryDirectory(prefix="psf-coalition-workshop-") as temporary:
        manifest = Path(temporary) / "manifest.json"
        manifest.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        compile_manifest(manifest, output)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "build/coalitions")
    parser.add_argument("--country", default="GER", help="Existing country tag used for this fictional workshop")
    args = parser.parse_args()
    build(args.output, args.country)
    print(f"Coalition workshop built in {args.output}")
