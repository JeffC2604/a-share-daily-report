from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from data_validation import ValidationResult, render_validation_preface
from risk_rules import assert_safe_output, confidence_label


@dataclass(frozen=True)
class ReportSection:
    title: str
    body: str
    confidence: str = "低"

    def render(self) -> str:
        return f"## {self.title}\n\n置信度：{confidence_label(self.confidence)}\n\n{self.body.strip()}"


@dataclass(frozen=True)
class StockAnalysis:
    name: str
    code: str
    sector: str
    sector_strength: str
    trend_position: str
    volume_price: str
    is_high_position: str
    chasing_risk: str
    tomorrow_conditions: list[str]
    risk_points: list[str]
    confidence: str = "低"

    def render(self) -> str:
        conditions = "\n".join(f"- {item}" for item in self.tomorrow_conditions) or "- 暂无"
        risks = "\n".join(f"- {item}" for item in self.risk_points) or "- 暂无"
        return f"""### 个股分析：{self.name}（{self.code}）

- 所属板块：{self.sector}
- 板块强弱：{self.sector_strength}
- 趋势位置：{self.trend_position}
- 量价关系：{self.volume_price}
- 是否高位：{self.is_high_position}
- 是否追涨风险：{self.chasing_risk}
- 置信度：{confidence_label(self.confidence)}

明日观察条件：
{conditions}

风险点：
{risks}

结论：不提供确定性买入建议，仅做观察、等待、轻仓试错、止损位和仓位控制参考。"""


@dataclass(frozen=True)
class FundAnalysis:
    name: str
    code: str
    latest_nav_date: str
    intraday_estimate_time: str
    top_holdings_updated_at: str
    benefits_from_mainline: str
    suitable_for_chasing: str = "默认不适合直接追涨"
    holding_lag_risk: str = "前十大持仓存在披露滞后，不能代表当前实时持仓。"
    concentration_risk: str = "需要检查行业和重仓股集中度，集中度越高，净值波动越大。"
    risk_points: list[str] = field(default_factory=list)
    confidence: str = "低"

    def render(self) -> str:
        risks = "\n".join(f"- {item}" for item in self.risk_points) or "- 暂无"
        return f"""### 基金分析：{self.name}（{self.code}）

- 最新净值日期：{self.latest_nav_date}
- 盘中估值时间：{self.intraday_estimate_time}
- 前十大持仓更新时间：{self.top_holdings_updated_at}
- 持仓滞后风险：{self.holding_lag_risk}
- 行业集中度风险：{self.concentration_risk}
- 是否受益于今日主线：{self.benefits_from_mainline}
- 是否适合追涨：{self.suitable_for_chasing}
- 置信度：{confidence_label(self.confidence)}

风险点：
{risks}

结论：基金分析默认不直接建议追涨，需结合净值位置、持仓集中度、主线持续性和个人风险承受能力观察。"""


class OpinionType(str, Enum):
    LOGICAL = "逻辑分析"
    EMOTIONAL = "情绪帖"
    TRAFFIC = "引流帖"
    HINDSIGHT = "马后炮"
    INSUFFICIENT_RISK = "风险提示不足"


@dataclass(frozen=True)
class OpinionDetection:
    opinion_type: OpinionType
    reasons: list[str]
    missing_risk_notes: list[str]
    confidence: str = "低"

    def render(self) -> str:
        reasons = "\n".join(f"- {item}" for item in self.reasons) or "- 暂无"
        risks = "\n".join(f"- {item}" for item in self.missing_risk_notes) or "- 暂无"
        return f"""### 市场观点识别

- 类型：{self.opinion_type.value}
- 置信度：{confidence_label(self.confidence)}

判断理由：
{reasons}

缺失的风险提示：
{risks}"""


def detect_market_opinion(text: str) -> OpinionDetection:
    traffic_words = ("加群", "关注", "私信", "课程", "付费", "内部消息")
    emotional_words = ("疯了", "崩了", "起飞", "错过", "血亏", "无脑")
    hindsight_words = ("早就说过", "昨天已经提示", "完全符合预期", "马后炮")
    risk_words = ("风险", "止损", "回撤", "不确定", "失效")
    logic_words = ("因为", "数据", "成交量", "估值", "业绩", "公告", "验证")

    reasons: list[str] = []
    missing: list[str] = []

    if any(word in text for word in traffic_words):
        reasons.append("存在关注、加群、付费或内部消息等引流特征。")
        opinion_type = OpinionType.TRAFFIC
    elif any(word in text for word in hindsight_words):
        reasons.append("存在事后归因或结果倒推倾向。")
        opinion_type = OpinionType.HINDSIGHT
    elif any(word in text for word in emotional_words):
        reasons.append("情绪化词汇较多，容易放大恐惧或贪婪。")
        opinion_type = OpinionType.EMOTIONAL
    elif not any(word in text for word in risk_words):
        reasons.append("观点没有明确风险、失效条件或不确定性说明。")
        opinion_type = OpinionType.INSUFFICIENT_RISK
    elif any(word in text for word in logic_words):
        reasons.append("包含数据、因果或可验证线索。")
        opinion_type = OpinionType.LOGICAL
    else:
        reasons.append("信息不足，无法判断为完整逻辑分析。")
        opinion_type = OpinionType.INSUFFICIENT_RISK

    if not any(word in text for word in risk_words):
        missing.append("未看到风险或失效条件。")
    if "成交量" not in text and "量" not in text:
        missing.append("未看到成交量验证。")
    if "大盘" not in text and "指数" not in text:
        missing.append("未结合大盘环境。")
    if "板块" not in text and "主线" not in text:
        missing.append("未结合板块环境。")

    confidence = "中" if reasons else "低"
    return OpinionDetection(opinion_type, reasons, missing, confidence)


@dataclass(frozen=True)
class DailyAStockReport:
    validation: ValidationResult
    market_judgment: ReportSection
    mainline_sector: ReportSection
    security_analysis: ReportSection
    risk_points: ReportSection
    tomorrow_watchlist: ReportSection
    trading_discipline: ReportSection
    one_sentence: ReportSection
    data_sources: ReportSection

    def render_markdown(self) -> str:
        sections = [
            render_validation_preface(self.validation),
            self.market_judgment.render(),
            self.mainline_sector.render(),
            self.security_analysis.render(),
            self.risk_points.render(),
            self.tomorrow_watchlist.render(),
            self.trading_discipline.render(),
            self.one_sentence.render(),
            self.data_sources.render(),
        ]
        markdown = "\n\n".join(sections).strip() + "\n"
        assert_safe_output(markdown)
        return markdown
