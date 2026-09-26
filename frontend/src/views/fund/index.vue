<template>
  <section class="page" data-module="fund">
    <header class="page-head">
      <div>
        <h2>养护资金管理</h2>
        <p class="page-desc">维护资金记录，围绕资金编号、费用类别、项目名称、批复金额做登记、筛选与状态流转。</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="openCreate">登记资金记录</button>
        <button class="btn" type="button" @click="exportRows">导出养护资金清单</button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in stats" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <form class="filter-bar" @submit.prevent="reload">
      <label class="filter-item">
        <span>资金编号/项目名称</span>
        <input v-model="filters.keyword" placeholder="按资金编号或项目名称检索" />
      </label>
      <label class="filter-item">
        <span>资金状态</span>
        <select v-model="filters.status">
          <option value="">全部状态</option>
          <option v-for="item in statusOptions" :key="item" :value="item">{{ item }}</option>
        </select>
      </label>
      <button class="btn" type="submit">查询</button>
      <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
    </form>

    <table class="data-table">
      <thead>
        <tr>
          <th v-for="column in columns" :key="column">{{ column }}</th>
          <th>可执行动作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="String(row.id)">
          <td v-for="column in columns" :key="column" :class="{ 'warn-cell': column === '资金提醒' && row[column] }">
            <template v-if="column === '资金提醒'">
              <span v-if="row[column]" class="warn-text">{{ row[column] }}</span>
              <span v-else class="muted-text">—</span>
            </template>
            <template v-else>{{ formatCell(row[column]) }}</template>
          </td>
          <td class="row-actions">
            <button
              v-for="action in availableActions(row)"
              :key="action"
              class="link"
              type="button"
              @click="runAction(action, row)"
            >
              {{ action }}
            </button>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length + 1" class="empty-state">暂无养护资金数据，可先登记资金记录</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条养护资金记录</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>

    <!-- 登记资金记录 -->
    <div v-if="creating" class="modal-mask" @click.self="creating = false">
      <form class="modal" @submit.prevent="submitCreate">
        <h3 class="modal-title">登记资金记录</h3>
        <label class="form-item">
          <span>资金编号 <i>*</i></span>
          <input v-model="form.资金编号" placeholder="如 FUND-0010" />
        </label>
        <label class="form-item">
          <span>费用类别 <i>*</i></span>
          <input v-model="form.费用类别" placeholder="如 日常养护" />
        </label>
        <label class="form-item">
          <span>项目名称 <i>*</i></span>
          <input v-model="form.项目名称" placeholder="同一项目重复登记会并入一条记录" />
        </label>
        <label class="form-item">
          <span>批复金额</span>
          <input v-model="form.批复金额" inputmode="decimal" placeholder="未取得批复时可留空" />
        </label>
        <label class="form-item">
          <span>本次支出金额</span>
          <input v-model="form.本次支出金额" inputmode="decimal" placeholder="本次登记的已用金额" />
        </label>
        <label class="form-item">
          <span>支出事项</span>
          <input v-model="form.支出事项" placeholder="如 沥青材料采购" />
        </label>
        <label class="form-item">
          <span>审批人员</span>
          <input v-model="form.审批人员" placeholder="提交审批时记录" />
        </label>
        <p class="form-preview">
          登记口径：已用 <strong>{{ preview.used }}</strong>，剩余
          <strong>{{ preview.remaining === null ? '待批复' : preview.remaining }}</strong>
        </p>
        <p v-if="preview.warning" class="warn-text">{{ preview.warning }}</p>
        <p v-if="formError" class="error-text">{{ formError }}</p>
        <div class="modal-actions">
          <button class="btn ghost" type="button" @click="creating = false">取消</button>
          <button class="btn primary" type="submit">提交登记</button>
        </div>
      </form>
    </div>

    <!-- 资金明细 -->
    <div v-if="detailRow" class="modal-mask" @click.self="detailRow = null">
      <div class="modal">
        <h3 class="modal-title">资金明细 · {{ detailRow.项目名称 }}</h3>
        <p class="form-preview">
          批复 <strong>{{ formatCell(detailRow.批复金额) }}</strong>｜已用
          <strong>{{ formatCell(detailRow.已用金额) }}</strong>｜剩余
          <strong>{{ formatCell(detailRow.剩余额度) }}</strong>
        </p>
        <table class="data-table detail-table">
          <thead>
            <tr><th>支出事项</th><th>金额</th></tr>
          </thead>
          <tbody>
            <tr v-for="(item, index) in detailRow.资金明细 ?? []" :key="index">
              <td>{{ item.事项 || '—' }}</td>
              <td>{{ formatCell(item.金额) }}</td>
            </tr>
            <tr v-if="!(detailRow.资金明细 ?? []).length">
              <td colspan="2" class="empty-state">暂无支出明细</td>
            </tr>
          </tbody>
        </table>
        <p v-if="detailRow.资金提醒" class="warn-text">{{ detailRow.资金提醒 }}</p>
        <div class="modal-actions">
          <button class="btn primary" type="button" @click="detailRow = null">关闭</button>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'

import { request } from '@/api/client'
import { evaluateFund, FUND_WARNING, STATUS_OVERSPENT } from '@/shared/fundCalc'

type Row = Record<string, string | number | null> & {
  资金提醒?: string
  资金状态?: string
  资金明细?: Array<{ 事项: string; 金额: number }>
}

