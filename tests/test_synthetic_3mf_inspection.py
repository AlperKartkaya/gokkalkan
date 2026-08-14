from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

lib3mf = pytest.importorskip(
    "lib3mf",
    reason="3MF testleri requirements/synthetic-render.lock gerektirir",
)

sys.path.insert(0, str(Path("perception/synthetic/tools").resolve()))

from inspect_3mf import (
    InspectionError,
    inspect_3mf,
    sha256_file,
    write_contact_sheets,
)


def make_position(x: float, y: float, z: float) -> lib3mf.Position:
    position = lib3mf.Position()
    for index, value in enumerate((x, y, z)):
        position.Coordinates[index] = value
    return position


def make_triangle(a: int, b: int, c: int) -> lib3mf.Triangle:
    triangle = lib3mf.Triangle()
    for index, value in enumerate((a, b, c)):
        triangle.Indices[index] = value
    return triangle


def write_fixture_3mf(path: Path) -> None:
    wrapper = lib3mf.get_wrapper()
    model = wrapper.CreateModel()
    mesh = model.AddMeshObject()
    mesh.SetName("fixture_tetrahedron")
    mesh.SetGeometry(
        [
            make_position(0, 0, 0),
            make_position(10, 0, 0),
            make_position(0, 20, 0),
            make_position(0, 0, 30),
        ],
        [
            make_triangle(0, 2, 1),
            make_triangle(0, 1, 3),
            make_triangle(1, 2, 3),
            make_triangle(2, 0, 3),
        ],
    )
    model.AddBuildItem(mesh, wrapper.GetIdentityTransform())
    model.QueryWriter("3mf").WriteToFile(str(path))


def test_inspection_reports_geometry_build_and_hash(tmp_path: Path) -> None:
    source = tmp_path / "fixture.3mf"
    write_fixture_3mf(source)
    source_config = {"expectedSha256": sha256_file(source)}

    report, _render_inputs = inspect_3mf(source, source_config=source_config)

    assert report["tool"]["lib3mfVersion"] == "2.5.0"
    assert report["source"] == {
        "fileName": "fixture.3mf",
        "sizeBytes": source.stat().st_size,
        "sha256": sha256_file(source),
        "unit": "MilliMeter",
        "unitToMillimeter": 1.0,
        "meshCount": 1,
        "componentObjectCount": 0,
        "buildItemCount": 1,
    }
    mesh = report["meshes"][0]
    assert mesh["lib3mfName"] == "fixture_tetrahedron"
    assert mesh["vertexCount"] == 4
    assert mesh["triangleCount"] == 4
    assert mesh["boundsMm"]["min"] == [0.0, 0.0, 0.0]
    assert mesh["boundsMm"]["max"] == [10.0, 20.0, 30.0]
    assert mesh["boundsMm"]["extents"] == [10.0, 20.0, 30.0]
    assert report["buildItems"][0]["resolvedMeshResourceIds"] == [1]


def test_inspection_is_deterministic(tmp_path: Path) -> None:
    source = tmp_path / "fixture.3mf"
    write_fixture_3mf(source)

    first, _ = inspect_3mf(source)
    second, _ = inspect_3mf(source)

    assert first == second


def test_inspection_rejects_unexpected_source_hash(tmp_path: Path) -> None:
    source = tmp_path / "fixture.3mf"
    write_fixture_3mf(source)

    with pytest.raises(InspectionError, match="SHA-256 uyuşmuyor"):
        inspect_3mf(source, source_config={"expectedSha256": "0" * 64})


def test_contact_sheet_is_generated_deterministically(tmp_path: Path) -> None:
    source = tmp_path / "fixture.3mf"
    write_fixture_3mf(source)
    report, render_inputs = inspect_3mf(source)
    output = tmp_path / "contact"

    first = write_contact_sheets(output, render_inputs, report["source"]["sha256"])
    first_hash = sha256_file(output / first["sheets"][0]["fileName"])
    second = write_contact_sheets(output, render_inputs, report["source"]["sha256"])
    second_hash = sha256_file(output / second["sheets"][0]["fileName"])

    assert first["status"] == "AR_02_PENDING_USER_CONFIRMATION"
    assert first == second
    assert first_hash == second_hash
    assert json.loads((output / "index.json").read_text())["sheets"] == first["sheets"]
