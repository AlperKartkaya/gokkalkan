"""Deterministic 3MF inspection and source-axis contact sheets.

Geometry and build structure are read through the official lib3mf binding.  The
contact sheets intentionally keep the source coordinate frame unchanged so that
AR-02 can confirm the nose and top axes before any normalization is performed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections.abc import Iterable
from pathlib import Path
from typing import Any

TOOL_NAME = "gokkalkan-inspect-3mf"
TOOL_VERSION = "1.0.0"
DEFAULT_SOURCE_CONFIG = Path("perception/synthetic/config/cad_source.json")
DEFAULT_ASSET_MANIFEST = Path(
    "perception/synthetic/config/cad_asset_manifest.json"
)
DEFAULT_REPORT = Path(
    "perception/synthetic/generated/inspection/modeller.report.json"
)
DEFAULT_CONTACT_SHEETS = Path(
    "perception/synthetic/generated/contact_sheets"
)

UNIT_TO_MM = {
    "MicroMeter": 0.001,
    "MilliMeter": 1.0,
    "CentiMeter": 10.0,
    "Inch": 25.4,
    "Foot": 304.8,
    "Meter": 1000.0,
}


class InspectionError(RuntimeError):
    """Raised when the source violates an inspection contract."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise InspectionError(f"JSON okunamadı: {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise InspectionError(f"JSON kökü nesne olmalı: {path}")
    return value


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _round(value: float, digits: int = 6) -> float:
    rounded = round(float(value), digits)
    return 0.0 if rounded == -0.0 else rounded


def _lib3mf() -> Any:
    try:
        import lib3mf
    except ImportError as exc:  # pragma: no cover - operator environment guard
        raise InspectionError(
            "lib3mf bulunamadı; requirements/synthetic-render.lock kurun"
        ) from exc
    return lib3mf


def _numpy() -> Any:
    try:
        import numpy as np
    except ImportError as exc:  # pragma: no cover - operator environment guard
        raise InspectionError(
            "NumPy bulunamadı; requirements/synthetic-render.lock kurun"
        ) from exc
    return np


def _vertices_array(mesh: Any, unit_to_mm: float) -> Any:
    np = _numpy()
    vertices = mesh.GetVertices()
    return np.asarray(
        [
            (
                float(vertex.Coordinates[0]) * unit_to_mm,
                float(vertex.Coordinates[1]) * unit_to_mm,
                float(vertex.Coordinates[2]) * unit_to_mm,
            )
            for vertex in vertices
        ],
        dtype=np.float64,
    )


def _transform_fields(transform: Any) -> list[list[float]]:
    return [
        [_round(transform.Fields[row][column], 9) for column in range(3)]
        for row in range(4)
    ]


def _root_mesh_ids(
    object_resource: Any,
    visited: set[int] | None = None,
) -> list[int]:
    resource_id = int(object_resource.GetResourceID())
    seen = set() if visited is None else set(visited)
    if resource_id in seen:
        raise InspectionError(f"Component döngüsü bulundu: resource {resource_id}")
    seen.add(resource_id)
    if object_resource.IsMeshObject():
        return [resource_id]
    if not object_resource.IsComponentsObject():
        return []
    mesh_ids: set[int] = set()
    for index in range(object_resource.GetComponentCount()):
        component = object_resource.GetComponent(index)
        mesh_ids.update(_root_mesh_ids(component.GetObjectResource(), seen))
    return sorted(mesh_ids)


def _manifest_assets(manifest: dict[str, Any] | None) -> dict[int, dict[str, Any]]:
    if manifest is None:
        return {}
    assets = manifest.get("assets")
    if not isinstance(assets, list):
        raise InspectionError("Asset manifest 'assets' listesi içermeli")
    mapped: dict[int, dict[str, Any]] = {}
    for asset in assets:
        resource_id = int(asset["sourceResourceId"])
        if resource_id in mapped:
            raise InspectionError(
                f"Asset manifest resource ID tekrar ediyor: {resource_id}"
            )
        mapped[resource_id] = asset
    return mapped


def _validate_manifest_geometry(
    resource_id: int,
    asset: dict[str, Any],
    vertex_count: int,
    triangle_count: int,
    extents_mm: Iterable[float],
    *,
    is_valid: bool,
    is_manifold_and_oriented: bool,
) -> None:
    expected = asset["sourceGeometry"]
    if int(expected["vertexCount"]) != vertex_count:
        raise InspectionError(
            f"Resource {resource_id} vertexCount uyuşmuyor: "
            f"{vertex_count} != {expected['vertexCount']}"
        )
    if int(expected["triangleCount"]) != triangle_count:
        raise InspectionError(
            f"Resource {resource_id} triangleCount uyuşmuyor: "
            f"{triangle_count} != {expected['triangleCount']}"
        )
    for actual, configured in zip(extents_mm, expected["boundsMm"], strict=True):
        if abs(float(actual) - float(configured)) > 0.05:
            raise InspectionError(
                f"Resource {resource_id} boundsMm uyuşmuyor: "
                f"{list(extents_mm)} != {expected['boundsMm']}"
            )
    if bool(expected["lib3mfValid"]) is not is_valid:
        raise InspectionError(
            f"Resource {resource_id} lib3mfValid uyuşmuyor: "
            f"{is_valid} != {expected['lib3mfValid']}"
        )
    if bool(expected["manifoldAndOriented"]) is not is_manifold_and_oriented:
        raise InspectionError(
            f"Resource {resource_id} manifoldAndOriented uyuşmuyor: "
            f"{is_manifold_and_oriented} != {expected['manifoldAndOriented']}"
        )


def inspect_3mf(
    input_path: Path,
    *,
    source_config: dict[str, Any] | None = None,
    asset_manifest: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], list[tuple[Any, dict[str, Any], Any]]]:
    """Inspect a 3MF and return its report plus meshes for contact-sheet use."""

    if not input_path.is_file():
        raise InspectionError(f"3MF bulunamadı: {input_path}")

    digest = sha256_file(input_path)
    if source_config is not None:
        expected = str(source_config.get("expectedSha256", ""))
        if digest != expected:
            raise InspectionError(
                f"CAD SHA-256 uyuşmuyor: actual={digest} expected={expected}"
            )

    lib3mf = _lib3mf()
    wrapper = lib3mf.get_wrapper()
    model = wrapper.CreateModel()
    try:
        reader = model.QueryReader("3mf")
        reader.ReadFromFile(str(input_path.resolve()))
    except Exception as exc:  # lib3mf raises generated binding exceptions
        raise InspectionError(f"lib3mf dosyayı okuyamadı: {exc}") from exc

    try:
        unit_enum = lib3mf.ModelUnit(model.GetUnit())
        unit_name = unit_enum.name
    except (ValueError, AttributeError) as exc:
        raise InspectionError(f"Desteklenmeyen 3MF unit: {model.GetUnit()}") from exc
    unit_to_mm = UNIT_TO_MM[unit_name]
    manifest_assets = _manifest_assets(asset_manifest)

    meshes: list[dict[str, Any]] = []
    render_inputs: list[tuple[Any, dict[str, Any], Any]] = []
    iterator = model.GetMeshObjects()
    while iterator.MoveNext():
        mesh = iterator.GetCurrentMeshObject()
        resource_id = int(mesh.GetResourceID())
        vertices = _vertices_array(mesh, unit_to_mm)
        if len(vertices) == 0:
            raise InspectionError(f"Resource {resource_id} boş mesh")
        minimum = vertices.min(axis=0)
        maximum = vertices.max(axis=0)
        extents = maximum - minimum
        vertex_count = int(mesh.GetVertexCount())
        triangle_count = int(mesh.GetTriangleCount())
        is_valid = bool(mesh.IsValid())
        is_manifold_and_oriented = bool(mesh.IsManifoldAndOriented())
        asset = manifest_assets.get(resource_id)
        if asset is not None:
            _validate_manifest_geometry(
                resource_id,
                asset,
                vertex_count,
                triangle_count,
                extents,
                is_valid=is_valid,
                is_manifold_and_oriented=is_manifold_and_oriented,
            )
        record = {
            "resourceId": resource_id,
            "lib3mfName": mesh.GetName() or None,
            "assetKey": asset["assetKey"] if asset else None,
            "displayName": asset["displayName"] if asset else f"Resource {resource_id}",
            "vertexCount": vertex_count,
            "triangleCount": triangle_count,
            "boundsMm": {
                "min": [_round(value) for value in minimum],
                "max": [_round(value) for value in maximum],
                "extents": [_round(value) for value in extents],
                "longestAxis": _round(max(extents)),
            },
            "isValid": is_valid,
            "isManifoldAndOriented": is_manifold_and_oriented,
            "orientationStatus": (
                asset["orientation"]["status"] if asset else "UNMAPPED"
            ),
            "scaleStatus": asset["scale"]["status"] if asset else "UNMAPPED",
        }
        meshes.append(record)
        render_inputs.append((mesh, record, vertices))

    meshes.sort(key=lambda item: item["resourceId"])
    render_inputs.sort(key=lambda item: item[1]["resourceId"])
    if manifest_assets and set(manifest_assets) != {
        item["resourceId"] for item in meshes
    }:
        raise InspectionError(
            "Asset manifest resource ID kümesi 3MF mesh kümesiyle eşleşmiyor"
        )

    components: list[dict[str, Any]] = []
    component_iterator = model.GetComponentsObjects()
    while component_iterator.MoveNext():
        components_object = component_iterator.GetCurrent()
        component_records = []
        for index in range(components_object.GetComponentCount()):
            component = components_object.GetComponent(index)
            child = component.GetObjectResource()
            component_records.append(
                {
                    "objectResourceId": int(child.GetResourceID()),
                    "transform4x3": (
                        _transform_fields(component.GetTransform())
                        if component.HasTransform()
                        else None
                    ),
                }
            )
        components.append(
            {
                "resourceId": int(components_object.GetResourceID()),
                "components": component_records,
                "resolvedMeshResourceIds": _root_mesh_ids(components_object),
            }
        )
    components.sort(key=lambda item: item["resourceId"])

    build_items: list[dict[str, Any]] = []
    build_iterator = model.GetBuildItems()
    index = 0
    while build_iterator.MoveNext():
        build_item = build_iterator.GetCurrent()
        object_resource = build_item.GetObjectResource()
        build_items.append(
            {
                "index": index,
                "objectResourceId": int(object_resource.GetResourceID()),
                "resolvedMeshResourceIds": _root_mesh_ids(object_resource),
                "transform4x3": (
                    _transform_fields(build_item.GetObjectTransform())
                    if build_item.HasObjectTransform()
                    else None
                ),
            }
        )
        index += 1

    warnings = []
    if any(item["lib3mfName"] is None for item in meshes):
        warnings.append(
            "Core 3MF mesh adları boş; takım adları sürümlü asset manifestinden alınmıştır."
        )
    if any(item["triangleCount"] > 500_000 for item in meshes):
        warnings.append(
            "En az bir mesh 500.000'den fazla üçgen içeriyor; FAZ 2 LOD gereklidir."
        )
    invalid_meshes = [
        item["displayName"]
        for item in meshes
        if not item["isValid"] or not item["isManifoldAndOriented"]
    ]
    if invalid_meshes:
        warnings.append(
            "lib3mf geçerlilik/manifold kontrolü başarısız: "
            + ", ".join(invalid_meshes)
            + ". FAZ 2 otomatik geometri tanısı ve kontrollü onarım gerektirir."
        )
    if any(item["orientationStatus"] != "VERIFIED" for item in meshes):
        warnings.append("AR-02 burun/üst yön onayı bekleniyor.")

    version = wrapper.GetLibraryVersion()
    report = {
        "schemaVersion": 1,
        "tool": {
            "name": TOOL_NAME,
            "version": TOOL_VERSION,
            "lib3mfVersion": ".".join(str(part) for part in version),
        },
        "source": {
            "fileName": input_path.name,
            "sizeBytes": input_path.stat().st_size,
            "sha256": digest,
            "unit": unit_name,
            "unitToMillimeter": unit_to_mm,
            "meshCount": len(meshes),
            "componentObjectCount": len(components),
            "buildItemCount": len(build_items),
        },
        "meshes": meshes,
        "componentObjects": components,
        "buildItems": build_items,
        "warnings": warnings,
    }
    return report, render_inputs


