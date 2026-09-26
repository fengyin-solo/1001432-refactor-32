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
      <article v-for="item in statCards" :key="item.label" class="stat-card" :class="item.danger ? 'stat-danger' : ''">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <form class="filter-bar" @submit.prevent="reload">
      <label class="filter-item">
        <span>关键字</span>
        <input v-model="keyword" placeholder="按资金编号或项目名称检索" />
      </label>
      <label class="filter-item">
        <span>资金状态</span>
        <select v-model="statusFilter">
          <option value="">全部状态</option>
          <option v-for="option in statuses" :key="option" :value="option">{{ option }}</option>
        </select>
      </label>
      <button class="btn" type="submit">查询</button>
      <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
    </form>

    <table class="data-table">
      <thead>
        <tr>
          <th v-for="column in columns" :key="column">{{ column }}</th>
          <th>资金提醒</th>
          <th>可执行动作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="String(row.id)">
          <td>{{ row.资金编号 }}</td>
          <td>{{ row.费用类别 }}</td>
          <td>{{ row.项目名称 }}</td>
          <td>{{ displayAmount(row.批复金额) }}</td>
          <td>{{ displayAmount(row.已用金额) }}</td>
          <td :class="{ 'amount-danger': isOverspent(row) }">{{ displayAmount(row.剩余额度) }}</td>
          <td>{{ row.审批人员 || '—' }}</td>
          <td>
            <span :class="['status-tag', isOverspent(row) ? 'tag-danger' : '']">{{ row.资金状态 }}</span>
          </td>
          <td class="notice-cell">
            <span v-if="noticeOf(row)" class="error-text">{{ noticeOf(row) }}</span>
            <span v-else class="muted-text">额度正常</span>
          </td>
          <td class="row-actions">
            <button
              v-for="action in actions"
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
          <td :colspan="columns.length + 2" class="empty-state">暂无养护资金数据，可先登记资金记录</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条养护资金记录</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>

    <div v-if="showCreate" class="modal-mask" @click.self="closeCreate">
      <form class="modal-card" @submit.prevent="submitCreate">
        <h3>登记资金记录</h3>
        <label class="form-item">
          <span>资金编号 *</span>
          <input v-model="form.资金编号" placeholder="例如 FUND-0006" />
        </label>
        <label class="form-item">
          <span>费用类别 *</span>
          <input v-model="form.费用类别" placeholder="例如 日常养护" />
        </label>
        <label class="form-item">
          <span>项目名称 *</span>
          <input v-model="form.项目名称" placeholder="同一项目只能登记一条" />
        </label>
        <label class="form-item">
          <span>批复金额</span>
          <input v-model="form.批复金额" placeholder="尚未批复可留空，留空时无法判断超支" />
        </label>
        <label class="form-item">
          <span>已用金额</span>
          <input v-model="form.已用金额" placeholder="默认 0" />
        </label>
        <label class="form-item">
          <span>审批人员</span>
          <input v-model="form.审批人员" placeholder="可选" />
        </label>
        <p v-if="createError" class="error-text">{{ createError }}</p>
        <div class="modal-actions">
          <button class="btn ghost" type="button" @click="closeCreate">取消</button>
          <button class="btn primary" type="submit">提交登记</button>
        </div>
      </form>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'

import { request } from '@/api/client'
import {
  EMPTY_STATS,
  displayAmount,
  isOverspent,
  budgetNotice,
  type FundRow,
  type FundStats,
} from './budget'

const ENDPOINT = '/api/fund'
const columns = ['资金编号', '费用类别', '项目名称', '批复金额', '已用金额', '剩余额度', '审批人员', '资金状态']
const actions = ['提交审批', '确认批复', '标记超支']
const statuses = ['待审批', '已批复', '执行中', '已超支']

const rows = ref<FundRow[]>([])
const total = ref(0)
const stats = ref<FundStats>({ ...EMPTY_STATS })
const errorMessage = ref('')
const keyword = ref('')
const statusFilter = ref('')

