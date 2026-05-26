from __future__ import annotations

import json
import time
from dataclasses import dataclass

import requests

from parsed_models import SectorData


SECTOR_FIELDS = "f12,f14,f2,f3,f6,f62,f104,f105,f128,f136"
SECTOR_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0 Safari/537.36"
    ),
    "Referer": "https://quote.eastmoney.com/",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Connection": "keep-alive",
}


def _sector_url(host: str, sector_type: str) -> str:
    return (
        f"https://{host}/api/qt/clist/get"
        "?pn=1&pz=20&po=1&np=1&fltt=2&invt=2&fid=f3"
        f"&fs=m:90+t:{sector_type}&fields={SECTOR_FIELDS}"
    )


INDUSTRY_URL = _sector_url("push2.eastmoney.com", "2")
CONCEPT_URL = _sector_url("push2.eastmoney.com", "3")
BACKUP_INDUSTRY_URL = _sector_url("push2delay.eastmoney.com", "2")
BACKUP_CONCEPT_URL = _sector_url("push2delay.eastmoney.com", "3")


@dataclass
class SectorFetchStatus:
    source: str
    status: str
    failure_reason: str = ""
    data: str = "\u7f3a\u5931"


@dataclass
class SectorFetchResult:
    statuses: list[SectorFetchStatus]
    data: list[SectorData]
    quality: "SectorQualityResult"


@dataclass
class SectorQualityResult:
    usable: bool
    reason: str
    missing_fields: list[str]
    zero_field_ratio: float
    quality_label: str


def _headers_summary() -> str:
    required = ["User-Agent", "Referer", "Accept", "Accept-Language", "Connection"]
    return ", ".join(f"{key}={'yes' if SECTOR_HEADERS.get(key) else 'no'}" for key in required)


def _fetch_text(source: str, url: str, retries: int = 3, delay_seconds: int = 2) -> tuple[str | None, SectorFetchStatus]:
    last_error_type = ""
    last_status_code: int | None = None
    last_response_preview = ""
    for attempt in range(1, retries + 1):
        print(f"\n=== {source} attempt {attempt}/{retries} ===")
        print(f"URL: {url}")
        print("Headers effective:", _headers_summary())
        try:
            response = requests.get(url, headers=SECTOR_HEADERS, timeout=10)
            last_status_code = response.status_code
            last_response_preview = response.text[:300]
            print("Status:", response.status_code)
            print("Raw first 300 chars:")
            print(last_response_preview)
            response.raise_for_status()
            return response.text, SectorFetchStatus(source=source, status="\u6210\u529f", data="\u6210\u529f")
        except Exception as exc:
            last_error_type = type(exc).__name__
            print("FAILED")
            print("Status:", last_status_code if last_status_code is not None else "N/A")
            print("Response first 300 chars:")
            print(last_response_preview)
            print("error_type:", last_error_type)
            print("error:", repr(exc))
            if attempt < retries:
                print(f"Retrying after {delay_seconds} seconds...")
                time.sleep(delay_seconds)
    reason = last_error_type
    if last_status_code is not None:
        reason = f"{last_error_type}({last_status_code})"
    return None, SectorFetchStatus(source=source, status="\u5931\u8d25", failure_reason=reason)


def _parse_sector_rows(text: str, category: str, source: str) -> list[SectorData]:
    payload = json.loads(text)
    rows: list[SectorData] = []
    for item in payload.get("data", {}).get("diff", []):
        rows.append(
            SectorData(
                code=item.get("f12", ""),
                name=item.get("f14", ""),
                category=category,
                last=item.get("f2", ""),
                pct_change=item.get("f3", ""),
                amount=item.get("f6", ""),
                fund_flow=item.get("f62", ""),
                rising_count=item.get("f104", ""),
                falling_count=item.get("f105", ""),
                lead_stock=item.get("f128", ""),
                lead_stock_pct=item.get("f136", ""),
                source=source,
            )
        )
    return rows


