"""CogSec sidecar listener.

监听 simulation state 更新文件，不改核心循环。
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import time

from app.modules import PrivacySanitizer, T0FastResponder


def main() -> int:
    parser = argparse.ArgumentParser(description="CogSec sidecar listener")
    parser.add_argument("--state-file", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("cogsec_sidecar_events.jsonl"))
    parser.add_argument("--poll-seconds", type=float, default=1.0)
    args = parser.parse_args()

    responder = T0FastResponder()
    sanitizer = PrivacySanitizer(enabled=False)
    last_mtime = 0.0

    args.output.parent.mkdir(parents=True, exist_ok=True)
    print(f"[sidecar] watching {args.state_file}")

    while True:
        if not args.state_file.exists():
            time.sleep(args.poll_seconds)
            continue

        stat = args.state_file.stat()
        if stat.st_mtime <= last_mtime:
            time.sleep(args.poll_seconds)
            continue

        last_mtime = stat.st_mtime
        payload = json.loads(args.state_file.read_text(encoding="utf-8"))
        text = str(payload.get("latest_text", ""))
        sanitized = sanitizer.sanitize(text)
        t0 = responder.scan(text)

        event = {
            "timestamp": time.time(),
            "state_id": payload.get("id"),
            "t0_alert": t0["alert"],
            "t0_hits": t0["hits"],
            "sanitized_text": sanitized.sanitized_text,
        }
        with args.output.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False) + "\n")

        time.sleep(args.poll_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