VIEW_DEFINITIONS = (
    ("+X", (0, 1, 0), (0, 0, 1), (1, 0, 0), "sağ=+Y  yukarı=+Z"),
    ("-X", (0, -1, 0), (0, 0, 1), (-1, 0, 0), "sağ=-Y  yukarı=+Z"),
    ("+Y", (-1, 0, 0), (0, 0, 1), (0, 1, 0), "sağ=-X  yukarı=+Z"),
    ("-Y", (1, 0, 0), (0, 0, 1), (0, -1, 0), "sağ=+X  yukarı=+Z"),
    ("+Z", (1, 0, 0), (0, 1, 0), (0, 0, 1), "sağ=+X  yukarı=+Y"),
    ("-Z", (1, 0, 0), (0, -1, 0), (0, 0, -1), "sağ=+X  yukarı=-Y"),
)


def _font(size: int, *, bold: bool = False) -> Any:
    from PIL import ImageFont

    candidates = [
        (
            "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
            if bold
            else "/System/Library/Fonts/Supplemental/Arial.ttf"
        ),
        (
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
            if bold
            else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
        ),
    ]
    for candidate in candidates:
        if Path(candidate).is_file():
            return ImageFont.truetype(candidate, size=size)
    return ImageFont.load_default()


def _render_point_view(
    vertices: Any,
    right_axis: tuple[int, int, int],
    up_axis: tuple[int, int, int],
    depth_axis: tuple[int, int, int],
    *,
    width: int,
    height: int,
) -> Any:
    from PIL import Image, ImageFilter

    np = _numpy()
    centered = vertices - vertices.mean(axis=0, keepdims=True)
    right = np.asarray(right_axis, dtype=np.float64)
    up = np.asarray(up_axis, dtype=np.float64)
    depth = np.asarray(depth_axis, dtype=np.float64)
    projected_x = centered @ right
    projected_y = centered @ up
    projected_depth = centered @ depth

    usable_width = width - 40
    usable_height = height - 40
    span_x = max(float(projected_x.max() - projected_x.min()), 1e-9)
    span_y = max(float(projected_y.max() - projected_y.min()), 1e-9)
    scale = min(usable_width / span_x, usable_height / span_y)
    x = np.rint((projected_x - projected_x.mean()) * scale + width / 2).astype(int)
    y = np.rint(height / 2 - (projected_y - projected_y.mean()) * scale).astype(int)
    keep = (x >= 0) & (x < width) & (y >= 0) & (y < height)
    x = x[keep]
    y = y[keep]
    depth_values = projected_depth[keep]
    depth_span = max(float(depth_values.max() - depth_values.min()), 1e-9)
    intensity = np.rint(
        65 + 190 * (depth_values - depth_values.min()) / depth_span
    ).astype(np.uint8)

    flat = y * width + x
    depth_image = np.zeros(width * height, dtype=np.uint8)
    np.maximum.at(depth_image, flat, intensity)
    depth_image = depth_image.reshape((height, width))
    mask = Image.fromarray(depth_image).filter(ImageFilter.MaxFilter(5))
    mask_array = np.asarray(mask, dtype=np.uint8)

    rgba = np.zeros((height, width, 4), dtype=np.uint8)
    rgba[..., 0] = np.clip(mask_array * 0.08, 0, 255).astype(np.uint8)
    rgba[..., 1] = np.clip(mask_array * 0.78, 0, 255).astype(np.uint8)
    rgba[..., 2] = np.clip(mask_array, 0, 255).astype(np.uint8)
    rgba[..., 3] = mask_array
    return Image.fromarray(rgba)


