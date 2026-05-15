"""T0 规则快速响应模块。

在任何 LLM 推理前执行，仅做正则检测，目标是亚秒级返回。
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import os
import re
import time
from typing import Any, Dict, List


@dataclass
class T0Hit:
    """单条命中结果。"""

    rule_id: str
    matched_text: str
    span_start: int
    span_end: int
    tags: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class T0FastResponder:
    """基于正则的红旗检测器。"""

    DEFAULT_PATTERNS: List[Dict[str, Any]] = [
        {
            "id": "screen_share_bank_card",
            "tags": ["screen_share", "bank_card"],
            "regex": r"(共享屏幕|远程(控制|协助)|screen\s*share).{0,24}(银行卡|卡号|cvv|验证码|bank\s*card)",
        },
        {
            "id": "safe_account_transfer",
            "tags": ["safe_account", "transfer"],
            "regex": r"(安全账户|监管账户|safe\s*account).{0,24}(转账|汇款|打款|transfer)",
        },
        {
            "id": "police_secrecy_isolation",
            "tags": ["police", "secrecy", "isolation"],
            "regex": r"(公安|警方|police).{0,28}(保密|不要告诉|单独联系|隔离|不要联系家人|secrecy|isolation)",
        },
    ]

    def __init__(self, patterns_path: str | None = None):
        self.patterns_path = patterns_path or os.environ.get("T0_PATTERNS_PATH")
        self._compiled = self._compile_patterns(self._load_patterns())

    def scan(self, text: str) -> Dict[str, Any]:
        """执行 T0 扫描并返回结构化结果。"""
        started = time.perf_counter()
        source = text or ""
        hits: List[T0Hit] = []

        for rule in self._compiled:
            for match in rule["pattern"].finditer(source):
                hits.append(
                    T0Hit(
                        rule_id=rule["id"],
                        matched_text=match.group(0),
                        span_start=match.start(),
                        span_end=match.end(),
                        tags=list(rule["tags"]),
                    )
                )

        elapsed_ms = round((time.perf_counter() - started) * 1000, 3)
        return {
            "alert": bool(hits),
            "latency_ms": elapsed_ms,
            "target_met": elapsed_ms < 500.0,
            "hits": [item.to_dict() for item in hits],
            "summary": self._build_summary(hits),
        }

    def _load_patterns(self) -> List[Dict[str, Any]]:
        if not self.patterns_path:
            return list(self.DEFAULT_PATTERNS)

        if not os.path.exists(self.patterns_path):
            return list(self.DEFAULT_PATTERNS)

        try:
            with open(self.patterns_path, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except Exception:
            return list(self.DEFAULT_PATTERNS)

        if isinstance(payload, dict):
            payload = payload.get("patterns", [])

        patterns: List[Dict[str, Any]] = []
        for item in payload if isinstance(payload, list) else []:
            if not isinstance(item, dict):
                continue
            if not item.get("id") or not item.get("regex"):
                continue
            tags = item.get("tags", [])
            if not isinstance(tags, list):
                tags = []
            patterns.append(
                {
                    "id": str(item["id"]),
                    "regex": str(item["regex"]),
                    "tags": [str(tag) for tag in tags],
                }
            )

        return patterns or list(self.DEFAULT_PATTERNS)

    def _compile_patterns(self, patterns: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        compiled: List[Dict[str, Any]] = []
        for rule in patterns:
            try:
                compiled.append(
                    {
                        "id": rule["id"],
                        "tags": list(rule.get("tags", [])),
                        "pattern": re.compile(rule["regex"], flags=re.IGNORECASE),
                    }
                )
            except re.error:
                continue
        return compiled

    def _build_summary(self, hits: List[T0Hit]) -> str:
        if not hits:
            return "未命中高危 T0 规则。"
        names = sorted({item.rule_id for item in hits})
        return f"命中 {len(hits)} 条红旗片段，规则: {', '.join(names)}。"
