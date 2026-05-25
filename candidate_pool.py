from __future__ import annotations

import json
import time
from dataclasses import dataclass

import requests

from data_sources import HEADERS
from parsed_models import CandidateStock, SectorData


STOCK_FIELDS = "f12,f14,f2,f3,f6,f8,f15,f16,f17"


@dataclass
class CandidatePoolResult:
    candidates: list[CandidateStock]
    confidence: str
    notes: list[str]


def _parse_float(value: object) -> float | None:
    try:
        return float(str(value).replace("%", "").strip())
    except (TypeError, ValueError):
        return None


def _fetch_sector_stocks(sector: SectorData, retries: int = 3, delay_seconds: int = 2) -> list[dict]:
    url = (
        "https://push2.eastmoney.com/api/qt/clist/get"
        "?pn=1&pz=30&po=1&np=1&fltt=2&invt=2&fid=f3"
        f"&fs=b:{sector.code}&fields={STOCK_FIELDS}"
    )
    for attempt in range(1, retries + 1):
        print(f"\n=== candidate pool {sector.name} attempt {attempt}/{retries} ===")
        print(f"URL: {url}")
        try:
            response = requests.get(url, headers=HEADERS, timeout=10)
            response.raise_for_status()
            print("Status:", response.status_code)
            print("Raw first 500 chars:")
            print(response.text[:500])
            payload = json.loads(response.text)
            return list(payload.get("data", {}).get("diff", []))
        except Exception as exc:
            print("FAILED")
            print("error_type:", type(exc).__name__)
            print("error:", repr(exc))
            if attempt < retries:
                print(f"Retrying after {delay_seconds} seconds...")
                time.sleep(delay_seconds)
    return []


def _strong_sectors(sector_data: list[SectorData], limit: int = 5) -> list[SectorData]:
    def score(item: SectorData) -> float:
        pct = _parse_float(item.pct_change) or 0.0
        amount = (_parse_float(item.amount) or 0.0) / 1_000_000_000
        fund_flow = (_parse_float(item.fund_flow) or 0.0) / 1_000_000_000
        rising = _parse_float(item.rising_count) or 0.0
        falling = _parse_float(item.falling_count) or 0.0
        lead_pct = _parse_float(item.lead_stock_pct) or 0.0
        breadth = 1.0 if rising > falling else -1.0
        return pct * 3 + min(amount, 20) + fund_flow + breadth * 2 + min(lead_pct, 20) * 0.5

    filtered = [
        item
        for item in sector_data
        if (_parse_float(item.pct_change) or 0) > 0
        and (_parse_float(item.rising_count) or 0) > (_parse_float(item.falling_count) or 0)
        and (_parse_float(item.lead_stock_pct) or 0) >= 5
    ]
    return sorted(filtered, key=score, reverse=True)[:limit]


