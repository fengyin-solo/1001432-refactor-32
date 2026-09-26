"""养护资金业务规则：状态流转、字段校验、去重与资金判断口径都收在这里。

已用金额、剩余额度、是否超支一律调用 app.services.budget 里的统一算法，
本服务不重复计算，只把算法结果同步到记录上，保证刷新后列表、合计与明细一致。
"""
from __future__ import annotations

from typing import Any

from app.services.budget import (
    APPROVED_FIELD,
    OVERSPENT_MESSAGE,
    USED_FIELD,
    Budget,
    evaluate,
    format_amount,
)
from app.store import store

MODULE = "fund"
PROJECT_FIELD = "项目名称"
REQUIRED_FIELDS = ["资金编号", "费用类别", PROJECT_FIELD]
OPTIONAL_AMOUNT_FIELDS = [APPROVED_FIELD, USED_FIELD, "审批人员"]
STATUS_ORDER = ["待审批", "已批复", "执行中", "已超支"]
OVERSPENT_STATUS = STATUS_ORDER[-1]
ACTION_RULES = {"提交审批": "已批复", "确认批复": "执行中", "标记超支": OVERSPENT_STATUS}
NEGATIVE_ACTIONS = ["标记超支"]
DUPLICATE_PROJECT_MESSAGE = "同一项目只允许登记一条资金记录，请勿重复登记"


class FundService:
    # ------------------------------------------------------------------ 查询
    def _filtered_rows(self, *, keyword: str | None, status: str | None) -> list[dict[str, Any]]:
        rows = store.rows(MODULE)
        if keyword:
            key = keyword.strip()
            rows = [
                row
                for row in rows
                if key in str(row.get("资金编号", "")) or key in str(row.get(PROJECT_FIELD, ""))
            ]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        return rows

    def list_entries(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = [self._present(row) for row in self._filtered_rows(keyword=keyword, status=status)]
        total = len(rows)
        start = max(page - 1, 0) * size
        return rows[start:start + size], total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None
        return self._present(entry)

    def stats(self, *, keyword: str | None = None, status: str | None = None) -> dict[str, Any]:
        """按与列表相同的过滤口径汇总；每个数都逐行取统一算法的结果再累加。"""
        rows = self._filtered_rows(keyword=keyword, status=status)
        approved_total = 0.0
        used_total = 0.0
        remaining_total = 0.0
        overspent_total = 0.0
        overspent_count = 0
        missing_count = 0
        for row in rows:
            budget = evaluate(row)
            if budget.approved is None:
                missing_count += 1
            else:
                approved_total += budget.approved
                remaining_total += budget.remaining or 0.0
            used_total += budget.used
            flagged = budget.overspent or row.get("status") == OVERSPENT_STATUS
            if flagged:
                overspent_count += 1
                overspent_total += max(budget.used - (budget.approved or 0.0), 0.0)
        return {
            "批复总额": format_amount(round(approved_total, 2)),
            "已用金额合计": format_amount(round(used_total, 2)),
            "剩余额度合计": format_amount(round(remaining_total, 2)),
            "超支项目": overspent_count,
            "超支合计": format_amount(round(overspent_total, 2)),
            "批复金额缺失": missing_count,
        }

    # ------------------------------------------------------------------ 登记
    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str], str]:
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, missing, ""
        rows = store.rows(MODULE)
        project = str(values.get(PROJECT_FIELD) or "").strip()
        if any(str(row.get(PROJECT_FIELD) or "").strip() == project for row in rows):
            # 同一项目重复登记只留一条：拦下新的一条，已有的那一条不动。
            return None, [], DUPLICATE_PROJECT_MESSAGE
        entry = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        for field in REQUIRED_FIELDS:
            entry[field] = str(values.get(field)).strip()
        for field in OPTIONAL_AMOUNT_FIELDS:
            raw = values.get(field)
            if raw is not None and str(raw).strip():
                entry[field] = raw
        entry["status"] = STATUS_ORDER[0]
        entry["pending"] = True
        entry["abnormal"] = False
        rows.append(entry)
        return self._present(entry), [], ""

    # ------------------------------------------------------------------ 流转
    def run_action(self, entry_id: int, action: str) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"资金记录 {entry_id} 不存在或已归档"
        if action not in ACTION_RULES:
            return None, f"动作「{action}」不属于养护资金可执行范围"
        target = ACTION_RULES[action]
        if target not in STATUS_ORDER:
            return None, f"目标状态「{target}」不在允许的状态序列里"
        # 超支的项目不能被改回执行中：金额口径超支或已标记超支都拦住，
        # 原有的提交审批、确认批复流程在未超支时保持不变。
        if target == "执行中" and self._is_overspent(entry):
            return None, OVERSPENT_MESSAGE
        entry["status"] = target
        entry["pending"] = target != OVERSPENT_STATUS
        entry["abnormal"] = target == OVERSPENT_STATUS
        return self._present(entry), f"资金记录已{action}"

    # ------------------------------------------------------------------ 内部
    def _is_overspent(self, entry: dict[str, Any]) -> bool:
        """统一超支判定：算法判定已用超批复，或已经走流程标记为已超支。"""
        return evaluate(entry).overspent or entry.get("status") == OVERSPENT_STATUS

    def _sync_flags(self, entry: dict[str, Any], budget: Budget, flagged: bool) -> None:
        """把统一算法的结论同步到记录上，避免列表、明细、看板各说各话。"""
        entry["已用金额"] = format_amount(budget.used)
        entry["剩余额度"] = format_amount(budget.remaining)
        entry["批复金额"] = format_amount(budget.approved)
        if flagged:
            entry["status"] = OVERSPENT_STATUS
            entry["abnormal"] = True
        entry["pending"] = entry.get("status") != OVERSPENT_STATUS
        entry["资金状态"] = entry.get("status")
        entry["资金提醒"] = budget.message

    def _present(self, entry: dict[str, Any]) -> dict[str, Any]:
        """输出一条记录的统一视图：金额、剩余额度、超支结论都来自统一算法。"""
        budget = evaluate(entry)
        flagged = budget.overspent or entry.get("status") == OVERSPENT_STATUS
        self._sync_flags(entry, budget, flagged)
        view = dict(entry)
        view["已超支"] = flagged
        return view