def _parse_float(value: object) -> float | None:
    try:
        text = str(value).replace("%", "").strip()
        if text in {"", "-", "None"}:
            return None
        return float(text)
    except (TypeError, ValueError):
        return None


def _has_nonzero_number(rows: list[SectorData], field: str) -> bool:
    for row in rows:
        value = _parse_float(getattr(row, field))
        if value is not None and value != 0:
            return True
    return False


def _has_text_value(rows: list[SectorData], field: str) -> bool:
    for row in rows:
        value = str(getattr(row, field)).strip()
        if value and value != "-":
            return True
    return False


def validate_sector_data_quality(rows: list[SectorData]) -> SectorQualityResult:
    core_checks = {
        "\u6da8\u8dcc\u5e45": _has_nonzero_number(rows, "pct_change"),
        "\u6210\u4ea4\u989d": _has_nonzero_number(rows, "amount"),
        "\u4e0a\u6da8\u5bb6\u6570": _has_nonzero_number(rows, "rising_count"),
        "\u4e0b\u8dcc\u5bb6\u6570": _has_nonzero_number(rows, "falling_count"),
        "\u9886\u6da8\u6807\u7684": _has_text_value(rows, "lead_stock"),
    }
    missing_fields = [field for field, ok in core_checks.items() if not ok]
    total_fields = max(1, len(core_checks))
    zero_field_ratio = len(missing_fields) / total_fields

    if not rows:
        return SectorQualityResult(
            usable=False,
            reason="\u677f\u5757\u6570\u636e\u4e3a\u7a7a",
            missing_fields=list(core_checks),
            zero_field_ratio=1.0,
            quality_label="\u4e0d\u53ef\u7528",
        )
    if not missing_fields:
        return SectorQualityResult(
            usable=True,
            reason="\u6838\u5fc3\u5b57\u6bb5\u53ef\u7528",
            missing_fields=[],
            zero_field_ratio=0.0,
            quality_label="\u53ef\u7528",
        )
    if len(missing_fields) < total_fields:
        return SectorQualityResult(
            usable=False,
            reason="\u677f\u5757\u63a5\u53e3\u8fd4\u56de\u4e0d\u5b8c\u6574\uff0c\u65e0\u6cd5\u5f62\u6210\u6709\u6548\u677f\u5757\u5f3a\u5f31\u5224\u65ad",
            missing_fields=missing_fields,
            zero_field_ratio=zero_field_ratio,
            quality_label="\u90e8\u5206\u53ef\u7528",
        )
    return SectorQualityResult(
        usable=False,
        reason="\u677f\u5757\u63a5\u53e3\u4ec5\u8fd4\u56de\u540d\u79f0\u53c2\u8003\uff0c\u6838\u5fc3\u5b57\u6bb5\u4e0d\u53ef\u7528",
        missing_fields=missing_fields,
        zero_field_ratio=zero_field_ratio,
        quality_label="\u4e0d\u53ef\u7528",
    )


def _print_quality(rows: list[SectorData], quality: SectorQualityResult) -> None:
    usable_field_count = 5 - len(quality.missing_fields)
    print("Sector data rows:", len(rows))
    print("Usable core field count:", usable_field_count)
    print("Sector data quality:", quality.quality_label)
    print("Sector quality usable:", quality.usable)
    print("Sector quality reason:", quality.reason)
    print("Sector missing fields:", ", ".join(quality.missing_fields) if quality.missing_fields else "none")
    print("Sector zero field ratio:", f"{quality.zero_field_ratio:.2f}")