def write_contact_sheet(
    output_path: Path,
    *,
    vertices: Any,
    mesh_record: dict[str, Any],
    source_sha256: str,
) -> None:
    from PIL import Image, ImageDraw

    tile_width, tile_height = 520, 390
    header_height, footer_height = 118, 70
    gap = 18
    canvas_width = tile_width * 3 + gap * 4
    canvas_height = header_height + tile_height * 2 + gap * 3 + footer_height
    canvas = Image.new("RGB", (canvas_width, canvas_height), "#070b12")
    draw = ImageDraw.Draw(canvas)
    title_font = _font(30, bold=True)
    body_font = _font(18)
    label_font = _font(22, bold=True)
    small_font = _font(15)

    name = mesh_record["displayName"]
    resource_id = mesh_record["resourceId"]
    extents = mesh_record["boundsMm"]["extents"]
    draw.text((gap, 14), f"{name} — kaynak eksen contact sheet", fill="#f8fafc", font=title_font)
    draw.text(
        (gap, 57),
        (
            f"resourceId={resource_id}  extents(mm)={extents}  "
            f"V={mesh_record['vertexCount']:,}  T={mesh_record['triangleCount']:,}"
        ),
        fill="#9fb3c8",
        font=body_font,
    )
    draw.text(
        (gap, 86),
        f"CAD SHA-256: {source_sha256}",
        fill="#64748b",
        font=small_font,
    )

    for index, (label, right, up, depth, legend) in enumerate(VIEW_DEFINITIONS):
        row, column = divmod(index, 3)
        left = gap + column * (tile_width + gap)
        top = header_height + gap + row * (tile_height + gap)
        draw.rounded_rectangle(
            (left, top, left + tile_width, top + tile_height),
            radius=16,
            fill="#111827",
            outline="#243244",
            width=2,
        )
        rendered = _render_point_view(
            vertices,
            right,
            up,
            depth,
            width=tile_width - 20,
            height=tile_height - 78,
        )
        canvas.paste(rendered, (left + 10, top + 50), rendered)
        draw.text(
            (left + 16, top + 12),
            f"KAMERA {label} TARAFINDA",
            fill="#00e5ff",
            font=label_font,
        )
        draw.text(
            (left + 16, top + tile_height - 25),
            legend,
            fill="#94a3b8",
            font=small_font,
        )

    footer_top = canvas_height - footer_height + 4
    draw.rounded_rectangle(
        (gap, footer_top, canvas_width - gap, canvas_height - gap),
        radius=12,
        fill="#3a2a07",
        outline="#ffb020",
        width=2,
    )
    draw.text(
        (gap + 18, footer_top + 14),
        "AR-02: BURUN hangi ±X/±Y/±Z yönüne, ÜST hangi yöne bakıyor?",
        fill="#ffd166",
        font=body_font,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output_path, format="PNG", optimize=True)


