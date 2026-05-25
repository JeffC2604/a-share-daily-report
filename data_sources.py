from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from pathlib import Path

import requests

from parsed_models import FundEstimateData, IndexData


EASTMONEY_INDEX_URL = (
    "https://push2.eastmoney.com/api/qt/ulist.np/get"
    "?fltt=2&invt=2"
    "&fields=f12,f14,f2,f3,f4,f5,f6,f17,f18"
    "&secids=1.000001,0.399001,0.399006,1.000300,1.000905,1.000852,1.000688"
)

BACKUP_INDEX_URL = "https://qt.gtimg.cn/q=sh000001,sz399001,sz399006,sh000300,sh000905,sh000852,sh000688"
FALLBACK_DATA_PATH = Path(__file__).with_name("fallback_data.json")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0 Safari/537.36"
    ),
    "Referer": "https://quote.eastmoney.com/",
}


@dataclass
class FetchResult:
    source: str
    url: str
    ok: bool
    text: str | None = None
    status_code: int | None = None
    error_type: str = ""
    error: str = ""


@dataclass
class IndexFetchResult:
    eastmoney: FetchResult
    backup: FetchResult | None
    local_fallback_used: bool
    data: list[IndexData]


@dataclass
class FundFetchResult:
    fetch: FetchResult
    data: FundEstimateData | None


def _fetch_with_retries(source: str, url: str, retries: int = 3, delay_seconds: int = 2) -> FetchResult:
    last_status: int | None = None
    last_error_type = ""
    last_error = ""

    for attempt in range(1, retries + 1):
        print(f"\n=== {source} attempt {attempt}/{retries} ===")
        print(f"URL: {url}")
        try:
            response = requests.get(url, headers=HEADERS, timeout=10)
            last_status = response.status_code
            response.raise_for_status()
            print("Status:", response.status_code)
            print("Raw first 500 chars:")
            print(response.text[:500])
            return FetchResult(source=source, url=url, ok=True, text=response.text, status_code=response.status_code)
        except Exception as exc:
            last_error_type = type(exc).__name__
            last_error = repr(exc)
            print("FAILED")
            print("error_type:", last_error_type)
            print("error:", last_error)
            if attempt < retries and delay_seconds > 0:
                print(f"Retrying after {delay_seconds} seconds...")
                time.sleep(delay_seconds)

    return FetchResult(
        source=source,
        url=url,
        ok=False,
        status_code=last_status,
        error_type=last_error_type,
        error=last_error,
    )


def _parse_jsonp(text: str) -> dict:
    match = re.search(r"^[^(]*\((.*)\);?\s*$", text, re.S)
    if not match:
        raise ValueError("JSONP format not recognized")
    return json.loads(match.group(1))


def _parse_eastmoney_index(text: str) -> list[IndexData]:
    data = json.loads(text)
    rows: list[IndexData] = []
    for item in data.get("data", {}).get("diff", []):
        rows.append(
            IndexData(
                code=item.get("f12", ""),
                name=item.get("f14", ""),
                last=item.get("f2", ""),
                pct_change=item.get("f3", ""),
                change=item.get("f4", ""),
                amount=item.get("f6", ""),
                source="eastmoney",
            )
        )
    return rows


def _parse_backup_index(text: str) -> list[IndexData]:
    rows: list[IndexData] = []
    for line in text.splitlines():
        if not line.strip():
            continue
        payload = line.split("=", 1)[-1].strip().strip('";')
        parts = payload.split("~")
        if len(parts) < 38:
            continue
        rows.append(
            IndexData(
                code=parts[2],
                name=parts[1],
                last=parts[3],
                pct_change=parts[32],
                change=parts[31],
                amount=parts[37],
                source="backup",
            )
        )
    return rows


def fetch_eastmoney_index() -> FetchResult:
    return _fetch_with_retries("东方财富指数接口", EASTMONEY_INDEX_URL, retries=3, delay_seconds=2)


def fetch_backup_index() -> FetchResult:
    return _fetch_with_retries("备用指数接口", BACKUP_INDEX_URL, retries=3, delay_seconds=2)


def load_fallback_data() -> list[IndexData]:
    if not FALLBACK_DATA_PATH.exists():
        return []
    data = json.loads(FALLBACK_DATA_PATH.read_text(encoding="utf-8"))
    rows: list[IndexData] = []
    for item in data.get("index_data", []):
        if not item.get("last"):
            continue
        rows.append(
            IndexData(
                code=item.get("code", ""),
                name=item.get("name", ""),
                last=item.get("last", ""),
                pct_change=item.get("pct_change", ""),
                change=item.get("change", ""),
                amount=item.get("amount", ""),
                source="local_fallback",
            )
        )
    return rows


def fetch_index_data() -> IndexFetchResult:
    eastmoney = fetch_eastmoney_index()
    backup: FetchResult | None = None
    data: list[IndexData] = []
    local_fallback_used = False

    if eastmoney.ok and eastmoney.text:
        try:
            data = _parse_eastmoney_index(eastmoney.text)
        except Exception as exc:
            eastmoney.ok = False
            eastmoney.error_type = type(exc).__name__
            eastmoney.error = repr(exc)

    if not data:
        print("\n东方财富指数接口暂时失败，指数数据缺失")
        backup = fetch_backup_index()
        if backup.ok and backup.text:
            try:
                data = _parse_backup_index(backup.text)
            except Exception as exc:
                backup.ok = False
                backup.error_type = type(exc).__name__
                backup.error = repr(exc)

    if not data:
        data = load_fallback_data()
        if data:
            local_fallback_used = True
            print("\nUsing local fallback_data.json index data")

    return IndexFetchResult(
        eastmoney=eastmoney,
        backup=backup,
        local_fallback_used=local_fallback_used,
        data=data,
    )


def fetch_tiantian_fund_estimate(fund_code: str) -> FundFetchResult:
    url = f"https://fundgz.1234567.com.cn/js/{fund_code}.js"
    fetch = _fetch_with_retries("天天基金数据", url, retries=3, delay_seconds=2)
    data: FundEstimateData | None = None

    if fetch.ok and fetch.text:
        try:
            parsed = _parse_jsonp(fetch.text)
            data = FundEstimateData(
                fund_code=parsed.get("fundcode", ""),
                name=parsed.get("name", ""),
                nav_date=parsed.get("jzrq", ""),
                nav=parsed.get("dwjz", ""),
                estimate_nav=parsed.get("gsz", ""),
                estimate_pct=parsed.get("gszzl", ""),
                estimate_time=parsed.get("gztime", ""),
            )
        except Exception as exc:
            fetch.ok = False
            fetch.error_type = type(exc).__name__
            fetch.error = repr(exc)

    return FundFetchResult(fetch=fetch, data=data)
