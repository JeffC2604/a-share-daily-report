from __future__ import annotations

from dataclasses import dataclass


@dataclass
class DataSourceStatus:
    source: str
    status: str
    failure_reason: str = ""
    data: str = "\u7f3a\u5931"


@dataclass
class IndexData:
    code: str
    name: str
    last: str | float
    pct_change: str | float
    change: str | float
    amount: str | float
    source: str


@dataclass
class FundEstimateData:
    fund_code: str
    name: str
    nav_date: str
    nav: str
    estimate_nav: str
    estimate_pct: str
    estimate_time: str


@dataclass
class SectorData:
    code: str
    name: str
    category: str
    last: str | float
    pct_change: str | float
    amount: str | float
    fund_flow: str | float
    rising_count: str | int
    falling_count: str | int
    lead_stock: str
    lead_stock_pct: str | float
    source: str


@dataclass
class CandidateStock:
    code: str
    name: str
    market_type: str
    sector: str
    latest_price: str | float
    pct_change: str | float
    amount: str | float
    turnover_rate: str | float
    reason: str
    risk_note: str
    confidence: str
