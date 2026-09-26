"""资金口径共用算法。

页面、接口、明细、合计全部以这里的函数为准：任何一处都不再自行相减、
不再自行判断超支，保证「同一份算法、同一个已用金额、同一个剩余额度」。
"""
from __future__ import annotations

from typing import Any, Iterable

# 批复金额缺失，或已用金额超过批复金额，统一用这一句讲明。
FUND_WARNING = "批复金额缺失或已用金额超过批复金额，请核对资金口径"

STATUS_PENDING = "待审批"
STATUS_APPROVED = "已批复"
STATUS_RUNNING = "执行中"
STATUS_OVERSPENT = "已超支"

# 审批阶段：批复前只看审批，批复后才进入资金口径判断。
STAGE_PENDING = "待审批"
STAGE_APPROVED = "已批复"
STAGE_RUNNING = "执行中"

AMOUNT_FIELDS = ("批复金额", "已用金额", "剩余额度")


def to_amount(value: Any) -> float | None:
    """把登记值解析成金额；空串、无法解析的值一律视为缺失（None）。"""
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return round(float(value), 2)
    text = str(value).strip().replace(",", "")
    if not text:
        return None
    try:
        return round(float(text), 2)
    except ValueError:
        return None


def sum_used(details: Iterable[Any]) -> float:
    """已用金额只从资金明细汇总，明细缺失时才回退到登记值。"""
    total = 0.0
    found = False
    for detail in details or []:
        amount = to_amount(detail.get("金额") if isinstance(detail, dict) else detail)
        if amount is not None:
            total += amount
            found = True
    if not found:
        return 0.0
    return round(total, 2)


def remaining_amount(approved: float | None, used: float) -> float | None:
    """剩余额度 = 批复金额 - 已用金额；批复金额缺失时无剩余可言。"""
    if approved is None:
        return None
    return round(approved - used, 2)


def is_overspent(approved: float | None, used: float) -> bool:
    """批复金额缺，或已用金额超过批复金额，即为超支口径命中。"""
    return approved is None or used > approved


def fund_status(approved: float | None, used: float, stage: str) -> str:
    """审批阶段 + 资金口径合一处推导最终状态。

    审批流程照旧（待审批 → 已批复 → 执行中）；进入执行后一旦命中超支
    口径即为「已超支」，且没有任何动作能把它改回「执行中」。
    """
    if stage == STAGE_PENDING:
        return STATUS_PENDING
    if stage == STAGE_APPROVED:
        return STATUS_APPROVED
    if stage == STAGE_RUNNING:
        return STATUS_OVERSPENT if is_overspent(approved, used) else STATUS_RUNNING
    return stage


def warning_for(approved: float | None, used: float) -> str:
    """缺批复或已用超出批复，给同一句提醒；否则不提醒。"""
    return FUND_WARNING if is_overspent(approved, used) else ""


def _details(entry: dict[str, Any]) -> list[dict[str, Any]]:
    details = entry.get("资金明细")
    if not isinstance(details, list):
        return []
    return [item for item in details if isinstance(item, dict)]


def evaluate(entry: dict[str, Any]) -> dict[str, Any]:
    """对一条资金记录执行完整算法，返回所有口径字段。

    已用金额的唯一来源是资金明细；旧数据没有明细时，用登记的「已用金额」
    补成一条明细后再算，保证历史记录刷新后口径仍一致。
    """
    details = _details(entry)
    if not details:
        legacy_used = to_amount(entry.get("已用金额"))
        if legacy_used is not None and legacy_used != 0:
            details = [{"事项": "已登记支出", "金额": legacy_used}]
    used = sum_used(details)
    approved = to_amount(entry.get("批复金额"))
    remaining = remaining_amount(approved, used)
    stage = str(entry.get("stage") or STATUS_PENDING)
    status = fund_status(approved, used, stage)
    warning = warning_for(approved, used)
    over_amount = round(used - approved, 2) if approved is not None and used > approved else 0.0
    return {
        "批复金额": approved,
        "已用金额": used,
        "剩余额度": remaining,
        "资金状态": status,
        "资金提醒": warning,
        "超支金额": over_amount,
        "资金明细": details,
        "_stage": stage,
        "_overspent": status == STATUS_OVERSPENT,
    }


def present(entry: dict[str, Any]) -> dict[str, Any]:
    """把内部记录按统一口径投影成列表/明细共用的输出结构。"""
    result = evaluate(entry)
    return {
        "id": entry.get("id"),
        "资金编号": entry.get("资金编号") or "",
        "费用类别": entry.get("费用类别") or "",
        "项目名称": entry.get("项目名称") or "",
        "批复金额": result["批复金额"],
        "已用金额": result["已用金额"],
        "剩余额度": result["剩余额度"],
        "审批人员": entry.get("审批人员") or "",
        "资金状态": result["资金状态"],
        "资金提醒": result["资金提醒"],
        "超支金额": result["超支金额"],
        "资金明细": result["资金明细"],
    }


def summarize(entries: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """合计口径：列表、统计卡片、导出共用同一份逐行算法结果。"""
    approved_total = 0.0
    used_total = 0.0
    overspent_total = 0.0
    overspent_count = 0
    for entry in entries:
        result = evaluate(entry)
        if result["批复金额"] is not None:
            approved_total += result["批复金额"]
        used_total += result["已用金额"]
        if result["_overspent"]:
            overspent_count += 1
            overspent_total += result["超支金额"]
    return {
        "批复总额": round(approved_total, 2),
        "已用金额合计": round(used_total, 2),
        "超支合计": round(overspent_total, 2),
        "超支项目": overspent_count,
    }