def write_contact_sheets(
    output_dir: Path,
    render_inputs: list[tuple[Any, dict[str, Any], Any]],
    source_sha256: str,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    records = []
    for _mesh, mesh_record, vertices in render_inputs:
        file_name = f"{mesh_record['assetKey'] or mesh_record['resourceId']}_source_axes.png"
        output_path = output_dir / file_name
        write_contact_sheet(
            output_path,
            vertices=vertices,
            mesh_record=mesh_record,
            source_sha256=source_sha256,
        )
        records.append(
            {
                "assetKey": mesh_record["assetKey"],
                "resourceId": mesh_record["resourceId"],
                "fileName": file_name,
                "sha256": sha256_file(output_path),
            }
        )
    index = {
        "schemaVersion": 1,
        "toolVersion": TOOL_VERSION,
        "sourceSha256": source_sha256,
        "status": "AR_02_PENDING_USER_CONFIRMATION",
        "sheets": records,
    }
    write_json(output_dir / "index.json", index)
    return index


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "3MF kaynağını lib3mf ile doğrular ve AR-02 kaynak-eksen "
            "contact sheet'lerini üretir."
        )
    )
    parser.add_argument("--input", type=Path, required=True, help="Kaynak .3mf")
    parser.add_argument(
        "--source-config", type=Path, default=DEFAULT_SOURCE_CONFIG
    )
    parser.add_argument(
        "--asset-manifest", type=Path, default=DEFAULT_ASSET_MANIFEST
    )
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument(
        "--contact-sheet-dir", type=Path, default=DEFAULT_CONTACT_SHEETS
    )
    parser.add_argument(
        "--skip-contact-sheets",
        action="store_true",
        help="Yalnız JSON rapor üret",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        source_config = load_json(args.source_config)
        asset_manifest = load_json(args.asset_manifest)
        report, render_inputs = inspect_3mf(
            args.input,
            source_config=source_config,
            asset_manifest=asset_manifest,
        )
        if not args.skip_contact_sheets:
            report["contactSheets"] = write_contact_sheets(
                args.contact_sheet_dir,
                render_inputs,
                report["source"]["sha256"],
            )
        write_json(args.report, report)
    except InspectionError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(
        json.dumps(
            {
                "status": "INSPECTED_AR_01_AR_02_PENDING",
                "report": str(args.report),
                "meshCount": report["source"]["meshCount"],
                "sourceSha256": report["source"]["sha256"],
                "contactSheetDir": (
                    None if args.skip_contact_sheets else str(args.contact_sheet_dir)
                ),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
