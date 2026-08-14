"""Extract centered, scaled LOD0 render assets from the verified 3MF source."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
from inspect_3mf import UNIT_TO_MM, InspectionError, _lib3mf, load_json, sha256_file

DEFAULT_SOURCE = Path("Modeller.3mf")
DEFAULT_SOURCE_CONFIG = Path("perception/synthetic/config/cad_source.json")
DEFAULT_ASSET_MANIFEST = Path("perception/synthetic/config/cad_asset_manifest.json")
DEFAULT_OUTPUT = Path("perception/synthetic/generated/normalized_assets")


def _faces_array(mesh: Any) -> np.ndarray:
    return np.asarray(
        [
            [int(value) for value in mesh.GetTriangle(index).Indices]
            for index in range(mesh.GetTriangleCount())
        ],
        dtype=np.uint32,
    )


def _vertices_array(mesh: Any, unit_to_mm: float) -> np.ndarray:
    return np.asarray(
        [[float(value) * unit_to_mm for value in vertex.Coordinates] for vertex in mesh.GetVertices()],
        dtype=np.float64,
    )


def topology_diagnostics(vertices: np.ndarray, faces: np.ndarray) -> dict[str, int | bool]:
    repeated_index = (
        (faces[:, 0] == faces[:, 1])
        | (faces[:, 1] == faces[:, 2])
        | (faces[:, 2] == faces[:, 0])
    )
    a = vertices[faces[:, 1]] - vertices[faces[:, 0]]
    b = vertices[faces[:, 2]] - vertices[faces[:, 0]]
    zero_area = np.linalg.norm(np.cross(a, b), axis=1) <= 1e-12

    canonical_faces = np.sort(faces, axis=1)
    _, face_counts = np.unique(canonical_faces, axis=0, return_counts=True)
    edges = np.concatenate(
        (faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]]), axis=0
    )
    edges.sort(axis=1)
    _, edge_counts = np.unique(edges, axis=0, return_counts=True)
    return {
        "degenerateTriangleCount": int(np.count_nonzero(repeated_index | zero_area)),
        "duplicateTriangleCount": int(np.sum(np.maximum(face_counts - 1, 0))),
        "boundaryEdgeCount": int(np.count_nonzero(edge_counts == 1)),
        "nonManifoldEdgeCount": int(np.count_nonzero(edge_counts > 2)),
        "closedTwoManifoldByEdgeCount": bool(np.all(edge_counts == 2)),
    }


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def convert_assets(
    *,
    source_path: Path,
    source_config: dict[str, Any],
    asset_manifest: dict[str, Any],
    output_dir: Path,
) -> dict[str, Any]:
    actual_hash = sha256_file(source_path)
    if actual_hash != source_config["expectedSha256"]:
        raise InspectionError("CAD SHA-256 uyuşmuyor")

    lib3mf = _lib3mf()
    wrapper = lib3mf.get_wrapper()
    model = wrapper.CreateModel()
    model.QueryReader("3mf").ReadFromFile(str(source_path.resolve()))
    unit_name = lib3mf.ModelUnit(model.GetUnit()).name
    unit_to_mm = UNIT_TO_MM[unit_name]
    meshes: dict[int, Any] = {}
    iterator = model.GetMeshObjects()
    while iterator.MoveNext():
        mesh = iterator.GetCurrentMeshObject()
        meshes[int(mesh.GetResourceID())] = mesh

    records = []
    for asset in sorted(asset_manifest["assets"], key=lambda item: item["assetKey"]):
        mesh = meshes[int(asset["sourceResourceId"])]
        vertices_mm = _vertices_array(mesh, unit_to_mm)
        faces = _faces_array(mesh)
        orientation = np.asarray(
            asset["orientation"]["sourceToPresentationRotation3x3"],
            dtype=np.float64,
        )
        vertices_mm = vertices_mm @ orientation.T
        center_mm = (vertices_mm.min(axis=0) + vertices_mm.max(axis=0)) / 2.0
        vertices_m = (
            (vertices_mm - center_mm)
            * float(asset["scale"]["factor"])
            / 1000.0
        ).astype(np.float32)
        diagnostics = topology_diagnostics(vertices_m.astype(np.float64), faces)

        asset_dir = output_dir / asset["assetKey"] / "lod0"
        asset_dir.mkdir(parents=True, exist_ok=True)
        vertices_path = asset_dir / "vertices_m.npy"
        faces_path = asset_dir / "faces.npy"
        np.save(vertices_path, vertices_m, allow_pickle=False)
        np.save(faces_path, faces, allow_pickle=False)
        bounds = vertices_m.max(axis=0) - vertices_m.min(axis=0)
        records.append(
            {
                "assetKey": asset["assetKey"],
                "lod": "LOD0",
                "sourceResourceId": asset["sourceResourceId"],
                "vertexCount": len(vertices_m),
                "triangleCount": len(faces),
                "boundsM": [round(float(value), 6) for value in bounds],
                "longestAxisM": round(float(bounds.max()), 6),
                "scaleStatus": asset["scale"]["status"],
                "scaleFactor": asset["scale"]["factor"],
                "orientationStatus": asset["orientation"]["status"],
                "sourceCenterMm": [round(float(value), 6) for value in center_mm],
                "topology": diagnostics,
                "renderUsable": bool(len(vertices_m) and len(faces)),
                "files": {
                    "vertices": str(vertices_path.relative_to(output_dir)),
                    "verticesSha256": _sha256(vertices_path),
                    "faces": str(faces_path.relative_to(output_dir)),
                    "facesSha256": _sha256(faces_path),
                },
            }
        )

    output = {
        "schemaVersion": 1,
        "status": "LOD0_VERIFIED_3MF_SCALE",
        "sourceCadSha256": actual_hash,
        "assets": records,
    }
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--source-config", type=Path, default=DEFAULT_SOURCE_CONFIG)
    parser.add_argument("--asset-manifest", type=Path, default=DEFAULT_ASSET_MANIFEST)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = convert_assets(
        source_path=args.input,
        source_config=load_json(args.source_config),
        asset_manifest=load_json(args.asset_manifest),
        output_dir=args.output_dir,
    )
    print(
        json.dumps(
            {
                "status": result["status"],
                "assets": len(result["assets"]),
                "output": str(args.output_dir / "manifest.json"),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
