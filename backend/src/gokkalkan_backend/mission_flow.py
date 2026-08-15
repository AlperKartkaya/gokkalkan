"""Deterministic competition mission state machine.

The class is deliberately free of I/O and threading.  ``MissionCore`` remains
the single owner and calls these transitions from its reducer thread.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from math import isfinite
from typing import Any, Iterable, Literal, Mapping

MissionStatus = Literal[
    "IDLE",
    "ACTIVE",
    "PAUSED",
    "MAINTENANCE",
    "ESTOP_LATCHED",
    "ROUND_COMPLETE",
]


def _range_gate(target_type: str, range_m: float) -> bool:
    if target_type == "F16":
        return 10 <= range_m <= 15
    if target_type in {"Helikopter", "Balistik Füze"}:
        return 5 <= range_m <= 15
    if target_type == "Mini/Micro İHA":
        return 0 < range_m <= 15
    return False


@dataclass(slots=True)
class MissionFlow:
    """Backend-owned stage, target-order and pause state."""

    stage: int = 3
    round: int = 1
    status: MissionStatus = "IDLE"
    target_order: list[str] = field(default_factory=list)
    completed_target_ids: list[str] = field(default_factory=list)
    selected_target_id: str | None = None
    previous_status: MissionStatus | None = None
    last_transition_reason: str = "BOOT"
    transition_sequence: int = 0

    def start_stage(
        self,
        stage: int,
        round_no: int,
        tracks: Iterable[Mapping[str, Any]],
        *,
        reason: str,
    ) -> None:
        self.stage = stage
        self.round = round_no
        self.status = "ACTIVE"
        self.previous_status = None
        self.completed_target_ids.clear()
        self._refresh_order(tracks)
        self._transition(reason)

    def refresh_tracks(self, tracks: Iterable[Mapping[str, Any]]) -> None:
        """Recompute backend priority without inventing or renaming track IDs."""

        self._refresh_order(tracks)
        if self.status == "ROUND_COMPLETE" and self.selected_target_id:
            self.status = "ACTIVE"
            self._transition("NEW_ELIGIBLE_TRACK")

    def record_engagement(self, target_id: str) -> bool:
        if self.status != "ACTIVE" or target_id != self.selected_target_id:
            return False
        if target_id not in self.completed_target_ids:
            self.completed_target_ids.append(target_id)
        self.selected_target_id = next(
            (
                candidate
                for candidate in self.target_order
                if candidate not in self.completed_target_ids
            ),
            None,
        )
        if self.selected_target_id is None:
            self.status = "ROUND_COMPLETE"
            self._transition("ALL_ELIGIBLE_TARGETS_ENGAGED")
        else:
            self._transition("TARGET_ENGAGED")
        return True

    def pause(self, reason: str) -> bool:
        if self.status not in {"ACTIVE", "ROUND_COMPLETE"}:
            return False
        self.previous_status = self.status
        self.status = "PAUSED"
        self._transition(reason)
        return True

    def resume(self, reason: str) -> bool:
        if self.status != "PAUSED":
            return False
        self.status = (
            self.previous_status
            if self.previous_status in {"ACTIVE", "ROUND_COMPLETE"}
            else "ACTIVE"
        )
        self.previous_status = None
        self._transition(reason)
        return True

    def start_maintenance(self, reason: str) -> bool:
        if self.status not in {"ACTIVE", "PAUSED", "ROUND_COMPLETE", "IDLE"}:
            return False
        self.previous_status = self.status
        self.status = "MAINTENANCE"
        self._transition(reason)
        return True

    def end_maintenance(self, reason: str) -> bool:
        if self.status != "MAINTENANCE":
            return False
        resume_status = (
            self.previous_status
            if self.previous_status in {"ACTIVE", "ROUND_COMPLETE"}
            else "ACTIVE"
        )
        self.status = "PAUSED"
        self.previous_status = resume_status
        self._transition(reason)
        return True

    def latch_estop(self, reason: str) -> None:
        if self.status != "ESTOP_LATCHED":
            self.previous_status = self.status
        self.status = "ESTOP_LATCHED"
        self._transition(reason)

    def release_estop(self, reason: str) -> None:
        """A reset only reaches PAUSED; explicit resume is still required."""

        if self.status == "ESTOP_LATCHED":
            resume_status = (
                self.previous_status
                if self.previous_status in {"ACTIVE", "ROUND_COMPLETE"}
                else "ACTIVE"
            )
            self.status = "PAUSED"
            self.previous_status = resume_status
            self._transition(reason)

    def reset(self, tracks: Iterable[Mapping[str, Any]]) -> None:
        self.status = "IDLE"
        self.previous_status = None
        self.completed_target_ids.clear()
        self._refresh_order(tracks)
        self._transition("TELEMETRY_RESET")

    def to_dict(self) -> dict[str, Any]:
        total = len(self.target_order)
        completed = len(self.completed_target_ids)
        return {
            "schemaVersion": 1,
            "status": self.status,
            "stage": self.stage,
            "round": self.round,
            "selectedTargetId": self.selected_target_id,
            "targetOrder": list(self.target_order),
            "completedTargetIds": list(self.completed_target_ids),
            "completedTargetCount": completed,
            "eligibleTargetCount": total,
            "progressPercent": round((completed / total) * 100) if total else 0,
            "roundComplete": self.status == "ROUND_COMPLETE",
            "nextRound": self.round + 1,
            "previousStatus": self.previous_status,
            "lastTransitionReason": self.last_transition_reason,
            "transitionSequence": self.transition_sequence,
        }

    def _refresh_order(self, tracks: Iterable[Mapping[str, Any]]) -> None:
        normalized = [track for track in tracks if self._eligible(track)]
        if self.stage == 1:
            ordered = normalized
        else:
            ordered = sorted(
                normalized,
                key=lambda item: (
                    float(item.get("rangeM", float("inf"))),
                    -float(item.get("confidence", 0.0)),
                    str(item.get("trackId", "")),
                ),
            )
        self.target_order = [
            str(track["trackId"])
            for track in ordered
            if str(track.get("trackId", "")).strip()
        ]
        self.selected_target_id = next(
            (
                target_id
                for target_id in self.target_order
                if target_id not in self.completed_target_ids
            ),
            None,
        )

    def _eligible(self, track: Mapping[str, Any]) -> bool:
        if not bool(track.get("fireCandidate", True)):
            return False
        try:
            range_m = float(track.get("rangeM", -1))
        except (TypeError, ValueError):
            return False
        if not isfinite(range_m) or range_m <= 0:
            return False
        friend_foe = str(track.get("friendFoe", "Bilinmeyen"))
        if self.stage == 1:
            return range_m <= 15
        if self.stage == 2:
            # Aşama 2 requires detection/tracking, not target-type
            # classification. Explicitly friendly tracks remain protected.
            return friend_foe != "Dost" and range_m <= 15
        return friend_foe == "Düşman" and _range_gate(
            str(track.get("targetType", "")),
            range_m,
        )

    def _transition(self, reason: str) -> None:
        self.transition_sequence += 1
        self.last_transition_reason = reason
