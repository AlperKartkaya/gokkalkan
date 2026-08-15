"""Resume-friendly plan renderer built on the one-record BlenderProc runner."""

from __future__ import annotations

import argparse
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from render_provenance import render_fingerprint

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
    parser.add_argument(
        "--workers",
        type=int,
        default=int(os.environ.get("GOKKALKAN_RENDER_WORKERS", "0")),
        help="Eşzamanlı bağımsız Blender süreci; 0 güvenli otomatik seçimdir",
    )
    parser.add_argument(
        "--render-device",
        choices=("auto", "cpu", "metal", "optix", "cuda", "hip"),
        default=os.environ.get("GOKKALKAN_RENDER_DEVICE", "auto").lower(),
    )
    parser.add_argument(
        "--blender",
        type=Path,
        default=Path(os.environ.get("GOKKALKAN_BLENDER", str(BLENDER))),
    )
    parser.add_argument(
        "--retries",
        type=int,
        default=int(os.environ.get("GOKKALKAN_RENDER_RETRIES", "2")),
        help="Tekil Blender çökmesinde yeniden deneme sayısı",
    )
    return parser.parse_args()


def auto_worker_count(requested: int) -> int:
    if requested < 0:
        raise ValueError("workers negatif olamaz")
    if requested > 0:
        return requested
    # Multiple Cycles processes can contend for one GPU and exhaust unified
    # memory. Two workers overlap Blender startup/validation without launching
    # an unbounded process per CPU core.
    return max(1, min(2, (os.cpu_count() or 2) // 4))


def _is_complete(batch_dir: Path, expected_fingerprint: str) -> bool:
    provenance_path = batch_dir / "render-provenance.json"
    if not (batch_dir / "record.json").is_file() or len(list(batch_dir.glob("*.hdf5"))) != 1:
        return False
    try:
        provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return False
    return provenance.get("renderFingerprint") == expected_fingerprint


def _render_one(
    *,
    record: dict[str, Any],
    plan_path: Path,
    output: Path,
    blender: Path,
    render_device: str,
    cpu_threads: int,
    retries: int,
    expected_fingerprint: str,
) -> str:
    batch_dir = output / str(record["recordId"])
    if retries < 0:
        raise ValueError("retries negatif olamaz")
    for attempt in range(retries + 1):
        if batch_dir.exists() and not _is_complete(batch_dir, expected_fingerprint):
            shutil.rmtree(batch_dir)
        command = [
            str(BLENDERPROC),
            "run",
            "--custom-blender-path",
            str(blender),
            str(RENDER_SCRIPT),
            "--plan",
            str(plan_path),
            "--record-id",
            str(record["recordId"]),
            "--output",
            str(batch_dir),
            "--render-device",
            render_device,
            "--cpu-threads",
            str(cpu_threads),
        ]
        try:
            subprocess.run(command, cwd=ROOT, check=True)
            break
        except subprocess.CalledProcessError:
            if attempt >= retries:
                raise
            delay = 2 * (attempt + 1)
            print(
                f"{record['recordId']} Blender çöktü; "
                f"{delay}s sonra yeniden deneniyor ({attempt + 1}/{retries})",
                flush=True,
            )
            time.sleep(delay)
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
    return str(record["recordId"])


def main() -> int:
    args = parse_args()
    workers = auto_worker_count(args.workers)
    if args.retries < 0:
        raise ValueError("retries negatif olamaz")
    if not BLENDERPROC.is_file():
        raise RuntimeError(f"BlenderProc bulunamadı: {BLENDERPROC}")
    if not args.blender.exists():
        raise RuntimeError(f"Blender bulunamadı: {args.blender}")
    plan = json.loads(args.plan.read_text(encoding="utf-8"))
    records = plan["records"][: args.limit]
    args.output.mkdir(parents=True, exist_ok=True)
    pending = [
        record
        for record in records
        if args.force
        or not _is_complete(
            args.output / str(record["recordId"]),
            render_fingerprint(plan, record),
        )
    ]
    skipped = len(records) - len(pending)
    rendered = 0
    cpu_threads = max(1, (os.cpu_count() or 1) // workers)
    print(
        f"Render: selected={len(records)} pending={len(pending)} workers={workers} "
        f"device={args.render_device} cpu_threads_per_worker={cpu_threads}",
        flush=True,
    )
    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="cad-render") as pool:
        futures: dict[Future[str], dict[str, Any]] = {
            pool.submit(
                _render_one,
                record=record,
                plan_path=args.plan,
                output=args.output,
                blender=args.blender,
                render_device=args.render_device,
                cpu_threads=cpu_threads,
                retries=args.retries,
                expected_fingerprint=render_fingerprint(plan, record),
            ): record
            for record in pending
        }
        try:
            for future in as_completed(futures):
                record_id = future.result()
                rendered += 1
                print(
                    f"[{rendered}/{len(pending)}] {record_id} PASS",
                    flush=True,
                )
        except BaseException:
            for future in futures:
                future.cancel()
            raise

    summary = {
        "status": "PASS",
        "plan": str(args.plan),
        "selected": len(records),
        "rendered": rendered,
        "skipped": skipped,
        "workers": workers,
        "renderDevice": args.render_device,
        "cpuThreadsPerWorker": cpu_threads,
        "retries": args.retries,
    }
    (args.output / "batch-summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
