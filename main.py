from __future__ import annotations

import json
import shutil
from datetime import date
from html import escape
from pathlib import Path

from analysis_rules import render_candidate_pool_observation, render_initial_observation, render_sector_heat_observation
from candidate_pool import build_candidate_pool
from data_sources import fetch_index_data, fetch_tiantian_fund_estimate
from parsed_models import DataSourceStatus
from risk_rules import print_risk_violations, scan_forbidden_output
from sector_sources import fetch_sector_data


CONFIG_PATH = Path("config.json")
PAGES_DIR = Path("public")
DEFAULT_CONFIG = {
    "report_date": "auto",
    "funds": ["018816"],
    "indexes": [
        {"code": "000001", "name": "\u4e0a\u8bc1\u6307\u6570"},
        {"code": "399001", "name": "\u6df1\u8bc1\u6210\u6307"},
        {"code": "399006", "name": "\u521b\u4e1a\u677f\u6307"},
        {"code": "000300", "name": "\u6caa\u6df1300"},
        {"code": "000688", "name": "\u79d1\u521b50"},
    ],
    "output_dir": "output",
}

CN_MISSING = "\u7f3a\u5931"
CN_SUCCESS = "\u6210\u529f"
CN_FAILED = "\u5931\u8d25"
CN_UNUSED = "\u672a\u4f7f\u7528"
CN_USED = "\u5df2\u4f7f\u7528"
CN_UNKNOWN = "\u672a\u77e5"

SRC_EASTMONEY = "\u4e1c\u65b9\u8d22\u5bcc\u6307\u6570\u63a5\u53e3"
SRC_BACKUP = "\u5907\u7528\u6307\u6570\u63a5\u53e3"
SRC_FALLBACK = "\u672c\u5730fallback_data.json"
SRC_TIATIAN = "\u5929\u5929\u57fa\u91d1\u6570\u636e"

STATUS_HEADERS = ["\u6570\u636e\u6e90", "\u72b6\u6001", "\u5931\u8d25\u539f\u56e0", "\u6570\u636e"]
INDEX_HEADERS = ["\u4ee3\u7801", "\u540d\u79f0", "\u6700\u65b0\u70b9\u4f4d", "\u6da8\u8dcc\u5e45", "\u6da8\u8dcc\u70b9", "\u6210\u4ea4\u989d", "\u6765\u6e90"]
SECTOR_HEADERS = ["\u7c7b\u578b", "\u4ee3\u7801", "\u540d\u79f0", "\u6da8\u8dcc\u5e45", "\u6210\u4ea4\u989d", "\u8d44\u91d1\u70ed\u5ea6", "\u4e0a\u6da8\u5bb6\u6570", "\u4e0b\u8dcc\u5bb6\u6570", "\u9886\u6da8\u6807\u7684", "\u9886\u6da8\u5e45"]
CANDIDATE_HEADERS = ["\u80a1\u7968\u4ee3\u7801", "\u80a1\u7968\u540d\u79f0", "\u5e02\u573a\u7c7b\u578b", "\u6240\u5c5e\u677f\u5757", "\u6700\u65b0\u4ef7", "\u6da8\u8dcc\u5e45", "\u6210\u4ea4\u989d", "\u6362\u624b\u7387", "\u5165\u9009\u539f\u56e0", "\u98ce\u9669\u63d0\u793a", "\u7f6e\u4fe1\u5ea6"]
FUND_HEADERS = ["\u57fa\u91d1\u4ee3\u7801", "\u540d\u79f0", "\u51c0\u503c\u65e5\u671f", "\u5355\u4f4d\u51c0\u503c", "\u4f30\u7b97\u51c0\u503c", "\u4f30\u7b97\u6da8\u5e45", "\u4f30\u503c\u65f6\u95f4"]


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        CONFIG_PATH.write_text(json.dumps(DEFAULT_CONFIG, ensure_ascii=False, indent=2), encoding="utf-8-sig")
        return DEFAULT_CONFIG
    data = json.loads(CONFIG_PATH.read_text(encoding="utf-8-sig"))
    return {**DEFAULT_CONFIG, **data}