const ENDPOINT = '/api/fund'
const columns = ['资金编号', '费用类别', '项目名称', '批复金额', '已用金额', '剩余额度', '审批人员', '资金状态', '资金提醒']
const statusOptions = ['待审批', '已批复', '执行中', '已超支']

const rows = ref<Row[]>([])
const total = ref(0)
const errorMessage = ref('')
const filters = ref<Record<string, string>>({ keyword: '', status: '' })
const stats = ref([
  { label: '批复总额', value: '—' },
  { label: '已用金额合计', value: '—' },
  { label: '超支项目', value: '—' },
  { label: '超支合计', value: '—' },
])

const creating = ref(false)
const formError = ref('')
const detailRow = ref<Row | null>(null)
const emptyForm = () => ({
  资金编号: '',
  费用类别: '',
  项目名称: '',
  批复金额: '',
  本次支出金额: '',
  支出事项: '',
  审批人员: '',
})
const form = reactive(emptyForm())

const preview = computed(() => {
  const amount = Number(form.本次支出金额)
  return evaluateFund({
    approved: form.批复金额,
    details: form.本次支出金额 !== '' && Number.isFinite(amount) && amount > 0
      ? [{ 事项: form.支出事项 || '本次登记支出', 金额: amount }]
      : [],
  })
})

function formatCell(value: unknown): string {
  if (value === null || value === undefined || value === '') return '—'
  if (typeof value === 'number') return value.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
  return String(value)
}

/** 已超支的项目不再给「确认批复 / 标记超支」，避免被改回执行中。 */
function availableActions(row: Row): string[] {
  const base = ['提交审批', '确认批复', '标记超支', '查看明细']
  if (row.资金状态 === STATUS_OVERSPENT) {
    return ['查看明细']
  }
  return base
}

function resetFilters() {
  filters.value = {}
  void reload()
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

function openCreate() {
  Object.assign(form, emptyForm())
  formError.value = ''
  creating.value = true
}

async function submitCreate() {
  formError.value = ''
  // 登记前先用同一份算法给出口径提示；缺批复仍可登记（应急场景），但提醒要讲明。
  const result = evaluateFund({
    approved: form.批复金额,
    details: form.本次支出金额 !== '' ? [{ 事项: form.支出事项 || '本次登记支出', 金额: Number(form.本次支出金额) }] : [],
  })
  if (result.approved === null && form.批复金额.trim() !== '') {
    formError.value = '批复金额无法识别为数字，请核对后再登记'
    return
  }
  try {
    const response = await request(ENDPOINT, {
      method: 'POST',
      body: JSON.stringify({ values: { ...form } }),
    })
    const payload = await response.json().catch(() => null)
    if (!response.ok || !payload?.ok) {
      throw new Error(payload?.message || '资金记录登记失败，请稍后重试')
    }
    creating.value = false
    await reload()
    if (result.warning) {
      errorMessage.value = FUND_WARNING
    }
  } catch (error) {
    formError.value = error instanceof Error ? error.message : '资金记录登记失败'
  }
}

async function runAction(action: string, row: Row) {
  errorMessage.value = ''
  if (action === '查看明细') {
    detailRow.value = row
    return
  }
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ values: { action, 审批人员: form.审批人员 } }),
    })
    const payload = await response.json().catch(() => null)
    if (!response.ok || !payload?.ok) {
      throw new Error(payload?.message || '养护资金动作未生效，请稍后重试')
    }
    if (payload.message) {
      errorMessage.value = payload.message
    }
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '养护资金操作失败'
  }
}

async function reload() {
  errorMessage.value = ''
  const query = new URLSearchParams(filters.value as Record<string, string>).toString()
  try {
    const response = await request(`${ENDPOINT}?${query}`)
    if (!response.ok) {
      throw new Error('资金记录列表读取失败')
    }
    const payload = await response.json()
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
    // 列表、合计、明细同源：统计卡片直接采用接口同一份算法的合计，页面不再自己算。
    const s = payload.stats ?? {}
    stats.value = [
      { label: '批复总额', value: formatCell(s['批复总额']) },
      { label: '已用金额合计', value: formatCell(s['已用金额合计']) },
      { label: '超支项目', value: String(s['超支项目'] ?? 0) },
      { label: '超支合计', value: formatCell(s['超支合计']) },
    ]
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '养护资金列表读取失败'
  }
}

onMounted(reload)
</script>

<style scoped>
.page-actions {
  display: flex;
  gap: 8px;
}
.muted-text {
  color: var(--muted);
}
.warn-text {
  color: #b42318;
}
.warn-cell {
  max-width: 220px;
  font-size: 12px;
}
.modal-mask {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 20;
}
.modal {
  width: 460px;
  max-height: 80vh;
  overflow: auto;
  background: #fff;
  border-radius: 10px;
  padding: 18px 20px;
  border: 1px solid var(--border);
}
.modal-title {
  margin: 0 0 12px;
  font-size: 16px;
}
.form-item {
  display: block;
  margin-bottom: 10px;
}
.form-item span {
  display: block;
  font-size: 12px;
  color: var(--muted);
  margin-bottom: 4px;
}
.form-item i {
  color: #b42318;
  font-style: normal;
}
.form-item input {
  width: 100%;
  padding: 6px 8px;
  border: 1px solid var(--border);
  border-radius: 6px;
}
.form-preview {
  font-size: 13px;
  color: var(--muted);
  margin: 8px 0;
}
.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 12px;
}
.detail-table {
  margin-top: 8px;
}
</style>
