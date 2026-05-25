from __future__ import annotations

from data_validation import DataKind, DataSourceStatus, validate_data_sources
from report_sections import DailyAStockReport, FundAnalysis, ReportSection, StockAnalysis


def build_example_report() -> str:
    validation = validate_data_sources(
        [
            DataSourceStatus(
                name="指数行情",
                source="正规行情源",
                kind=DataKind.QUOTE,
                success=True,
                data_time="2026-05-25 15:00",
                payload={"上证指数": 4130.71},
            ),
            DataSourceStatus(
                name="基金盘中估值",
                source="天天基金",
                kind=DataKind.INTRADAY_ESTIMATE,
                success=True,
                data_time="2026-05-25 13:38",
                payload={"估算涨幅": "2.42%"},
                is_intraday_estimate=True,
            ),
            DataSourceStatus(
                name="基金前十大持仓",
                source="天天基金",
                kind=DataKind.HOLDINGS,
                success=True,
                data_time="2026-03-31",
                payload={"持仓": ["江波龙", "德明利"]},
            ),
        ]
    )

    stock = StockAnalysis(
        name="示例股票",
        code="000000",
        sector="半导体",
        sector_strength="强于大盘",
        trend_position="中高位震荡",
        volume_price="放量上涨后等待确认",
        is_high_position="偏高，需要防冲高回落",
        chasing_risk="存在追涨风险",
        tomorrow_conditions=["观察是否继续放量", "若跌破关键位需重新评估"],
        risk_points=["高位放量滞涨", "板块退潮"],
        confidence="中",
    )

    fund = FundAnalysis(
        name="方正富邦核心优势混合C",
        code="018816",
        latest_nav_date="2026-05-22",
        intraday_estimate_time="2026-05-25 13:38",
        top_holdings_updated_at="2026-03-31",
        benefits_from_mainline="若半导体和存储主线延续，可能受益；该判断依赖持仓未显著变化的假设。",
        risk_points=["科技赛道集中", "持仓披露滞后", "单日估值不能代表最终净值"],
        confidence="中",
    )

    security_body = "\n\n".join([stock.render(), fund.render()])

    report = DailyAStockReport(
        validation=validation,
        market_judgment=ReportSection(
            "今日大盘判断",
            "指数偏强，成交量活跃，风险偏好集中在科技成长方向。需要继续观察成交量是否维持。",
            "中",
        ),
        mainline_sector=ReportSection(
            "主线板块判断",
            "主线偏向半导体、先进封装、存储和PCB。机器人相对偏弱，需等待资金回流确认。",
            "中",
        ),
        security_analysis=ReportSection("个股/基金分析", security_body, "中"),
        risk_points=ReportSection(
            "风险点",
            "主要风险是高位一致性、追涨、情绪退潮、假突破和基金持仓披露滞后。",
            "中",
        ),
        tomorrow_watchlist=ReportSection(
            "明日观察重点",
            "观察科技主线是否继续放量，PCB资金分歧是否修复，机器人是否重新走强。",
            "中",
        ),
        trading_discipline=ReportSection(
            "操作纪律",
            "以观察、等待、轻仓试错、止损位和仓位控制为主，不给确定性买入指令。",
            "高",
        ),
        one_sentence=ReportSection(
            "一句话结论",
            "科技主线仍有机会，但高位和追涨风险同步抬升，更适合等待确认。",
            "中",
        ),
        data_sources=ReportSection(
            "数据来源",
            "行情数据优先来自实时行情软件或交易所/正规行情源；公告、监管和交易公开信息优先参考交易所和巨潮资讯。",
            "中",
        ),
    )
    return report.render_markdown()


if __name__ == "__main__":
    print(build_example_report())