def resolve_report_date(config: dict) -> str:
    configured = str(config.get("report_date", "auto"))
    if configured.lower() == "auto":
        return date.today().isoformat()
    return configured


def markdown_table(headers: list[str], rows: list[list[object]]) -> str:
    if not rows:
        rows = [[CN_MISSING] + [""] * (len(headers) - 1)]
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        padded = row + [""] * (len(headers) - len(row))
        lines.append("| " + " | ".join(str(value) for value in padded[: len(headers)]) + " |")
    return "\n".join(lines)


def html_table(headers: list[str], rows: list[list[object]], status_column: int | None = None) -> str:
    if not rows:
        rows = [[CN_MISSING] + [""] * (len(headers) - 1)]
    head = "".join(f"<th>{escape(header)}</th>" for header in headers)
    body_rows = []
    for row in rows:
        padded = row + [""] * (len(headers) - len(row))
        css_class = ""
        if status_column is not None:
            status = str(padded[status_column])
            if status == CN_SUCCESS:
                css_class = ' class="status-success"'
            elif status == CN_FAILED or CN_MISSING in status:
                css_class = ' class="status-failed"'
        cells = "".join(f"<td>{escape(str(value))}</td>" for value in padded[: len(headers)])
        body_rows.append(f"<tr{css_class}>{cells}</tr>")
    return f"<table><thead><tr>{head}</tr></thead><tbody>{''.join(body_rows)}</tbody></table>"


def build_status_rows(index_result, fund_results, sector_result) -> list[DataSourceStatus]:
    backup = index_result.backup
    rows = [
        DataSourceStatus(
            source=SRC_EASTMONEY,
            status=CN_SUCCESS if index_result.eastmoney.ok else CN_FAILED,
            failure_reason=index_result.eastmoney.error_type,
            data=CN_SUCCESS if index_result.eastmoney.ok else CN_MISSING,
        ),
        DataSourceStatus(
            source=SRC_BACKUP,
            status=CN_SUCCESS if backup and backup.ok else f"{CN_UNUSED}/{CN_FAILED}",
            failure_reason="" if backup and backup.ok else (backup.error_type if backup else ""),
            data=CN_SUCCESS if backup and backup.ok else CN_MISSING,
        ),
        DataSourceStatus(
            source=SRC_FALLBACK,
            status=CN_USED if index_result.local_fallback_used else CN_UNUSED,
            data=CN_SUCCESS if index_result.local_fallback_used else CN_MISSING,
        ),
    ]
    for sector_status in sector_result.statuses:
        rows.append(
            DataSourceStatus(
                source=sector_status.source,
                status=sector_status.status,
                failure_reason=sector_status.failure_reason,
                data=sector_status.data,
            )
        )
    for fund_result in fund_results:
        fund_code = fund_result.data.fund_code if fund_result.data else fund_result.fetch.url.rsplit("/", 1)[-1].replace(".js", "")
        rows.append(
            DataSourceStatus(
                source=f"{SRC_TIATIAN} {fund_code}",
                status=CN_SUCCESS if fund_result.fetch.ok else CN_FAILED,
                failure_reason=fund_result.fetch.error_type,
                data=CN_SUCCESS if fund_result.data else CN_MISSING,
            )
        )
    return rows


