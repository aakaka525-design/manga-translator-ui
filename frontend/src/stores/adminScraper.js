import { defineStore } from 'pinia'
import { reactive } from 'vue'
import { getSessionToken } from '@/api'

const ERROR_CODE_MESSAGES = {
  SCRAPER_ALERT_WEBHOOK_FAILED: 'Webhook 发送失败，请检查地址与网络连通性',
  SCRAPER_ALERT_CONFIG_INVALID: '告警配置无效，请先配置可用 webhook 地址',
  SCRAPER_ALERT_STORE_ERROR: '告警存储读取失败，请稍后重试'
}

function _authHeaders() {
  const token = getSessionToken()
  const headers = {}
  if (token) {
    headers['X-Session-Token'] = token
  }
  return headers
}

async function _jsonOrEmpty(response) {
  try {
    return await response.json()
  } catch (_err) {
    return {}
  }
}

function _buildError(payload, fallback) {
  const detail = payload?.detail
  if (typeof detail === 'string' && detail.trim()) {
    return detail
  }
  if (detail && typeof detail === 'object') {
    const code = String(detail.code || '').trim()
    const message = String(detail.message || '').trim()
    if (code && ERROR_CODE_MESSAGES[code]) {
      return ERROR_CODE_MESSAGES[code] + (message ? `: ${message}` : '')
    }
    if (message) {
      return message
    }
  }
  return fallback
}

export const useAdminScraperStore = defineStore('admin-scraper', () => {
  const state = reactive({
    loading: false,
    error: '',
    tasks: [],
    total: 0,
    limit: 20,
    offset: 0,
    hasMore: false,
    alerts: [],
    alertsTotal: 0,
    health: {
      status: 'unknown',
      db: {},
      scheduler: {},
      alerts: {},
      time: ''
    },
    queueStats: {
      pending: 0,
      running: 0,
      retrying: 0,
      done: 0,
      failed: 0,
      backlog: 0,
      oldest_pending_age_sec: null
    },
    metrics: {
      hours: 24,
      total: 0,
      success: 0,
      partial: 0,
      error: 0,
      success_rate: 0,
      provider_breakdown: {},
      error_code_breakdown: {}
    }
  })

  async function fetchTasks(params = {}) {
    const query = new URLSearchParams()
    if (params.status) query.set('status', params.status)
    if (params.provider) query.set('provider', params.provider)
    query.set('limit', String(params.limit || state.limit || 20))
    query.set('offset', String(params.offset || state.offset || 0))

    const suffix = query.toString() ? `?${query.toString()}` : ''
    const response = await fetch(`/admin/scraper/tasks${suffix}`, {
      headers: _authHeaders()
    })
    if (!response.ok) {
      const payload = await _jsonOrEmpty(response)
      throw new Error(_buildError(payload, `Scraper 任务获取失败 (${response.status})`))
    }

    const data = await response.json()
    state.tasks = Array.isArray(data?.items) ? data.items : []
    state.total = Number(data?.total || 0)
    state.limit = Number(data?.limit || 20)
    state.offset = Number(data?.offset || 0)
    state.hasMore = Boolean(data?.has_more)
    return data
  }

  async function fetchMetrics(hours = 24) {
    const response = await fetch(`/admin/scraper/metrics?hours=${encodeURIComponent(String(hours))}`, {
      headers: _authHeaders()
    })
    if (!response.ok) {
      const payload = await _jsonOrEmpty(response)
      throw new Error(_buildError(payload, `Scraper 指标获取失败 (${response.status})`))
    }

    const data = await response.json()
    state.metrics = {
      ...state.metrics,
      ...data,
      provider_breakdown: data?.provider_breakdown || {},
      error_code_breakdown: data?.error_code_breakdown || {}
    }
    return data
  }

  async function fetchHealth() {
    const response = await fetch('/admin/scraper/health', {
      headers: _authHeaders()
    })
    if (!response.ok) {
      const payload = await _jsonOrEmpty(response)
      throw new Error(_buildError(payload, `Scraper 健康状态获取失败 (${response.status})`))
    }
    const data = await response.json()
    state.health = {
      status: data?.status || 'unknown',
      db: data?.db || {},
      scheduler: data?.scheduler || {},
      alerts: data?.alerts || {},
      time: data?.time || ''
    }
    return data
  }

  async function fetchAlerts(params = {}) {
    const query = new URLSearchParams()
    if (params.severity) query.set('severity', params.severity)
    if (params.rule) query.set('rule', params.rule)
    query.set('limit', String(params.limit || 20))
    query.set('offset', String(params.offset || 0))
    const suffix = query.toString() ? `?${query.toString()}` : ''

    const response = await fetch(`/admin/scraper/alerts${suffix}`, {
      headers: _authHeaders()
    })
    if (!response.ok) {
      const payload = await _jsonOrEmpty(response)
      throw new Error(_buildError(payload, `Scraper 告警列表获取失败 (${response.status})`))
    }

    const data = await response.json()
    state.alerts = Array.isArray(data?.items) ? data.items : []
    state.alertsTotal = Number(data?.total || 0)
    return data
  }

  async function fetchQueueStats() {
    const response = await fetch('/admin/scraper/queue/stats', {
      headers: _authHeaders()
    })
    if (!response.ok) {
      const payload = await _jsonOrEmpty(response)
      throw new Error(_buildError(payload, `Scraper 队列统计获取失败 (${response.status})`))
    }

    const data = await response.json()
    state.queueStats = {
      pending: Number(data?.pending || 0),
      running: Number(data?.running || 0),
      retrying: Number(data?.retrying || 0),
      done: Number(data?.done || 0),
      failed: Number(data?.failed || 0),
      backlog: Number(data?.backlog || 0),
      oldest_pending_age_sec:
        data?.oldest_pending_age_sec === null || data?.oldest_pending_age_sec === undefined
          ? null
          : Number(data.oldest_pending_age_sec)
    }
    return data
  }

  async function sendTestWebhook(webhookUrl = '') {
    const payload = {}
    if (webhookUrl && String(webhookUrl).trim()) {
      payload.webhook_url = String(webhookUrl).trim()
    }
    const response = await fetch('/admin/scraper/alerts/test-webhook', {
      method: 'POST',
      headers: {
        ..._authHeaders(),
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(payload)
    })
    const data = await _jsonOrEmpty(response)
    if (!response.ok) {
      throw new Error(_buildError(data, `Webhook 测试失败 (${response.status})`))
    }
    return {
      sent: Boolean(data?.sent),
      attempts: Number(data?.attempts || 0),
      status: data?.status || 'unknown',
      message: data?.message || ''
    }
  }

  async function refresh() {
    state.loading = true
    state.error = ''
    try {
      await Promise.all([
        fetchTasks(),
        fetchMetrics(state.metrics.hours || 24),
        fetchHealth(),
        fetchAlerts({ limit: 20, offset: 0 }),
        fetchQueueStats()
      ])
    } catch (err) {
      state.error = err?.message || 'Scraper 监控刷新失败'
    } finally {
      state.loading = false
    }
  }

  return {
    state,
    fetchTasks,
    fetchMetrics,
    fetchHealth,
    fetchAlerts,
    fetchQueueStats,
    sendTestWebhook,
    refresh
  }
})
