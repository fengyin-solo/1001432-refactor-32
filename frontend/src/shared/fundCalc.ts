/**
 * 资金口径共用算法（前端镜像）。
 *
 * 与后端 app/services/fund_calc.py 一一对应：页面预估、表单校验只准调用
 * 这里的函数；列表与合计的最终值一律以后端同算法的返回为准，刷新前后一致。
 */

/** 批复金额缺失，或已用金额超过批复金额，统一用这一句讲明。 */
export const FUND_WARNING = '批复金额缺失或已用金额超过批复金额，请核对资金口径'

export const STATUS_PENDING = '待审批'
export const STATUS_APPROVED = '已批复'
export const STATUS_RUNNING = '执行中'
export const STATUS_OVERSPENT = '已超支'

const STAGE_PENDING = STATUS_PENDING
const STAGE_APPROVED = STATUS_APPROVED
const STAGE_RUNNING = STATUS_RUNNING

export interface FundDetail {
  事项: string
  金额: number
}

export interface FundEvaluation {
  approved: number | null
  used: number
  remaining: number | null
  status: string
  warning: string
  overAmount: number
  overspent: boolean
}

/** 金额解析：空值与非法数字视为缺失；支持千分位逗号。 */
export function toAmount(value: unknown): number | null {
  if (value === null || value === undefined || value === '') return null
  if (typeof value === 'boolean') return null
  if (typeof value === 'number') return Number.isFinite(value) ? round2(value) : null
  const text = String(value).trim().replace(/,/g, '')
  if (!text) return null
  const num = Number(text)
  return Number.isFinite(num) ? round2(num) : null
}

function round2(value: number): number {
  return Math.round((value + Number.EPSILON) * 100) / 100
}

/** 已用金额只从资金明细汇总。 */
export function sumUsed(details: Array<{ 金额?: unknown } | number>): number {
  let total = 0
  let found = false
  for (const detail of details ?? []) {
    const amount = toAmount(typeof detail === 'number' ? detail : detail?.金额)
    if (amount !== null) {
      total += amount
      found = true
    }
  }
  return found ? round2(total) : 0
}

/** 剩余额度 = 批复金额 - 已用金额；批复缺失时无剩余。 */
export function remainingAmount(approved: number | null, used: number): number | null {
  if (approved === null) return null
  return round2(approved - used)
}

/** 批复金额缺，或已用金额超过批复金额，即为超支口径命中。 */
export function isOverspent(approved: number | null, used: number): boolean {
  return approved === null || used > approved
}

/** 审批阶段 + 资金口径合一处推导最终状态。 */
export function fundStatus(approved: number | null, used: number, stage: string): string {
  if (stage === STAGE_PENDING) return STATUS_PENDING
  if (stage === STAGE_APPROVED) return STATUS_APPROVED
  if (stage === STAGE_RUNNING) return isOverspent(approved, used) ? STATUS_OVERSPENT : STATUS_RUNNING
  return stage
}

/** 缺批复或已用超批复，给同一句提醒。 */
export function warningFor(approved: number | null, used: number): string {
  return isOverspent(approved, used) ? FUND_WARNING : ''
}

/** 对一条资金记录执行完整算法。 */
export function evaluateFund(input: {
  approved: unknown
  details?: FundDetail[]
  used?: unknown
  stage?: string
}): FundEvaluation {
  const details = input.details ?? []
  const used = details.length ? sumUsed(details) : (toAmount(input.used) ?? 0)
  const approved = toAmount(input.approved)
  const remaining = remainingAmount(approved, used)
  const stage = input.stage ?? STAGE_PENDING
  const status = fundStatus(approved, used, stage)
  const warning = warningFor(approved, used)
  const overAmount = approved !== null && used > approved ? round2(used - approved) : 0
  return {
    approved,
    used,
    remaining,
    status,
    warning,
    overAmount,
    overspent: status === STATUS_OVERSPENT,
  }
}
