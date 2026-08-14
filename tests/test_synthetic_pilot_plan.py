from __future__ import annotations

import json
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "perception/synthetic/tools"))

from build_pilot_plan import build_pilot_plan
from generate_scene_matrix import generate_render_plan


def test_pilot_selects_378_route_derived_worlds() -> None:
    synthetic = ROOT / "perception/synthetic"
    profile = tomllib.loads(
        (
            synthetic / "config/scene_profiles/committee_tilted_targets_sweep_v1.toml"
        ).read_text(encoding="utf-8")
    )
    assets = json.loads(
        (synthetic / "config/cad_asset_manifest.json").read_text(encoding="utf-8")
    )
    full = generate_render_plan(
        profile=profile,
        asset_manifest=assets,
        source_sha256="a" * 64,
        asset_manifest_sha256="b" * 64,
        seed=42,
    )

    pilot = build_pilot_plan(full)

    assert len(pilot["records"]) == 378
    assert {record["longitudinalDistanceM"] for record in pilot["records"]} == {
        5.0,
        10.0,
        15.0,
    }
    assert {record["topSurfaceViewBucketDeg"] for record in pilot["records"]} == {
        8.0,
        16.0,
        24.0,
    }
    assert {record["routeId"] for record in pilot["records"]} == {
        "ROTA_1",
        "ROTA_2",
        "ROTA_3",
    }
    assert all("viewYawBucketDeg" not in record for record in pilot["records"])
