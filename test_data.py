from __future__ import annotations

import sys

from data_sources import fetch_index_data, fetch_tiantian_fund_estimate
from parsed_models import DataSourceStatus


def print_table(title: str, headers: list[str], rows: list[list[object]]) -> None:
    print(f"\n=== {title} ===")
    if not rows:
        print("(empty)")
        return

    widths = [len(header) for header in headers]
    for row in rows:
        for index, value in enumerate(row):
            widths[index] = max(widths[index], len(str(value)))

    def fmt(row: list[object]) -> str:
        return " | ".join(str(value).ljust(widths[index]) for index, value in enumerate(row))

    print(fmt(headers))
    print("-+-".join("-" * width for width in widths))
    for row in rows:
        print(fmt(row))


def build_status_rows(index_result, fund_result) -> list[DataSourceStatus]:
    backup = index_result.backup
    return [
        DataSourceStatus(
            source="东方财富指数接口",
            status="成功" if index_result.eastmoney.ok else "失败",
            failure_reason=index_result.eastmoney.error_type,
            data="成功" if index_result.eastmoney.ok else "缺失",
        ),
        DataSourceStatus(
            source="备用指数接口",
            status="成功" if backup and backup.ok else "未使用/失败",
            failure_reason="" if backup and backup.ok else (backup.error_type if backup else ""),
            data="成功" if backup and backup.ok else "缺失",
        ),
        DataSourceStatus(
            source="本地fallback_data.json",
            status="已使用" if index_result.local_fallback_used else "未使用",
            data="成功" if index_result.local_fallback_used else "缺失",
        ),
        DataSourceStatus(
            source="天天基金数据",
            status="成功" if fund_result.fetch.ok else "失败",
            failure_reason=fund_result.fetch.error_type,
            data="成功" if fund_result.data else "缺失",
        ),
    ]


def main() -> None:
    print("Python executable:", sys.executable)

    index_result = fetch_index_data()
    fund_result = fetch_tiantian_fund_estimate("018816")

    status_rows = [
        [item.source, item.status, item.failure_reason, item.data]
        for item in build_status_rows(index_result, fund_result)
    ]
    print_table("Data source status", ["source", "status", "failure_reason", "data"], status_rows)

    index_rows = [
        [item.code, item.name, item.last, item.pct_change, item.change, item.amount, item.source]
        for item in index_result.data
    ]
    print_table("Index parsed data", ["code", "name", "last", "pct_change", "change", "amount", "source"], index_rows)

    fund_rows = []
    if fund_result.data:
        item = fund_result.data
        fund_rows.append(
            [
                item.fund_code,
                item.name,
                item.nav_date,
                item.nav,
                item.estimate_nav,
                item.estimate_pct,
                item.estimate_time,
            ]
        )
    print_table(
        "Tiantian fund 018816 parsed data",
        ["fund_code", "name", "nav_date", "nav", "estimate_nav", "estimate_pct", "estimate_time"],
        fund_rows,
    )


if __name__ == "__main__":
    main()
