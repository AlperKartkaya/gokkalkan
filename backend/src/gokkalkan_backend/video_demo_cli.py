"""CLI surface for opening truthful capability-video rehearsal sessions."""

from __future__ import annotations

import argparse
import json

from .video_demo import CAPABILITIES, VideoDemoError, finish_run, start_run


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="gokkalkan video-demo")
    sub = parser.add_subparsers(dest="operation", required=True)
    run = sub.add_parser("run", help="video yeteneği için kanıt oturumu açar; fiziksel komut göndermez")
    run.add_argument("--capability", choices=tuple(CAPABILITIES), required=True)
    run.add_argument("--api-url", default="http://127.0.0.1:8088")
    run.add_argument("--output-root", default="/var/lib/gokkalkan/video-runs")
    run.add_argument("--timeout-sec", type=float, default=3.0)
    finish = sub.add_parser("finish", help="oturumun bitiş sağlık/state/events kanıtını kaydeder")
    finish.add_argument("--run-path", required=True)
    finish.add_argument("--api-url", default="http://127.0.0.1:8088")
    finish.add_argument("--timeout-sec", type=float, default=3.0)
    args = parser.parse_args(argv)
    try:
        if args.operation == "run":
            result = start_run(
                args.capability,
                api_url=args.api_url,
                output_root=args.output_root,
                timeout_sec=args.timeout_sec,
            )
        else:
            report = finish_run(args.run_path, api_url=args.api_url, timeout_sec=args.timeout_sec)
    except VideoDemoError as exc:
        print(json.dumps({"ok": False, "error": str(exc), "physicalOutput": False}, ensure_ascii=False))
        return 1
    if args.operation == "finish":
        print(json.dumps({"ok": True, "runId": report["runId"], "capability": report["capability"], "physicalOutput": False}, ensure_ascii=False))
    else:
        print(json.dumps({
            "ok": True,
            "runId": result.run_id,
            "capability": result.capability,
            "path": str(result.path),
            "physicalOutput": False,
            "nextPhysicalAction": result.report["physicalActionRequired"],
        }, ensure_ascii=False))
    return 0
