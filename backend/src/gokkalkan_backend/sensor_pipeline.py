"""In-process TFA50-L -> yaw association -> Mission Core callback pipeline."""

from __future__ import annotations

import time
from typing import Callable

from .lidar_adapter import TFA50LSerialAdapter
from .range_fusion import (
    FusedRangeDecision,
    TimedRange,
    TrackBearing,
    YawRangeAssociator,
)


class TFA50LFusionPipeline:
    def __init__(
        self,
        adapter: TFA50LSerialAdapter,
        associator: YawRangeAssociator,
        *,
        selected_track: Callable[[], TrackBearing | None],
        turret_yaw_deg: Callable[[], float],
        on_decision: Callable[[FusedRangeDecision], object],
        on_raw_sample: Callable[[TimedRange], object] | None = None,
        monotonic_ns: Callable[[], int] = time.monotonic_ns,
    ) -> None:
        self.adapter = adapter
        self.associator = associator
        self.selected_track = selected_track
        self.turret_yaw_deg = turret_yaw_deg
        self.on_decision = on_decision
        self.on_raw_sample = on_raw_sample
        self.monotonic_ns = monotonic_ns

    def tick(self) -> list[FusedRangeDecision]:
        decisions = []
        for sample in self.adapter.poll():
            decision = self.associator.associate(
                sample,
                self.selected_track(),
                turret_yaw_deg=self.turret_yaw_deg(),
                now_monotonic_ns=self.monotonic_ns(),
            )
            self.on_decision(decision)
            if self.on_raw_sample is not None and sample.distance_m is not None:
                try:
                    self.on_raw_sample(sample)
                except Exception:
                    pass
            decisions.append(decision)
        return decisions