def _candidate_from_stock(stock: dict, sector: SectorData) -> CandidateStock | None:
    code = str(stock.get("f12", ""))
    pct = _parse_float(stock.get("f3"))
    amount = _parse_float(stock.get("f6"))
    turnover = _parse_float(stock.get("f8"))
    latest = stock.get("f2", "")

    if pct is None or amount is None or turnover is None:
        return None
    latest_value = _parse_float(latest)
    if latest_value is None or latest_value <= 0:
        return None
    if pct <= 0 or amount <= 0:
        return None
    if turnover < 0.5 or turnover > 35:
        return None
    if pct >= 19.8 and turnover < 1:
        return None
    if turnover <= 0:
        return None

    confidence = "\u9ad8"
    if amount < 500_000_000 or turnover < 1 or turnover > 25:
        confidence = "\u4e2d"

    reason_parts = ["\u5019\u9009\u89c2\u5bdf"]
    if pct >= (_parse_float(sector.pct_change) or 0):
        reason_parts.append("\u5f3a\u4e8e\u677f\u5757")
    else:
        reason_parts.append("\u8ddf\u968f\u677f\u5757")
    if turnover >= 8:
        reason_parts.append("\u6ce2\u52a8\u8f83\u5927")
    reason_parts.append("\u9700\u8981\u89c2\u5bdf\u6301\u7eed\u6027")

    risk_parts = ["\u9700\u8981\u89c2\u5bdf\u6301\u7eed\u6027"]
    if pct >= 8:
        risk_parts.append("\u4e0d\u9002\u5408\u8ffd\u9ad8")
    if confidence != "\u9ad8":
        risk_parts.append("\u6570\u636e\u4e0d\u5b8c\u6574\uff0c\u7f6e\u4fe1\u5ea6\u964d\u4f4e")
    market_type = _market_type(code)
    if code.startswith("688"):
        risk_parts.append("\u79d1\u521b\u677f\u80a1\u7968\uff0c\u9700\u6ce8\u610f\u4ea4\u6613\u6743\u9650\u548c\u6ce2\u52a8\u98ce\u9669")
    if code.startswith("300"):
        risk_parts.append("\u521b\u4e1a\u677f\u80a1\u7968\uff0c\u9700\u6ce8\u610f\u4ea4\u6613\u6743\u9650\u548c\u6ce2\u52a8\u98ce\u9669")

    return CandidateStock(
        code=code,
        name=stock.get("f14", ""),
        market_type=market_type,
        sector=sector.name,
        latest_price=latest,
        pct_change=stock.get("f3", ""),
        amount=stock.get("f6", ""),
        turnover_rate=stock.get("f8", ""),
        reason="\uff1b".join(reason_parts),
        risk_note="\uff1b".join(risk_parts),
        confidence=confidence,
    )


def _market_type(code: str) -> str:
    if code.startswith("688"):
        return "\u79d1\u521b\u677f"
    if code.startswith("300") or code.startswith("30"):
        return "\u521b\u4e1a\u677f"
    if code.startswith("60"):
        return "\u6caa\u5e02\u4e3b\u677f"
    if code.startswith("00"):
        return "\u6df1\u5e02\u4e3b\u677f"
    return "\u672a\u77e5"


def build_candidate_pool(sector_data: list[SectorData], limit: int = 12) -> CandidatePoolResult:
    if not sector_data:
        return CandidatePoolResult(
            candidates=[],
            confidence="\u4f4e",
            notes=["\u6570\u636e\u4e0d\u5b8c\u6574\uff0c\u7f6e\u4fe1\u5ea6\u964d\u4f4e"],
        )

    candidates: list[CandidateStock] = []
    notes: list[str] = []
    for sector in _strong_sectors(sector_data):
        rows = _fetch_sector_stocks(sector)
        if not rows:
            notes.append(f"{sector.name}\uff1a\u6570\u636e\u4e0d\u5b8c\u6574\uff0c\u7f6e\u4fe1\u5ea6\u964d\u4f4e")
            continue
        for stock in rows:
            candidate = _candidate_from_stock(stock, sector)
            if candidate:
                candidates.append(candidate)

    def candidate_score(item: CandidateStock) -> float:
        pct = _parse_float(item.pct_change) or 0.0
        amount = (_parse_float(item.amount) or 0.0) / 1_000_000_000
        turnover = _parse_float(item.turnover_rate) or 0.0
        turnover_score = 5 if 1 <= turnover <= 20 else 1
        return pct * 2 + min(amount, 20) + turnover_score

    deduped: dict[str, CandidateStock] = {}
    for item in sorted(candidates, key=candidate_score, reverse=True):
        deduped.setdefault(item.code, item)

    final_candidates = list(deduped.values())[:limit]
    confidence = "\u4e2d" if notes or not final_candidates else "\u9ad8"
    if not final_candidates:
        notes.append("\u6570\u4e0d\u5b8c\u6574\uff0c\u7f6e\u4fe1\u5ea6\u964d\u4f4e")
        confidence = "\u4f4e"

    return CandidatePoolResult(candidates=final_candidates, confidence=confidence, notes=notes)
