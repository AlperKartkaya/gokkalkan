"""Competition-stage and target-balloon ground-truth contracts."""

from __future__ import annotations

import hashlib


class SceneContractError(ValueError):
    """Raised when a presentation class cannot form a safe scene contract."""


def eligible_stage_ids(presentation_class: str) -> list[str]:
    is_friend = presentation_class.startswith("dost_")
    if is_friend:
        if "f16" not in presentation_class and "helikopter" not in presentation_class:
            raise SceneContractError("dost sınıf yalnız F16 veya Helikopter olabilir")
        return ["ASAMA_3"]
    if not presentation_class.startswith("dusman_"):
        raise SceneContractError(f"bilinmeyen sunum sınıfı: {presentation_class}")
    if "drone" in presentation_class or "fuze" in presentation_class:
        return ["ASAMA_1", "ASAMA_2"]
    if "f16" in presentation_class or "helikopter" in presentation_class:
        return ["ASAMA_1", "ASAMA_3"]
    raise SceneContractError(f"hedef tipi çözümlenemedi: {presentation_class}")


def scene_ground_truth(
    *,
    world_id: str,
    presentation_class: str,
    balloon_diameter_m: float = 0.14,
) -> dict:
    if not 0.12 <= balloon_diameter_m <= 0.16:
        raise SceneContractError("balon çapı [0.12, 0.16] m aralığında olmalı")
    friend_foe = "Dost" if presentation_class.startswith("dost_") else "Düşman"
    target_id = "TARGET-" + hashlib.sha256(world_id.encode()).hexdigest()[:12]
    balloon_id = (
        "BALLOON-" + hashlib.sha256(f"{world_id}|balloon".encode()).hexdigest()[:12]
    )
    return {
        "targetInstanceId": target_id,
        "eligibleStageIds": eligible_stage_ids(presentation_class),
        "friendFoe": friend_foe,
        "balloon": {
            "instanceId": balloon_id,
            "targetInstanceId": target_id,
            "diameterM": balloon_diameter_m,
            "relativeCenterM": [0.0, 0.0, -0.40],
            "colorHex": "#F50A0A",
            "fireCandidateAllowed": friend_foe == "Düşman",
        },
    }
