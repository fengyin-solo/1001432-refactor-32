/**
 * 养护资金共用口径：页面各处只从这里取已用金额、剩余额度和提醒文案。
 *
 * 金额与超支结论一律以后端 /api/fund 返回的统一算法结果为准，前端不再
 * 各写一遍计算；这里只负责透传、格式化和按状态选择提醒，保证资金列表、
 * 合计卡片与明细提示说的是同一句话、同一个数。
 */

export interface FundRow {
  id: number
  资金编号: string
  费用类别: string
  项目名称: string
  批复金额: string
  已用金额: string
  剩余额度: string
  审批人员?: string
  资金状态: string
  资金提醒?: string
  已超支?: boolean
  [key: string]: string | number | boolean | null | undefined
}

export interface FundStats {
  批复总额: string
  已用金额合计: string
  剩余额度合计: string
  超支项目: number
  超支合计: string
  批复金额缺失: number
}

/** 与后端 app/services/budget.py 保持一致的两句话。 */
export const MISSING_APPROVED_MESSAGE = '批复金额缺失，暂无法判断资金是否超支'
export const OVERSPENT_MESSAGE = '已用金额超过批复金额，该项目资金已超支'

const PLACEHOLDER = '—'

/** 展示金额：后端已按两位小数算好，这里只兜底空值。 */
export function displayAmount(value: string | number | null | undefined): string {
  if (value === null || value === undefined || value === '') return PLACEHOLDER
  return String(value)
}

/**
 * 取一条资金记录的提醒：列表行、合计入口、明细/动作反馈三处共用这一个函数。
 * 优先用后端统一算法写入的「资金提醒」，再按同一口径兜底缺失批复的情况。
 */
export function budgetNotice(row: Pick<FundRow, '批复金额' | '资金提醒'>): string {
  if (row.资金提醒) return row.资金提醒
  if (!row.批复金额 || row.批复金额 === PLACEHOLDER) return MISSING_APPROVED_MESSAGE
  return ''
}

export function isOverspent(row: Pick<FundRow, '已超支' | '资金状态'>): boolean {
  return row.已超支 === true || row.资金状态 === '已超支'
}

export const EMPTY_STATS: FundStats = {
  批复总额: PLACEHOLDER,
  已用金额合计: PLACEHOLDER,
  剩余额度合计: PLACEHOLDER,
  超支项目: 0,
  超支合计: PLACEHOLDER,
  批复金额缺失: 0,
}
