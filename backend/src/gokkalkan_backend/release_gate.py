"""Reproducible release manifest and three-gate readiness decision."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Iterable


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_release_manifest(
    *,
    root: str | Path,
    version: str,
    component_paths: Iterable[str],
    output: str | Path,
    software_gate: bool,
    sensor_evidence: str | Path | None = None,
    hil_evidence: str | Path | None = None,
) -> dict[str, Any]:
    base = Path(root).resolve()
    components = []
    for value in sorted(set(component_paths)):
        path = (base / value).resolve()
        try:
            relative = path.relative_to(base)
        except ValueError as exc:
            raise ValueError(f"release path escapes root: {value}") from exc
        if not path.exists():
            raise ValueError(f"release component missing: {value}")
        files = (
            [path]
            if path.is_file()
            else sorted(
                item
                for item in path.rglob("*")
                if item.is_file()
                and "__pycache__" not in item.parts
                and item.suffix not in {".pyc", ".pyo"}
            )
        )
        for file_path in files:
            components.append(
                {
                    "path": str(file_path.relative_to(base)),
                    "sha256": _sha256(file_path),
                }
            )

    def physical_gate(path_value: str | Path | None, key: str) -> tuple[bool, str | None]:
        if path_value is None:
            return False, None
        path = Path(path_value)
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload.get(key) is True, _sha256(path)

    sensor_ok, sensor_hash = physical_gate(sensor_evidence, "physicalGatePassed")
    hil_ok, hil_hash = physical_gate(hil_evidence, "physicalGatePassed")
    gates = {"software": software_gate, "sensor": sensor_ok, "hil": hil_ok}
    manifest = {
        "schemaVersion": 1,
        "version": version,
        "components": components,
        "evidence": {"sensorSha256": sensor_hash, "hilSha256": hil_hash},
        "gates": gates,
        "readyForPhysicalManufacturingClaim": all(gates.values()),
        "physicalOutput": False,
    }
    target = Path(output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def verify_release_manifest(
    manifest_path: str | Path, *, root: str | Path = "."
) -> dict[str, Any]:
    source = Path(manifest_path)
    base = Path(root).resolve()
    manifest = json.loads(source.read_text(encoding="utf-8"))
    errors: list[str] = []
    for component in manifest.get("components", []):
        path = (base / str(component.get("path", ""))).resolve()
        try:
            path.relative_to(base)
        except ValueError:
            errors.append("COMPONENT_ESCAPES_ROOT")
            continue
        if not path.is_file():
            errors.append(f"COMPONENT_MISSING:{component.get('path')}")
        elif _sha256(path) != component.get("sha256"):
            errors.append(f"COMPONENT_HASH_MISMATCH:{component.get('path')}")
    gates = manifest.get("gates", {})
    if manifest.get("readyForPhysicalManufacturingClaim") is not all(
        gates.get(name) is True for name in ("software", "sensor", "hil")
    ):
        errors.append("GATE_SUMMARY_MISMATCH")
    return {
        "ok": not errors,
        "errors": sorted(set(errors)),
        "version": manifest.get("version"),
        "gates": gates,
        "physicalOutput": False,
    }
