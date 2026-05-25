from __future__ import annotations

import json
import time
from dataclasses import dataclass

import requests

from data_sources import HEADERS
from parsed_models import SectorData


SECTOR_FIELDS = "f12,f14,f2,f3,f6,f62,f104,f105,f128,f136"
INDUSTRY_URL = (
    "https://push2.eastmoney.com/api/qt/clist/get"
    "?pn=1&pz=20&po=1&np=1&fltt=2&invt=2&fid=f3"
    f"&fs=m:90+t:2&fields={SECTOR_FIELDS}"
)
CONCEPT_URL = (
    "https://push2.eastmoney.com/api/qt/clist/get"
    "?pn=1&pz=20&po=1&np=1&fltt=2&invt=2&fid=f3"
    f"&fs=m:90+t:3&fields={SECTOR_FIELDS}"
)


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


def _fetch_text(source: str, url: str, retries: int = 3, delay_seconds: int = 2) -> tuple[str | None, SectorFetchStatus]:
    last_error_type = ""
    for attempt in range(1, retries + 1):
        print(f"\n=== {source} attempt {attempt}/{retries} ===")
        print(f"URL: {url}")
        try:
            response = requests.get(url, headers=HEADERS, timeout=10)
            response.raise_for_status()
            print("Status:", response.status_code)
            print("Raw first 500 chars:")
            print(response.text[:500])
            return response.text, SectorFetchStatus(source=source, status="\u6210\u529f", data="\u6210\u529f")
        except Exception as exc:
            last_error_type = type(exc).__name__
            print("FAILED")
            print("error_type:", last_error_type)
            print("error:", repr(exc))
            if attempt < retries:
                print(f"Retrying after {delay_seconds} seconds...")
                time.sleep(delay_seconds)
    return None, SectorFetchStatus(source=source, status="\u5931\u8d25", failure_reason=last_error_type)


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


def fetch_sector_data() -> SectorFetchResult:
    statuses: list[SectorFetchStatus] = []
    data: list[SectorData] = []

    industry_text, industry_status = _fetch_text("\u4e1c\u65b9\u8d22\u5bcc\u884c\u4e1a\u677f\u5757", INDUSTRY_URL)
    statuses.append(industry_status)
    if industry_text:
        try:
            data.extend(_parse_sector_rows(industry_text, "\u884c\u4e1a", "eastmoney"))
        except Exception as exc:
            industry_status.status = "\u5931\u8d25"
            industry_status.failure_reason = type(exc).__name__
            industry_status.data = "\u7f3a\u5931"

    concept_text, concept_status = _fetch_text("\u4e1c\u65b9\u8d22\u5bcc\u6982\u5ff5\u677f\u5757", CONCEPT_URL)
    statuses.append(concept_status)
    if concept_text:
        try:
            data.extend(_parse_sector_rows(concept_text, "\u6982\u5ff5", "eastmoney"))
        except Exception as exc:
            concept_status.status = "\u5931\u8d25"
            concept_status.failure_reason = type(exc).__name__
            concept_status.data = "\u7f3a\u5931"

    return SectorFetchResult(statuses=statuses, data=data)