def _fetch_sector_category(
    category: str,
    primary_source: str,
    primary_url: str,
    backup_source: str,
    backup_url: str,
) -> tuple[list[SectorFetchStatus], list[SectorData]]:
    statuses: list[SectorFetchStatus] = []
    data: list[SectorData] = []

    primary_text, primary_status = _fetch_text(primary_source, primary_url)
    statuses.append(primary_status)
    if primary_text:
        try:
            data = _parse_sector_rows(primary_text, category, "eastmoney")
            primary_quality = validate_sector_data_quality(data)
            if primary_quality.usable:
                return statuses, data
            primary_status.status = "\u90e8\u5206\u6210\u529f / \u6570\u636e\u4e0d\u53ef\u7528"
            primary_status.failure_reason = primary_quality.reason
            primary_status.data = primary_quality.quality_label
            print(f"{category} primary data quality:", primary_quality.quality_label)
            print(f"{category} primary missing fields:", ", ".join(primary_quality.missing_fields) if primary_quality.missing_fields else "none")
        except Exception as exc:
            primary_status.status = "\u5931\u8d25"
            primary_status.failure_reason = type(exc).__name__
            primary_status.data = "\u7f3a\u5931"
            print("Parse FAILED")
            print("error_type:", type(exc).__name__)
            print("error:", repr(exc))

    backup_text, backup_status = _fetch_text(backup_source, backup_url)
    statuses.append(backup_status)
    if backup_text:
        try:
            data = _parse_sector_rows(backup_text, category, "eastmoney_backup")
            backup_quality = validate_sector_data_quality(data)
            if backup_quality.usable:
                return statuses, data
            backup_status.status = "\u90e8\u5206\u6210\u529f / \u6570\u636e\u4e0d\u53ef\u7528"
            backup_status.failure_reason = backup_quality.reason
            backup_status.data = backup_quality.quality_label
            print(f"{category} backup data quality:", backup_quality.quality_label)
            print(f"{category} backup missing fields:", ", ".join(backup_quality.missing_fields) if backup_quality.missing_fields else "none")
        except Exception as exc:
            backup_status.status = "\u5931\u8d25"
            backup_status.failure_reason = type(exc).__name__
            backup_status.data = "\u7f3a\u5931"
            print("Backup parse FAILED")
            print("error_type:", type(exc).__name__)
            print("error:", repr(exc))

    return statuses, data


def fetch_sector_data() -> SectorFetchResult:
    statuses: list[SectorFetchStatus] = []
    data: list[SectorData] = []

    industry_statuses, industry_data = _fetch_sector_category(
        "\u884c\u4e1a",
        "\u4e1c\u65b9\u8d22\u5bcc\u884c\u4e1a\u539f\u59cb\u63a5\u53e3",
        INDUSTRY_URL,
        "\u5907\u7528\u884c\u4e1a\u677f\u5757\u63a5\u53e3",
        BACKUP_INDUSTRY_URL,
    )
    statuses.extend(industry_statuses)
    data.extend(industry_data)

    concept_statuses, concept_data = _fetch_sector_category(
        "\u6982\u5ff5",
        "\u4e1c\u65b9\u8d22\u5bcc\u6982\u5ff5\u539f\u59cb\u63a5\u53e3",
        CONCEPT_URL,
        "\u5907\u7528\u6982\u5ff5\u677f\u5757\u63a5\u53e3",
        BACKUP_CONCEPT_URL,
    )
    statuses.extend(concept_statuses)
    data.extend(concept_data)

    if not data:
        print("\u4e91\u7aef\u73af\u5883\u4e0b\u677f\u5757\u63a5\u53e3\u6682\u65f6\u4e0d\u53ef\u7528")

    quality = validate_sector_data_quality(data)
    _print_quality(data, quality)
    if not quality.usable:
        statuses.append(
            SectorFetchStatus(
                source="\u677f\u5757\u6570\u636e\u8d28\u91cf",
                status="\u90e8\u5206\u6210\u529f / \u6570\u636e\u4e0d\u53ef\u7528",
                failure_reason=quality.reason,
                data=quality.quality_label,
            )
        )
    else:
        statuses.append(
            SectorFetchStatus(
                source="\u677f\u5757\u6570\u636e\u8d28\u91cf",
                status="\u6210\u529f",
                data=quality.quality_label,
            )
        )

    return SectorFetchResult(statuses=statuses, data=data, quality=quality)
