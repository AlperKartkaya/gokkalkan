import blenderproc as bproc

"""Render one deterministic F16 smoke frame through BlenderProc."""

import colorsys
import json
import tomllib
from pathlib import Path

import bpy
import numpy as np

ROOT = Path(__file__).resolve().parents[3]
SYNTHETIC = ROOT / "perception/synthetic"
PLAN = SYNTHETIC / "generated/render_plans/committee_tilt_sweep_v1.json"
ASSET_DIR = SYNTHETIC / "generated/normalized_assets/f16/lod0"
OUTPUT = SYNTHETIC / "generated/render_batches/smoke"
MATERIAL_PROFILE = SYNTHETIC / "config/material_profiles/nominal_colors.toml"


def select_smoke_record(records: list[dict]) -> dict:
    for record in records:
        if (
            record["assetKey"] == "f16"
            and record["presentationClass"] == "dusman_f16_kirmizi"
            and record["routeId"] == "ROTA_2"
            and record["longitudinalDistanceM"] == 5.0
            and record["topSurfaceViewBucketDeg"] == 12.0
        ):
            return record
    raise RuntimeError("Smoke render kaydı bulunamadı")


def material_rgb(profile: dict, record: dict) -> list[float]:
    base_hex = profile["enemyHex"].lstrip("#")
    rgb = tuple(int(base_hex[index : index + 2], 16) / 255 for index in (0, 2, 4))
    hue, saturation, value = colorsys.rgb_to_hsv(*rgb)
    variant = next(
        item
        for item in profile["appearanceVariants"]
        if item["id"] == record["appearanceProfileId"]
    )
    adjusted = colorsys.hsv_to_rgb(
        hue,
        min(1.0, saturation * float(variant["saturationScale"])),
        min(1.0, value * float(variant["valueScale"])),
    )
    return [*adjusted, 1.0]


def main() -> None:
    bproc.init()
    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    record = select_smoke_record(plan["records"])
    material_profile = tomllib.loads(MATERIAL_PROFILE.read_text(encoding="utf-8"))
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
    material.set_principled_shader_value(
        "Base Color", material_rgb(material_profile, record)
    )
    material.set_principled_shader_value("Roughness", 0.58)
    target.add_material(material)

    balloon_contract = record["sceneGroundTruth"]["balloon"]
    balloon_location = np.asarray(record["targetPositionM"]) + np.asarray(
        balloon_contract["relativeCenterM"]
    )
    balloon = bproc.object.create_primitive(
        "SPHERE",
        scale=[balloon_contract["diameterM"] / 2] * 3,
        location=balloon_location.tolist(),
    )
    balloon.set_cp("category_id", 7)
    balloon_material = bproc.material.create("balon_kirmizi")
    balloon_material.set_principled_shader_value(
        "Base Color", [0.9569, 0.0392, 0.0392, 1.0]
    )
    balloon_material.set_principled_shader_value("Roughness", 0.48)
    balloon.add_material(balloon_material)

    rope_center = (np.asarray(record["targetPositionM"]) + balloon_location) / 2
    rope = bproc.object.create_primitive(
        "CYLINDER",
        scale=[0.004, 0.004, 0.16],
        location=rope_center.tolist(),
    )
    rope.set_cp("category_id", 0)
    rope_material = bproc.material.create("balon_ipi")
    rope_material.set_principled_shader_value("Base Color", [0.08, 0.08, 0.08, 1.0])
    rope.add_material(rope_material)

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
