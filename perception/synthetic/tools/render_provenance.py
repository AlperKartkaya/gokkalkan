"""Stable provenance fingerprint for one CAD render record."""

from __future__ import annotations

import hashlib
import json
from typing import Any


def render_fingerprint(plan: dict[str, Any], record: dict[str, Any]) -> str:
    """Bind cached output to CAD, orientation manifest and record pose."""

    payload = {
        "sourceCadSha256": plan["sourceCadSha256"],
        "assetManifestSha256": plan["assetManifestSha256"],
        "record": record,
    }
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