def build_missing_notes(index_result, fund_results, sector_result) -> list[str]:
    notes: list[str] = []
    if not index_result.eastmoney.ok:
        reason = index_result.eastmoney.error_type or CN_UNKNOWN
        notes.append(f"\u4e1c\u65b9\u8d22\u5bcc\u4e3b\u6307\u6570\u63a5\u53e3\u5931\u8d25\uff0c\u5931\u8d25\u539f\u56e0\uff1a{reason}\u3002")
    if not index_result.eastmoney.ok and index_result.backup and index_result.backup.ok:
        notes.append("\u4e1c\u65b9\u8d22\u5bcc\u4e3b\u63a5\u53e3\u5931\u8d25\uff0c\u4f46\u5907\u7528\u6307\u6570\u63a5\u53e3\u6210\u529f\uff0c\u6307\u6570\u6570\u636e\u6765\u81ea\u5907\u7528\u63a5\u53e3\u3002")
    if not index_result.data:
        notes.append("\u6240\u6709\u6307\u6570\u63a5\u53e3\u548c\u672c\u5730 fallback \u6570\u636e\u5747\u4e0d\u53ef\u7528\uff0c\u6307\u6570\u6570\u636e\u7f3a\u5931\u3002")
    for sector_status in sector_result.statuses:
        if sector_status.status == CN_FAILED or sector_status.data == CN_MISSING:
            reason = sector_status.failure_reason or CN_UNKNOWN
            notes.append(f"{sector_status.source}\u6570\u636e\u7f3a\u5931\uff0c\u5931\u8d25\u539f\u56e0\uff1a{reason}\u3002")
    if sector_result.statuses and not sector_result.data:
        notes.append("\u4e91\u7aef\u73af\u5883\u4e0b\u677f\u5757\u63a5\u53e3\u6682\u65f6\u4e0d\u53ef\u7528\u3002")
    for fund_result in fund_results:
        if not fund_result.data:
            reason = fund_result.fetch.error_type or CN_UNKNOWN
            fund_code = fund_result.fetch.url.rsplit("/", 1)[-1].replace(".js", "")
            notes.append(f"\u5929\u5929\u57fa\u91d1 {fund_code} \u4f30\u503c\u6570\u636e\u7f3a\u5931\uff0c\u5931\u8d25\u539f\u56e0\uff1a{reason}\u3002")
    if not notes:
        notes.append("\u6682\u65e0\u6570\u636e\u7f3a\u5931\u3002")
    return notes


def collect_rows(index_result, fund_results, sector_result, configured_indexes: list[dict]):
    configured_codes = {str(item.get("code", "")) for item in configured_indexes}
    filtered_index_data = [item for item in index_result.data if not configured_codes or str(item.code) in configured_codes]
    index_rows = [[item.code, item.name, item.last, item.pct_change, item.change, item.amount, item.source] for item in filtered_index_data]
    sector_rows = [
        [
            item.category,
            item.code,
            item.name,
            item.pct_change,
            item.amount,
            item.fund_flow,
            item.rising_count,
            item.falling_count,
            item.lead_stock,
            item.lead_stock_pct,
        ]
        for item in sector_result.data
    ]
    fund_data = []
    fund_rows = []
    for fund_result in fund_results:
        if fund_result.data:
            item = fund_result.data
            fund_data.append(item)
            fund_rows.append([item.fund_code, item.name, item.nav_date, item.nav, item.estimate_nav, item.estimate_pct, item.estimate_time])
    return filtered_index_data, index_rows, sector_rows, fund_data, fund_rows


