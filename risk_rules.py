from __future__ import annotations

import re
from dataclasses import dataclass


FORBIDDEN_PHRASES = (
    "\u4e70\u5165",
    "\u5356\u51fa",
    "\u5fc5\u6da8",
    "\u5fc5\u8dcc",
    "\u7a33\u8d5a",
    "\u6ee1\u4ed3",
    "\u68ad\u54c8",
    "\u63a8\u8350\u4e2a\u80a1",
    "\u786e\u5b9a\u6027\u673a\u4f1a",
)


@dataclass(frozen=True)
class RiskViolation:
    phrase: str
    sentence: str


@dataclass(frozen=True)
class RiskScanResult:
    passed: bool
    violations: list[RiskViolation]


def _sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[\u3002\uff01\uff1f.!?])|\n+", text)
    return [part.strip() for part in parts if part.strip()]


def scan_forbidden_output(text: str) -> RiskScanResult:
    violations: list[RiskViolation] = []
    for sentence in _sentences(text):
        for phrase in FORBIDDEN_PHRASES:
            if phrase in sentence:
                violations.append(RiskViolation(phrase=phrase, sentence=sentence))
    return RiskScanResult(passed=not violations, violations=violations)


def assert_safe_output(text: str) -> None:
    result = scan_forbidden_output(text)
    if result.passed:
        return
    details = "\n".join(f"- {item.phrase}: {item.sentence}" for item in result.violations)
    raise ValueError(f"Forbidden output detected:\n{details}")


def print_risk_violations(result: RiskScanResult) -> None:
    print("Forbidden output detected. Report was not generated.")
    for item in result.violations:
        print("phrase:", item.phrase)
        print("sentence:", item.sentence)


def confidence_label(value: str | None) -> str:
    if value in {"\u9ad8", "\u4e2d", "\u4f4e"}:
        return value
    return "\u4f4e"
