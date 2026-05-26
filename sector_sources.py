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
            if data:
                return statuses, data
            primary_status.status = "\u5931\u8d25"
            primary_status.failure_reason = "EmptyData"
            primary_status.data = "\u7f3a\u5931"
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
            if data:
                return statuses, data
            backup_status.status = "\u5931\u8d25"
            backup_status.failure_reason = "EmptyData"
            backup_status.data = "\u7f3a\u5931"
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
        "\u4e1c\u65b9\u8d22\u5bcc\u884c\u4e1a\u677f\u5757",
        INDUSTRY_URL,
        "\u5907\u7528\u884c\u4e1a\u677f\u5757\u63a5\u53e3",
        BACKUP_INDUSTRY_URL,
    )
    statuses.extend(industry_statuses)
    data.extend(industry_data)

    concept_statuses, concept_data = _fetch_sector_category(
        "\u6982\u5ff5",
        "\u4e1c\u65b9\u8d22\u5bcc\u6982\u5ff5\u677f\u5757",
        CONCEPT_URL,
        "\u5907\u7528\u6982\u5ff5\u677f\u5757\u63a5\u53e3",
        BACKUP_CONCEPT_URL,
    )
    statuses.extend(concept_statuses)
    data.extend(concept_data)

    if not data:
        print("\u4e91\u7aef\u73af\u5883\u4e0b\u677f\u5757\u63a5\u53e3\u6682\u65f6\u4e0d\u53ef\u7528")

    return SectorFetchResult(statuses=statuses, data=data)
