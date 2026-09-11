"""LIWC 词典加载器。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List


def load_liwc_dictionary(path: str) -> Dict[str, List[str]]:
    """加载 LIWC 词典 JSON。"""
    file_path = Path(path)
    if not file_path.exists():
        return {}

    payload = json.loads(file_path.read_text(encoding="utf-8"))
    if isinstance(payload, dict) and "categories" in payload:
        payload = payload["categories"]

    if not isinstance(payload, dict):
        return {}

    result: Dict[str, List[str]] = {}
    for key, values in payload.items():
        if not isinstance(values, list):
            continue
        result[str(key)] = [str(item) for item in values if str(item).strip()]
    return result
