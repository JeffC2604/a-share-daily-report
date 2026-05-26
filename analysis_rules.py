from __future__ import annotations

from parsed_models import CandidateStock, DataSourceStatus, FundEstimateData, IndexData, SectorData
from risk_rules import assert_safe_output


CN_HIGH = "\u9ad8"
CN_MEDIUM = "\u4e2d"
CN_LOW = "\u4f4e"
CN_FAILED = "\u5931\u8d25"
CN_MISSING = "\u7f3a\u5931"
CN_UNAVAILABLE = "\u4e0d\u53ef\u7528"
SRC_FALLBACK = "\u672c\u5730fallback_data.json"


def _confidence(has_index_data: bool, has_fund_data: bool, failed_sources: int) -> str:
    if not has_index_data or not has_fund_data:
        return CN_LOW
    if failed_sources:
        return CN_MEDIUM
    return CN_HIGH


def _parse_float(value: object) -> float | None:
    try:
        return float(str(value).replace("%", "").strip())
    except (TypeError, ValueError):
        return None


def _index_observation(index_data: list[IndexData]) -> str:
    pct_values = [_parse_float(item.pct_change) for item in index_data]
    valid_values = [value for value in pct_values if value is not None]

    if not valid_values:
        return "\u6307\u6570\u6570\u636e\u4e0d\u8db3\uff0c\u65e0\u6cd5\u5224\u65ad\u6574\u4f53\u5f3a\u5f31\u3002"

    positive = sum(1 for value in valid_values if value > 0)
    negative = sum(1 for value in valid_values if value < 0)
    max_value = max(valid_values)
    min_value = min(valid_values)

    if positive >= max(1, len(valid_values) - 1):
        return "\u6307\u6570\u6574\u4f53\u504f\u5f3a\uff0c\u4f46\u4ecd\u9700\u7ed3\u5408\u6570\u636e\u6e90\u7a33\u5b9a\u6027\u89c2\u5bdf\u3002"
    if negative >= max(1, len(valid_values) - 1):
        return "\u6307\u6570\u6574\u4f53\u504f\u5f31\uff0c\u9700\u8981\u6ce8\u610f\u6570\u636e\u5b8c\u6574\u6027\u548c\u540e\u7eed\u786e\u8ba4\u3002"
    if max_value > 0 and min_value < 0:
        return "\u6307\u6570\u8868\u73b0\u5206\u5316\uff0c\u4e0d\u5b9c\u7528\u5355\u4e00\u6307\u6570\u4ee3\u8868\u6574\u4f53\u5e02\u573a\u3002"
    return "\u6307\u6570\u6574\u4f53\u8868\u73b0\u4e2d\u6027\uff0c\u6682\u672a\u5f62\u6210\u660e\u786e\u5f3a\u5f31\u5224\u65ad\u3002"


def _fund_observation(fund_data: list[FundEstimateData]) -> list[str]:
    if not fund_data:
        return ["\u57fa\u91d1\u4f30\u503c\u6570\u636e\u7f3a\u5931\uff0c\u65e0\u6cd5\u5224\u65ad\u4f30\u503c\u65b9\u5411\u3002"]

    observations: list[str] = []
    for item in fund_data:
        pct = _parse_float(item.estimate_pct)
        if pct is None:
            direction = "\u4f30\u7b97\u6da8\u5e45\u7f3a\u5931\uff0c\u65e0\u6cd5\u5224\u65ad\u65b9\u5411\u3002"
        elif pct >= 3:
            direction = "\u4f30\u503c\u4e0a\u6da8\u4e14\u6ce2\u52a8\u8f83\u5927\u3002"
        elif pct > 0:
            direction = "\u4f30\u503c\u4e0a\u6da8\u3002"
        elif pct <= -3:
            direction = "\u4f30\u503c\u4e0b\u8dcc\u4e14\u6ce2\u52a8\u8f83\u5927\u3002"
        elif pct < 0:
            direction = "\u4f30\u503c\u4e0b\u8dcc\u3002"
        else:
            direction = "\u4f30\u503c\u6ce2\u52a8\u8f83\u5c0f\u3002"
        observations.append(f"{item.fund_code} {item.name}\uff1a{direction}")
    return observations


def _data_completeness(statuses: list[DataSourceStatus]) -> tuple[str, int]:
    failed = [
        item
        for item in statuses
        if (item.status == CN_FAILED or item.data in {CN_MISSING, CN_UNAVAILABLE} or CN_UNAVAILABLE in item.status) and item.source != SRC_FALLBACK
    ]
    if not failed:
        return "\u6570\u636e\u6e90\u5b8c\u6574\u3002", 0
    names = "\u3001".join(item.source for item in failed)
    return f"\u5b58\u5728\u6570\u636e\u7f3a\u5931\u6216\u6570\u636e\u6e90\u5931\u8d25\uff1a{names}\u3002", len(failed)