def render_report(index_result, fund_results, sector_result, candidate_result, report_date: str, configured_indexes: list[dict]) -> str:
    statuses = build_status_rows(index_result, fund_results, sector_result)
    status_rows = [[item.source, item.status, item.failure_reason, item.data] for item in statuses]
    filtered_index_data, index_rows, sector_rows, fund_data, fund_rows = collect_rows(index_result, fund_results, sector_result, configured_indexes)
    missing_notes = "\n".join(f"- {note}" for note in build_missing_notes(index_result, fund_results, sector_result))
    initial_observation = render_initial_observation(filtered_index_data, fund_data, statuses)
    sector_observation = render_sector_heat_observation(sector_result.data, [DataSourceStatus(s.source, s.status, s.failure_reason, s.data) for s in sector_result.statuses])
    candidate_observation = render_candidate_pool_observation(candidate_result.candidates, candidate_result.confidence, candidate_result.notes)
    candidate_rows = [
        [
            item.code,
            item.name,
            item.market_type,
            item.sector,
            item.latest_price,
            item.pct_change,
            item.amount,
            item.turnover_rate,
            item.reason,
            item.risk_note,
            item.confidence,
        ]
        for item in candidate_result.candidates
    ]

    return f"""# \u6bcf\u65e5 A \u80a1\u6570\u636e\u65e5\u62a5

\u65e5\u671f\uff1a{report_date}

{initial_observation}

{sector_observation}

{candidate_observation}

## \u6570\u636e\u6e90\u72b6\u6001

{markdown_table(STATUS_HEADERS, status_rows)}

## \u6307\u6570\u6570\u636e\u8868

{markdown_table(INDEX_HEADERS, index_rows)}

## \u677f\u5757\u6570\u636e\u8868

{markdown_table(SECTOR_HEADERS, sector_rows)}

## \u5019\u9009\u89c2\u5bdf\u6c60\u8868

{markdown_table(CANDIDATE_HEADERS, candidate_rows)}

## \u57fa\u91d1\u4f30\u503c\u8868

{markdown_table(FUND_HEADERS, fund_rows)}

## \u6570\u636e\u7f3a\u5931\u63d0\u793a

{missing_notes}

## \u98ce\u9669\u63d0\u793a

\u4ee5\u4e0b\u5185\u5bb9\u4ec5\u4e3a\u6570\u636e\u6293\u53d6\u548c\u6574\u7406\u7ed3\u679c\uff0c\u4e0d\u6784\u6210\u6295\u8d44\u5efa\u8bae\u3002\u5e02\u573a\u5b58\u5728\u4e0d\u786e\u5b9a\u6027\uff0c\u8bf7\u7ed3\u5408\u81ea\u8eab\u98ce\u9669\u627f\u53d7\u80fd\u529b\u72ec\u7acb\u51b3\u7b56\u3002
"""


