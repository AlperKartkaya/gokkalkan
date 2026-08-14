"""Resume-friendly plan renderer built on the one-record BlenderProc runner."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SYNTHETIC_ROOT = ROOT / "perception/synthetic"
DEFAULT_PLAN = SYNTHETIC_ROOT / "generated/render_plans/cad_pilot_378.json"
DEFAULT_OUTPUT = SYNTHETIC_ROOT / "generated/render_batches/cad_pilot_378"
BLENDERPROC = ROOT / ".venv-synthetic/bin/blenderproc"
BLENDER = ROOT / ".tools/blender-4.2.1/Blender.app"
RENDER_SCRIPT = SYNTHETIC_ROOT / "tools/render_dataset.py"
VALIDATE_SCRIPT = SYNTHETIC_ROOT / "tools/validate_render_batch.py"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, default=DEFAULT_PLAN)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    plan = json.loads(args.plan.read_text(encoding="utf-8"))
    records = plan["records"][: args.limit]
    args.output.mkdir(parents=True, exist_ok=True)
    rendered = skipped = 0
    for index, record in enumerate(records, start=1):
        batch_dir = args.output / record["recordId"]
        complete = (batch_dir / "record.json").is_file() and len(
            list(batch_dir.glob("*.hdf5"))
        ) == 1
        if complete and not args.force:
            skipped += 1
            continue
        command = [
            str(BLENDERPROC),
            "run",
            "--custom-blender-path",
            str(BLENDER),
            str(RENDER_SCRIPT),
            "--plan",
            str(args.plan),
            "--record-id",
            record["recordId"],
            "--output",
            str(batch_dir),
        ]
        subprocess.run(command, cwd=ROOT, check=True)
        subprocess.run(
            [
                str(ROOT / ".venv-synthetic/bin/python"),
                str(VALIDATE_SCRIPT),
                "--batch",
                str(batch_dir),
                "--output",
                str(batch_dir / "validation.json"),
            ],
            cwd=ROOT,
            check=True,
        )
        rendered += 1
        print(f"[{index}/{len(records)}] {record['recordId']} PASS", flush=True)

    summary = {
        "status": "PASS",
        "plan": str(args.plan),
        "selected": len(records),
        "rendered": rendered,
        "skipped": skipped,
    }
    (args.output / "batch-summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