def render_initial_observation(
    index_data: list[IndexData],
    fund_data: list[FundEstimateData],
    statuses: list[DataSourceStatus],
) -> str:
    completeness, failed_sources = _data_completeness(statuses)
    confidence = _confidence(bool(index_data), bool(fund_data), failed_sources)
    fund_lines = "\n".join(f"- {line}" for line in _fund_observation(fund_data))

    markdown = f"""## \u521d\u6b65\u5e02\u573a\u89c2\u5bdf

\u7f6e\u4fe1\u5ea6\uff1a{confidence}

- \u6570\u636e\u5b8c\u6574\u6027\uff1a{completeness}
- \u6307\u6570\u89c2\u5bdf\uff1a{_index_observation(index_data)}
- \u57fa\u91d1\u4f30\u503c\u89c2\u5bdf\uff1a
{fund_lines}
- \u7f6e\u4fe1\u5ea6\u8bf4\u660e\uff1a\u82e5\u4e3b\u8981\u6570\u636e\u6e90\u5931\u8d25\u3001\u4f7f\u7528\u5907\u7528\u63a5\u53e3\u6216\u6570\u636e\u7f3a\u5931\uff0c\u7ed3\u8bba\u7f6e\u4fe1\u5ea6\u81ea\u52a8\u4e0b\u8c03\u3002
"""
    assert_safe_output(markdown)
    return markdown


def _top_sector_lines(sector_data: list[SectorData], limit: int = 5) -> list[str]:
    def pct_value(item: SectorData) -> float:
        return _parse_float(item.pct_change) or 0.0

    lines: list[str] = []
    for item in sorted(sector_data, key=pct_value, reverse=True)[:limit]:
        lines.append(
            f"{item.category} {item.name}\uff1a\u6da8\u8dcc\u5e45 {item.pct_change}\uff0c"
            f"\u6210\u4ea4\u989d {item.amount}\uff0c\u8d44\u91d1\u70ed\u5ea6 {item.fund_flow}\uff0c"
            f"\u9886\u6da8\u6807\u7684 {item.lead_stock}\u3002"
        )
    return lines


def render_sector_heat_observation(sector_data: list[SectorData], statuses: list[DataSourceStatus]) -> str:
    failed = [item for item in statuses if item.status == CN_FAILED or item.data in {CN_MISSING, CN_UNAVAILABLE} or CN_UNAVAILABLE in item.status]
    confidence = _confidence(bool(sector_data), True, len(failed))

    if not sector_data:
        body = "- \u677f\u5757\u63a5\u53e3\u8fd4\u56de\u4e0d\u5b8c\u6574\uff0c\u65e0\u6cd5\u5f62\u6210\u6709\u6548\u677f\u5757\u5f3a\u5f31\u5224\u65ad\u3002"
    else:
        lines = _top_sector_lines(sector_data)
        body = "\n".join(f"- {line}" for line in lines)

    if failed:
        failed_names = "\u3001".join(item.source for item in failed)
        source_note = f"- \u6570\u636e\u6e90\u63d0\u793a\uff1a{failed_names}\u5b58\u5728\u5931\u8d25\u6216\u7f3a\u5931\uff0c\u7f6e\u4fe1\u5ea6\u4e0b\u8c03\u3002"
    else:
        source_note = "- \u6570\u636e\u6e90\u63d0\u793a\uff1a\u677f\u5757\u6570\u636e\u6e90\u8fd4\u56de\u6210\u529f\u3002"

    markdown = f"""## \u677f\u5757\u70ed\u5ea6\u89c2\u5bdf

\u7f6e\u4fe1\u5ea6\uff1a{confidence}

{body}
{source_note}
"""
    assert_safe_output(markdown)
    return markdown


def render_candidate_pool_observation(candidates: list[CandidateStock], confidence: str, notes: list[str]) -> str:
    if candidates:
        body = "- \u5019\u9009\u89c2\u5bdf\u3002\n- \u9700\u8981\u89c2\u5bdf\u6301\u7eed\u6027\u3002\n- \u4e0d\u9002\u5408\u8ffd\u9ad8\u3002"
    else:
        body = "- \u6570\u636e\u4e0d\u5b8c\u6574\uff0c\u7f6e\u4fe1\u5ea6\u964d\u4f4e\u3002"

    note_lines = "\n".join(f"- {note}" for note in notes)
    if not note_lines:
        note_lines = "- \u5019\u9009\u89c2\u5bdf\u3002"

    markdown = f"""## \u81ea\u52a8\u5019\u9009\u89c2\u5bdf\u6c60

\u7f6e\u4fe1\u5ea6\uff1a{confidence}

{body}
{note_lines}
"""
    assert_safe_output(markdown)
    return markdown