def render_html_report(index_result, fund_results, sector_result, candidate_result, report_date: str, configured_indexes: list[dict]) -> str:
    statuses = build_status_rows(index_result, fund_results, sector_result)
    status_rows = [[item.source, item.status, item.failure_reason, item.data] for item in statuses]
    filtered_index_data, index_rows, sector_rows, fund_data, fund_rows = collect_rows(index_result, fund_results, sector_result, configured_indexes)
    missing_notes = "".join(f"<li>{escape(note)}</li>" for note in build_missing_notes(index_result, fund_results, sector_result))
    initial_html = "<br>".join(escape(line) for line in render_initial_observation(filtered_index_data, fund_data, statuses).splitlines() if line.strip())
    sector_html = "<br>".join(escape(line) for line in render_sector_heat_observation(sector_result.data, [DataSourceStatus(s.source, s.status, s.failure_reason, s.data) for s in sector_result.statuses]).splitlines() if line.strip())
    candidate_html = "<br>".join(escape(line) for line in render_candidate_pool_observation(candidate_result.candidates, candidate_result.confidence, candidate_result.notes).splitlines() if line.strip())
    candidate_rows = [
        [
            item.code,
            item.name,
            item.market_type,
            item.sector,
            item.latest_price,
            item.pct_change,
            item.amount,
            item.turnover_rate,
            item.reason,
            item.risk_note,
            item.confidence,
        ]
        for item in candidate_result.candidates
    ]

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <title>\u6bcf\u65e5 A \u80a1\u6570\u636e\u65e5\u62a5 {escape(report_date)}</title>
  <style>
    body {{ margin: 0; padding: 32px 16px; background: #f6f7f9; color: #1f2937; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Microsoft YaHei", sans-serif; line-height: 1.6; }}
    main {{ max-width: 960px; margin: 0 auto; background: #ffffff; padding: 28px; border: 1px solid #e5e7eb; }}
    h1, h2 {{ margin-top: 0; }}
    table {{ width: 100%; border-collapse: collapse; margin: 12px 0 28px; font-size: 14px; }}
    th, td {{ border: 1px solid #d1d5db; padding: 8px 10px; text-align: left; vertical-align: top; }}
    th {{ background: #f3f4f6; font-weight: 600; }}
    tr.status-failed td {{ background: #fff1f2; }}
    tr.status-success td {{ background: #f0fdf4; }}
    .notice {{ background: #f9fafb; border: 1px solid #e5e7eb; padding: 12px 14px; margin-bottom: 24px; }}
  </style>
</head>
<body>
  <main>
    <h1>\u6bcf\u65e5 A \u80a1\u6570\u636e\u65e5\u62a5</h1>
    <p>\u65e5\u671f\uff1a{escape(report_date)}</p>
    <section class="notice">{initial_html}</section>
    <section class="notice">{sector_html}</section>
    <section class="notice">{candidate_html}</section>
    <h2>\u6570\u636e\u6e90\u72b6\u6001</h2>
    {html_table(STATUS_HEADERS, status_rows, status_column=1)}
    <h2>\u6307\u6570\u6570\u636e\u8868</h2>
    {html_table(INDEX_HEADERS, index_rows)}
    <h2>\u677f\u5757\u6570\u636e\u8868</h2>
    {html_table(SECTOR_HEADERS, sector_rows)}
    <h2>\u5019\u9009\u89c2\u5bdf\u6c60\u8868</h2>
    {html_table(CANDIDATE_HEADERS, candidate_rows)}
    <h2>\u57fa\u91d1\u4f30\u503c\u8868</h2>
    {html_table(FUND_HEADERS, fund_rows)}
    <h2>\u6570\u636e\u7f3a\u5931\u63d0\u793a</h2>
    <ul>{missing_notes}</ul>
    <h2>\u98ce\u9669\u63d0\u793a</h2>
    <p>\u4ee5\u4e0b\u5185\u5bb9\u4ec5\u4e3a\u6570\u636e\u6293\u53d6\u548c\u6574\u7406\u7ed3\u679c\uff0c\u4e0d\u6784\u6210\u6295\u8d44\u5efa\u8bae\u3002\u5e02\u573a\u5b58\u5728\u4e0d\u786e\u5b9a\u6027\uff0c\u8bf7\u7ed3\u5408\u81ea\u8eab\u98ce\u9669\u627f\u53d7\u80fd\u529b\u72ec\u7acb\u51b3\u7b56\u3002</p>
  </main>
</body>
</html>
"""


def main() -> None:
    config = load_config()
    report_date = resolve_report_date(config)
    funds = [str(code) for code in config.get("funds", [])]
    output_dir = Path(str(config.get("output_dir", "output")))

    index_result = fetch_index_data()
    sector_result = fetch_sector_data()
    candidate_result = build_candidate_pool(sector_result.data)
    fund_results = [fetch_tiantian_fund_estimate(fund_code) for fund_code in funds]

    markdown = render_report(index_result, fund_results, sector_result, candidate_result, report_date, config.get("indexes", []))
    scan_result = scan_forbidden_output(markdown)
    if not scan_result.passed:
        print_risk_violations(scan_result)
        return

    html = render_html_report(index_result, fund_results, sector_result, candidate_result, report_date, config.get("indexes", []))
    html_scan_result = scan_forbidden_output(html)
    if not html_scan_result.passed:
        print_risk_violations(html_scan_result)
        return

    output_dir.mkdir(exist_ok=True)
    markdown_path = output_dir / f"daily_report_{report_date}.md"
    html_path = output_dir / f"daily_report_{report_date}.html"
    markdown_path.write_text(markdown, encoding="utf-8-sig")
    html_path.write_text(html, encoding="utf-8-sig")

    PAGES_DIR.mkdir(exist_ok=True)
    pages_html_path = PAGES_DIR / html_path.name
    pages_index_path = PAGES_DIR / "index.html"
    shutil.copy2(html_path, pages_html_path)
    shutil.copy2(html_path, pages_index_path)

    print(f"Markdown report generated: {markdown_path.resolve()}")
    print(f"HTML report generated: {html_path.resolve()}")
    print(f"Pages HTML generated: {pages_html_path.resolve()}")
    print(f"Pages index generated: {pages_index_path.resolve()}")


if __name__ == "__main__":
    main()