const statCards = computed(() => [
  { label: '批复总额', value: stats.value.批复总额, danger: false },
  { label: '已用金额', value: stats.value.已用金额合计, danger: false },
  { label: '剩余额度', value: stats.value.剩余额度合计, danger: false },
  { label: '超支项目', value: stats.value.超支项目, danger: stats.value.超支项目 > 0 },
  { label: '超支合计', value: stats.value.超支合计, danger: stats.value.超支项目 > 0 },
])

const showCreate = ref(false)
const createError = ref('')
const form = reactive({
  资金编号: '',
  费用类别: '',
  项目名称: '',
  批复金额: '',
  已用金额: '',
  审批人员: '',
})

function noticeOf(row: FundRow): string {
  return budgetNotice(row)
}

function resetFilters() {
  keyword.value = ''
  statusFilter.value = ''
  void reload()
}

function buildQuery(): string {
  const query = new URLSearchParams()
  if (keyword.value.trim()) query.set('keyword', keyword.value.trim())
  if (statusFilter.value) query.set('status', statusFilter.value)
  const text = query.toString()
  return text ? `?${text}` : ''
}

function exportRows() {
  window.open(`${ENDPOINT}/export${buildQuery()}`, '_blank')
}

function openCreate() {
  createError.value = ''
  showCreate.value = true
}

function closeCreate() {
  showCreate.value = false
}

async function submitCreate() {
  createError.value = ''
  const values: Record<string, string> = {}
  for (const key of Object.keys(form)) {
    const value = form[key as keyof typeof form].trim()
    if (value) values[key] = value
  }
  try {
    const response = await request(ENDPOINT, {
      method: 'POST',
      body: JSON.stringify({ values }),
    })
    const payload = await response.json()
    if (!response.ok || !payload.ok) {
      throw new Error(payload.message || '资金记录未登记成功')
    }
    closeCreate()
    await reload()
  } catch (error) {
    createError.value = error instanceof Error ? error.message : '资金记录登记失败'
  }
}

async function runAction(action: string, row: FundRow) {
  errorMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ values: { action } }),
    })
    const payload = await response.json()
    if (!response.ok || !payload.ok) {
      // 动作被统一算法拦下（如超支项目改回执行中）时，直接展示同一句提醒。
      throw new Error(payload.message || '养护资金动作未生效，请稍后重试')
    }
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '养护资金操作失败'
  }
}

async function reload() {
  errorMessage.value = ''
  const query = buildQuery()
  try {
    const [listResponse, statsResponse] = await Promise.all([
      request(`${ENDPOINT}${query}`),
      request(`${ENDPOINT}/stats${query}`),
    ])
    if (!listResponse.ok) {
      throw new Error('资金记录列表读取失败')
    }
    if (!statsResponse.ok) {
      throw new Error('资金合计读取失败')
    }
    const payload = await listResponse.json()
    stats.value = await statsResponse.json()
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '养护资金列表读取失败'
  }
}

onMounted(reload)
</script>

<style scoped>
.muted-text {
  color: var(--muted);
  font-size: 12px;
}

.amount-danger {
  color: #b42318;
  font-weight: 600;
}

.stat-danger .stat-value {
  color: #b42318;
}

.notice-cell {
  max-width: 240px;
  font-size: 12px;
}

.status-tag {
  display: inline-block;
  padding: 1px 8px;
  border-radius: 10px;
  background: #eef2f7;
  font-size: 12px;
}

.status-tag.tag-danger {
  background: #fee4e2;
  color: #b42318;
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

.modal-card {
  width: 420px;
  background: #fff;
  border-radius: 10px;
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.modal-card h3 {
  margin: 0;
}

.form-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 12px;
  color: var(--muted);
}

.form-item input {
  padding: 6px 8px;
  border: 1px solid var(--border);
  border-radius: 6px;
  font-size: 13px;
}

.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 6px;
}
</style>
