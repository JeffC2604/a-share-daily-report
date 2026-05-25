from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class DataKind(str, Enum):
    QUOTE = "quote"
    INTRADAY_ESTIMATE = "intraday_estimate"
    CLOSING_NAV = "closing_nav"
    HOLDINGS = "holdings"
    ANNOUNCEMENT = "announcement"
    OTHER = "other"


@dataclass(frozen=True)
class DataSourceStatus:
    name: str
    source: str
    kind: DataKind
    success: bool
    data_time: str | None = None
    payload: Any = None
    error: str | None = None
    is_empty: bool = False
    is_intraday_estimate: bool = False
    is_closing_nav: bool = False
    notes: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ValidationResult:
    sources: list[DataSourceStatus]
    missing_data: list[str]
    warnings: list[str]
    is_complete: bool
    confidence: str

    @property
    def incomplete_notice(self) -> str:
        if self.is_complete:
            return ""
        return "数据不完整，以下判断仅供观察，不适合做确定性交易依据。"


def _is_empty_payload(payload: Any) -> bool:
    if payload is None:
        return True
    if isinstance(payload, str):
        return payload.strip() == ""
    if isinstance(payload, (dict, list, tuple, set)):
        return len(payload) == 0
    return False


def _has_valid_time(data_time: str | None) -> bool:
    if not data_time:
        return False
    try:
        datetime.fromisoformat(data_time.replace(" ", "T"))
        return True
    except ValueError:
        return True


def validate_data_sources(sources: list[DataSourceStatus]) -> ValidationResult:
    missing_data: list[str] = []
    warnings: list[str] = []

    normalized: list[DataSourceStatus] = []
    for source in sources:
        is_empty = source.is_empty or _is_empty_payload(source.payload)
        notes = list(source.notes)

        if not source.success:
            missing_data.append(f"{source.name}: 数据源返回失败")
        if is_empty:
            missing_data.append(f"{source.name}: 返回数据为空")
        if not _has_valid_time(source.data_time):
            missing_data.append(f"{source.name}: 缺少有效数据时间")

        if source.kind == DataKind.INTRADAY_ESTIMATE and not source.is_intraday_estimate:
            notes.append("该数据应标记为盘中估值")
        if source.kind == DataKind.CLOSING_NAV and not source.is_closing_nav:
            notes.append("该数据应标记为收盘净值")
        if source.is_intraday_estimate:
            warnings.append(f"{source.name}: 使用盘中估值，不能等同于最终净值")
        if source.kind == DataKind.HOLDINGS:
            warnings.append(f"{source.name}: 持仓信息存在披露滞后风险")

        normalized.append(
            DataSourceStatus(
                name=source.name,
                source=source.source,
                kind=source.kind,
                success=source.success,
                data_time=source.data_time,
                payload=source.payload,
                error=source.error,
                is_empty=is_empty,
                is_intraday_estimate=source.is_intraday_estimate,
                is_closing_nav=source.is_closing_nav,
                notes=notes,
            )
        )

    is_complete = not missing_data
    if not is_complete:
        confidence = "低"
    elif warnings:
        confidence = "中"
    else:
        confidence = "高"

    return ValidationResult(
        sources=normalized,
        missing_data=missing_data,
        warnings=warnings,
        is_complete=is_complete,
        confidence=confidence,
    )


def render_validation_preface(result: ValidationResult) -> str:
    lines = ["## 数据口径", ""]
    if result.incomplete_notice:
        lines.extend([result.incomplete_notice, ""])

    lines.append(f"- 数据完整度：{'完整' if result.is_complete else '不完整'}")
    lines.append(f"- 总体置信度：{result.confidence}")

    if result.missing_data:
        lines.append("- 缺失/异常数据：")
        lines.extend(f"  - {item}" for item in result.missing_data)

    if result.warnings:
        lines.append("- 数据风险：")
        lines.extend(f"  - {item}" for item in result.warnings)

    lines.append("- 数据源状态：")
    for source in result.sources:
        status = "成功" if source.success and not source.is_empty else "异常"
        time = source.data_time or "未提供"
        valuation_type = ""
        if source.is_intraday_estimate:
            valuation_type = "，盘中估值"
        if source.is_closing_nav:
            valuation_type = "，收盘净值"
        lines.append(f"  - {source.name}：{status}，时间：{time}{valuation_type}，来源：{source.source}")

    return "\n".join(lines)
