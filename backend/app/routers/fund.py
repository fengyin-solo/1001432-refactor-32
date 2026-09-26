"""养护资金接口：维护资金记录，覆盖提交审批、确认批复、标记超支等动作。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.schemas import ActionResult, EntryPayload, PageResult
from app.services.fund import FundService

router = APIRouter(prefix="/api/fund", tags=["养护资金"])

service = FundService()

LIST_FIELDS = ["资金编号", "费用类别", "项目名称", "批复金额", "已用金额", "剩余额度", "审批人员", "资金状态"]
STATUSES = ["待审批", "已批复", "执行中", "已超支"]


@router.get("", response_model=PageResult[dict])
def list_entries(
    keyword: str | None = Query(default=None, description="按资金编号或项目名称检索"),
    status: str | None = Query(default=None, description="待审批、已批复、执行中、已超支"),
    page: int = 1,
    size: int = 20,
) -> PageResult[dict]:
    """按资金编号与状态过滤养护资金列表；合计与明细共用同一份资金算法。"""
    if size > 200:
        raise HTTPException(status_code=400, detail="每页最多 200 条，请缩小分页范围")
    items, total, stats = service.list_entries(keyword=keyword, status=status, page=page, size=size)
    return PageResult(items=items, total=total, page=page, size=size, stats=stats)


@router.get("/export")
def export_entries(keyword: str | None = None, status: str | None = None) -> dict[str, Any]:
    """导出养护资金清单：全量数据与合计口径，和列表完全一致。"""
    items, total, stats = service.list_entries(keyword=keyword, status=status, page=1, size=10000)
    return {"module": "fund", "total": total, "stats": stats, "items": items}


@router.get("/{entry_id}", response_model=dict)
def get_entry(entry_id: int) -> dict:
    """读取单条资金记录明细；不存在时给出可读的错误说明。"""
    entry = service.get_entry(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"资金记录 {entry_id} 不存在或已归档")
    return entry


@router.post("", response_model=ActionResult)
def create_entry(payload: EntryPayload) -> ActionResult:
    """登记一条资金记录，缺字段时说明原因而不是静默丢弃；同项目重复登记只留一条。"""
    entry, missing, merge_message = service.create_entry(payload.values)
    if missing:
        return ActionResult(ok=False, message=f"缺少必填字段：{'、'.join(missing)}")
    return ActionResult(ok=True, message=merge_message or "资金记录已登记", entry=entry)


@router.post("/{entry_id}/actions", response_model=ActionResult)
def run_action(entry_id: int, payload: EntryPayload) -> ActionResult:
    """对单条资金记录执行提交审批、确认批复、标记超支；不允许的动作会被拦下并说明原因。"""
    action = str(payload.values.get("action") or "").strip()
    approver = str(payload.values.get("审批人员") or "").strip()
    entry, message = service.run_action(entry_id, action, approver=approver)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)
