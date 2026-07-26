from pathlib import Path

import pytest

from gokkalkan_backend.ballistic_compensation import BallisticCompensation


def test_unverified_table_never_returns_correction() -> None:
    assert BallisticCompensation.unverified().elevation_for_range(10) is None


def test_active_table_interpolates_only_inside_calibrated_range(tmp_path: Path) -> None:
    source = tmp_path / "trajectory.toml"
    source.write_text(
        """
[calibration]
id = "FIELD-SHOT-1"
status = "ACTIVE"

[[point]]
range_m = 5.0
elevation_deg = 1.0

[[point]]
range_m = 15.0
elevation_deg = 3.0
""",
        encoding="utf-8",
    )
    table = BallisticCompensation.from_toml(source)
    assert table.elevation_for_range(10) == pytest.approx(2)
    assert table.elevation_for_range(4) is None
