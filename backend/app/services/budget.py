"""养护资金的统一判断算法。

资金是否超支、已用金额与剩余额度是多少，整个系统只允许在这里算一遍：
资金列表、资金明细、统计合计、导出、状态流转都调用本模块，保证各处
拿到的是同一个已用金额、剩余额度和同一句提醒。

口径：
- 批复金额缺失（没有填或填了无法识别的内容）时，不判断超支，统一提示
  MISSING_APPROVED_MESSAGE；
- 已用金额缺省按 0 计；
- 已用金额超过批复金额时判定超支，统一提示 OVERSPENT_MESSAGE；
- 金额统一保留两位小数，避免 0.1 + 0.2 之类的浮点尾数让两处对不上。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

APPROVED_FIELD = "批复金额"
USED_FIELD = "已用金额"

# 同一句话讲清楚：批复金额缺失
MISSING_APPROVED_MESSAGE = "批复金额缺失，暂无法判断资金是否超支"
# 同一句话讲清楚：已用金额超过批复金额
OVERSPENT_MESSAGE = "已用金额超过批复金额，该项目资金已超支"

MISSING_AMOUNT = "—"


@dataclass(frozen=True)
class Budget:
    """一条资金记录按统一算法算出的结果。"""

    approved: float | None
    used: float
    remaining: float | None
    overspent: bool
    message: str


def to_amount(value: Any) -> float | None:
    """把登记进来的金额文本/数字解析成数字；空值或无法识别时返回 None。"""
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return round(float(value), 2)
    text = str(value).strip().replace(",", "").replace("，", "")
    if not text:
        return None
    try:
        return round(float(text), 2)
    except ValueError:
        return None


def evaluate(values: dict[str, Any]) -> Budget:
    """按唯一口径评估一条资金记录的已用金额、剩余额度与超支状态。"""
    approved = to_amount(values.get(APPROVED_FIELD))
    used = to_amount(values.get(USED_FIELD)) or 0.0
    if approved is None:
        return Budget(
            approved=None,
            used=used,
            remaining=None,
            overspent=False,
            message=MISSING_APPROVED_MESSAGE,
        )
    remaining = round(approved - used, 2)
    overspent = used > approved
    return Budget(
        approved=approved,
        used=used,
        remaining=remaining,
        overspent=overspent,
        message=OVERSPENT_MESSAGE if overspent else "",
    )


def format_amount(value: float | None) -> str:
    """金额的统一展示格式：两位小数；没有金额时显示占位符。"""
    if value is None:
        return MISSING_AMOUNT
    return f"{value:.2f}"
