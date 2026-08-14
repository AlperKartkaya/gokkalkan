import blenderproc as bproc

"""Render one deterministic F16 smoke frame through BlenderProc."""

import json
from pathlib import Path

import bpy
import numpy as np

ROOT = Path(__file__).resolve().parents[3]
SYNTHETIC = ROOT / "perception/synthetic"
PLAN = SYNTHETIC / "generated/render_plans/committee_tilt_sweep_v1.json"
ASSET_DIR = SYNTHETIC / "generated/normalized_assets/f16/lod0"
OUTPUT = SYNTHETIC / "generated/render_batches/smoke"


def select_smoke_record(records: list[dict]) -> dict:
    for record in records:
        if (
            record["assetKey"] == "f16"
            and record["presentationClass"] == "dusman_f16_kirmizi"
            and record["distanceM"] == 5.0
            and record["viewYawBucketDeg"] == 0.0
            and record["topSurfaceViewBucketDeg"] == 12.0
            and abs(record["targetPositionM"][0]) < 0.12
            and abs(record["targetPositionM"][2] - 1.30) < 0.10
        ):
            return record
    raise RuntimeError("Smoke render kaydı bulunamadı")


def main() -> None:
    bproc.init()
    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    record = select_smoke_record(plan["records"])
    vertices = np.load(ASSET_DIR / "vertices_m.npy", allow_pickle=False)
    faces = np.load(ASSET_DIR / "faces.npy", allow_pickle=False)

    mesh = bpy.data.meshes.new("f16_lod0")
    mesh.from_pydata(vertices.tolist(), [], faces.tolist())
    mesh.update()
    target = bproc.object.create_from_blender_mesh(mesh, "f16")
    target.set_location(record["targetPositionM"])
    target.set_rotation_mat(np.asarray(record["targetRotationWorld3x3"]))
    target.set_cp("category_id", 1)

    material = bproc.material.create("dusman_kirmizi")
    material.set_principled_shader_value("Base Color", [0.9569, 0.0392, 0.0392, 1.0])
    material.set_principled_shader_value("Roughness", 0.58)
    target.add_material(material)

    ground = bproc.object.create_primitive(
        "PLANE", scale=[8.0, 8.0, 1.0], location=[0.0, 7.5, 0.0]
    )
    ground.set_cp("category_id", 0)
    ground_material = bproc.material.create("ground")
    ground_material.set_principled_shader_value("Base Color", [0.025, 0.03, 0.04, 1.0])
    ground_material.set_principled_shader_value("Roughness", 0.9)
    ground.add_material(ground_material)

    bproc.renderer.set_world_background([0.005, 0.008, 0.012], strength=0.3)
    key = bproc.types.Light()
    key.set_type("AREA")
    key.set_location([-2.0, 1.0, 4.0])
    key.set_energy(450.0)
    fill = bproc.types.Light()
    fill.set_type("AREA")
    fill.set_location([2.0, 4.0, 3.0])
    fill.set_energy(250.0)

    bproc.camera.set_resolution(640, 360)
    camera_location = np.asarray([0.0, 0.0, 1.30])
    target_location = np.asarray(record["targetPositionM"])
    rotation = bproc.camera.rotation_from_forward_vec(target_location - camera_location)
    camera_pose = bproc.math.build_transformation_mat(camera_location, rotation)
    bproc.camera.add_camera_pose(camera_pose)

    bproc.renderer.set_max_amount_of_samples(16)
    bproc.renderer.enable_depth_output(activate_antialiasing=False)
    bproc.renderer.enable_segmentation_output(
        map_by=["instance", "class", "name"],
        default_values={"category_id": 0},
    )
    data = bproc.renderer.render()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    bproc.writer.write_hdf5(str(OUTPUT), data)
    (OUTPUT / "record.json").write_text(
        json.dumps(record, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


main()
