from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "perception/synthetic/tools"))

from scene_contract import SceneContractError, scene_ground_truth


@pytest.mark.parametrize(
    ("presentation_class", "stages", "friend_foe", "allowed"),
    [
        ("dusman_drone_kirmizi", ["ASAMA_1", "ASAMA_2"], "Düşman", True),
        ("dusman_fuze_kirmizi", ["ASAMA_1", "ASAMA_2"], "Düşman", True),
        ("dusman_f16_kirmizi", ["ASAMA_1", "ASAMA_3"], "Düşman", True),
        ("dost_f16_camgobegi", ["ASAMA_3"], "Dost", False),
        ("dost_helikopter_camgobegi", ["ASAMA_3"], "Dost", False),
    ],
)
def test_scene_contract_links_balloon_and_respects_stage_rules(
    presentation_class: str,
    stages: list[str],
    friend_foe: str,
    allowed: bool,
) -> None:
    scene = scene_ground_truth(
        world_id="WORLD-EXAMPLE",
        presentation_class=presentation_class,
    )

    assert scene["eligibleStageIds"] == stages
    assert scene["friendFoe"] == friend_foe
    assert scene["balloon"]["targetInstanceId"] == scene["targetInstanceId"]
    assert scene["balloon"]["fireCandidateAllowed"] is allowed


def test_scene_contract_rejects_invalid_balloon_or_class() -> None:
    with pytest.raises(SceneContractError):
        scene_ground_truth(
            world_id="WORLD-1",
            presentation_class="dost_drone_camgobegi",
        )
    with pytest.raises(SceneContractError):
        scene_ground_truth(
            world_id="WORLD-1",
            presentation_class="dusman_f16_kirmizi",
            balloon_diameter_m=0.30,
        )
