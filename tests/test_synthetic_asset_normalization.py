from __future__ import annotations

import sys
from pathlib import Path

import pytest

np = pytest.importorskip(
    "numpy",
    reason="CAD normalizasyon testleri requirements/synthetic-render.lock gerektirir",
)

sys.path.insert(0, str(Path("perception/synthetic/tools").resolve()))

from convert_cad_assets import topology_diagnostics


def test_topology_diagnostics_accepts_closed_tetrahedron() -> None:
    vertices = np.asarray(
        [[0, 0, 0], [1, 0, 0], [0, 1, 0], [0, 0, 1]], dtype=np.float64
    )
    faces = np.asarray(
        [[0, 2, 1], [0, 1, 3], [1, 2, 3], [2, 0, 3]], dtype=np.uint32
    )

    result = topology_diagnostics(vertices, faces)

    assert result == {
        "degenerateTriangleCount": 0,
        "duplicateTriangleCount": 0,
        "boundaryEdgeCount": 0,
        "nonManifoldEdgeCount": 0,
        "closedTwoManifoldByEdgeCount": True,
    }


def test_topology_diagnostics_reports_open_and_degenerate_mesh() -> None:
    vertices = np.asarray(
        [[0, 0, 0], [1, 0, 0], [0, 1, 0]], dtype=np.float64
    )
    faces = np.asarray([[0, 1, 2], [0, 0, 1]], dtype=np.uint32)

    result = topology_diagnostics(vertices, faces)

    assert result["degenerateTriangleCount"] == 1
    assert result["boundaryEdgeCount"] > 0
    assert result["closedTwoManifoldByEdgeCount"] is False
