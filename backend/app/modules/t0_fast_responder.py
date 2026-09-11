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


def adapt_t0_for_frontend(result: Dict[str, Any] | None) -> Dict[str, Any]:
    """Align T0 payload with both backend (`alert`/`hits`) and UI (`matched`/`patterns`)."""
    payload = dict(result or {})
    hits = payload.get("hits") or []
    patterns: List[str] = []
    keywords: List[str] = []
    for item in hits:
        if not isinstance(item, dict):
            continue
        rule_id = item.get("rule_id")
        if rule_id:
            patterns.append(str(rule_id))
        for tag in item.get("tags") or []:
            keywords.append(str(tag))
        matched_text = item.get("matched_text")
        if matched_text:
            keywords.append(str(matched_text))
    payload["matched"] = bool(payload.get("alert") or hits)
    payload["matched_patterns"] = list(dict.fromkeys(patterns))
    payload["matched_keywords"] = list(dict.fromkeys(keywords))
    return payload


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
            "regex": r"(安全账户|监管账户|safe\s*account).{0,24}(转账|转入|汇款|打款|transfer)|(转账|转入|汇款|打款|transfer).{0,16}(安全账户|监管账户)",
        },
        {
            "id": "police_secrecy_isolation",
            "tags": ["police", "secrecy", "isolation"],
            "regex": r"(公安|警方|police).{0,28}(保密|不要告诉|单独联系|隔离|不要联系家人|secrecy|isolation)",
        },
        {
            "id": "credit_fraud_app",
            "tags": ["credit_fraud", "app_download"],
            "regex": r"(征信|信用(评分|记录|异常)|贷款(异常|风险)).{0,40}(下载|安装|APP|app|点击链接)",
        },
        {
            "id": "impersonation_with_app",
            "tags": ["impersonation", "app_download"],
            "regex": r"(冒充|我是).{0,20}(银行|客服|监管|公安|法院).{0,40}(下载|安装|APP|app|开启|共享)",
        },
        {
            "id": "verification_code_request",
            "tags": ["verification_code"],
            "regex": r"(把|将)?.{0,6}(验证码|动态码|短信码).{0,12}(发我|发给我|告诉我|提供)|提供.{0,6}(验证码|动态码)",
        },
        {
            "id": "secrecy_isolation",
            "tags": ["secrecy", "isolation"],
            "regex": r"不要告诉(任何人|别人|家人|朋友)|别告诉(别人|家人)|不要和任何人说",
        },
        {
            "id": "unknown_app_download",
            "tags": ["app_download"],
            "regex": r"(下载|安装).{0,16}(APP|app|软件|应用)",
        },
        {
            "id": "classic_impersonation_opening",
            "tags": ["impersonation", "scam_hook"],
            "regex": r"我是(秦始皇|汉武帝|玉皇大帝|纪委|公检法|公安|警察|检察院|法院|客服|领导)",
        },
        {
            "id": "credit_card_repay_lure",
            "tags": ["loan_fraud", "credit_card"],
            "regex": r"(信用卡).{0,12}(代还|套现|养卡|提额)|(代还|套现).{0,12}(信用卡)|虚假贷款|代办信用卡",
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
        return adapt_t0_for_frontend({
            "alert": bool(hits),
            "latency_ms": elapsed_ms,
            "target_met": elapsed_ms < 500.0,
            "hits": [item.to_dict() for item in hits],
            "summary": self._build_summary(hits),
        })

    def _load_patterns(self) -> List[Dict[str, Any]]:
        merged = {item["id"]: dict(item) for item in self.DEFAULT_PATTERNS}
        file_patterns: List[Dict[str, Any]] = []
        if self.patterns_path and os.path.exists(self.patterns_path):
            try:
                with open(self.patterns_path, "r", encoding="utf-8") as handle:
                    payload = json.load(handle)
            except Exception:
                payload = []
            if isinstance(payload, dict):
                payload = payload.get("patterns", [])
            for item in payload if isinstance(payload, list) else []:
                if not isinstance(item, dict):
                    continue
                if not item.get("id") or not item.get("regex"):
                    continue
                tags = item.get("tags", [])
                if not isinstance(tags, list):
                    tags = []
                file_patterns.append(
                    {
                        "id": str(item["id"]),
                        "regex": str(item["regex"]),
                        "tags": [str(tag) for tag in tags],
                    }
                )
        for item in file_patterns:
            merged[item["id"]] = item
        return list(merged.values())

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
