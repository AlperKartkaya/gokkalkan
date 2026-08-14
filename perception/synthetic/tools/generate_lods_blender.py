import bpy

"""Generate deterministic Blender decimation LODs from normalized LOD0 arrays."""

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--assets-root",
        type=Path,
        default=Path("perception/synthetic/generated/normalized_assets"),
    )
    return parser.parse_args(sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else [])


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def decimate(vertices: np.ndarray, faces: np.ndarray, *, ratio: float) -> tuple[np.ndarray, np.ndarray]:
    mesh = bpy.data.meshes.new("source")
    mesh.from_pydata(vertices.tolist(), [], faces.tolist())
    mesh.update()
    obj = bpy.data.objects.new("source", mesh)
    bpy.context.collection.objects.link(obj)
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    modifier = obj.modifiers.new(name="deterministic_decimate", type="DECIMATE")
    modifier.decimate_type = "COLLAPSE"
    modifier.ratio = ratio
    modifier.use_collapse_triangulate = True
    bpy.ops.object.modifier_apply(modifier=modifier.name)
    result_vertices = np.asarray([vertex.co[:] for vertex in mesh.vertices], dtype=np.float32)
    result_faces = np.asarray([polygon.vertices[:] for polygon in mesh.polygons], dtype=np.uint32)
    bpy.data.objects.remove(obj, do_unlink=True)
    return result_vertices, result_faces


def main() -> None:
    args = parse_args()
    manifest_path = args.assets_root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    source_records = {record["assetKey"]: record for record in manifest["assets"] if record["lod"] == "LOD0"}
    records = list(source_records.values())
    for asset_key, source in sorted(source_records.items()):
        lod0 = args.assets_root / asset_key / "lod0"
        vertices = np.load(lod0 / "vertices_m.npy", allow_pickle=False)
        faces = np.load(lod0 / "faces.npy", allow_pickle=False)
        # Conservative ratios are intentional: target silhouettes carry the
        # classification signal and must remain stable at long range.
        for lod_name, ratio in (("LOD1", 0.95), ("LOD2", 0.90)):
            lod_vertices, lod_faces = decimate(vertices, faces, ratio=ratio)
            lod_dir = args.assets_root / asset_key / lod_name.lower()
            lod_dir.mkdir(parents=True, exist_ok=True)
            vertices_path = lod_dir / "vertices_m.npy"
            faces_path = lod_dir / "faces.npy"
            np.save(vertices_path, lod_vertices, allow_pickle=False)
            np.save(faces_path, lod_faces, allow_pickle=False)
            bounds = lod_vertices.max(axis=0) - lod_vertices.min(axis=0)
            records.append(
                {
                    **{key: value for key, value in source.items() if key not in {"files", "lod", "vertexCount", "triangleCount", "boundsM", "longestAxisM"}},
                    "lod": lod_name,
                    "decimationRatio": ratio,
                    "vertexCount": len(lod_vertices),
                    "triangleCount": len(lod_faces),
                    "boundsM": [round(float(value), 6) for value in bounds],
                    "longestAxisM": round(float(bounds.max()), 6),
                    "files": {
                        "vertices": str(vertices_path.relative_to(args.assets_root)),
                        "verticesSha256": sha256(vertices_path),
                        "faces": str(faces_path.relative_to(args.assets_root)),
                        "facesSha256": sha256(faces_path),
                    },
                }
            )
    manifest["status"] = "LOD_COMPLETE_PROVISIONAL_SCALE"
    manifest["assets"] = sorted(records, key=lambda item: (item["assetKey"], item["lod"]))
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": manifest["status"], "records": len(records)}))


main()
