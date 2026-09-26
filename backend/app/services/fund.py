"""养护资金业务规则。

状态与金额判断全部走 ``fund_calc`` 这一份共用算法，本层只负责登记、
审批流转、同项目去重与存取。
"""
from __future__ import annotations

from typing import Any

from app.services import fund_calc
from app.store import store

MODULE = "fund"
REQUIRED_FIELDS = ["资金编号", "费用类别", "项目名称"]
# 审批流程照旧：待审批 --提交审批--> 已批复 --确认批复--> 执行中。
ACTION_STAGE = {"提交审批": fund_calc.STAGE_APPROVED, "确认批复": fund_calc.STAGE_RUNNING}
ACTION_LABEL = dict(ACTION_STAGE, **{"标记超支": "标记超支"})


class FundService:
    def __init__(self) -> None:
        self._deduplicated = False

    # ---------- 内部工具 ----------

    def _ensure_dedup(self) -> None:
        """同一项目重复登记只留一条：启动后首次访问时归并一次。"""
        if self._deduplicated:
            return
        self._deduplicated = True
        rows = store.rows(MODULE)
        merged: dict[str, dict[str, Any]] = {}
        order: list[str] = []
        for row in rows:
            key = str(row.get("项目名称") or "").strip()
            if key not in merged:
                merged[key] = row
                order.append(key)
                continue
            target = merged[key]
            target["资金明细"] = fund_calc.evaluate(target)["资金明细"] + fund_calc.evaluate(row)["资金明细"]
            # 批复金额以最新一条非空登记为准；资金编号保留首条，避免编号漂移。
            incoming = fund_calc.to_amount(row.get("批复金额"))
            if incoming is not None:
                target["批复金额"] = incoming
            if str(target.get("资金编号") or "").strip() == "":
                target["资金编号"] = row.get("资金编号")
        deduped = [merged[key] for key in order]
        rows[:] = deduped
        for row in rows:
            self._sync(row)

    def _sync(self, entry: dict[str, Any]) -> None:
        """把共用算法的结论写回 status/abnormal，并兼容旧数据的 stage。"""
        legacy_status = str(entry.get("status") or "")
        if "stage" not in entry:
            if legacy_status in (fund_calc.STATUS_RUNNING, fund_calc.STATUS_OVERSPENT):
                entry["stage"] = fund_calc.STAGE_RUNNING
            elif legacy_status == fund_calc.STATUS_APPROVED:
                entry["stage"] = fund_calc.STAGE_APPROVED
            else:
                entry["stage"] = fund_calc.STAGE_PENDING
        result = fund_calc.evaluate(entry)
        entry["status"] = result["资金状态"]
        entry["资金状态"] = result["资金状态"]
        entry["已用金额"] = result["已用金额"]
        entry["剩余额度"] = result["剩余额度"]
        entry["pending"] = result["资金状态"] != fund_calc.STATUS_OVERSPENT
        entry["abnormal"] = result["_overspent"]

    # ---------- 查询 ----------

    def list_entries(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int, dict[str, Any]]:
        self._ensure_dedup()
        rows = store.rows(MODULE)
        for row in rows:
            self._sync(row)
        filtered = rows
        if keyword:
            filtered = [row for row in filtered if keyword in str(row.get("资金编号", "")) or keyword in str(row.get("项目名称", ""))]
        if status:
            filtered = [row for row in filtered if fund_calc.evaluate(row)["资金状态"] == status]
        # 合计与列表、明细同源：先按同一批过滤后的记录汇总，再分页。
        stats = fund_calc.summarize(filtered)
        total = len(filtered)
        start = max(page - 1, 0) * size
        page_rows = [fund_calc.present(row) for row in filtered[start:start + size]]
        return page_rows, total, stats

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        self._ensure_dedup()
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None
        self._sync(entry)
        return fund_calc.present(entry)

    # ---------- 登记 ----------

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str], str]:
        self._ensure_dedup()
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, missing, ""
        rows = store.rows(MODULE)
        project = str(values.get("项目名称")).strip()

        amount = fund_calc.to_amount(values.get("本次支出金额"))
        detail_text = str(values.get("支出事项") or "本次登记支出").strip()
        new_details = [{"事项": detail_text, "金额": amount}] if amount is not None and amount > 0 else []

        # 同一项目重复登记只留一条：并入既有记录。
        existing = next((row for row in rows if str(row.get("项目名称") or "").strip() == project), None)
        if existing is not None:
            existing.setdefault("资金明细", [])
            existing["资金明细"].extend(new_details)
            approved = fund_calc.to_amount(values.get("批复金额"))
            if approved is not None:
                existing["批复金额"] = approved
            if str(values.get("费用类别") or "").strip():
                existing["费用类别"] = values.get("费用类别")
            if str(values.get("审批人员") or "").strip():
                existing["审批人员"] = values.get("审批人员")
            self._sync(existing)
            return fund_calc.present(existing), [], f"项目「{project}」已存在，登记金额已并入同一条记录"

        entry: dict[str, Any] = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        entry.update({field: values.get(field) for field in REQUIRED_FIELDS})
        entry["项目名称"] = project
        entry["批复金额"] = fund_calc.to_amount(values.get("批复金额"))
        entry["审批人员"] = str(values.get("审批人员") or "").strip()
        entry["资金明细"] = new_details
        entry["stage"] = fund_calc.STAGE_PENDING
        rows.append(entry)
        self._sync(entry)
        return fund_calc.present(entry), [], "资金记录已登记"

    # ---------- 审批 / 超支动作 ----------

    def run_action(
        self,
        entry_id: int,
        action: str,
        *,
        approver: str = "",
    ) -> tuple[dict[str, Any] | None, str]:
        self._ensure_dedup()
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"资金记录 {entry_id} 不存在或已归档"
        if action not in ACTION_LABEL:
            return None, f"动作「{action}」不属于养护资金可执行范围"

        snapshot = fund_calc.evaluate(entry)
        approved, used = snapshot["批复金额"], snapshot["已用金额"]

        if action == "标记超支":
            # 只是同一份算法的手动入口：算法没命中就不能硬标。
            if entry.get("stage") != fund_calc.STAGE_RUNNING:
                return None, "项目尚未进入执行阶段，不能标记超支"
            if snapshot["_overspent"]:
                return None, fund_calc.FUND_WARNING
            return None, "已用金额未超过批复金额，不能标记为超支"

        if action == "提交审批":
            if snapshot["_overspent"]:
                # 已超支的项目不能被改回执行中（也不能退回审批环节）。
                return None, fund_calc.FUND_WARNING
            entry["stage"] = ACTION_STAGE[action]
            if approver:
                entry["审批人员"] = approver
        else:  # 确认批复：批复后即进入执行
            if snapshot["_overspent"]:
                # 已超支的项目不能被改回执行中。
                return None, fund_calc.FUND_WARNING
            entry["stage"] = ACTION_STAGE[action]

        self._sync(entry)
        result = fund_calc.evaluate(entry)
        message = f"资金记录已{ACTION_LABEL[action]}"
        if result["资金提醒"]:
            message = f"{message}；{result['资金提醒']}"
        return fund_calc.present(entry), message
